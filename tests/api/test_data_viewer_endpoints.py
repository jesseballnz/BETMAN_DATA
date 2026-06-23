from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


client = TestClient(app)
AUTH = {"Authorization": "Bearer " + settings.admin_api_key}


def test_data_viewer_endpoints_empty_safe():
    checks = [
        ("GET", "/v1/health"),
        ("GET", "/v1/stats/overview"),
        ("GET", "/v1/meetings"),
        ("GET", "/v1/races"),
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
        ("GET", "/v1/analytics/trainer-win-rates"),
        ("GET", "/v1/analytics/jockey-win-rates"),
    ]

    for method, path in checks:
        response = client.request(method, path, headers=AUTH if path != "/v1/health" else None)
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
