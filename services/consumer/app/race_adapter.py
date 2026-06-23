"""
RaceAdapter — consumes race data from external providers.

Polls external race data APIs (TAB NZ, Racing Australia, etc.) and
upserts meetings, races, runners, and race_entries into the warehouse.
Detects race state changes (scratching, result, abandonment) and
publishes race state events to Redis for WebSocket fanout.
"""

import asyncio
from typing import List, Dict, Any

import structlog

from app.config import settings
from app.state import StateManager
from app.providers import LoveracingClient, RacingVictoriaClient

log = structlog.get_logger(__name__)


class RaceAdapter:
    """
    Syncs race data from configured external providers.
    Provider clients are loaded from api_key_configs in the DB.
    """

    def __init__(self, state: StateManager, db_url: str) -> None:
        self._state = state
        self._db_url = db_url
        # Initialize providers
        self._providers = {
            "loveracing": LoveracingClient(api_key="placeholder"),
            "racing_victoria": RacingVictoriaClient(api_key="placeholder")
        }

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
        Normalizes external data and maps to internal UUIDs via provider_entity_mappings.
        """
        for provider_name, client in self._providers.items():
            log.info("race_adapter.sync_provider", provider=provider_name)
            try:
                normalized_races = await client.fetch_todays_races()
                for race in normalized_races:
                    await self._process_normalized_race(provider_name, race)
            except Exception:
                log.exception("race_adapter.provider_sync_error", provider=provider_name)

    async def _process_normalized_race(self, provider_name: str, race_data: dict) -> None:
        """
        Takes a NormalizedRace dict and upserts it using the Entity Resolution Service logic.
        """
        # TODO: Implement database upsert with ID resolution using provider_entity_mappings
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
