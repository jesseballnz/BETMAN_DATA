from __future__ import annotations

import json
from datetime import date as date_type
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from app.db import fetch_all

router = APIRouter(prefix="/meetings", tags=["meetings"])


def _parse_date_param(value: str | None) -> date_type | None:
    if value is None:
        return None
    try:
        return date_type.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="date must be YYYY-MM-DD") from exc


def _coerce_races(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(decoded, list):
            return [item for item in decoded if isinstance(item, dict)]
    return []


@router.get("")
async def list_meetings(request: Request, date: str | None = Query(None, description="YYYY-MM-DD")):
    meeting_date = _parse_date_param(date)
    rows = await fetch_all(
        request,
        """
        SELECT
            m.id,
            m.track_name,
            m.meeting_date,
            m.surface,
            m.jurisdiction,
            m.status,
            COUNT(r.id)::int AS race_count,
            COUNT(*) FILTER (WHERE r.status = 'running')::int AS running_races,
            COUNT(*) FILTER (WHERE r.status = 'finished')::int AS finished_races,
            COALESCE(
                json_agg(
                    json_build_object(
                        'id', r.id,
                        'race_number', r.race_number,
                        'name', r.name,
                        'distance_m', r.distance_m,
                        'status', r.status,
                        'scheduled_start_time', r.scheduled_start_time
                    ) ORDER BY r.race_number
                ) FILTER (WHERE r.id IS NOT NULL),
                '[]'::json
            ) AS races
        FROM meetings m
        LEFT JOIN races r ON r.meeting_id = m.id
        WHERE ($1::date IS NULL OR m.meeting_date = $1::date)
        GROUP BY m.id, m.track_name, m.meeting_date, m.surface, m.jurisdiction, m.status
        ORDER BY m.track_name, m.id
        """,
        meeting_date,
    )
    for row in rows:
        row["races"] = _coerce_races(row.get("races"))
    return {"date": date, "meetings": rows}
