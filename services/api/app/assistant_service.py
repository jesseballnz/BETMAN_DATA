from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from app.config import settings

ALLOWED_TABLES = {
    "audio_chunks",
    "audio_events",
    "barrier_outcomes",
    "barrier_statistics",
    "behaviour_observations",
    "bloodline_performance",
    "clips",
    "commentary_entities",
    "csi_readings",
    "dam_affinity_stats",
    "dam_family_relatives",
    "dam_produce_records",
    "dam_sectional_metrics",
    "dams",
    "discovered_patterns",
    "discovery_runs",
    "entity_relationships",
    "event_predictions",
    "excitement_scores",
    "feeds",
    "fixed_odds_ticks",
    "fixed_odds_tick_daily_summary",
    "gate_advantage_scores",
    "heatmap_scores",
    "heatmap_sessions",
    "horse_scores",
    "horses",
    "jockey_stats",
    "keyframes",
    "market_signals",
    "market_signal_daily_summary",
    "media_segments",
    "meetings",
    "ocr_observations",
    "odds_analytics",
    "odds_movements",
    "odds_snapshots",
    "odds_snapshot_daily_summary",
    "pattern_signals",
    "pedigree_affinities",
    "pedigrees",
    "provider_entity_mappings",
    "race_classes",
    "race_entries",
    "race_results",
    "race_sectionals",
    "race_style_profiles",
    "race_summaries",
    "race_timeline_events",
    "races",
    "runner_embeddings",
    "runners",
    "scene_classifications",
    "score_history",
    "signal_performance",
    "sire_photos",
    "sires",
    "smart_money_indicators",
    "smart_money_daily_summary",
    "soil_moisture_probes",
    "soil_moisture_readings",
    "speed_ratings",
    "stable_signals",
    "stream_sessions",
    "tab_event_payloads",
    "tote_pools",
    "tote_pool_daily_summary",
    "track_bias_index",
    "track_bias_records",
    "track_condition_readings",
    "track_heatmap_cells",
    "track_maps",
    "track_wind_records",
    "trainer_patterns",
    "trainer_stats",
    "transcript_segments",
    "weather_readings",
    "weather_stations",
}
BLOCKED_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "TRUNCATE",
    "COPY",
    "GRANT",
    "REVOKE",
    "MERGE",
    "CALL",
    "EXECUTE",
    "DO",
}
DEFAULT_LIMIT = 100
MAX_LIMIT = 200
TABLE_EXPRESSION_KEYWORDS = {
    "BASE_ENTRIES",
    "LATERAL",
    "LATEST_PRICES",
    "RESULTS",
    "TARGET",
}
TABLE_ALIASES = {
    "audio": "audio_events",
    "audio chunks": "audio_chunks",
    "barrier outcomes": "barrier_outcomes",
    "barrier stats": "barrier_statistics",
    "barrier statistics": "barrier_statistics",
    "behaviour": "behaviour_observations",
    "behavior": "behaviour_observations",
    "bloodline": "bloodline_performance",
    "bloodlines": "bloodline_performance",
    "clips": "clips",
    "commentary": "transcript_segments",
    "csi": "csi_readings",
    "discovered patterns": "discovered_patterns",
    "discovery runs": "discovery_runs",
    "events": "race_timeline_events",
    "excitement": "excitement_scores",
    "feeds": "feeds",
    "fixed odds": "fixed_odds_ticks",
    "fixed odds summary": "fixed_odds_tick_daily_summary",
    "fixed odds summaries": "fixed_odds_tick_daily_summary",
    "gates": "gate_advantage_scores",
    "gate advantage": "gate_advantage_scores",
    "heatmap": "heatmap_scores",
    "horse scores": "horse_scores",
    "jockey stats": "jockey_stats",
    "market signals": "market_signals",
    "market signal summary": "market_signal_daily_summary",
    "market signal summaries": "market_signal_daily_summary",
    "meetings": "meetings",
    "ocr": "ocr_observations",
    "odds analytics": "odds_analytics",
    "odds movements": "odds_movements",
    "odds snapshots": "odds_snapshots",
    "odds summary": "odds_snapshot_daily_summary",
    "odds summaries": "odds_snapshot_daily_summary",
    "pattern signals": "pattern_signals",
    "pedigree": "pedigrees",
    "pedigrees": "pedigrees",
    "race classes": "race_classes",
    "race entries": "race_entries",
    "race results": "race_results",
    "race sectionals": "race_sectionals",
    "race summaries": "race_summaries",
    "race timeline": "race_timeline_events",
    "races": "races",
    "runners": "runners",
    "scene": "scene_classifications",
    "scores": "horse_scores",
    "signal performance": "signal_performance",
    "smart money": "smart_money_indicators",
    "smart money summary": "smart_money_daily_summary",
    "smart money summaries": "smart_money_daily_summary",
    "soil moisture": "soil_moisture_readings",
    "speed ratings": "speed_ratings",
    "stable signals": "stable_signals",
    "tab payloads": "tab_event_payloads",
    "tote pools": "tote_pools",
    "tote pool summary": "tote_pool_daily_summary",
    "tote pool summaries": "tote_pool_daily_summary",
    "track bias": "track_bias_index",
    "track conditions": "track_condition_readings",
    "track heatmap": "track_heatmap_cells",
    "track maps": "track_maps",
    "track wind": "track_wind_records",
    "trainer patterns": "trainer_patterns",
    "trainer stats": "trainer_stats",
    "transcripts": "transcript_segments",
    "weather": "weather_readings",
    "weather stations": "weather_stations",
}
TEXT_SEARCH_TABLES = {
    "discovered_patterns": ("description", "pattern_type"),
    "ocr_observations": ("detected_text", "normalized_text", "observation_type"),
    "pedigrees": ("sire", "dam", "damsire", "family_line", "provider_name"),
    "race_summaries": ("summary_text", "winner_name", "margin_description"),
    "race_timeline_events": ("event_type", "source_type"),
    "races": ("name", "race_class_code", "race_class_group", "conditions_description"),
    "runners": ("name", "type", "country_of_origin"),
    "transcript_segments": ("text", "language"),
}
TABLE_SEARCH_COLUMNS = {
    "audio_chunks": ("id", "segment_id", "started_at", "ended_at", "duration_ms", "storage_uri", "codec", "sample_rate", "created_at"),
    "audio_events": ("id", "segment_id", "audio_chunk_id", "started_at", "ended_at", "event_type", "confidence", "model_version", "created_at"),
    "barrier_outcomes": ("race_id", "runner_id", "barrier_number", "final_position", "won", "placed", "track_name", "surface", "distance_m", "condition_category", "race_date"),
    "barrier_statistics": ("track_name", "surface", "distance_band", "condition_category", "barrier_number", "total_runners", "wins", "win_rate", "place_rate", "avg_win_price"),
    "behaviour_observations": ("race_entry_id", "runner_id", "stage", "attribute", "value_numeric", "value_text", "captured_at", "observer"),
    "bloodline_performance": ("sire", "track_name", "surface", "condition_category", "distance_band", "runners", "wins", "win_rate", "place_rate", "roi"),
    "clips": ("feed_id", "race_id", "clip_type", "started_at", "ended_at", "duration_ms", "storage_uri", "codec", "resolution"),
    "commentary_entities": ("entity_type", "raw_text", "normalized_value", "runner_id", "confidence", "created_at"),
    "csi_readings": ("session_id", "captured_at", "heart_rate", "heart_rate_variability", "breathing_rate", "motion_score", "signal_quality"),
    "discovered_patterns": ("id", "pattern_type", "description", "roi", "confidence", "sample_size", "first_detected", "active"),
    "discovery_runs": ("id", "job_type", "started_at", "finished_at", "status", "patterns_found", "signals_emitted", "error_message"),
    "entity_relationships": ("from_type", "from_id", "relationship", "to_type", "to_id", "weight", "valid_from", "valid_to"),
    "event_predictions": ("race_id", "feed_id", "event_type", "predicted_at", "confidence", "source_type", "created_at"),
    "excitement_scores": ("audio_event_id", "race_id", "race_offset_ms", "score", "peak", "model_version", "created_at"),
    "feeds": ("id", "name", "active", "created_at"),
    "fixed_odds_ticks": ("race_id", "race_entry_id", "price", "source", "captured_at", "time_to_jump_s"),
    "fixed_odds_tick_daily_summary": ("summary_date", "race_id", "race_entry_id", "source", "tick_count", "price_sum", "price_count", "min_price", "max_price", "last_price", "first_captured_at", "last_captured_at"),
    "gate_advantage_scores": ("track_name", "surface", "distance_band", "condition_category", "barrier_number", "gas_score", "sample_size", "confidence"),
    "heatmap_scores": ("session_id", "sweating_score", "symmetry_score", "recovery_score", "coat_uniformity", "created_at"),
    "heatmap_sessions": ("race_id", "race_entry_id", "runner_id", "captured_at", "operator", "camera_type", "created_at"),
    "horse_scores": ("race_id", "race_entry_id", "runner_id", "bc_score", "gas_score", "mis_score", "sis_score", "hfs_score", "alpha_score", "market_price", "betman_probability", "calculated_at"),
    "jockey_stats": ("jockey", "track_name", "gate_zone", "going", "race_style", "runners", "wins", "win_rate", "roi", "updated_at"),
    "keyframes": ("segment_id", "frame_timestamp", "offset_ms", "storage_uri", "width", "height", "created_at"),
    "market_signals": ("race_id", "race_entry_id", "signal_type", "magnitude", "detected_at", "time_to_jump_s", "created_at"),
    "market_signal_daily_summary": ("summary_date", "race_id", "race_entry_id", "signal_type", "signal_count", "magnitude_sum", "max_magnitude", "first_detected_at", "last_detected_at"),
    "media_segments": ("feed_id", "stream_session_id", "sequence_number", "segment_started_at", "segment_ended_at", "duration_ms", "storage_uri", "processing_status"),
    "meetings": ("id", "track_name", "meeting_date", "surface", "jurisdiction", "status", "created_at"),
    "ocr_observations": ("segment_id", "keyframe_id", "frame_timestamp", "detected_text", "normalized_text", "observation_type", "confidence", "created_at"),
    "odds_analytics": ("race_id", "race_entry_id", "opening_price", "closing_price", "min_price", "max_price", "total_movement_pct", "steam_detected", "blowout_detected", "updated_at"),
    "odds_movements": ("race_id", "race_entry_id", "detected_at", "time_to_jump_s", "from_price", "to_price", "movement_pct", "movement_type", "source"),
    "odds_snapshots": ("race_id", "race_entry_id", "captured_at", "source", "win_price", "place_price", "market_status"),
    "odds_snapshot_daily_summary": ("summary_date", "race_id", "race_entry_id", "source", "market_status", "snapshot_count", "win_price_sum", "win_price_count", "place_price_sum", "place_price_count", "min_win_price", "max_win_price", "last_win_price", "min_place_price", "max_place_price", "last_place_price", "first_captured_at", "last_captured_at"),
    "pattern_signals": ("pattern_id", "race_id", "race_entry_id", "signal_strength", "generated_at", "expires_at"),
    "pedigree_affinities": ("sire", "affinity_type", "context_track", "context_distance_band", "context_condition", "affinity_score", "win_rate", "sample_size"),
    "pedigrees": ("runner_id", "sire", "dam", "damsire", "grandsire_pat", "grandsire_mat", "family_line", "colour", "horse_uuid", "provider_name"),
    "race_classes": ("code", "group", "rank", "description"),
    "race_entries": ("race_id", "runner_id", "barrier_number", "saddle_cloth", "jockey_or_driver", "trainer", "weight_kg", "scratched", "final_position", "age", "sex"),
    "race_results": ("race_id", "race_entry_id", "finish_position", "margin_lengths", "in_running", "finish_time_s", "split_600m_s", "split_400m_s", "split_200m_s"),
    "race_sectionals": ("race_id", "race_entry_id", "checkpoint_m", "time_s", "position_at", "created_at"),
    "race_style_profiles": ("runner_id", "track_name", "distance_band", "dominant_style", "sample_size", "updated_at"),
    "race_summaries": ("race_id", "summary_text", "winner_name", "margin_description", "model_version", "generated_at"),
    "race_timeline_events": ("race_id", "event_type", "event_time", "source_type", "confidence", "created_at"),
    "races": ("id", "meeting_id", "race_number", "name", "distance_m", "scheduled_start_time", "actual_start_time", "race_class_code", "race_class_group", "prize_money", "surface", "status", "stake", "track_direction", "rail_position", "conditions_description"),
    "runners": ("id", "external_runner_id", "name", "type", "country_of_origin", "horse_uuid", "created_at"),
    "scene_classifications": ("keyframe_id", "scene_type", "confidence", "model_version", "created_at"),
    "score_history": ("race_id", "race_entry_id", "alpha_score", "market_price", "snapshot_at", "created_at"),
    "signal_performance": ("signal_type", "period_days", "bets", "winners", "stake_total", "returns_total", "roi", "strike_rate", "avg_win_price", "edge", "updated_at"),
    "smart_money_indicators": ("race_id", "race_entry_id", "indicator_type", "confidence", "detected_at", "created_at"),
    "smart_money_daily_summary": ("summary_date", "race_id", "race_entry_id", "indicator_type", "indicator_count", "confidence_sum", "max_confidence", "first_detected_at", "last_detected_at"),
    "soil_moisture_probes": ("station_id", "probe_label", "position_description", "depth_mm", "zone", "active", "created_at"),
    "soil_moisture_readings": ("probe_id", "recorded_at", "moisture_pct", "soil_temperature_c", "created_at"),
    "speed_ratings": ("race_id", "race_entry_id", "rating", "rating_method", "time_adjusted", "class_adjusted", "track_variant", "created_at"),
    "stable_signals": ("trainer", "race_id", "race_entry_id", "signal_type", "confidence", "market_move_pct", "detected_at"),
    "stream_sessions": ("feed_id", "started_at", "ended_at", "status", "selected_rendition_url", "created_at"),
    "tab_event_payloads": ("source", "external_race_id", "country", "race_date", "fetched_at"),
    "tote_pools": ("race_id", "pool_type", "pool_size", "captured_at", "dividend", "created_at"),
    "tote_pool_daily_summary": ("summary_date", "race_id", "pool_type", "sample_count", "pool_size_sum", "pool_size_count", "max_pool_size", "last_pool_size", "dividend_sum", "dividend_count", "first_captured_at", "last_captured_at"),
    "track_bias_index": ("track_name", "race_date", "tbi_rail", "tbi_outside", "tbi_pace", "tbi_composite", "races_in_sample", "updated_at"),
    "track_bias_records": ("track_name", "race_date", "race_id", "bias_type", "magnitude", "confidence", "source", "created_at"),
    "track_condition_readings": ("meeting_id", "race_id", "condition_code", "condition_category", "penetrometer_value", "recorded_at", "source", "avg_soil_moisture_pct", "notes"),
    "track_heatmap_cells": ("track_name", "surface", "condition_category", "distance_band", "zone", "distance_from_finish_band", "win_count", "place_count", "runner_count", "win_rate", "place_rate", "intensity"),
    "track_maps": ("track_name", "surface", "circumference_m", "straight_m", "created_at"),
    "track_wind_records": ("track_name", "recorded_at", "wind_speed_kmh", "wind_direction_deg", "straight_wind_effect", "straight_wind_kmh"),
    "trainer_patterns": ("trainer", "pattern_type", "runners", "wins", "win_rate", "roi", "updated_at"),
    "trainer_stats": ("trainer", "track_name", "surface", "condition_category", "distance_band", "race_class_group", "run_number", "runners", "wins", "places", "win_rate", "roi", "avg_win_price"),
    "transcript_segments": ("race_id", "race_offset_ms", "started_at", "ended_at", "text", "language", "confidence", "model_version", "created_at"),
    "weather_readings": ("station_id", "recorded_at", "temperature_c", "humidity_pct", "wind_speed_kmh", "wind_gust_kmh", "wind_direction_deg", "rainfall_mm", "rainfall_24h_mm", "barometric_pressure_hpa"),
    "weather_stations": ("track_name", "station_id", "label", "latitude", "longitude", "elevation_m", "active", "created_at"),
}


