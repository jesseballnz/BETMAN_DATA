"""
WeatherAdapter — polls WeatherLink stations and soil moisture probes.

For each active weather_station in the DB:
  1. Load the API key from api_key_configs (decrypted at runtime)
  2. Poll the WeatherLink v2 API for current conditions
  3. Write weather_readings to the DB
  4. Poll each associated soil_moisture_probe
  5. Write soil_moisture_readings to the DB
  6. Update the Redis weather snapshot for the track (for fast API access)
  7. Compute a rolling average soil moisture and update track_condition_readings
     if the derived condition has changed

The multi-probe soil moisture array gives a spatial picture of the track
that feeds directly into barrier_outcomes at race time.
"""

import asyncio
from datetime import UTC, datetime

import httpx
import structlog

from app.config import settings
from app.state import StateManager

log = structlog.get_logger(__name__)


class WeatherAdapter:
    def __init__(self, state: StateManager, db_url: str) -> None:
        self._state = state
        self._db_url = db_url

    async def run(self, stop_event: asyncio.Event) -> None:
        log.info("weather_adapter.starting")
        while not stop_event.is_set():
            try:
                await self._sync_all_stations()
            except Exception:
                log.exception("weather_adapter.sync_error")
            await asyncio.sleep(settings.weatherlink_poll_interval_s)
        log.info("weather_adapter.stopped")

    async def _sync_all_stations(self) -> None:
        """Fetch and persist readings for every active weather station."""
        stations = await self._load_active_stations()
        if not stations:
            return

        async with httpx.AsyncClient(timeout=15.0) as http:
            await asyncio.gather(
                *[self._sync_station(station, http) for station in stations]
            )

    async def _load_active_stations(self) -> list[dict]:
        """
        Load active weather_stations with their decrypted API keys.
        TODO: query weather_stations JOIN api_key_configs from DB,
        decrypt api_key using settings.platform_master_key.
        """
        return []  # placeholder

    async def _sync_station(self, station: dict, http: httpx.AsyncClient) -> None:
        """
        Poll the WeatherLink API for a single station and write all readings.

        WeatherLink v2 API docs:
          https://weatherlink.github.io/v2-api/
        Endpoint: GET /v2/current/{station_id}?api-key={key}
        """
        station_id = station.get("station_id")
        api_key = station.get("api_key")  # already decrypted
        track_name = station.get("track_name")

        try:
            url = f"{settings.weatherlink_base_url}/current/{station_id}"
            resp = await http.get(url, params={"api-key": api_key})
            resp.raise_for_status()
            data = resp.json()

            reading = self._parse_weather(data, station["id"])
            await self._write_weather_reading(reading)

            # Update Redis snapshot for fast API access
            await self._state.set_weather_snapshot(track_name, reading)

            # Sync soil probes (separate WeatherLink sensor records)
            await self._sync_probes(station, data, http)

        except httpx.HTTPStatusError as e:
            log.warning(
                "weather_adapter.api_error",
                station_id=station_id,
                status=e.response.status_code,
            )
        except Exception:
            log.exception("weather_adapter.station_error", station_id=station_id)

    def _parse_weather(self, data: dict, db_station_id: int) -> dict:
        """
        Map a WeatherLink API response to a weather_readings row dict.
        WeatherLink returns sensor data in a nested 'sensors' array.
        """
        sensors = {s["sensor_type"]: s["data"][0] for s in data.get("sensors", []) if s.get("data")}
        iss = sensors.get(37, {})  # ISS sensor type = 37 (integrated sensor suite)
        return {
            "station_id": db_station_id,
            "recorded_at": datetime.now(UTC).isoformat(),
            "temperature_c": self._f_to_c(iss.get("temp")),
            "humidity_pct": iss.get("hum"),
            "wind_speed_kmh": self._mph_to_kmh(iss.get("wind_speed_avg_last_10_min")),
            "wind_gust_kmh": self._mph_to_kmh(iss.get("wind_speed_hi_last_10_min")),
            "wind_direction_deg": iss.get("wind_dir_scalar_avg_last_10_min"),
            "rainfall_mm": self._in_to_mm(iss.get("rainfall_last_15_min_clicks")),
            "rainfall_1h_mm": self._in_to_mm(iss.get("rainfall_last_60_min_clicks")),
            "rainfall_24h_mm": self._in_to_mm(iss.get("rainfall_daily_clicks")),
            "barometric_pressure_hpa": self._inhg_to_hpa(iss.get("bar_sea_level")),
            "uv_index": iss.get("uv_index"),
            "solar_radiation_wm2": iss.get("solar_rad"),
            "dew_point_c": self._f_to_c(iss.get("dew_point")),
        }

    async def _sync_probes(
        self, station: dict, api_data: dict, http: httpx.AsyncClient
    ) -> None:
        """
        Parse soil moisture probe readings from the WeatherLink response
        and write to soil_moisture_readings.
        TODO: implement probe sensor type mapping.
        """
        pass

    async def _write_weather_reading(self, reading: dict) -> None:
        """Write a weather_readings row to the DB. TODO: implement."""
        pass

    # ── Unit conversion helpers ──────────────────────────────────────────────

    @staticmethod
    def _f_to_c(f: float | None) -> float | None:
        return round((f - 32) * 5 / 9, 2) if f is not None else None

    @staticmethod
    def _mph_to_kmh(mph: float | None) -> float | None:
        return round(mph * 1.60934, 2) if mph is not None else None

    @staticmethod
    def _in_to_mm(inches: float | None) -> float | None:
        return round(inches * 25.4, 2) if inches is not None else None

    @staticmethod
    def _inhg_to_hpa(inhg: float | None) -> float | None:
        return round(inhg * 33.8639, 2) if inhg is not None else None
