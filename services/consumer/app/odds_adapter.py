"""
OddsAdapter — consumes odds and pricing data from external sources.

Writes odds_snapshots to the warehouse and detects significant
movements (steam, drift, blowout, late firm) which are written to
odds_movements and published to Redis for WebSocket fanout.

Market suspension events are cross-referenced with race timeline
signals — a suspended market is a strong indicator of imminent jump.
"""

import asyncio
from decimal import Decimal

import structlog

from app.config import settings
from app.state import StateManager

log = structlog.get_logger(__name__)


class OddsAdapter:
    def __init__(self, state: StateManager, db_url: str) -> None:
        self._state = state
        self._db_url = db_url
        # In-memory cache of last known price per entry: {race_entry_id: Decimal}
        self._last_prices: dict[int, Decimal] = {}

    async def run(self, stop_event: asyncio.Event) -> None:
        log.info("odds_adapter.starting")
        while not stop_event.is_set():
            try:
                await self._sync_odds()
            except Exception:
                log.exception("odds_adapter.sync_error")
            await asyncio.sleep(settings.odds_poll_interval_s)
        log.info("odds_adapter.stopped")

    async def _sync_odds(self) -> None:
        """
        Fetch current odds for all upcoming races.
        For each entry: write snapshot, detect movement, update analytics.

        TODO: implement provider-specific client using api_key_configs.
        """
        pass

    async def _process_snapshot(
        self,
        race_id: int,
        race_entry_id: int,
        new_price: Decimal,
        source: str,
        time_to_jump_s: int,
    ) -> None:
        """
        Compare the new price against the last known price and detect movements.
        Writes to odds_snapshots and conditionally to odds_movements.
        Updates odds_analytics summary for this entry.
        """
        last = self._last_prices.get(race_entry_id)
        self._last_prices[race_entry_id] = new_price

        if last is None or last == 0:
            return  # No movement to detect — first snapshot

        movement_pct = float((new_price - last) / last * 100)
        movement_type = self._classify_movement(movement_pct, time_to_jump_s)

        if movement_type:
            await self._write_movement(
                race_id, race_entry_id, last, new_price, movement_pct,
                movement_type, time_to_jump_s, source,
            )
            if movement_type in ("steam", "blowout"):
                await self._state.publish_event(
                    "betman:races:odds",
                    {
                        "event": "odds_movement",
                        "race_id": race_id,
                        "race_entry_id": race_entry_id,
                        "movement_type": movement_type,
                        "from_price": float(last),
                        "to_price": float(new_price),
                        "movement_pct": movement_pct,
                        "time_to_jump_s": time_to_jump_s,
                    },
                )

    def _classify_movement(
        self, movement_pct: float, time_to_jump_s: int
    ) -> str | None:
        """
        Classify a price movement based on configured thresholds.

        Negative movement_pct = price shortened (firming).
        Positive movement_pct = price lengthened (drifting).
        """
        steam_t = -settings.odds_steam_threshold_pct
        blowout_t = settings.odds_blowout_threshold_pct
        late_window = settings.odds_late_firm_window_s

        if movement_pct <= steam_t:
            return "late_firm" if time_to_jump_s <= late_window else "steam"
        if movement_pct <= -5:
            return "firm"
        if movement_pct >= blowout_t:
            return "blowout"
        if movement_pct >= 5:
            return "drift"
        return None

    async def _write_movement(
        self,
        race_id: int,
        race_entry_id: int,
        from_price: Decimal,
        to_price: Decimal,
        movement_pct: float,
        movement_type: str,
        time_to_jump_s: int,
        source: str,
    ) -> None:
        """
        Write an odds_movements row.
        TODO: implement DB write.
        """
        log.info(
            "odds_adapter.movement_detected",
            race_id=race_id,
            entry_id=race_entry_id,
            type=movement_type,
            from_price=float(from_price),
            to_price=float(to_price),
            pct=round(movement_pct, 1),
            time_to_jump_s=time_to_jump_s,
        )
