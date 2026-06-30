from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request

from app.config import settings
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
    approx_rows_by_table = {
        row["table_name"]: int(row.get("approx_rows") or 0)
        for row in table_stats
    }
    counts = await fetch_row(
        request,
        """
        SELECT
            (SELECT COUNT(*)::int FROM meetings) AS meetings,
            (SELECT COUNT(*)::int FROM races) AS races,
            (SELECT COUNT(*)::int FROM runners) AS runners,
            (SELECT COUNT(*)::int FROM race_entries) AS entries
        """,
    ) or {"meetings": 0, "races": 0, "runners": 0, "entries": 0}
    counts["odds_snapshots"] = approx_rows_by_table.get("odds_snapshots", 0)
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


@router.get("/warehouse")
async def get_warehouse_overview(request: Request):
    data_tables = await fetch_all(
        request,
        """
        SELECT
            c.relname AS table_name,
            'public' AS schema_name,
            COALESCE(s.n_live_tup::bigint, c.reltuples::bigint, 0) AS approx_rows,
            COALESCE(s.n_dead_tup::bigint, 0) AS dead_rows,
            pg_total_relation_size(c.oid) AS total_bytes,
            pg_relation_size(c.oid) AS table_bytes,
            pg_indexes_size(c.oid) AS index_bytes,
            COALESCE(s.seq_scan::bigint, 0) AS seq_scan,
            COALESCE(s.idx_scan::bigint, 0) AS idx_scan,
            COALESCE(s.n_tup_ins::bigint, 0) AS inserts,
            COALESCE(s.n_tup_upd::bigint, 0) AS updates,
            COALESCE(s.n_tup_del::bigint, 0) AS deletes,
            COALESCE(io.heap_blks_read::bigint, 0) AS heap_blocks_read,
            COALESCE(io.heap_blks_hit::bigint, 0) AS heap_blocks_hit,
            COALESCE(io.idx_blks_read::bigint, 0) AS index_blocks_read,
            COALESCE(io.idx_blks_hit::bigint, 0) AS index_blocks_hit,
            s.last_autovacuum::text AS last_autovacuum,
            s.last_autoanalyze::text AS last_autoanalyze
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
        LEFT JOIN pg_statio_user_tables io ON io.relid = c.oid
        WHERE n.nspname = 'public' AND c.relkind = 'r'
        ORDER BY pg_total_relation_size(c.oid) DESC, c.relname
        """,
    )
    data_db_size = await fetch_value(request, "SELECT pg_database_size(current_database())") or 0
    data_database = _database(
        name="betman",
        system="BETMAN Data",
        engine="PostgreSQL",
        host="betman-heatmap-syd1",
        location="127.0.0.1:5432",
        role="warehouse",
        total_size_bytes=int(data_db_size),
        tables=[_table(row, database="betman", system="BETMAN Data") for row in data_tables],
        source="live_pg_stat",
    )

    external = _load_external_snapshot()
    databases = [data_database, *external.get("databases", [])]
    for db in databases:
        db["tables"] = [_normalise_external_table(table, db) for table in db.get("tables", [])]
        db["table_count"] = len(db["tables"])
        db["row_count"] = sum(int(table.get("approx_rows") or 0) for table in db["tables"])
        db["hot_tables"] = sorted(db["tables"], key=lambda item: int(item.get("read_ops") or 0), reverse=True)[:8]
        db["large_tables"] = sorted(db["tables"], key=lambda item: int(item.get("total_bytes") or 0), reverse=True)[:8]

    all_tables = [table for db in databases for table in db["tables"]]
    large_tables = sorted(all_tables, key=lambda item: int(item.get("total_bytes") or 0), reverse=True)[:20]
    hot_tables = sorted(all_tables, key=lambda item: int(item.get("read_ops") or 0), reverse=True)[:20]
    bottlenecks = _bottlenecks(databases)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "live": ["BETMAN Data PostgreSQL"],
            "snapshot": external.get("sources", []),
            "snapshot_generated_at": external.get("generated_at"),
        },
        "databases": databases,
        "large_tables": large_tables,
        "hot_tables": hot_tables,
        "bottlenecks": bottlenecks,
        "architecture": {
            "nodes": _architecture_nodes(databases),
            "edges": [
                {"source": "BETMAN Core", "target": "BETMAN Data", "label": "auth, audit, core state"},
                {"source": "BETMAN Heatmap", "target": "BETMAN Data", "label": "race board, sensor/media state"},
                {"source": "LineForge", "target": "BETMAN Data", "label": "pedigree/breeding intelligence"},
                {"source": "RuView", "target": "BETMAN Heatmap", "label": "sensor/pose telemetry"},
                {"source": "TAB Affiliate", "target": "BETMAN Data", "label": "race cards, results, odds, pools"},
            ],
        },
    }


def _load_external_snapshot() -> dict[str, Any]:
    path = Path(settings.warehouse_snapshot_path)
    if not path.exists():
        return {"generated_at": None, "sources": [], "databases": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "generated_at": None,
            "sources": [str(path)],
            "databases": [],
            "load_error": str(exc),
        }


def _database(
    *,
    name: str,
    system: str,
    engine: str,
    host: str,
    location: str,
    role: str,
    total_size_bytes: int,
    tables: list[dict[str, Any]],
    source: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "system": system,
        "engine": engine,
        "host": host,
        "location": location,
        "role": role,
        "total_size_bytes": total_size_bytes,
        "tables": tables,
        "source": source,
    }


