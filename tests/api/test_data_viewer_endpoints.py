from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.routers.meetings import _coerce_races
from app.routers.races import _sample_time_series
from app.routers import tracks as tracks_module


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
        ("GET", "/v1/races?date_from=2026-04-27&date_to=2026-06-26"),
        ("GET", "/v1/market/signals"),
        ("GET", "/v1/market/steamers"),
        ("GET", "/v1/market/drifters"),
        ("GET", "/v1/market/smart-money"),
        ("GET", "/v1/discovery/patterns"),
        ("GET", "/v1/discovery/patterns/by-gate"),
        ("GET", "/v1/discovery/signals"),
        ("GET", "/v1/discovery/runs"),
        ("GET", "/v1/intelligence/scores/leaderboard"),
        ("GET", "/v1/intelligence/scores/leaderboard?date_from=2026-04-27&date_to=2026-06-26"),
        ("GET", "/v1/intelligence/signals/performance"),
        ("GET", "/v1/search/ocr?q=Winx&days=60"),
        ("GET", "/v1/search/transcripts?q=Winx&days=60"),
        ("GET", "/v1/tracks"),
        ("GET", "/v1/tracks/Ellerslie/barriers"),
        ("GET", "/v1/tracks/Ellerslie/heatmap"),
        ("GET", "/v1/analytics/racing-pulse"),
        ("GET", "/v1/analytics/racing-pulse?date_from=2026-04-27&date_to=2026-06-26"),
        ("GET", "/v1/analytics/trainer-win-rates"),
        ("GET", "/v1/analytics/trainer-win-rates?date_from=2026-04-27&date_to=2026-06-26"),
        ("GET", "/v1/analytics/jockey-win-rates"),
        ("GET", "/v1/analytics/jockey-win-rates?date_from=2026-04-27&date_to=2026-06-26"),
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


def test_tracks_list_preserves_surface_contexts(monkeypatch):
    async def fake_fetch_all(request, query, *params):
        assert "WHEN 'grass' THEN 'turf'" in query
        assert "GROUP BY track_name, surface" in query
        assert "derived_heatmap_cell_count" in query
        return [
            {
                "track_name": "Awapuni",
                "surface": "synthetic",
                "race_count": 12,
                "meeting_count": 2,
                "barrier_sample_size": 96,
                "heatmap_cell_count": 8,
            },
            {
                "track_name": "Awapuni",
                "surface": "turf",
                "race_count": 40,
                "meeting_count": 5,
                "barrier_sample_size": 320,
                "heatmap_cell_count": 16,
            },
        ]

    monkeypatch.setattr(tracks_module, "fetch_all", fake_fetch_all)

    response = client.get("/v1/tracks", headers=AUTH)

    assert response.status_code == 200
    assert response.json()["tracks"] == [
        {
            "track_name": "Awapuni",
            "surface": "synthetic",
            "race_count": 12,
            "meeting_count": 2,
            "barrier_sample_size": 96,
            "heatmap_cell_count": 8,
        },
        {
            "track_name": "Awapuni",
            "surface": "turf",
            "race_count": 40,
            "meeting_count": 5,
            "barrier_sample_size": 320,
            "heatmap_cell_count": 16,
        },
    ]


def test_track_heatmap_derives_cells_from_barrier_outcomes(monkeypatch):
    calls = []

    async def fake_fetch_all(request, query, *params):
        calls.append(query)
        assert params == ("Ellerslie", "turf", "good", "sprint")
        if "FROM track_heatmap_cells" in query:
            return []
        assert "FROM barrier_outcomes" in query
        assert "relative_barrier" in query
        assert "distance_m" in query
        return [
            {
                "zone": "inside",
                "distance_from_finish_band": "sprint",
                "win_rate": 12.5,
                "place_rate": 37.5,
                "intensity": 1.0,
            }
        ]

    monkeypatch.setattr(tracks_module, "fetch_all", fake_fetch_all)

    response = client.get(
        "/v1/tracks/Ellerslie/heatmap?surface=turf&condition_category=good&distance_band=sprint",
        headers=AUTH,
    )

    assert response.status_code == 200
    assert response.json()["cells"] == [
        {
            "zone": "inside",
            "distance_from_finish_band": "sprint",
            "win_rate": 12.5,
            "place_rate": 37.5,
            "intensity": 1.0,
        }
    ]
    assert len(calls) == 2


def test_track_heatmap_middle_alias_uses_legacy_mile_rows(monkeypatch):
    captured = []

    async def fake_fetch_all(request, query, *params):
        captured.append(params)
        return []

    monkeypatch.setattr(tracks_module, "fetch_all", fake_fetch_all)

    response = client.get(
        "/v1/tracks/Albury/heatmap?surface=turf&distance_band=middle",
        headers=AUTH,
    )

    assert response.status_code == 200
    assert captured
    assert all(params == ("Albury", "turf", "mile") for params in captured)
