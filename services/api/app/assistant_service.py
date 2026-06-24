from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from app.config import settings

ALLOWED_TABLES = {
    "meetings",
    "races",
    "race_entries",
    "runners",
    "odds_snapshots",
    "odds_movements",
    "odds_analytics",
    "barrier_outcomes",
    "barrier_statistics",
    "track_condition_readings",
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

        prompt = (
            "Return strict JSON with keys sql, summary, confidence, chart. "
            "Generate exactly one read-only SELECT query against these tables only: "
            f"{', '.join(sorted(ALLOWED_TABLES))}. Always include LIMIT <= {MAX_LIMIT}."
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
    if not upper_sql.startswith("SELECT "):
        raise ValueError("Only SELECT queries are allowed")
    for keyword in BLOCKED_KEYWORDS:
        if re.search(rf"\b{keyword}\b", upper_sql):
            raise ValueError(f"Blocked keyword detected: {keyword}")

    tables = [
        match.split(".")[-1]
        for match in re.findall(r"\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_\.]*)", upper_sql)
    ]
    disallowed = [table.lower() for table in tables if table.lower() not in ALLOWED_TABLES]
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

    if "steamer" in lowered or "drifter" in lowered:
        movement_types = (
            ["steam", "firm", "late_firm"] if "steamer" in lowered else ["drift", "blowout"]
        )
        comparator = "< 0" if "steamer" in lowered else "> 0"
        sql = (
            "SELECT m.track_name, r.race_number, run.name AS runner_name, "
            "om.movement_type, om.from_price, om.to_price, "
            "om.movement_pct, om.detected_at "
            "FROM odds_movements om "
            "JOIN races r ON r.id = om.race_id "
            "JOIN meetings m ON m.id = r.meeting_id "
            "JOIN race_entries re ON re.id = om.race_entry_id "
            "JOIN runners run ON run.id = re.runner_id "
            f"WHERE om.movement_type = ANY($1::text[]) AND om.movement_pct {comparator} "
            "AND m.meeting_date >= CURRENT_DATE - $2::int "
            "ORDER BY ABS(om.movement_pct) DESC LIMIT 50"
        )
        return AssistantPlan(
            question=question,
            sql=sql,
            params=[movement_types, days],
            summary="Recent market movers ranked by price-change magnitude.",
            confidence=0.82,
            chart={"type": "bar", "x": "runner_name", "y": "movement_pct"},
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
        params = [track or "", days]
        sql = (
            "SELECT barrier_number, COUNT(*) AS runners, COUNT(*) FILTER (WHERE won) AS wins, "
            "ROUND(COUNT(*) FILTER (WHERE won)::numeric * 100.0 / NULLIF(COUNT(*), 0), 2) "
            "AS win_rate, "
            "ROUND(COUNT(*) FILTER (WHERE placed)::numeric * 100.0 / NULLIF(COUNT(*), 0), 2) "
            "AS place_rate "
            "FROM barrier_outcomes WHERE ($1 = '' OR LOWER(track_name) = LOWER($1)) "
            "AND race_date >= CURRENT_DATE - $2::int "
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
