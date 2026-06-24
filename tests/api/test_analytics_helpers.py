from app.analytics_helpers import compute_person_metrics


def test_compute_person_metrics_calculates_rates_and_roi():
    rows = [
        {
            "person": "A Trainer",
            "split_value": None,
            "final_position": 1,
            "closing_price": 3.5,
        },
        {
            "person": "A Trainer",
            "split_value": None,
            "final_position": 2,
            "closing_price": 5.0,
        },
        {
            "person": "A Trainer",
            "split_value": None,
            "final_position": 5,
            "closing_price": 4.0,
        },
        {
            "person": "B Trainer",
            "split_value": None,
            "final_position": 1,
            "closing_price": None,
        },
    ]

    results = compute_person_metrics(rows, min_runners=1, order_by="win_rate")

    assert results[0]["person"] == "B Trainer"
    a_trainer = next(item for item in results if item["person"] == "A Trainer")
    assert a_trainer["runners"] == 3
    assert a_trainer["wins"] == 1
    assert a_trainer["places"] == 2
    assert a_trainer["win_rate"] == 33.33
    assert a_trainer["place_rate"] == 66.67
    assert a_trainer["roi"] == 16.67
