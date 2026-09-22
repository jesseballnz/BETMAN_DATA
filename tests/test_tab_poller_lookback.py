from pathlib import Path


POLLER = Path(__file__).resolve().parents[1] / "scripts" / "poll_tab_events.sh"
FETCHER = Path(__file__).resolve().parents[1] / "scripts" / "fetch_tab_event_history.py"
LOADER = Path(__file__).resolve().parents[1] / "scripts" / "load_tab_event_payloads.sql"


def test_poller_rechecks_previous_day_by_default() -> None:
    """Late results or a transient poll failure must not leave history gaps."""
    script = POLLER.read_text(encoding="utf-8")

    assert "LOOKBACK_DAYS=${BETMAN_DATA_TAB_LOOKBACK_DAYS:-1}" in script
    assert 'date_offset "${today}" "-${LOOKBACK_DAYS}"' in script


def test_poller_includes_hong_kong_by_default() -> None:
    script = POLLER.read_text(encoding="utf-8")

    assert "COUNTRIES=${BETMAN_DATA_TAB_COUNTRIES:-NZ,AUS,HK}" in script


def test_poller_rechecks_exact_unresolved_historical_events() -> None:
    script = POLLER.read_text(encoding="utf-8")

    assert "RECONCILE_DAYS=${BETMAN_DATA_TAB_RECONCILE_DAYS:-14}" in script
    assert "--reconcile-targets" in script
    assert "r.status = 'scheduled'" in script
    assert "re.final_position IS DISTINCT FROM rr.finish_position" in script


def test_listing_status_overrides_stale_event_detail_status() -> None:
    fetcher = FETCHER.read_text(encoding="utf-8")
    loader = LOADER.read_text(encoding="utf-8")

    assert 'payload["_betman_listing_race_status"] = listing_status' in fetcher
    assert '"_betman_status_only": True' in fetcher
    assert "payload->>'_betman_listing_race_status'" in loader
    assert "tab_event_status_overrides" in loader
    assert "COALESCE((payload->>'_betman_status_only')::boolean, false) = false" in loader
    assert "meetings.status IN ('completed', 'abandoned')" in loader
    assert "races.status IN ('finished', 'abandoned')" in loader


def test_official_results_repair_entry_positions_before_barrier_outcomes() -> None:
    loader = LOADER.read_text(encoding="utf-8")
    update = """UPDATE race_entries re
SET final_position = rr.finish_position
FROM race_results rr"""

    assert update in loader
    assert loader.index(update) < loader.index("WITH eligible_entries AS")
