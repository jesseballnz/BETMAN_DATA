from app.routers.races import _coerce_runner_fit_row


def test_runner_fit_jsonb_records_are_returned_as_objects() -> None:
    row = {
        "runner_name": "Identity Proof",
        "track": '{"starts": 3, "wins": 1, "seconds": 0, "thirds": 1}',
        "distance": {"starts": 2, "wins": 1, "seconds": 0, "thirds": 0},
        "condition": '{"starts": 0, "wins": 0, "seconds": 0, "thirds": 0}',
    }

    result = _coerce_runner_fit_row(row)

    assert result["track"] == {"starts": 3, "wins": 1, "seconds": 0, "thirds": 1}
    assert result["distance"] == {"starts": 2, "wins": 1, "seconds": 0, "thirds": 0}
    assert result["condition"] == {"starts": 0, "wins": 0, "seconds": 0, "thirds": 0}
