from datetime import UTC, datetime, timedelta

import pytest
from app.routers import race_day
from fastapi import HTTPException
from starlette.requests import Request


def request(authorization: str | None = None):
    headers = (
        [] if authorization is None else [(b"authorization", authorization.encode())]
    )
    return Request(
        {"type": "http", "method": "GET", "path": "/v1/race-day", "headers": headers}
    )


class Response:
    status_code = 200

    def __init__(self, subject: str):
        self.subject = subject

    def json(self):
        return {"user": {"currentUser": self.subject}}


class Client:
    subject = "betman"

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, *args, **kwargs):
        return Response(self.subject)


@pytest.mark.asyncio
async def test_race_day_requires_core_session():
    with pytest.raises(HTTPException) as exc:
        await race_day._operator(request())
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_race_day_allows_only_exact_betman_subject(monkeypatch):
    race_day._auth_cache.clear()
    monkeypatch.setattr(race_day.httpx, "AsyncClient", Client)
    Client.subject = "subscriber"
    with pytest.raises(HTTPException) as exc:
        await race_day._operator(request("Bearer subscriber"))
    assert exc.value.status_code == 403
    Client.subject = "betman"
    assert await race_day._operator(request("Bearer betman")) == "betman"


def test_t_minus_twenty_phase_boundary():
    start = datetime(2026, 9, 18, 3, 0, tzinfo=UTC)
    assert race_day._phase(start, start - timedelta(minutes=20, seconds=1)) == "waiting"
    assert race_day._phase(start, start - timedelta(minutes=20)) == "pre"
    assert race_day._phase(start, start) == "post"
