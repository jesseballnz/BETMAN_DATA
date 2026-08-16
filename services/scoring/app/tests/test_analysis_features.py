from app.analysis_features import (
    build_runner_features,
    capped_kelly,
    deterministic_probabilities,
    market_probabilities,
)


def test_market_probabilities_remove_overround_and_sum_to_one():
    values = market_probabilities([2.0, 3.0, 4.0])
    assert values is not None
    assert round(sum(value for value in values if value is not None), 6) == 1.0


def test_deterministic_probabilities_are_repeatable_and_normalized():
    args = ([0.5, 0.3, 0.2], [0.4, 0.4, 0.2])
    assert deterministic_probabilities(*args) == deterministic_probabilities(*args)
    assert round(sum(deterministic_probabilities(*args)), 6) == 1.0


def test_kelly_is_capped_and_never_stakes_on_negative_edge():
    assert capped_kelly(0.40, 2.0) == 0.0
    assert capped_kelly(0.60, 3.0) == 0.05


def test_feature_missingness_is_explicit():
    features, missing = build_runner_features({"distance_m": 1200}, 0.25)
    assert features["market_probability"] == 0.25
    assert "barrier_number" in missing
