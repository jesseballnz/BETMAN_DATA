"""Disposable-Postgres proof for the environment-local Race Day API."""

import asyncio
import importlib.util
import os
from types import SimpleNamespace

import asyncpg

module_path = os.environ.get("RACE_DAY_MODULE_PATH")
if module_path:
    spec = importlib.util.spec_from_file_location("race_day_candidate", module_path)
    race_day = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(race_day)
else:
    from app.routers import race_day


class Request:
    def __init__(self, pool):
        self.app = SimpleNamespace(state=SimpleNamespace(db_pool=pool))
        self.headers = {}
        self.cookies = {}


async def run():
    pool = await asyncpg.create_pool(
        os.environ["RACE_DAY_TEST_DATABASE_URL"], min_size=1, max_size=2
    )
    original = race_day._operator

    async def operator(_request):
        return "betman"

    race_day._operator = operator
    try:
        request = Request(pool)
        meetings = await race_day.meetings(request)
        assert [row["name"] for row in meetings["meetings"]] == ["Te Aroha"]
        dashboard = await race_day.select_meeting(
            race_day.MeetingSelection(meeting_id="test-te-aroha"), request
        )
        assert dashboard["meeting"]["name"] == "Te Aroha"
        assert len(dashboard["races"]) == 2
        assert dashboard["races"][0]["state"] == "open"
        assert dashboard["races"][1]["state"] == "locked"
        assert [row["horse_number"] for row in dashboard["races"][0]["sessions"]] == [
            "1",
            "4",
        ]
        first, unavailable = dashboard["races"][0]["sessions"]
        await race_day.set_phase(
            first["id"], race_day.PhaseAction(phase="pre", action="start"), request
        )
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO heatmap_race_day.scan_frames
                   (runner_scan_id,phase,camera_key,captured_at,raw_storage_path,content_sha256,
                    idempotency_key,assignment_source,analysis_json)
                   VALUES($1,'pre','camera-1',now(),'/tmp/pre.jpg','pre-digest','pre-key','manual','{\"delta_c\":1.1}'::jsonb)""",
                first["id"],
            )
        await race_day.set_phase(
            first["id"], race_day.PhaseAction(phase="pre", action="finish"), request
        )
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE races SET actual_start_time=now()-interval '1 minute' WHERE id=1"
            )
        await race_day.set_phase(
            first["id"], race_day.PhaseAction(phase="post", action="start"), request
        )
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO heatmap_race_day.scan_frames
                   (runner_scan_id,phase,camera_key,captured_at,raw_storage_path,content_sha256,
                    idempotency_key,assignment_source,analysis_json)
                   VALUES($1,'post','camera-2',now(),'/tmp/post.jpg','post-digest','post-key','manual','{\"delta_c\":3.5}'::jsonb)""",
                first["id"],
            )
        await race_day.set_phase(
            first["id"], race_day.PhaseAction(phase="post", action="finish"), request
        )
        await race_day.skip(
            unavailable["id"], race_day.SkipAction(reason="did not present"), request
        )
        closed = await race_day.close_race(dashboard["races"][0]["id"], request)
        assert closed["races"][0]["state"] == "archived"
        assert closed["races"][1]["state"] == "open"
    finally:
        race_day._operator = original
        await pool.close()


if __name__ == "__main__":
    asyncio.run(run())
    print(
        "PASS: environment-local meeting selector populates Te Aroha races and runners"
    )
