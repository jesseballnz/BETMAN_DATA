from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.db import fetch_all

router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.get("")
async def list_meetings(request: Request, date: str | None = Query(None, description="YYYY-MM-DD")):
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
        date,
    )
    return {"date": date, "meetings": rows}
