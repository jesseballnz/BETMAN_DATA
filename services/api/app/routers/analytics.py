from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from app.analytics_helpers import compute_person_metrics
from app.db import fetch_all
from app.routers.tracks import canonical_track_name

router = APIRouter(prefix="/analytics", tags=["analytics"])
VALID_GROUP_BYS = {"track", "barrier"}
VALID_ORDER_BYS = {"win_rate", "place_rate", "roi", "runners"}


def _where_date_clause(
    date_from: str | None,
    date_to: str | None,
    *,
    params: list[Any],
    column: str = "m.meeting_date",
) -> list[str]:
    clauses: list[str] = []
    if date_from is not None:
        params.append(_parse_date_param(date_from, "date_from"))
        clauses.append(f"{column} >= ${len(params)}::date")
    if date_to is not None:
        params.append(_parse_date_param(date_to, "date_to"))
        clauses.append(f"{column} <= ${len(params)}::date")
    return clauses


def _parse_date_param(value: str | None, label: str) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"{label} must be YYYY-MM-DD") from exc


@router.get("/trainer-win-rates")
async def get_trainer_win_rates(
    request: Request,
    track: str | None = None,
    surface: str | None = None,
    condition_category: str | None = None,
    distance_min: int | None = None,
    distance_max: int | None = None,
    race_class_group: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    min_runners: int = Query(default=5, ge=1),
    order_by: str = Query(default="win_rate"),
    group_by: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
):
    return await _get_people_rates(
        request,
        role_column="re.trainer",
        role_label="trainer",
        track=track,
        surface=surface,
        condition_category=condition_category,
        distance_min=distance_min,
        distance_max=distance_max,
        race_class_group=race_class_group,
        date_from=date_from,
        date_to=date_to,
        min_runners=min_runners,
        order_by=order_by,
        group_by=group_by,
        limit=limit,
    )


@router.get("/jockey-win-rates")
async def get_jockey_win_rates(
    request: Request,
    track: str | None = None,
    surface: str | None = None,
    condition_category: str | None = None,
    distance_min: int | None = None,
    distance_max: int | None = None,
    race_class_group: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    min_runners: int = Query(default=5, ge=1),
    order_by: str = Query(default="win_rate"),
    group_by: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
):
    return await _get_people_rates(
        request,
        role_column="re.jockey_or_driver",
        role_label="jockey",
        track=track,
        surface=surface,
        condition_category=condition_category,
        distance_min=distance_min,
        distance_max=distance_max,
        race_class_group=race_class_group,
        date_from=date_from,
        date_to=date_to,
        min_runners=min_runners,
        order_by=order_by,
        group_by=group_by,
        limit=limit,
    )


