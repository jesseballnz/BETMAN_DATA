from pathlib import Path


POLLER = Path(__file__).resolve().parents[1] / "scripts" / "poll_tab_events.sh"


def test_poller_rechecks_previous_day_by_default() -> None:
    """Late results or a transient poll failure must not leave history gaps."""
    script = POLLER.read_text(encoding="utf-8")

    assert "LOOKBACK_DAYS=${BETMAN_DATA_TAB_LOOKBACK_DAYS:-1}" in script
    assert 'date_offset "${today}" "-${LOOKBACK_DAYS}"' in script


def test_poller_includes_hong_kong_by_default() -> None:
    script = POLLER.read_text(encoding="utf-8")

    assert "COUNTRIES=${BETMAN_DATA_TAB_COUNTRIES:-NZ,AUS,HK}" in script
