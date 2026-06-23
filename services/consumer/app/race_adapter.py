"""
RaceAdapter — consumes race data from external providers.

Polls external race data APIs (TAB NZ, Racing Australia, etc.) and
upserts meetings, races, runners, and race_entries into the warehouse.
Detects race state changes (scratching, result, abandonment) and
publishes race state events to Redis for WebSocket fanout.
"""

import asyncio

import structlog

from app.config import settings
from app.state import StateManager

log = structlog.get_logger(__name__)


class RaceAdapter:
    """
    Syncs race data from configured external providers.
    Provider clients are loaded from api_key_configs in the DB.
    """

    def __init__(self, state: StateManager, db_url: str) -> None:
        self._state = state
        self._db_url = db_url

    async def run(self, stop_event: asyncio.Event) -> None:
        log.info("race_adapter.starting")
        while not stop_event.is_set():
            try:
                await self._sync_today()
            except Exception:
                log.exception("race_adapter.sync_error")
            await asyncio.sleep(settings.race_data_poll_interval_s)
        log.info("race_adapter.stopped")

    async def _sync_today(self) -> None:
        """
        Fetch today's meetings and races from configured providers.
        Upserts into meetings, races, runners, and race_entries tables.
        On result confirmation: triggers barrier_outcomes write and
        barrier_statistics rebuild.

        TODO: implement provider-specific API clients using api_key_configs.
        """
        pass

    async def _on_race_result(self, race_id: int) -> None:
        """
        Called when a race result is confirmed.
        Triggers the barrier analysis pipeline and publishes a result event.
        """
        await self._write_barrier_outcomes(race_id)
        await self._rebuild_barrier_statistics(race_id)
        await self._state.remove_live_race(race_id)
        await self._state.publish_event(
            "betman:races:results",
            {"event": "race_result", "race_id": race_id},
        )
        log.info("race_adapter.result_processed", race_id=race_id)

    async def _write_barrier_outcomes(self, race_id: int) -> None:
        """
        Write one barrier_outcomes row per race entry, joining to:
          - track_condition_readings (condition at race time)
          - weather_readings (weather at race time)
          - soil_moisture_readings (soil moisture at race time)

        TODO: implement DB write.
        """
        pass

    async def _rebuild_barrier_statistics(self, race_id: int) -> None:
        """
        Recompute barrier_statistics aggregations and track_heatmap_cells
        for the track/condition/distance band affected by this race.

        TODO: implement aggregation query and upsert.
        """
        pass