def _table(row: dict[str, Any], *, database: str, system: str) -> dict[str, Any]:
    read_ops = int(row.get("seq_scan") or 0) + int(row.get("idx_scan") or 0)
    disk_reads = int(row.get("heap_blocks_read") or 0) + int(row.get("index_blocks_read") or 0)
    cache_hits = int(row.get("heap_blocks_hit") or 0) + int(row.get("index_blocks_hit") or 0)
    return {
        "database": database,
        "system": system,
        "schema_name": row.get("schema_name") or "public",
        "table_name": row["table_name"],
        "approx_rows": int(row.get("approx_rows") or 0),
        "dead_rows": int(row.get("dead_rows") or 0),
        "total_bytes": int(row.get("total_bytes") or 0),
        "table_bytes": int(row.get("table_bytes") or 0),
        "index_bytes": int(row.get("index_bytes") or 0),
        "seq_scan": int(row.get("seq_scan") or 0),
        "idx_scan": int(row.get("idx_scan") or 0),
        "read_ops": read_ops,
        "disk_reads": disk_reads,
        "cache_hits": cache_hits,
        "writes": int(row.get("inserts") or 0) + int(row.get("updates") or 0) + int(row.get("deletes") or 0),
        "last_autovacuum": row.get("last_autovacuum"),
        "last_autoanalyze": row.get("last_autoanalyze"),
    }


def _normalise_external_table(table: dict[str, Any], db: dict[str, Any]) -> dict[str, Any]:
    normalised = {
        "database": db.get("name"),
        "system": db.get("system"),
        "schema_name": table.get("schema_name") or "main",
        "table_name": table.get("table_name"),
        "approx_rows": int(table.get("approx_rows") or 0),
        "dead_rows": int(table.get("dead_rows") or 0),
        "total_bytes": int(table.get("total_bytes") or 0),
        "table_bytes": int(table.get("table_bytes") or table.get("total_bytes") or 0),
        "index_bytes": int(table.get("index_bytes") or 0),
        "seq_scan": int(table.get("seq_scan") or 0),
        "idx_scan": int(table.get("idx_scan") or 0),
        "read_ops": int(table.get("read_ops") or 0),
        "disk_reads": int(table.get("disk_reads") or 0),
        "cache_hits": int(table.get("cache_hits") or 0),
        "writes": int(table.get("writes") or 0),
        "last_autovacuum": table.get("last_autovacuum"),
        "last_autoanalyze": table.get("last_autoanalyze"),
    }
    normalised["flags"] = _table_flags(normalised)
    return normalised


def _table_flags(table: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    rows = int(table.get("approx_rows") or 0)
    total_bytes = int(table.get("total_bytes") or 0)
    read_ops = int(table.get("read_ops") or 0)
    seq_scan = int(table.get("seq_scan") or 0)
    idx_scan = int(table.get("idx_scan") or 0)
    dead_rows = int(table.get("dead_rows") or 0)
    if total_bytes >= 10 * 1024 * 1024:
        flags.append("large")
    if read_ops >= 10_000:
        flags.append("hot")
    if rows and dead_rows / rows >= 0.1:
        flags.append("dead_rows")
    if seq_scan > 1_000 and idx_scan == 0:
        flags.append("seq_scan_only")
    if rows == 0 and total_bytes > 0:
        flags.append("empty_allocated")
    return flags


def _bottlenecks(databases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for db in databases:
        for table in db.get("tables", []):
            flags = table.get("flags") or _table_flags(table)
            if not flags:
                continue
            if "seq_scan_only" in flags:
                severity = "high"
                message = "High sequential scan count with no index scans"
            elif "dead_rows" in flags:
                severity = "medium"
                message = "Dead-row ratio suggests vacuum/analyze attention"
            elif "large" in flags and "hot" in flags:
                severity = "medium"
                message = "Large and frequently read table"
            elif "empty_allocated" in flags:
                severity = "low"
                message = "Allocated storage but no rows"
            else:
                severity = "info"
                message = "Worth watching"
            issues.append(
                {
                    "severity": severity,
                    "system": db.get("system"),
                    "database": db.get("name"),
                    "table_name": table.get("table_name"),
                    "message": message,
                    "flags": flags,
                    "read_ops": table.get("read_ops"),
                    "total_bytes": table.get("total_bytes"),
                    "approx_rows": table.get("approx_rows"),
                }
            )
    severity_rank = {"high": 0, "medium": 1, "low": 2, "info": 3}
    return sorted(issues, key=lambda item: (severity_rank.get(item["severity"], 9), -int(item.get("read_ops") or 0)))[:20]


def _architecture_nodes(databases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    nodes = [
        {"id": "TAB Affiliate", "kind": "source", "size_bytes": 0, "table_count": 0},
    ]
    for db in databases:
        nodes.append(
            {
                "id": db.get("system"),
                "database": db.get("name"),
                "engine": db.get("engine"),
                "host": db.get("host"),
                "kind": db.get("role"),
                "size_bytes": db.get("total_size_bytes"),
                "table_count": db.get("table_count"),
                "row_count": db.get("row_count"),
            }
        )
    return nodes
