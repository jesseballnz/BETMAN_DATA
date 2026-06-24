from __future__ import annotations

from fastapi import APIRouter, Request

from app.db import fetch_all, fetch_row, fetch_value

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/overview")
async def get_stats_overview(request: Request):
    table_stats = await fetch_all(
        request,
        """
        SELECT c.relname AS table_name,
               COALESCE(s.n_live_tup::bigint, c.reltuples::bigint, 0) AS approx_rows,
               pg_total_relation_size(c.oid) AS total_bytes,
               pg_relation_size(c.oid) AS table_bytes,
               pg_indexes_size(c.oid) AS index_bytes
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
        WHERE n.nspname = 'public' AND c.relkind = 'r'
        ORDER BY pg_total_relation_size(c.oid) DESC, c.relname
        """,
    )
    counts = await fetch_row(
        request,
        """
        SELECT
            (SELECT COUNT(*)::int FROM meetings) AS meetings,
            (SELECT COUNT(*)::int FROM races) AS races,
            (SELECT COUNT(*)::int FROM runners) AS runners,
            (SELECT COUNT(*)::int FROM race_entries) AS entries,
            (SELECT COUNT(*)::int FROM odds_snapshots) AS odds_snapshots
        """,
    ) or {"meetings": 0, "races": 0, "runners": 0, "entries": 0, "odds_snapshots": 0}
    today_counts = await fetch_row(
        request,
        """
        SELECT
            (
                SELECT COUNT(*)::int
                FROM meetings
                WHERE meeting_date = CURRENT_DATE
            ) AS meetings_today,
            (
                SELECT COUNT(*)::int
                FROM races r
                JOIN meetings m ON m.id = r.meeting_id
                WHERE m.meeting_date = CURRENT_DATE
            ) AS races_today,
            (
                SELECT COUNT(*)::int
                FROM race_entries re
                JOIN races r ON r.id = re.race_id
                JOIN meetings m ON m.id = r.meeting_id
                WHERE m.meeting_date = CURRENT_DATE
            ) AS runners_today
        """,
    ) or {"meetings_today": 0, "races_today": 0, "runners_today": 0}
    freshness = (
        await fetch_row(
            request,
            """
        SELECT
            (SELECT MAX(captured_at) FROM odds_snapshots) AS latest_odds_snapshot,
            (SELECT MAX(recorded_at) FROM weather_readings) AS latest_weather_reading,
            (SELECT MAX(segment_started_at) FROM media_segments) AS latest_media_segment,
            (SELECT MAX(meeting_date) FROM meetings) AS latest_meeting_date
        """,
        )
        or {}
    )
    ingestion = await fetch_row(
        request,
        """
        SELECT
            (
                SELECT COUNT(*)::int
                FROM odds_snapshots
                WHERE captured_at >= NOW() - INTERVAL '24 hours'
            ) AS odds_snapshots_24h,
            (
                SELECT COUNT(*)::int
                FROM weather_readings
                WHERE recorded_at >= NOW() - INTERVAL '24 hours'
            ) AS weather_readings_24h,
            (
                SELECT COUNT(*)::int
                FROM media_segments
                WHERE segment_started_at >= NOW() - INTERVAL '24 hours'
            ) AS media_segments_24h
        """,
    ) or {"odds_snapshots_24h": 0, "weather_readings_24h": 0, "media_segments_24h": 0}
    total_db_size = (
        await fetch_value(
            request,
            "SELECT pg_database_size(current_database())",
        )
        or 0
    )

    return {
        "database": {
            "name": "betman",
            "total_size_bytes": total_db_size,
            "table_count": len(table_stats),
        },
        "counts": {**counts, **today_counts},
        "freshness": freshness,
        "ingestion_last_24h": ingestion,
        "tables": table_stats,
    }
