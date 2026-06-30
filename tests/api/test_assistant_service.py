import pytest

from app.assistant_service import (
    build_rule_based_plan,
    enforce_limit,
    validate_safe_select,
)


def test_enforce_limit_adds_default_limit():
    assert enforce_limit("SELECT * FROM races") == "SELECT * FROM races LIMIT 100"


@pytest.mark.parametrize(
    ("sql", "message"),
    [
        ("SELECT * FROM races; DROP TABLE races", "Multiple statements"),
        ("DROP TABLE races", "Only SELECT"),
        ("SELECT * FROM tenant_api_keys LIMIT 10", "Table not allowed"),
        ("SELECT * FROM races", "LIMIT clause"),
    ],
)
def test_validate_safe_select_rejects_unsafe_sql(sql: str, message: str):
    with pytest.raises(ValueError, match=message):
        validate_safe_select(sql)


def test_rule_based_plan_for_steamers_is_safe():
    plan = build_rule_based_plan("today's steamers")
    assert plan is not None
    validate_safe_select(plan.sql)
    assert plan.params[0] == ["late_money", "smart_money", "steamer", "steam", "firm", "late_firm"]


def test_rule_based_plan_with_lateral_join_is_safe():
    plan = build_rule_based_plan("top jockeys on wet tracks")
    assert plan is not None
    validate_safe_select(plan.sql)
    assert "JOIN LATERAL" in plan.sql


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT text FROM transcript_segments LIMIT 10",
        "SELECT detected_text FROM ocr_observations LIMIT 10",
        "SELECT sire, roi FROM bloodline_performance LIMIT 10",
        "SELECT alpha_score FROM horse_scores LIMIT 10",
        "SELECT signal_type FROM market_signals LIMIT 10",
        "SELECT signal_count FROM market_signal_daily_summary LIMIT 10",
        "SELECT indicator_count FROM smart_money_daily_summary LIMIT 10",
        "SELECT snapshot_count FROM odds_snapshot_daily_summary LIMIT 10",
        "SELECT rainfall_24h_mm FROM weather_readings LIMIT 10",
    ],
)
def test_validate_safe_select_allows_domain_tables(sql: str):
    validate_safe_select(sql)


@pytest.mark.parametrize(
    "question",
    [
        "find horse named Imperatriz",
        "show pedigree for Savabeel",
        "show discovered patterns",
        "show pattern signals",
        "top horse scores last 30 days",
        "show smart money",
        "show weather at Ellerslie",
        "search transcripts for boxed on",
        "search ocr for dividend",
        "search for Te Akau",
        "show race_summaries",
    ],
)
def test_rule_based_plan_expanded_natural_language_is_safe(question: str):
    plan = build_rule_based_plan(question)
    assert plan is not None
    validate_safe_select(plan.sql)


def test_validate_safe_select_still_rejects_private_platform_tables():
    with pytest.raises(ValueError, match="Table not allowed"):
        validate_safe_select("SELECT key_prefix FROM tenant_api_keys LIMIT 10")


def test_smart_money_uses_joined_market_plan():
    plan = build_rule_based_plan("show smart money")
    assert plan is not None
    validate_safe_select(plan.sql)
    assert "JOIN races" in plan.sql
    assert "smart_money_indicators smi" in plan.sql


def test_runner_meeting_shortest_odds_question_uses_odds_plan():
    plan = build_rule_based_plan("Looking at Kilroy, what is the shortest odds on the meeting")
    assert plan is not None
    validate_safe_select(plan.sql)
    assert plan.params == ["Kilroy"]
    assert "odds_snapshots" in plan.sql
    assert "ORDER BY lp.win_price ASC" in plan.sql
    assert plan.confidence > 0.8


def test_top_value_runners_uses_horse_scores_plan():
    plan = build_rule_based_plan("top value runners in today's card")
    assert plan is not None
    validate_safe_select(plan.sql)
    assert "horse_scores hs" in plan.sql
    assert "value_score" in plan.sql
    assert plan.params == []
    assert plan.confidence > 0.8


def test_trainer_market_overperformance_uses_expected_wins_plan():
    plan = build_rule_based_plan("which trainers are over-performing the market this week")
    assert plan is not None
    validate_safe_select(plan.sql)
    assert "expected_wins" in plan.sql
    assert "wins_above_market" in plan.sql
    assert "horse_scores hs" in plan.sql
    assert plan.params == [7]
    assert plan.confidence > 0.8


def test_today_steamers_uses_populated_market_signals_plan():
    plan = build_rule_based_plan("today's steamers")
    assert plan is not None
    validate_safe_select(plan.sql)
    assert "market_signals ms" in plan.sql
    assert "odds_movements" not in plan.sql
    assert plan.params == [["late_money", "smart_money", "steamer", "steam", "firm", "late_firm"]]


def test_weather_query_sql_is_valid():
    plan = build_rule_based_plan("show weather at Ellerslie")
    assert plan is not None
    validate_safe_select(plan.sql)
    assert "weather_readings wr" in plan.sql
    assert "barometric_pressure_hpa FROM" in plan.sql


def test_heavy_ellerslie_barrier_question_uses_context_filters():
    plan = build_rule_based_plan("best barrier on a heavy 10 at Ellerslie over 1400m")
    assert plan is not None
    validate_safe_select(plan.sql)
    assert "barrier_outcomes" in plan.sql
    assert "condition_category" in plan.sql
    assert "distance_m" in plan.sql
    assert plan.params == ["Ellerslie", 180, "heavy", 1400]
