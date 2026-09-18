from pathlib import Path


LOADER_SQL = Path(__file__).resolve().parents[1] / "scripts" / "load_tab_event_payloads.sql"


def test_every_json_array_expansion_rejects_scalar_payloads() -> None:
    """A single provider null/object must never stop the global TAB poller."""
    calls = [
        line.strip()
        for line in LOADER_SQL.read_text(encoding="utf-8").splitlines()
        if "jsonb_array_elements(" in line
    ]

    assert calls, "TAB loader must contain JSON array expansions"
    for call in calls:
        assert "CASE WHEN jsonb_typeof(" in call
        assert "= 'array'" in call
        assert "ELSE '[]'::jsonb END" in call