@router.get("/racing-pulse")
async def get_racing_pulse(
    request: Request,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = Query(default=12, ge=1, le=50),
):
    params: list[Any] = []
    date_clauses = _where_date_clause(date_from, date_to, params=params)
    where_sql = f"WHERE {' AND '.join(date_clauses)}" if date_clauses else ""

    totals = await fetch_all(
        request,
        f"""
        SELECT
            COUNT(DISTINCT m.id)::int AS meetings,
            COUNT(DISTINCT r.id)::int AS races,
            COUNT(re.id)::int AS runners,
            COUNT(DISTINCT NULLIF(re.jockey_or_driver, ''))::int AS jockeys,
            COUNT(DISTINCT NULLIF(re.trainer, ''))::int AS trainers,
            COUNT(DISTINCT m.track_name)::int AS tracks,
            COUNT(re.id) FILTER (WHERE re.final_position IS NOT NULL)::int AS resulted_runners,
            COUNT(re.id) FILTER (WHERE re.scratched)::int AS scratched_runners,
            MIN(m.meeting_date)::text AS first_meeting_date,
            MAX(m.meeting_date)::text AS latest_meeting_date
        FROM meetings m
        JOIN races r ON r.meeting_id = m.id
        LEFT JOIN race_entries re ON re.race_id = r.id
        {where_sql}
        """,
        *params,
    )

    coverage = await fetch_all(
        request,
        f"""
        SELECT
            m.meeting_date::text AS date,
            COUNT(DISTINCT m.id)::int AS meetings,
            COUNT(DISTINCT r.id)::int AS races,
            COUNT(re.id)::int AS runners,
            COUNT(DISTINCT NULLIF(re.jockey_or_driver, ''))::int AS jockeys,
            COUNT(DISTINCT NULLIF(re.trainer, ''))::int AS trainers,
            COUNT(DISTINCT m.track_name)::int AS tracks,
            ROUND(COUNT(re.id)::numeric / NULLIF(COUNT(DISTINCT r.id), 0), 2)::float AS avg_field_size
        FROM meetings m
        JOIN races r ON r.meeting_id = m.id
        LEFT JOIN race_entries re ON re.race_id = r.id
        {where_sql}
        GROUP BY m.meeting_date
        ORDER BY m.meeting_date DESC
        LIMIT 30
        """,
        *params,
    )

    track_activity = await fetch_all(
        request,
        f"""
        SELECT
            m.track_name,
            COALESCE(m.jurisdiction, 'Unknown') AS jurisdiction,
            COALESCE(m.surface, 'Unknown') AS surface,
            COUNT(DISTINCT m.id)::int AS meetings,
            COUNT(DISTINCT r.id)::int AS races,
            COUNT(re.id)::int AS runners,
            COUNT(DISTINCT NULLIF(re.jockey_or_driver, ''))::int AS jockeys,
            COUNT(DISTINCT NULLIF(re.trainer, ''))::int AS trainers,
            ROUND(COUNT(re.id)::numeric / NULLIF(COUNT(DISTINCT r.id), 0), 2)::float AS avg_field_size
        FROM meetings m
        JOIN races r ON r.meeting_id = m.id
        LEFT JOIN race_entries re ON re.race_id = r.id
        {where_sql}
        GROUP BY m.track_name, COALESCE(m.jurisdiction, 'Unknown'), COALESCE(m.surface, 'Unknown')
        ORDER BY runners DESC, races DESC
        LIMIT {limit}
        """,
        *params,
    )

    race_class_activity = await fetch_all(
        request,
        f"""
        SELECT
            COALESCE(NULLIF(r.race_class_group, ''), NULLIF(r.race_class_code, ''), 'Unclassified') AS race_class,
            COUNT(DISTINCT r.id)::int AS races,
            COUNT(re.id)::int AS runners,
            ROUND(COUNT(re.id)::numeric / NULLIF(COUNT(DISTINCT r.id), 0), 2)::float AS avg_field_size
        FROM meetings m
        JOIN races r ON r.meeting_id = m.id
        LEFT JOIN race_entries re ON re.race_id = r.id
        {where_sql}
        GROUP BY COALESCE(NULLIF(r.race_class_group, ''), NULLIF(r.race_class_code, ''), 'Unclassified')
        ORDER BY runners DESC, races DESC
        LIMIT {limit}
        """,
        *params,
    )

    market = await fetch_all(
        request,
        f"""
        WITH scoped_entries AS (
            SELECT
                re.id AS race_entry_id,
                re.final_position,
                r.id AS race_id
            FROM race_entries re
            JOIN races r ON r.id = re.race_id
            JOIN meetings m ON m.id = r.meeting_id
            {where_sql}
        ),
        filtered_prices AS (
            SELECT
                se.race_entry_id,
                se.final_position,
                se.race_id,
                lp.closing_price,
                lp.captured_at
            FROM scoped_entries se
            JOIN LATERAL (
                SELECT
                    COALESCE(os.win_sp, os.win_price)::float AS closing_price,
                    os.captured_at
                FROM odds_snapshots os
                WHERE os.race_entry_id = se.race_entry_id
                  AND COALESCE(os.win_sp, os.win_price) IS NOT NULL
                ORDER BY os.captured_at DESC
                LIMIT 1
            ) lp ON TRUE
        ),
        favourites AS (
            SELECT DISTINCT ON (race_id)
                race_id,
                final_position,
                closing_price
            FROM filtered_prices
            ORDER BY race_id, closing_price ASC NULLS LAST
        )
        SELECT
            COUNT(*)::int AS priced_runners,
            ROUND(AVG(closing_price)::numeric, 2)::float AS avg_closing_price,
            ROUND(MIN(closing_price)::numeric, 2)::float AS min_closing_price,
            ROUND(MAX(closing_price)::numeric, 2)::float AS max_closing_price,
            MAX(captured_at)::text AS latest_price_at,
            (SELECT COUNT(*)::int FROM favourites) AS favourite_races,
            (SELECT COUNT(*)::int FROM favourites WHERE final_position = 1) AS favourite_wins,
            ROUND(
                (SELECT COUNT(*)::numeric FROM favourites WHERE final_position = 1) * 100.0
                / NULLIF((SELECT COUNT(*) FROM favourites), 0),
                2
            )::float AS favourite_win_rate
        FROM filtered_prices
        """,
        *params,
    )

    people_params: list[Any] = []
    people_clauses = _where_date_clause(date_from, date_to, params=people_params)
    if people_clauses:
        people_clauses.append("re.scratched = false")
    else:
        people_clauses = ["re.scratched = false"]
    people_where_sql = f"WHERE {' AND '.join(people_clauses)}"

    async def people_rows(role_column: str) -> list[dict[str, Any]]:
        return await fetch_all(
            request,
            f"""
            SELECT
                {role_column} AS person,
                NULL::text AS split_value,
                re.final_position,
                lp.closing_price
            FROM race_entries re
            JOIN races r ON r.id = re.race_id
            JOIN meetings m ON m.id = r.meeting_id
            LEFT JOIN LATERAL (
                SELECT COALESCE(os.win_sp, os.win_price)::float AS closing_price
                FROM odds_snapshots os
                WHERE os.race_entry_id = re.id
                  AND COALESCE(os.win_sp, os.win_price) IS NOT NULL
                ORDER BY os.captured_at DESC
                LIMIT 1
            ) lp ON TRUE
            {people_where_sql}
                AND {role_column} IS NOT NULL
                AND re.final_position IS NOT NULL
            """,
            *people_params,
        )

    jockeys = compute_person_metrics(await people_rows("re.jockey_or_driver"), min_runners=3, order_by="wins")[:limit]
    trainers = compute_person_metrics(await people_rows("re.trainer"), min_runners=3, order_by="wins")[:limit]

    return {
        "filters": {"date_from": date_from, "date_to": date_to},
        "totals": dict(totals[0]) if totals else {},
        "coverage": [dict(row) for row in reversed(coverage)],
        "top_jockeys": jockeys,
        "top_trainers": trainers,
        "track_activity": [dict(row) for row in track_activity],
        "race_class_activity": [dict(row) for row in race_class_activity],
        "market": dict(market[0]) if market else {},
    }


