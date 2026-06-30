from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.routers.meetings import _coerce_races
from app.routers.races import _sample_time_series


client = TestClient(app)
AUTH = {"Authorization": "Bearer " + settings.admin_api_key}


def test_data_viewer_endpoints_empty_safe():
    checks = [
        ("GET", "/v1/health"),
        ("GET", "/v1/stats/overview"),
        ("GET", "/v1/meetings"),
        ("GET", "/v1/meetings?date=2026-06-26"),
        ("GET", "/v1/races"),
        ("GET", "/v1/races?date=2026-06-26"),
        ("GET", "/v1/market/signals"),
        ("GET", "/v1/market/steamers"),
        ("GET", "/v1/market/drifters"),
        ("GET", "/v1/market/smart-money"),
        ("GET", "/v1/discovery/patterns"),
        ("GET", "/v1/discovery/patterns/by-gate"),
        ("GET", "/v1/discovery/signals"),
        ("GET", "/v1/discovery/runs"),
        ("GET", "/v1/intelligence/scores/leaderboard"),
        ("GET", "/v1/intelligence/signals/performance"),
        ("GET", "/v1/tracks"),
        ("GET", "/v1/tracks/Ellerslie/barriers"),
        ("GET", "/v1/tracks/Ellerslie/heatmap"),
        ("GET", "/v1/analytics/racing-pulse"),
        ("GET", "/v1/analytics/trainer-win-rates"),
        ("GET", "/v1/analytics/jockey-win-rates"),
    ]

    for method, path in checks:
        response = client.request(
            method, path, headers=AUTH if path != "/v1/health" else None
        )
        assert response.status_code == 200, path

    assistant = client.post(
        "/v1/assistant/query",
        headers=AUTH,
        json={"question": "today's steamers"},
    )
    assert assistant.status_code == 200
    payload = assistant.json()
    assert "sql" in payload
    assert payload["rows"] == []


def test_meeting_races_are_normalized_from_json_string():
    assert _coerce_races('[{"id": 1, "race_number": 1}, "bad", null]') == [
        {"id": 1, "race_number": 1}
    ]
    assert _coerce_races([{"id": 2}]) == [{"id": 2}]
    assert _coerce_races("not json") == []
    assert _coerce_races(None) == []


def test_time_series_sampling_preserves_edges_and_limit():
    rows = [{"value": index} for index in range(1000)]

    sampled = _sample_time_series(rows, 320)

    assert len(sampled) == 320
    assert sampled[0] == {"value": 0}
    assert sampled[-1] == {"value": 999}
