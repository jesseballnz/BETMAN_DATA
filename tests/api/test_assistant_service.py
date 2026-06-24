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
    assert plan.params[0] == ["steam", "firm", "late_firm"]