async def _get_people_rates(
    request: Request,
    *,
    role_column: str,
    role_label: str,
    track: str | None,
    surface: str | None,
    condition_category: str | None,
    distance_min: int | None,
    distance_max: int | None,
    race_class_group: str | None,
    date_from: str | None,
    date_to: str | None,
    min_runners: int,
    order_by: str,
    group_by: str | None,
    limit: int,
):
    validated_order = order_by if order_by in VALID_ORDER_BYS else "win_rate"
    validated_group = group_by if group_by in VALID_GROUP_BYS else None

    clauses = [
        f"{role_column} IS NOT NULL",
        "re.scratched = false",
        "re.final_position IS NOT NULL",
    ]
    params: list[Any] = []
    if track is not None:
        params.append(canonical_track_name(track))
        clauses.append(f"LOWER(m.track_name) = LOWER(${len(params)})")
    if surface is not None:
        params.append(surface)
        clauses.append(f"COALESCE(r.surface, m.surface) = ${len(params)}")
    if condition_category is not None:
        params.append(condition_category)
        clauses.append(f"LOWER(COALESCE(tc.condition_category, '')) = LOWER(${len(params)})")
    if distance_min is not None:
        params.append(distance_min)
        clauses.append(f"r.distance_m >= ${len(params)}")
    if distance_max is not None:
        params.append(distance_max)
        clauses.append(f"r.distance_m <= ${len(params)}")
    if race_class_group is not None:
        params.append(race_class_group)
        clauses.append(f"r.race_class_group = ${len(params)}")
    if date_from is not None:
        params.append(_parse_date_param(date_from, "date_from"))
        clauses.append(f"m.meeting_date >= ${len(params)}::date")
    if date_to is not None:
        params.append(_parse_date_param(date_to, "date_to"))
        clauses.append(f"m.meeting_date <= ${len(params)}::date")

    split_select = "NULL::text AS split_value"
    if validated_group == "track":
        split_select = "m.track_name AS split_value"
    elif validated_group == "barrier":
        split_select = "COALESCE(re.barrier_number::text, 'Unknown') AS split_value"

    rows = await fetch_all(
        request,
        f"""
        SELECT
            {role_column} AS person,
            {split_select},
            re.final_position,
            lp.closing_price
        FROM race_entries re
        JOIN races r ON r.id = re.race_id
        JOIN meetings m ON m.id = r.meeting_id
        LEFT JOIN LATERAL (
            SELECT COALESCE(os.win_sp, os.win_price)::float AS closing_price
            FROM odds_snapshots os
            WHERE os.race_entry_id = re.id
              AND COALESCE(os.win_sp, os.win_price) IS NOT NULL
            ORDER BY os.captured_at DESC
            LIMIT 1
        ) lp ON TRUE
        LEFT JOIN LATERAL (
            SELECT condition_category
            FROM track_condition_readings tcr
            WHERE tcr.race_id = r.id OR (tcr.race_id IS NULL AND tcr.meeting_id = m.id)
            ORDER BY CASE WHEN tcr.race_id = r.id THEN 0 ELSE 1 END, recorded_at DESC
            LIMIT 1
        ) tc ON TRUE
        WHERE {" AND ".join(clauses)}
        """,
        *params,
    )

    items = compute_person_metrics(rows, min_runners=min_runners, order_by=validated_order)[:limit]
    return {
        "role": role_label,
        "filters": {
            "track": track,
            "surface": surface,
            "condition_category": condition_category,
            "distance_min": distance_min,
            "distance_max": distance_max,
            "race_class_group": race_class_group,
            "date_from": date_from,
            "date_to": date_to,
            "min_runners": min_runners,
            "group_by": validated_group,
            "order_by": validated_order,
        },
        "items": items,
    }
