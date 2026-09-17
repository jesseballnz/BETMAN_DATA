"""BETMAN-only meeting-first Race Day capture workflow.

The race card stays authoritative in BETMAN Data's public tables. Mutable
capture state lives only in the dedicated heatmap_race_day schema.
"""

from __future__ import annotations

import hashlib
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import asyncpg
import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.config import settings

router = APIRouter(prefix="/race-day", tags=["race-day"])
_AUTH_TTL = 15.0
_auth_cache: dict[str, tuple[float, str]] = {}
SCAN_WINDOW = timedelta(minutes=20)


class MeetingSelection(BaseModel):
    meeting_id: str = Field(min_length=1, max_length=160)


class PhaseAction(BaseModel):
    phase: str
    action: str


class SkipAction(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


def _racing_date() -> date:
    # NZ is UTC+12/+13. Using the stdlib avoids a deployment dependency.
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo("Pacific/Auckland")).date()


async def _operator(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    cookie = request.cookies.get("betman_session", "")
    headers: dict[str, str] = {}
    if authorization.lower().startswith("bearer "):
        headers["Authorization"] = authorization
    elif cookie:
        headers["Cookie"] = f"betman_session={cookie}"
    if not headers:
        raise HTTPException(401, "Sign in with the BETMAN operator account")
    credential = headers.get("Authorization") or headers.get("Cookie") or ""
    key = hashlib.sha256(credential.encode()).hexdigest()
    cached = _auth_cache.get(key)
    now = time.monotonic()
    if cached and cached[0] > now:
        return cached[1]
    try:
        async with httpx.AsyncClient(timeout=6, verify=settings.core_auth_verify_ssl) as client:
            response = await client.get(
                f"{settings.core_auth_base_url.rstrip('/')}/api/auth-config",
                headers=headers,
            )
    except httpx.HTTPError as exc:
        raise HTTPException(503, "BETMAN identity service unavailable") from exc
    if response.status_code != 200:
        raise HTTPException(401, "BETMAN session expired")
    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(503, "BETMAN identity response was invalid") from exc
    user = payload.get("user") if isinstance(payload.get("user"), dict) else payload
    subject = str(user.get("currentUser") or user.get("username") or user.get("id") or "").strip()
    if subject.casefold() != "betman":
        raise HTTPException(403, "Race Day is restricted to the BETMAN operator")
    if len(_auth_cache) >= 128:
        _auth_cache.clear()
    _auth_cache[key] = (now + _AUTH_TTL, subject)
    return subject


def _pool(request: Request) -> asyncpg.Pool:
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(503, "BETMAN Data database unavailable")
    return pool


def _phase(start_at: datetime | None, now: datetime | None = None) -> str:
    if start_at is None:
        return "waiting"
    current = now or datetime.now(UTC)
    if start_at.tzinfo is None:
        start_at = start_at.replace(tzinfo=UTC)
    if current < start_at - SCAN_WINDOW:
        return "waiting"
    return "pre" if current < start_at else "post"


async def _meeting_options(conn: asyncpg.Connection, start: date) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT m.id, m.external_meeting_id, m.track_name, m.meeting_date,
               m.status, COUNT(r.id)::int AS race_count,
               EXISTS (SELECT 1 FROM heatmap_race_day.meeting_runs mr
                       WHERE mr.meeting_id=m.id AND mr.state='active') AS selected
        FROM meetings m LEFT JOIN races r ON r.meeting_id=m.id
        WHERE m.meeting_date BETWEEN $1 AND $1 + 3
        GROUP BY m.id ORDER BY m.meeting_date, m.track_name
        """,
        start,
    )
    return [
        {
            "id": str(row["external_meeting_id"] or row["id"]),
            "warehouse_id": row["id"],
            "name": row["track_name"],
            "date": row["meeting_date"].isoformat(),
            "status": row["status"],
            "race_count": row["race_count"],
            "selected": row["selected"],
        }
        for row in rows
    ]


def _frame(row: asyncpg.Record) -> dict[str, Any]:
    return {
        "id": row["id"],
        "camera_key": row["camera_key"],
        "captured_at": row["captured_at"].isoformat(),
        "phase": row["phase"],
        "assignment_source": row["assignment_source"],
        "ocr_horse_number": row["ocr_horse_number"],
        "ocr_confidence": row["ocr_confidence"],
        "analysis": row["analysis_json"] or {},
        "raw_url": f"frames/{row['id']}/raw",
        "processed_url": f"frames/{row['id']}/processed" if row["processed_storage_path"] else None,
    }


def _summary(frames: list[dict[str, Any]]) -> dict[str, Any]:
    deltas = []
    for frame in frames:
        analysis = frame.get("analysis") if isinstance(frame.get("analysis"), dict) else {}
        for key in ("delta_c", "temperature_delta_c", "max_delta_c"):
            try:
                value = float(analysis.get(key))
            except (TypeError, ValueError):
                continue
            if value == value:
                deltas.append(value)
                break
    return {
        "image_count": len(frames),
        "camera_count": len({f["camera_key"] for f in frames}),
        "max_delta_c": round(max(deltas), 1) if deltas else None,
        "captured_at": max((f["captured_at"] for f in frames), default=None),
    }


def _comparison(pre: dict[str, Any], post: dict[str, Any]) -> dict[str, Any] | None:
    if not pre["image_count"] or not post["image_count"]:
        return None
    before, after = pre["max_delta_c"], post["max_delta_c"]
    change = round(after - before, 1) if before is not None and after is not None else None
    return {
        "delta_change_c": change,
        "thermal_flag": change is not None and change >= 2.0,
        "multi_angle": pre["camera_count"] >= 2 and post["camera_count"] >= 2,
        "note": "Temperature change is evidence for review, not a veterinary diagnosis.",
    }


async def _dashboard(conn: asyncpg.Connection, operator: str | None = None) -> dict[str, Any]:
    meeting = await conn.fetchrow(
        """SELECT mr.id AS meeting_run_id,m.id,m.external_meeting_id,m.track_name,m.meeting_date
           FROM heatmap_race_day.meeting_runs mr JOIN meetings m ON m.id=mr.meeting_id
           WHERE mr.state='active' LIMIT 1"""
    )
    if not meeting:
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "meeting": None,
            "operator": operator,
            "current_race_run_id": None,
            "races": [],
        }
    races = await conn.fetch(
        """SELECT rr.id AS race_run_id,rr.state,rr.closed_at,rr.archive_status,
                  r.id AS race_id,r.race_number,r.name,r.scheduled_start_time,r.actual_start_time
           FROM heatmap_race_day.race_runs rr JOIN races r ON r.id=rr.race_id
           WHERE rr.meeting_run_id=$1 ORDER BY r.scheduled_start_time NULLS LAST,r.race_number""",
        meeting["meeting_run_id"],
    )
    sessions = await conn.fetch(
        """SELECT rss.* FROM heatmap_race_day.runner_scan_sessions rss
           JOIN heatmap_race_day.race_runs rr ON rr.id=rss.race_run_id
           WHERE rr.meeting_run_id=$1
           ORDER BY rr.id,
                    CASE WHEN rss.horse_number ~ '^[0-9]+$'
                         THEN rss.horse_number::int ELSE 9999 END,
                    rss.horse_name""",
        meeting["meeting_run_id"],
    )
    frames = await conn.fetch(
        """SELECT sf.* FROM heatmap_race_day.scan_frames sf
           JOIN heatmap_race_day.runner_scan_sessions rss ON rss.id=sf.runner_scan_id
           JOIN heatmap_race_day.race_runs rr ON rr.id=rss.race_run_id
           WHERE rr.meeting_run_id=$1 ORDER BY sf.captured_at,sf.id""",
        meeting["meeting_run_id"],
    )
    by_session: dict[int, list[dict[str, Any]]] = {}
    for row in frames:
        by_session.setdefault(row["runner_scan_id"], []).append(_frame(row))
    by_race: dict[int, list[dict[str, Any]]] = {}
    for row in sessions:
        all_frames = by_session.get(row["id"], [])
        pre = [f for f in all_frames if f["phase"] == "pre"]
        post = [f for f in all_frames if f["phase"] == "post"]
        ps, qs = _summary(pre), _summary(post)
        by_race.setdefault(row["race_run_id"], []).append(
            {
                "id": row["id"],
                "race_entry_id": row["race_entry_id"],
                "runner_id": row["runner_id"],
                "horse_number": row["horse_number"],
                "horse_name": row["horse_name"],
                "state": row["state"],
                "active_phase": row["active_phase"],
                "skip_reason": row["skip_reason"],
                "pre": pre,
                "post": post,
                "pre_summary": ps,
                "post_summary": qs,
                "comparison": _comparison(ps, qs),
            }
        )
    payload = []
    for row in races:
        start_at = row["actual_start_time"] or row["scheduled_start_time"]
        payload.append(
            {
                "id": row["race_run_id"],
                "race_id": row["race_id"],
                "number": row["race_number"],
                "name": row["name"] or f"Race {row['race_number']}",
                "start_at": start_at.isoformat() if start_at else None,
                "phase": _phase(start_at),
                "state": row["state"],
                "locked": row["state"] == "locked",
                "closed_at": row["closed_at"].isoformat() if row["closed_at"] else None,
                "archive_status": row["archive_status"],
                "sessions": by_race.get(row["race_run_id"], []),
            }
        )
    current = next(
        (r for r in payload if r["state"] in {"open", "closing", "archive_failed"}), None
    )
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "meeting": {
            "id": str(meeting["external_meeting_id"] or meeting["id"]),
            "warehouse_id": meeting["id"],
            "name": meeting["track_name"],
            "date": meeting["meeting_date"].isoformat(),
        },
        "operator": operator,
        "current_race_run_id": current["id"] if current else None,
        "races": payload,
    }


@router.get("/meetings")
async def meetings(request: Request):
    await _operator(request)
    async with _pool(request).acquire() as conn:
        start = _racing_date()
        return {
            "from_date": start.isoformat(),
            "to_date": (start + timedelta(days=3)).isoformat(),
            "source": "betman-data-postgres",
            "meetings": await _meeting_options(conn, start),
        }


@router.get("")
async def dashboard(request: Request):
    operator = await _operator(request)
    async with _pool(request).acquire() as conn:
        return await _dashboard(conn, operator)


@router.post("/meeting/select")
async def select_meeting(body: MeetingSelection, request: Request):
    operator = await _operator(request)
    async with _pool(request).acquire() as conn, conn.transaction():
        start = _racing_date()
        meeting = await conn.fetchrow(
            """SELECT id FROM meetings WHERE meeting_date BETWEEN $1 AND $1+3
               AND (external_meeting_id=$2 OR id::text=$2) LIMIT 1""",
            start,
            body.meeting_id,
        )
        if not meeting:
            raise HTTPException(404, "Meeting not found in the upcoming synced BETMAN race card")
        active = await conn.fetchrow(
            """SELECT id,meeting_id FROM heatmap_race_day.meeting_runs
               WHERE state='active' FOR UPDATE"""
        )
        if active and active["meeting_id"] != meeting["id"]:
            progressed = await conn.fetchval(
                """SELECT EXISTS(SELECT 1 FROM heatmap_race_day.runner_scan_sessions rss
                   JOIN heatmap_race_day.race_runs rr ON rr.id=rss.race_run_id
                   WHERE rr.meeting_run_id=$1 AND rss.state NOT IN ('awaiting-pre','cancelled'))""",
                active["id"],
            )
            if progressed:
                raise HTTPException(
                    409, "Close the active meeting's races before selecting another meeting"
                )
            await conn.execute(
                """UPDATE heatmap_race_day.meeting_runs
                   SET state='cancelled',updated_at=now() WHERE id=$1""",
                active["id"],
            )
            active = None
        meeting_run_id = (
            active["id"]
            if active
            else await conn.fetchval(
                """INSERT INTO heatmap_race_day.meeting_runs(meeting_id,selected_by)
                   VALUES($1,$2) RETURNING id""",
                meeting["id"],
                operator,
            )
        )
        race_rows = await conn.fetch(
            """SELECT id FROM races WHERE meeting_id=$1
               ORDER BY scheduled_start_time NULLS LAST,race_number""",
            meeting["id"],
        )
        if not race_rows:
            raise HTTPException(409, "The selected meeting has no synced races")
        existing = await conn.fetchval(
            "SELECT COUNT(*) FROM heatmap_race_day.race_runs WHERE meeting_run_id=$1",
            meeting_run_id,
        )
        for index, race in enumerate(race_rows):
            race_run_id = await conn.fetchval(
                """INSERT INTO heatmap_race_day.race_runs(meeting_run_id,race_id,state)
                   VALUES($1,$2,$3)
                   ON CONFLICT(meeting_run_id,race_id)
                   DO UPDATE SET race_id=EXCLUDED.race_id RETURNING id""",
                meeting_run_id,
                race["id"],
                "open" if not existing and index == 0 else "locked",
            )
            await conn.execute(
                """INSERT INTO heatmap_race_day.runner_scan_sessions
                   (race_run_id,race_entry_id,runner_id,horse_number,horse_name)
                   SELECT $1,re.id,re.runner_id,
                          COALESCE(NULLIF(re.saddle_cloth,''),re.id::text),run.name
                   FROM race_entries re JOIN runners run ON run.id=re.runner_id
                   WHERE re.race_id=$2 AND NOT re.scratched
                   ON CONFLICT(race_run_id,race_entry_id) DO NOTHING""",
                race_run_id,
                race["id"],
            )
    async with _pool(request).acquire() as conn:
        return await _dashboard(conn, operator)


async def _session(conn: asyncpg.Connection, session_id: int, lock: bool = False):
    return await conn.fetchrow(
        """SELECT rss.*,rr.state AS race_run_state,r.scheduled_start_time,r.actual_start_time
           FROM heatmap_race_day.runner_scan_sessions rss
           JOIN heatmap_race_day.race_runs rr ON rr.id=rss.race_run_id
           JOIN races r ON r.id=rr.race_id WHERE rss.id=$1"""
        + (" FOR UPDATE" if lock else ""),
        session_id,
    )


@router.post("/sessions/{session_id}/phase")
async def set_phase(session_id: int, body: PhaseAction, request: Request):
    await _operator(request)
    if body.phase not in {"pre", "post"} or body.action not in {"start", "finish"}:
        raise HTTPException(422, "Phase must be pre/post and action start/finish")
    async with _pool(request).acquire() as conn, conn.transaction():
        row = await _session(conn, session_id, True)
        if not row:
            raise HTTPException(404, "Runner scan not found")
        if row["race_run_state"] != "open":
            raise HTTPException(409, "Close the previous race before scanning this race")
        current = _phase(row["actual_start_time"] or row["scheduled_start_time"])
        if body.action == "start" and current != body.phase:
            raise HTTPException(
                409,
                "Pre-race scanning opens 20 minutes before the race"
                if current == "waiting"
                else f"The race is in its {current}-race phase",
            )
        expected = f"awaiting-{body.phase}" if body.action == "start" else f"scanning-{body.phase}"
        if row["state"] != expected:
            raise HTTPException(409, f"Runner is not {expected.replace('-', ' ')}")
        if body.action == "start":
            try:
                await conn.execute(
                    """UPDATE heatmap_race_day.runner_scan_sessions SET state=$1,active_phase=$2,
                       pre_started_at=CASE WHEN $2='pre'
                                          THEN COALESCE(pre_started_at,now())
                                          ELSE pre_started_at END,
                       post_started_at=CASE WHEN $2='post'
                                           THEN COALESCE(post_started_at,now())
                                           ELSE post_started_at END,
                       updated_at=now() WHERE id=$3""",
                    f"scanning-{body.phase}",
                    body.phase,
                    session_id,
                )
            except asyncpg.UniqueViolationError as exc:
                raise HTTPException(
                    409, "Finish the active horse before selecting another"
                ) from exc
        else:
            count = await conn.fetchval(
                """SELECT COUNT(*) FROM heatmap_race_day.scan_frames
                   WHERE runner_scan_id=$1 AND phase=$2""",
                session_id,
                body.phase,
            )
            if not count:
                raise HTTPException(409, "No camera images were captured for this scan")
            await conn.execute(
                """UPDATE heatmap_race_day.runner_scan_sessions SET state=$1,active_phase=NULL,
                   pre_completed_at=CASE WHEN $2='pre' THEN now() ELSE pre_completed_at END,
                   post_completed_at=CASE WHEN $2='post' THEN now() ELSE post_completed_at END,
                   updated_at=now() WHERE id=$3""",
                "awaiting-post" if body.phase == "pre" else "complete",
                body.phase,
                session_id,
            )
    async with _pool(request).acquire() as conn:
        return await _dashboard(conn)


@router.post("/sessions/{session_id}/skip")
async def skip(session_id: int, body: SkipAction, request: Request):
    await _operator(request)
    async with _pool(request).acquire() as conn, conn.transaction():
        row = await _session(conn, session_id, True)
        if not row:
            raise HTTPException(404, "Runner scan not found")
        if row["active_phase"]:
            raise HTTPException(409, "Finish the active scan before marking unavailable")
        await conn.execute(
            """UPDATE heatmap_race_day.runner_scan_sessions
               SET state='cancelled',skip_reason=$1,updated_at=now() WHERE id=$2""",
            body.reason,
            session_id,
        )
    async with _pool(request).acquire() as conn:
        return await _dashboard(conn)


@router.post("/races/{race_run_id}/close")
async def close_race(race_run_id: int, request: Request):
    operator = await _operator(request)
    async with _pool(request).acquire() as conn, conn.transaction():
        row = await conn.fetchrow(
            """SELECT rr.*,COALESCE(r.actual_start_time,r.scheduled_start_time) AS start_at
               FROM heatmap_race_day.race_runs rr JOIN races r ON r.id=rr.race_id
               WHERE rr.id=$1 FOR UPDATE""",
            race_run_id,
        )
        if not row:
            raise HTTPException(404, "Race not found")
        if row["state"] != "open":
            raise HTTPException(409, "Close races in meeting order")
        if row["start_at"] and datetime.now(UTC) < row["start_at"]:
            raise HTTPException(409, "The race has not started yet")
        incomplete = await conn.fetchval(
            """SELECT COUNT(*) FROM heatmap_race_day.runner_scan_sessions
               WHERE race_run_id=$1 AND state NOT IN('complete','cancelled')""",
            race_run_id,
        )
        if incomplete:
            raise HTTPException(
                409, f"Complete or mark unavailable all {incomplete} remaining runner scans"
            )
        await conn.execute(
            """UPDATE heatmap_race_day.race_runs SET state='archived',closed_by=$1,closed_at=now(),
               archive_status='complete',updated_at=now() WHERE id=$2""",
            operator,
            race_run_id,
        )
        await conn.execute(
            """UPDATE heatmap_race_day.race_runs SET state='open',updated_at=now() WHERE id=(
               SELECT rr2.id FROM heatmap_race_day.race_runs rr2 JOIN races r2 ON r2.id=rr2.race_id
               WHERE rr2.meeting_run_id=$1 AND rr2.state='locked'
               ORDER BY r2.scheduled_start_time NULLS LAST,r2.race_number LIMIT 1)""",
            row["meeting_run_id"],
        )
        left = await conn.fetchval(
            """SELECT COUNT(*) FROM heatmap_race_day.race_runs
               WHERE meeting_run_id=$1 AND state!='archived'""",
            row["meeting_run_id"],
        )
        if not left:
            await conn.execute(
                """UPDATE heatmap_race_day.meeting_runs
                   SET state='completed',completed_at=now(),updated_at=now()
                   WHERE id=$1""",
                row["meeting_run_id"],
            )
    async with _pool(request).acquire() as conn:
        return await _dashboard(conn, operator)


@router.get("/archive")
async def archive(request: Request):
    await _operator(request)
    async with _pool(request).acquire() as conn:
        rows = await conn.fetch(
            """SELECT mr.id,m.track_name,m.meeting_date,COUNT(rr.id)::int AS race_count
               FROM heatmap_race_day.meeting_runs mr JOIN meetings m ON m.id=mr.meeting_id
               JOIN heatmap_race_day.race_runs rr ON rr.meeting_run_id=mr.id
               WHERE rr.state='archived' GROUP BY mr.id,m.track_name,m.meeting_date
               ORDER BY m.meeting_date DESC,m.track_name"""
        )
        return {
            "meetings": [
                {
                    "id": r["id"],
                    "name": r["track_name"],
                    "date": r["meeting_date"].isoformat(),
                    "races": [{} for _ in range(r["race_count"])],
                }
                for r in rows
            ]
        }


async def _serve_frame(frame_id: int, processed: bool, request: Request):
    await _operator(request)
    async with _pool(request).acquire() as conn:
        row = await conn.fetchrow(
            """SELECT raw_storage_path,processed_storage_path
               FROM heatmap_race_day.scan_frames WHERE id=$1""",
            frame_id,
        )
    if not row:
        raise HTTPException(404, "Frame not found")
    raw = row["processed_storage_path"] if processed else row["raw_storage_path"]
    if not raw:
        raise HTTPException(404, "Processed frame not available")
    root = Path(settings.heatmap_storage_path).resolve()
    path = Path(raw).resolve()
    if path != root and root not in path.parents:
        raise HTTPException(403, "Frame path is outside Heatmap storage")
    if not path.is_file():
        raise HTTPException(404, "Frame file not found")
    return FileResponse(path)


@router.get("/frames/{frame_id}/raw")
async def raw_frame(frame_id: int, request: Request):
    return await _serve_frame(frame_id, False, request)


@router.get("/frames/{frame_id}/processed")
async def processed_frame(frame_id: int, request: Request):
    return await _serve_frame(frame_id, True, request)
