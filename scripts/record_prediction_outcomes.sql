\set ON_ERROR_STOP on

-- Attach verified outcomes to immutable prediction snapshots. This is the
-- calibration ledger used for Brier score, log loss, and paper-trade ROI.
UPDATE race_prediction_snapshots p
SET outcome_position = rr.finish_position,
    outcome_recorded_at = now(),
    brier_score = power(p.probability - CASE WHEN rr.finish_position = 1 THEN 1.0 ELSE 0.0 END, 2),
    log_loss = -ln(GREATEST(
        0.000001,
        CASE WHEN rr.finish_position = 1 THEN p.probability ELSE 1.0 - p.probability END
    )),
    roi = CASE
        WHEN p.market_price IS NULL OR p.market_price <= 1 THEN NULL
        WHEN rr.finish_position = 1 THEN (p.market_price - 1.0) * COALESCE(p.stake_fraction, 0)
        ELSE -COALESCE(p.stake_fraction, 0)
    END
FROM race_results rr
WHERE rr.race_entry_id = p.race_entry_id
  AND COALESCE(rr.result_quality, 'verified') = 'verified'
  AND p.outcome_position IS NULL;