@dataclass
class AssistantPlan:
    question: str
    sql: str
    params: list[Any] = field(default_factory=list)
    summary: str = ""
    confidence: float = 0.5
    chart: dict[str, Any] | None = None
    provider: str = "rule_based"


class AssistantProvider(Protocol):
    async def translate(self, question: str) -> AssistantPlan | None: ...


class OpenAIProvider:
    async def translate(self, question: str) -> AssistantPlan | None:
        if not settings.openai_api_key:
            return None

        table_guide = "; ".join(
            f"{table}({', '.join(columns[:8])})"
            for table, columns in sorted(TABLE_SEARCH_COLUMNS.items())
            if table in ALLOWED_TABLES
        )
        prompt = (
            "Return strict JSON with keys sql, summary, confidence, chart. "
            "Generate exactly one read-only SELECT query against these tables only: "
            f"{', '.join(sorted(ALLOWED_TABLES))}. Always include LIMIT <= {MAX_LIMIT}. "
            "Prefer public racing intelligence tables over platform/admin tables. "
            f"Useful columns: {table_guide}"
        )
        payload = {
            "model": settings.betman_llm_model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": question},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }
        headers = {
            "Authorization": "Bearer " + settings.openai_api_key,
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            sql = enforce_limit(str(parsed.get("sql", "")))
            validate_safe_select(sql)
            return AssistantPlan(
                question=question,
                sql=sql,
                params=[],
                summary=str(parsed.get("summary") or "AI-generated query executed."),
                confidence=float(parsed.get("confidence") or 0.55),
                chart=parsed.get("chart") if isinstance(parsed.get("chart"), dict) else None,
                provider="openai",
            )
        except Exception:
            return None


class RuleBasedProvider:
    async def translate(self, question: str) -> AssistantPlan | None:
        return build_rule_based_plan(question)


async def resolve_plan(question: str) -> AssistantPlan:
    for provider in (OpenAIProvider(), RuleBasedProvider()):
        plan = await provider.translate(question)
        if plan is not None:
            plan.sql = enforce_limit(plan.sql)
            validate_safe_select(plan.sql)
            return plan
    raise ValueError("Unable to translate query")


def validate_safe_select(sql: str) -> None:
    normalized = " ".join(sql.strip().split())
    upper_sql = normalized.upper()

    if not normalized:
        raise ValueError("SQL is empty")
    if ";" in normalized:
        raise ValueError("Multiple statements are not allowed")
    if not (upper_sql.startswith("SELECT ") or upper_sql.startswith("WITH ")):
        raise ValueError("Only SELECT queries are allowed")
    for keyword in BLOCKED_KEYWORDS:
        if re.search(rf"\b{keyword}\b", upper_sql):
            raise ValueError(f"Blocked keyword detected: {keyword}")

    cte_names = _extract_cte_names(upper_sql)
    tables = [
        table
        for table in (
            match.split(".")[-1].lower()
            for match in re.findall(r"\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_\.]*)", upper_sql)
        )
        if table.upper() not in TABLE_EXPRESSION_KEYWORDS and table not in cte_names
    ]
    disallowed = [table for table in tables if table not in ALLOWED_TABLES]
    if disallowed:
        raise ValueError(f"Table not allowed: {', '.join(sorted(set(disallowed)))}")

    limit_match = re.search(r"\bLIMIT\s+(\d+)\b", upper_sql)
    if not limit_match:
        raise ValueError("A LIMIT clause is required")
    if int(limit_match.group(1)) > MAX_LIMIT:
        raise ValueError("LIMIT exceeds maximum allowed rows")


def enforce_limit(sql: str, default_limit: int = DEFAULT_LIMIT) -> str:
    normalized = " ".join(sql.strip().split())
    if not normalized:
        return normalized
    if re.search(r"\bLIMIT\s+\d+\b", normalized, flags=re.IGNORECASE):
        return normalized
    return f"{normalized} LIMIT {default_limit}"


def build_rule_based_plan(question: str) -> AssistantPlan | None:
    lowered = question.lower().strip()
    days = _extract_days(lowered)
    track = _extract_track(question)
    distance = _extract_distance(lowered)
    condition = _extract_condition(lowered)
    search_term = _extract_search_term(question)
    table = _extract_table_reference(lowered)

    if _is_market_mover_question(lowered):
        return _build_market_mover_plan(question, days, today_only=_mentions_today(lowered))

    if table and table.endswith("_daily_summary"):
        return _build_table_scan_plan(question, table, search_term)

    if _is_odds_question(lowered):
        runner_name = _extract_runner_context(question) or search_term
        if runner_name:
            scope = "meeting" if "meeting" in lowered or "card" in lowered else "runner"
            if any(term in lowered for term in ("shortest", "lowest", "favourite", "favorite")) and scope == "meeting":
                sql = (
                    "WITH target AS ("
                    "  SELECT m.id AS meeting_id, m.track_name, m.meeting_date, "
                    "         r.id AS target_race_id, r.race_number AS target_race_number, "
                    "         run.name AS target_runner "
                    "  FROM runners run "
                    "  JOIN race_entries re ON re.runner_id = run.id "
                    "  JOIN races r ON r.id = re.race_id "
                    "  JOIN meetings m ON m.id = r.meeting_id "
                    "  WHERE run.name ILIKE '%' || $1 || '%' "
                    "  ORDER BY m.meeting_date DESC, r.scheduled_start_time DESC NULLS LAST, r.race_number DESC "
                    "  LIMIT 1"
                    "), latest_prices AS ("
                    "  SELECT DISTINCT ON (os.race_entry_id) os.race_entry_id, os.win_price, "
                    "         os.place_price, os.source, os.captured_at "
                    "  FROM odds_snapshots os "
                    "  JOIN race_entries re ON re.id = os.race_entry_id "
                    "  JOIN races r ON r.id = re.race_id "
                    "  JOIN target t ON t.meeting_id = r.meeting_id "
                    "  WHERE os.win_price IS NOT NULL "
                    "  ORDER BY os.race_entry_id, os.captured_at DESC"
                    ") "
                    "SELECT t.track_name, t.meeting_date, t.target_runner, "
                    "       r.race_number, run.name AS runner_name, lp.win_price, lp.place_price, "
                    "       lp.source, lp.captured_at, "
                    "       (run.name ILIKE '%' || $1 || '%') AS is_target_runner "
                    "FROM target t "
                    "JOIN races r ON r.meeting_id = t.meeting_id "
                    "JOIN race_entries re ON re.race_id = r.id "
                    "JOIN runners run ON run.id = re.runner_id "
                    "JOIN latest_prices lp ON lp.race_entry_id = re.id "
                    "ORDER BY lp.win_price ASC, r.race_number, run.name LIMIT 50"
                )
                summary = "Shortest current win prices across the runner's latest meeting context."
                confidence = 0.86
            else:
                sql = (
                    "SELECT m.track_name, m.meeting_date, r.race_number, run.name AS runner_name, "
                    "       os.win_price, os.place_price, os.win_sp, os.place_sp, os.market_status, "
                    "       os.source, os.captured_at "
                    "FROM runners run "
                    "JOIN race_entries re ON re.runner_id = run.id "
                    "JOIN races r ON r.id = re.race_id "
                    "JOIN meetings m ON m.id = r.meeting_id "
                    "JOIN odds_snapshots os ON os.race_entry_id = re.id "
                    "WHERE run.name ILIKE '%' || $1 || '%' "
                    "ORDER BY m.meeting_date DESC, r.scheduled_start_time DESC NULLS LAST, "
                    "os.captured_at DESC LIMIT 50"
                )
                summary = "Latest odds history for the named runner."
                confidence = 0.82
            return AssistantPlan(
                question=question,
                sql=sql,
                params=[runner_name],
                summary=summary,
                confidence=confidence,
                chart={"type": "table"},
            )

    if any(term in lowered for term in ("find horse", "find runner", "search horse", "search runner", "runner named", "horse named")):
        term = search_term or _strip_intent_words(question, ("find", "search", "horse", "runner", "named", "called"))
        sql = (
            "SELECT run.id, run.name, run.type, run.country_of_origin, run.horse_uuid, "
            "p.sire, p.dam, p.damsire, p.colour "
            "FROM runners run "
            "LEFT JOIN pedigrees p ON p.runner_id = run.id "
            "WHERE $1 = '' OR run.name ILIKE '%' || $1 || '%' "
            "ORDER BY run.name LIMIT 50"
        )
        return AssistantPlan(
            question=question,
            sql=sql,
            params=[term],
            summary="Runner and pedigree lookup across the warehouse.",
            confidence=0.74,
            chart={"type": "table"},
        )

    if any(term in lowered for term in ("pedigree", "progeny", "sire", "dam", "damsire", "bloodline", "bloodlines")):
        term = _extract_pedigree_term(question) or search_term or _strip_intent_words(
            question,
            ("show", "find", "search", "pedigree", "progeny", "sire", "dam", "damsire", "bloodline", "bloodlines", "for"),
        )
        if any(term in lowered for term in ("top sire", "best sire", "wet sire", "bloodline performance", "bloodlines")):
            sql = (
                "SELECT sire, track_name, surface, condition_category, distance_band, "
                "runners, wins, win_rate, place_rate, avg_win_price, roi "
                "FROM bloodline_performance "
                "WHERE ($1 = '' OR sire ILIKE '%' || $1 || '%' OR COALESCE(condition_category, '') ILIKE '%' || $1 || '%') "
                "ORDER BY roi DESC NULLS LAST, wins DESC, runners DESC LIMIT 50"
            )
            summary = "Bloodline performance ranked by ROI, wins, and sample size."
        else:
            sql = (
                "SELECT run.name AS runner_name, p.sire, p.dam, p.damsire, "
                "p.grandsire_pat, p.grandsire_mat, p.family_line, p.colour, p.provider_name "
                "FROM pedigrees p JOIN runners run ON run.id = p.runner_id "
                "WHERE $1 = '' OR run.name ILIKE '%' || $1 || '%' OR p.sire ILIKE '%' || $1 || '%' "
                "OR p.dam ILIKE '%' || $1 || '%' OR p.damsire ILIKE '%' || $1 || '%' "
                "ORDER BY run.name LIMIT 50"
            )
            summary = "Pedigree lookup across runner, sire, dam, and damsire fields."
        return AssistantPlan(
            question=question,
            sql=sql,
            params=[term],
            summary=summary,
            confidence=0.78,
            chart={"type": "table"},
        )

    if any(term in lowered for term in ("pattern signal", "pattern signals", "signals from patterns")):
        sql = (
            "SELECT ps.pattern_id, dp.description AS pattern_description, m.track_name, r.race_number, "
            "run.name AS runner_name, ps.signal_strength, ps.generated_at, ps.expires_at "
            "FROM pattern_signals ps "
            "JOIN discovered_patterns dp ON dp.id = ps.pattern_id "
            "JOIN races r ON r.id = ps.race_id "
            "JOIN meetings m ON m.id = r.meeting_id "
            "LEFT JOIN race_entries re ON re.id = ps.race_entry_id "
            "LEFT JOIN runners run ON run.id = re.runner_id "
            "WHERE m.meeting_date >= CURRENT_DATE - $1::int "
            "ORDER BY ps.signal_strength DESC, ps.generated_at DESC LIMIT 50"
        )
        return AssistantPlan(
            question=question,
            sql=sql,
            params=[days],
            summary="Recent pattern-generated signals ranked by strength.",
            confidence=0.78,
            chart={"type": "bar", "x": "runner_name", "y": "signal_strength"},
        )

    if any(term in lowered for term in ("pattern", "patterns", "discovery", "discoveries")):
        sql = (
            "SELECT dp.id, dp.pattern_type, dp.description, dp.roi, dp.confidence, "
            "dp.sample_size, dp.first_detected, dp.valid_until, dp.active "
            "FROM discovered_patterns dp "
            "WHERE ($1 = '' OR dp.description ILIKE '%' || $1 || '%' OR dp.pattern_type ILIKE '%' || $1 || '%') "
            "ORDER BY dp.active DESC, dp.roi DESC NULLS LAST, dp.confidence DESC, dp.first_detected DESC LIMIT 50"
        )
        return AssistantPlan(
            question=question,
            sql=sql,
            params=[search_term],
            summary="Discovered racing patterns ranked by ROI and confidence.",
            confidence=0.8,
            chart={"type": "table"},
        )

    if _is_value_or_alpha_question(lowered):
        return _build_value_runner_plan(question, days, today_only=_mentions_today(lowered))

    if _is_race_card_question(lowered):
        return _build_race_card_plan(question, days, today_only=_mentions_today(lowered))

    if "trainer" in lowered and any(term in lowered for term in ("over-performing", "overperforming", "over performing", "market")):
        sql = (
            "SELECT re.trainer, COUNT(*) AS runners, "
            "       COUNT(*) FILTER (WHERE re.final_position = 1) AS wins, "
            "       ROUND(SUM(1.0 / hs.market_price)::numeric, 2) AS expected_wins, "
            "       ROUND((COUNT(*) FILTER (WHERE re.final_position = 1)::numeric - SUM(1.0 / hs.market_price)::numeric), 2) AS wins_above_market, "
            "       ROUND(AVG(hs.market_price)::numeric, 2) AS avg_market_price "
            "FROM race_entries re "
            "JOIN races r ON r.id = re.race_id "
            "JOIN meetings m ON m.id = r.meeting_id "
            "JOIN horse_scores hs ON hs.race_entry_id = re.id "
            "WHERE re.trainer IS NOT NULL AND re.final_position IS NOT NULL "
            "AND hs.market_price IS NOT NULL AND hs.market_price > 1 "
            "AND m.meeting_date >= CURRENT_DATE - $1::int "
            "GROUP BY re.trainer HAVING COUNT(*) >= 3 "
            "ORDER BY wins_above_market DESC, wins DESC, runners DESC LIMIT 25"
        )
        return AssistantPlan(
            question=question,
            sql=sql,
            params=[7 if "week" in lowered else days],
            summary="Trainers over-performing market expectation based on latest available win prices.",
            confidence=0.84,
            chart={"type": "bar", "x": "trainer", "y": "wins_above_market"},
        )

    if "smart money" in lowered:
        sql = (
            "SELECT m.track_name, r.race_number, run.name AS runner_name, smi.indicator_type, "
            "smi.confidence, smi.detected_at "
            "FROM smart_money_indicators smi "
            "JOIN races r ON r.id = smi.race_id "
            "JOIN meetings m ON m.id = r.meeting_id "
            "LEFT JOIN race_entries re ON re.id = smi.race_entry_id "
            "LEFT JOIN runners run ON run.id = re.runner_id "
            "WHERE m.meeting_date >= CURRENT_DATE - $1::int "
            "ORDER BY smi.confidence DESC, smi.detected_at DESC LIMIT 50"
        )
        return AssistantPlan(
            question=question,
            sql=sql,
            params=[days],
            summary="Smart-money indicators ranked by confidence.",
            confidence=0.82,
            chart={"type": "bar", "x": "runner_name", "y": "confidence"},
        )

    if "stable signal" in lowered or "stable signals" in lowered:
        sql = (
            "SELECT ss.trainer, m.track_name, r.race_number, run.name AS runner_name, "
            "ss.signal_type, ss.confidence, ss.market_move_pct, ss.detected_at "
            "FROM stable_signals ss "
            "JOIN races r ON r.id = ss.race_id "
            "JOIN meetings m ON m.id = r.meeting_id "
            "LEFT JOIN race_entries re ON re.id = ss.race_entry_id "
            "LEFT JOIN runners run ON run.id = re.runner_id "
            "WHERE m.meeting_date >= CURRENT_DATE - $1::int "
            "ORDER BY ss.confidence DESC, ABS(ss.market_move_pct) DESC NULLS LAST LIMIT 50"
        )
        return AssistantPlan(
            question=question,
            sql=sql,
            params=[days],
            summary="Stable signals ranked by confidence and market movement.",
            confidence=0.78,
            chart={"type": "bar", "x": "trainer", "y": "confidence"},
        )

    if _has_weather_intent(lowered):
        sql = (
            "SELECT ws.track_name, wr.recorded_at, wr.temperature_c, wr.humidity_pct, "
            "wr.wind_speed_kmh, wr.wind_gust_kmh, wr.wind_direction_deg, wr.rainfall_mm, "
            "wr.rainfall_24h_mm, wr.barometric_pressure_hpa "
            "FROM weather_readings wr "
            "JOIN weather_stations ws ON ws.id = wr.station_id "
            "WHERE ($1 = '' OR ws.track_name ILIKE '%' || $1 || '%') "
            "ORDER BY wr.recorded_at DESC LIMIT 50"
        )
        return AssistantPlan(
            question=question,
            sql=sql,
            params=[track or search_term],
            summary="Latest weather readings by track.",
            confidence=0.78,
            chart={"type": "table"},
        )

    if any(term in lowered for term in ("condition", "going", "penetrometer", "soil moisture", "moisture")):
        sql = (
            "SELECT m.track_name, r.race_number, tcr.condition_code, tcr.condition_category, "
            "tcr.penetrometer_value, tcr.avg_soil_moisture_pct, tcr.recorded_at, tcr.source, tcr.notes "
            "FROM track_condition_readings tcr "
            "LEFT JOIN meetings m ON m.id = tcr.meeting_id "
            "LEFT JOIN races r ON r.id = tcr.race_id "
            "WHERE ($1 = '' OR m.track_name ILIKE '%' || $1 || '%') "
            "ORDER BY tcr.recorded_at DESC LIMIT 50"
        )
        return AssistantPlan(
            question=question,
            sql=sql,
            params=[track or search_term],
            summary="Track condition readings and going changes.",
            confidence=0.76,
            chart={"type": "table"},
        )

    if "transcript" in lowered or "commentary" in lowered:
        sql = (
            "SELECT m.track_name, r.race_number, ts.race_offset_ms, ts.started_at, ts.ended_at, "
            "ts.text, ts.confidence, ts.model_version "
            "FROM transcript_segments ts "
            "LEFT JOIN races r ON r.id = ts.race_id "
            "LEFT JOIN meetings m ON m.id = r.meeting_id "
            "WHERE $1 = '' OR ts.text ILIKE '%' || $1 || '%' "
            "ORDER BY ts.created_at DESC LIMIT 50"
        )
        return AssistantPlan(
            question=question,
            sql=sql,
            params=[search_term],
            summary="Commentary transcript search.",
            confidence=0.74,
            chart={"type": "table"},
        )

    if "ocr" in lowered or "screen text" in lowered or "vision text" in lowered:
        sql = (
            "SELECT oo.frame_timestamp, oo.detected_text, oo.normalized_text, oo.observation_type, "
            "oo.confidence, oo.created_at "
            "FROM ocr_observations oo "
            "WHERE $1 = '' OR oo.detected_text ILIKE '%' || $1 || '%' OR oo.normalized_text ILIKE '%' || $1 || '%' "
            "ORDER BY oo.created_at DESC LIMIT 50"
        )
        return AssistantPlan(
            question=question,
            sql=sql,
            params=[search_term],
            summary="OCR observation search across extracted frame text.",
            confidence=0.72,
            chart={"type": "table"},
        )

    if "summary" in lowered or "summaries" in lowered or "story" in lowered:
        sql = (
            "SELECT m.track_name, r.race_number, rs.winner_name, rs.margin_description, "
            "rs.summary_text, rs.generated_at, rs.model_version "
            "FROM race_summaries rs "
            "JOIN races r ON r.id = rs.race_id "
            "JOIN meetings m ON m.id = r.meeting_id "
            "WHERE $1 = '' OR rs.summary_text ILIKE '%' || $1 || '%' OR rs.winner_name ILIKE '%' || $1 || '%' "
            "ORDER BY rs.generated_at DESC LIMIT 50"
        )
        return AssistantPlan(
            question=question,
            sql=sql,
            params=[search_term],
            summary="Race summary and narrative search.",
            confidence=0.72,
            chart={"type": "table"},
        )

    if any(term in lowered for term in ("search", "find", "mentions", "mention")) and search_term:
        return _build_cross_text_search_plan(question, search_term)

    if table:
        return _build_table_scan_plan(question, table, search_term)

    if "steamer" in lowered or "drifter" in lowered:
        signal_types = (
            ["late_money", "smart_money", "steamer", "steam", "firm", "late_firm"]
            if "steamer" in lowered
            else ["drifter", "drift", "blowout"]
        )
        date_clause = "m.meeting_date = CURRENT_DATE" if _mentions_today(lowered) else "m.meeting_date >= CURRENT_DATE - $2::int"
        sql = (
            "SELECT m.track_name, r.race_number, run.name AS runner_name, "
            "ms.signal_type, ms.magnitude, ms.detected_at, ms.time_to_jump_s "
            "FROM market_signals ms "
            "JOIN races r ON r.id = ms.race_id "
            "JOIN meetings m ON m.id = r.meeting_id "
            "LEFT JOIN race_entries re ON re.id = ms.race_entry_id "
            "JOIN runners run ON run.id = re.runner_id "
            "WHERE ms.signal_type = ANY($1::text[]) "
            f"AND {date_clause} "
            "ORDER BY ms.magnitude DESC, ms.detected_at DESC LIMIT 50"
        )
        return AssistantPlan(
            question=question,
            sql=sql,
            params=[signal_types] if _mentions_today(lowered) else [signal_types, days],
            summary="Recent market pressure signals ranked by magnitude.",
            confidence=0.82,
            chart={"type": "bar", "x": "runner_name", "y": "magnitude"},
        )

    if "jockey" in lowered or "trainer" in lowered:
        person_col = "re.jockey_or_driver" if "jockey" in lowered else "re.trainer"
        label = "jockey" if "jockey" in lowered else "trainer"
        conditions = [
            "re.scratched = false",
            "re.final_position IS NOT NULL",
            "m.meeting_date >= CURRENT_DATE - $1::int",
        ]
        params: list[Any] = [days]
        param_index = 2
        if track:
            conditions.append(f"LOWER(m.track_name) = LOWER(${param_index})")
            params.append(track)
            param_index += 1
        if condition:
            conditions.append(f"LOWER(COALESCE(tc.condition_category, '')) = LOWER(${param_index})")
            params.append(condition)
            param_index += 1
        if distance is not None:
            conditions.append(f"r.distance_m = ${param_index}")
            params.append(distance)
            param_index += 1

        sql = (
            f"SELECT {person_col} AS person, COUNT(*) AS runners, "
            "COUNT(*) FILTER (WHERE re.final_position = 1) AS wins, "
            "COUNT(*) FILTER (WHERE re.final_position <= 3) AS places, "
            "ROUND(COUNT(*) FILTER (WHERE re.final_position = 1)::numeric "
            "* 100.0 / NULLIF(COUNT(*), 0), 2) AS win_rate, "
            "ROUND(COUNT(*) FILTER (WHERE re.final_position <= 3)::numeric "
            "* 100.0 / NULLIF(COUNT(*), 0), 2) AS place_rate "
            "FROM race_entries re "
            "JOIN races r ON r.id = re.race_id "
            "JOIN meetings m ON m.id = r.meeting_id "
            "LEFT JOIN LATERAL ("
            "  SELECT tcr.condition_category FROM track_condition_readings tcr "
            "  WHERE tcr.race_id = r.id OR (tcr.race_id IS NULL AND tcr.meeting_id = m.id) "
            "  ORDER BY CASE WHEN tcr.race_id = r.id THEN 0 ELSE 1 END, "
            "tcr.recorded_at DESC LIMIT 1"
            ") tc ON TRUE "
            f"WHERE {' AND '.join(conditions)} AND {person_col} IS NOT NULL "
            f"GROUP BY {person_col} ORDER BY win_rate DESC, runners DESC LIMIT 25"
        )
        return AssistantPlan(
            question=question,
            sql=sql,
            params=params,
            summary=f"Top {label}s matching the requested context.",
            confidence=0.78,
            chart={"type": "bar", "x": "person", "y": "win_rate"},
        )

    if "gate" in lowered or "barrier" in lowered:
        params: list[Any] = [track or "", days]
        filters = [
            "($1 = '' OR LOWER(track_name) = LOWER($1))",
            "race_date >= CURRENT_DATE - $2::int",
        ]
        if condition:
            params.append(condition)
            filters.append(f"LOWER(COALESCE(condition_category, '')) = LOWER(${len(params)})")
        if distance is not None:
            params.append(distance)
            filters.append(f"distance_m = ${len(params)}")
        sql = (
            "SELECT barrier_number, COUNT(*) AS runners, COUNT(*) FILTER (WHERE won) AS wins, "
            "ROUND(COUNT(*) FILTER (WHERE won)::numeric * 100.0 / NULLIF(COUNT(*), 0), 2) "
            "AS win_rate, "
            "ROUND(COUNT(*) FILTER (WHERE placed)::numeric * 100.0 / NULLIF(COUNT(*), 0), 2) "
            "AS place_rate "
            f"FROM barrier_outcomes WHERE {' AND '.join(filters)} "
            "GROUP BY barrier_number ORDER BY win_rate DESC, runners DESC LIMIT 20"
        )
        return AssistantPlan(
            question=question,
            sql=sql,
            params=params,
            summary="Barrier performance ranked by strike rate.",
            confidence=0.76,
            chart={"type": "bar", "x": "barrier_number", "y": "win_rate"},
        )

    sql = (
        "SELECT m.track_name, r.race_number, r.name, r.status, "
        "r.distance_m, r.scheduled_start_time "
        "FROM races r JOIN meetings m ON m.id = r.meeting_id "
        "WHERE m.meeting_date >= CURRENT_DATE - $1::int "
        "ORDER BY m.meeting_date DESC, m.track_name, r.race_number LIMIT 50"
    )
    return AssistantPlan(
        question=question,
        sql=sql,
        params=[days],
        summary="Recent races matching the available warehouse context.",
        confidence=0.4,
        chart={"type": "table"},
    )


def _extract_days(question: str) -> int:
    if "week" in question:
        return 7
    match = re.search(r"last\s+(\d+)\s+day", question)
    if match:
        return int(match.group(1))
    return 180


def _extract_track(question: str) -> str | None:
    match = re.search(r"(?:at|on)\s+([A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+)*)", question)
    return match.group(1).strip() if match else None


def _extract_distance(question: str) -> int | None:
    match = re.search(r"(\d{3,4})m", question)
    return int(match.group(1)) if match else None


def _extract_condition(question: str) -> str | None:
    match = re.search(r"\b(heavy|soft|good|firm|synthetic)\b", question)
    return match.group(1) if match else None


def _mentions_today(question: str) -> bool:
    return "today" in question or "today's" in question or "todays" in question


def _extract_cte_names(upper_sql: str) -> set[str]:
    if not upper_sql.startswith("WITH "):
        return set()
    return {
        match.group(1).lower()
        for match in re.finditer(r"(?:WITH|,)\s+([A-Z_][A-Z0-9_]*)\s+AS\s*\(", upper_sql)
    }


def _is_value_or_alpha_question(question: str) -> bool:
    return any(
        term in question
        for term in (
            "horse score",
            "horse scores",
            "alpha score",
            "alpha runners",
            "top alpha",
            "top-scored",
            "top scored",
            "leaderboard",
            "betman probability",
            "betman edge",
            "probability edge",
            "biggest edge",
            "market-implied",
            "market implied",
            "value score",
            "value runner",
            "value runners",
            "top value",
        )
    )


def _is_market_mover_question(question: str) -> bool:
    return any(term in question for term in ("market mover", "market movers", "biggest movers", "price movers"))


def _is_race_card_question(question: str) -> bool:
    has_scope = _mentions_today(question) or re.search(r"\blast\s+\d+\s+day", question)
    return bool(has_scope) and any(term in question for term in ("race", "races", "card", "meeting", "meetings"))


def _has_weather_intent(question: str) -> bool:
    return bool(re.search(r"\b(weather|rain|wind|humidity|temperature)\b", question))


def _build_value_runner_plan(question: str, days: int, *, today_only: bool = False) -> AssistantPlan:
    date_clause = (
        "(m.meeting_date = CURRENT_DATE OR hs.calculated_at::date = CURRENT_DATE)"
        if today_only
        else "m.meeting_date >= CURRENT_DATE - $1::int"
    )
    sql = (
        "SELECT m.track_name, m.meeting_date, r.race_number, run.name AS runner_name, "
        "hs.alpha_score, hs.value_score, hs.betman_probability, hs.implied_probability, "
        "hs.market_price, ROUND((hs.betman_probability - hs.implied_probability)::numeric, 4) AS probability_edge, "
        "hs.calculated_at "
        "FROM horse_scores hs "
        "JOIN races r ON r.id = hs.race_id "
        "JOIN meetings m ON m.id = r.meeting_id "
        "JOIN runners run ON run.id = hs.runner_id "
        f"WHERE {date_clause} "
        "ORDER BY hs.value_score DESC NULLS LAST, probability_edge DESC NULLS LAST, hs.alpha_score DESC NULLS LAST LIMIT 50"
    )
    return AssistantPlan(
        question=question,
        sql=sql,
        params=[] if today_only else [days],
        summary="Top value runners ranked by BETMAN value score and probability edge.",
        confidence=0.86,
        chart={"type": "bar", "x": "runner_name", "y": "value_score"},
    )


def _build_market_mover_plan(question: str, days: int, *, today_only: bool = False) -> AssistantPlan:
    date_clause = "m.meeting_date = CURRENT_DATE" if today_only else "m.meeting_date >= CURRENT_DATE - $1::int"
    sql = (
        "SELECT m.track_name, m.meeting_date, r.race_number, run.name AS runner_name, "
        "ms.signal_type, ms.magnitude, ms.detected_at, ms.time_to_jump_s "
        "FROM market_signals ms "
        "JOIN races r ON r.id = ms.race_id "
        "JOIN meetings m ON m.id = r.meeting_id "
        "LEFT JOIN race_entries re ON re.id = ms.race_entry_id "
        "LEFT JOIN runners run ON run.id = re.runner_id "
        f"WHERE {date_clause} "
        "ORDER BY ABS(ms.magnitude) DESC NULLS LAST, ms.detected_at DESC LIMIT 50"
    )
    return AssistantPlan(
        question=question,
        sql=sql,
        params=[] if today_only else [days],
        summary="Market movers ranked by absolute move magnitude.",
        confidence=0.82,
        chart={"type": "bar", "x": "runner_name", "y": "magnitude"},
    )


def _build_race_card_plan(question: str, days: int, *, today_only: bool = False) -> AssistantPlan:
    date_clause = "m.meeting_date = CURRENT_DATE" if today_only else "m.meeting_date >= CURRENT_DATE - $1::int"
    sql = (
        "SELECT m.track_name, m.meeting_date, r.race_number, r.name, r.status, "
        "r.distance_m, r.race_class_group, r.scheduled_start_time "
        "FROM races r JOIN meetings m ON m.id = r.meeting_id "
        f"WHERE {date_clause} "
        "ORDER BY m.meeting_date DESC, m.track_name, r.race_number LIMIT 50"
    )
    return AssistantPlan(
        question=question,
        sql=sql,
        params=[] if today_only else [days],
        summary="Race card matching the requested date context.",
        confidence=0.76,
        chart={"type": "table"},
    )


def _is_odds_question(question: str) -> bool:
    return any(
        term in question
        for term in (
            "odds",
            "price",
            "prices",
            "market",
            "favourite",
            "favorite",
            "shortest",
            "lowest",
        )
    )


def _extract_runner_context(question: str) -> str:
    for pattern in (
        r"\blooking\s+at\s+([A-Z][A-Za-z'\-]*(?:\s+[A-Z][A-Za-z'\-]*){0,4})",
        r"\bfor\s+([A-Z][A-Za-z'\-]*(?:\s+[A-Z][A-Za-z'\-]*){0,4})",
        r"\bof\s+([A-Z][A-Za-z'\-]*(?:\s+[A-Z][A-Za-z'\-]*){0,4})",
    ):
        match = re.search(pattern, question, flags=re.IGNORECASE)
        if match:
            return _clean_entity(match.group(1))
    quoted = re.search(r"['\"]([^'\"]{2,80})['\"]", question)
    if quoted and len(quoted.group(1).split()) <= 5:
        return _clean_entity(quoted.group(1))
    return ""


def _extract_search_term(question: str) -> str:
    quoted = re.search(r"['\"]([^'\"]{2,80})['\"]", question)
    if quoted and len(quoted.group(1).split()) <= 6:
        return quoted.group(1).strip()
    lowered = question.lower()
    for marker in (" for ", " about ", " containing ", " contains ", " mentioning ", " mentions ", " named ", " called "):
        if marker in lowered:
            return question[lowered.rfind(marker) + len(marker):].strip(" ?.")
    leading = re.match(r"\s*(?:search|find|show|list)\s+(?:me\s+)?(.{2,80})", question, flags=re.IGNORECASE)
    if leading:
        term = re.sub(
            r"\b(?:for|about|the|a|an|horse|runner|runners|horses|progeny|pedigree|pedigrees|table|rows|recent|latest|all|today|today's|todays)\b",
            "",
            leading.group(1),
            flags=re.IGNORECASE,
        )
        return " ".join(term.strip(" ?.").split())
    return ""


def _extract_table_reference(question: str) -> str | None:
    for alias, table in sorted(TABLE_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", question):
            if any(word in question for word in ("show", "list", "search", "table", "recent", "latest", "all")):
                return table
    snake_match = re.search(r"\b([a-z]+(?:_[a-z]+)+)\b", question)
    if snake_match and snake_match.group(1) in TABLE_SEARCH_COLUMNS:
        return snake_match.group(1)
    return None


def _strip_intent_words(question: str, words: tuple[str, ...]) -> str:
    value = question
    for word in words:
        value = re.sub(rf"\b{re.escape(word)}\b", "", value, flags=re.IGNORECASE)
    return " ".join(value.strip(" ?.").split())


def _clean_entity(value: str) -> str:
    value = re.split(r"\b(?:what|which|who|where|when|why|how|is|are|was|were|on|at|in|over|under)\b", value, maxsplit=1)[0]
    return " ".join(value.strip(" ,?.'\"").split())


def _extract_pedigree_term(question: str) -> str:
    match = re.search(
        r"\b(?:find|show|search|list)\s+([A-Z][A-Za-z'\-]*(?:\s+[A-Z][A-Za-z'\-]*){0,3})\s+progeny\b",
        question,
        flags=re.IGNORECASE,
    )
    if match:
        return _clean_entity(match.group(1))
    return ""


def _build_table_scan_plan(question: str, table: str, search_term: str) -> AssistantPlan:
    columns = TABLE_SEARCH_COLUMNS.get(table)
    if not columns:
        return build_rule_based_plan("recent races")  # type: ignore[return-value]
    where = ""
    params: list[Any] = []
    searchable = TEXT_SEARCH_TABLES.get(table)
    if search_term and searchable:
        params.append(search_term)
        where = " WHERE " + " OR ".join(f"{column} ILIKE '%' || $1 || '%'" for column in searchable)
    order_column = _best_order_column(columns)
    sql = f"SELECT {', '.join(columns)} FROM {table}{where} ORDER BY {order_column} DESC NULLS LAST LIMIT 50"
    return AssistantPlan(
        question=question,
        sql=sql,
        params=params,
        summary=f"Recent rows from {table.replace('_', ' ')}.",
        confidence=0.68,
        chart={"type": "table"},
    )


def _build_cross_text_search_plan(question: str, search_term: str) -> AssistantPlan:
    sql = (
        "SELECT source, label, snippet, occurred_at FROM ("
        "SELECT 'runners' AS source, name AS label, COALESCE(country_of_origin, type, '') AS snippet, created_at AS occurred_at "
        "FROM runners WHERE name ILIKE '%' || $1 || '%' "
        "UNION ALL "
        "SELECT 'races' AS source, COALESCE(name, race_class_code, 'race') AS label, COALESCE(conditions_description, race_class_group, '') AS snippet, scheduled_start_time AS occurred_at "
        "FROM races WHERE COALESCE(name, '') ILIKE '%' || $1 || '%' OR COALESCE(conditions_description, '') ILIKE '%' || $1 || '%' "
        "UNION ALL "
        "SELECT 'transcripts' AS source, 'commentary' AS label, text AS snippet, started_at AS occurred_at "
        "FROM transcript_segments WHERE text ILIKE '%' || $1 || '%' "
        "UNION ALL "
        "SELECT 'ocr' AS source, observation_type AS label, detected_text AS snippet, frame_timestamp AS occurred_at "
        "FROM ocr_observations WHERE detected_text ILIKE '%' || $1 || '%' OR normalized_text ILIKE '%' || $1 || '%' "
        "UNION ALL "
        "SELECT 'patterns' AS source, pattern_type AS label, description AS snippet, first_detected AS occurred_at "
        "FROM discovered_patterns WHERE description ILIKE '%' || $1 || '%' OR pattern_type ILIKE '%' || $1 || '%' "
        ") results ORDER BY occurred_at DESC NULLS LAST LIMIT 50"
    )
    return AssistantPlan(
        question=question,
        sql=sql,
        params=[search_term],
        summary="Cross-table text search across runners, races, transcripts, OCR, and discovered patterns.",
        confidence=0.7,
        chart={"type": "table"},
    )


def _best_order_column(columns: tuple[str, ...]) -> str:
    for candidate in (
        "created_at",
        "updated_at",
        "generated_at",
        "detected_at",
        "recorded_at",
        "captured_at",
        "started_at",
        "meeting_date",
        "race_date",
        "id",
    ):
        if candidate in columns:
            return candidate
    return columns[0]
