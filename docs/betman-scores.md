# BETMAN Proprietary Scores

This document defines the computation methodology for all 10 BETMAN proprietary scores.
These scores are calculated by the `services/scoring/` service and stored in `horse_scores`.

---

## Score Philosophy

Each score is:
- **Normalised to 0–100** for display (raw values stored separately for computation)
- **Sample-size weighted** — low confidence with <10 observations reduces the score toward 50 (neutral)
- **Time-decayed** — recent observations are weighted more heavily than historical ones
- **Refreshed continuously** — recalculated whenever new input data arrives

---

## 1. Gate Advantage Score (GAS)

**Purpose:** Quantify the barrier draw advantage/disadvantage for this specific runner in this specific race context.

```
raw_GAS = (observed_win_rate / expected_win_rate) - 1

where:
  observed_win_rate = barrier_statistics.win_rate for this barrier/track/condition/distance/field_size
  expected_win_rate = 1 / field_size

Confidence-weighted:
  GAS = raw_GAS × min(1.0, sample_size / 50)   # full confidence at 50+ observations

Normalised to 0–100:
  GAS_score = 50 + (GAS × 100)                 # 50 = neutral, >50 = advantage, <50 = disadvantage
```

**Adjustments:**
- Rail position modifier: if rail is out 3m+, inside draw GAS decreases
- Soil moisture modifier: if rail probe moisture >45%, inside draw GAS increases
- Wind modifier: if there is a headwind in the straight, leader GAS decreases

---

## 2. Market Intelligence Score (MIS)

**Purpose:** Detect and score the degree of smart money confidence in this runner.

```
Components:
  steam_signal      = max(0, (steam_pct - threshold) / threshold) if steam_detected else 0
  late_firm_signal  = max(0, late_firming_pct / 20) if within 10min of jump else 0
  compression_signal = price_compression_index for this race

MIS_raw = weighted_average(
  steam_signal      × 0.40,
  late_firm_signal  × 0.40,
  compression_signal× 0.20
)

MIS_score = min(100, MIS_raw × 100)
```

**Key thresholds (configurable):**
- Steam: >20% firming in <5 minutes
- Late firm: any firming inside 10 minutes of jump
- High MIS (>70): strong smart money signal — treat as primary filter

---

## 3. Stable Intent Score (SIS)

**Purpose:** Detect trainer confidence signals for this specific runner in this race.

```
Components:
  market_move_alignment = 1 if trainer's market moves are consistent with historical bet patterns
  trainer_track_sr      = trainer.win_rate at this track / overall_win_rate  (relative strength)
  trainer_pattern_match = 1 if (first_up AND trainer.first_up_sr > 0.25)
                          1 if (second_up AND trainer.second_up_sr > 0.22)
                          etc.

SIS_raw = weighted_average(
  market_move_alignment × 0.50,
  trainer_track_sr      × 0.30,
  trainer_pattern_match × 0.20
)

SIS_score = min(100, SIS_raw × 100)
```

**Interpretation:**
- SIS > 75: trainer appears to have confidence in this runner
- SIS < 25: trainer signals (or lack of market move) suggest non-competitive run

---

## 4. Heatmap Fitness Score (HFS)

**Purpose:** Assess physical readiness based on pre-race infrared and CSI sensor data.

```
Components (all normalised to 0–1, higher = better):
  calm_score        = 1 - (agitation_score / 5)          # from behaviour_observations
  sweat_score       = 1 - (sweating_score / 10)          # from heatmap_scores
  symmetry_score    = heatmap_scores.symmetry_score       # already 0–1
  hrv_score         = normalise(heart_rate_variability)   # higher HRV = calmer
  breath_score      = normalise_inverse(breathing_rate)   # lower rate = calmer

HFS_raw = weighted_average(
  calm_score    × 0.25,
  sweat_score   × 0.25,
  symmetry_score× 0.20,
  hrv_score     × 0.15,
  breath_score  × 0.15
)

HFS_score = HFS_raw × 100
```

**If no sensor data:** HFS is absent (null) — do not impute.

---

## 5. Weather Affinity Score (WAS)

**Purpose:** Score how well this runner's historical performance aligns with today's conditions.

```
Inputs:
  current_condition_category  (heavy, soft, good, firm)
  current_temperature_c
  current_humidity_pct
  current_rainfall_24h_mm
  runner's bloodline wet_track_affinity (from pedigree_affinities)
  runner's historical condition_code win_rate vs overall win_rate

WAS_raw = weighted_average(
  condition_win_rate_ratio  × 0.40,   # how much better/worse on this surface
  bloodline_affinity        × 0.35,   # pedigree affinity to conditions
  trainer_condition_roi     × 0.25    # trainer outperformance in these conditions
)

WAS_score = 50 + ((WAS_raw - 1.0) × 50)  # 50 = neutral, >50 = affinity, <50 = aversion
```

---

## 6. Bloodline Match Score (BMS)

**Purpose:** Score pedigree fit for this race's specific track, distance, and conditions.

```
Inputs from pedigree_affinities:
  sire_track_affinity       for current track
  sire_distance_affinity    for current distance band
  sire_condition_affinity   for current condition
  damsire_affinity          (weighted at 50% of sire)

BMS_raw = weighted_average(
  sire_track_affinity     × 0.35,
  sire_distance_affinity  × 0.30,
  sire_condition_affinity × 0.20,
  damsire_affinity        × 0.15
)

BMS_score = min(100, max(0, (BMS_raw - 0.5) / 0.5 × 100))
```

**Data quality note:** BMS requires sufficient progeny data (min 20 starters) to be meaningful.

---

## 7. Track Bias Index (TBI)

**Purpose:** Score how much the current track bias favours or disadvantages this runner's draw and race style.

```
Inputs:
  track_bias_index (TBI_rail, TBI_outside, TBI_pace) for today's meeting
  runner's gate_zone (inside_third / middle_third / outside_third)
  runner's dominant_race_style (leader / on_pace / midfield / backmarker)

bias_favour = (rail_bias × gate_inside_flag)
            + (outside_bias × gate_outside_flag)
            + (pace_bias × front_runner_flag)

TBI_score = 50 + (bias_favour × 50)
```

**Real-time update:** TBI is recalculated after each race in the meeting as the bias picture becomes clearer.

---

## 8. Value Score (VS)

**Purpose:** Compare market price to the BETMAN combined probability estimate.

```
betman_probability = f(BC, GAS, MIS, SIS, HFS, WAS, BMS, TBI)
  — trained regression model combining all scores into a win probability estimate

implied_probability = 1 / current_win_price  (from latest fixed odds tick)

value_edge = betman_probability - implied_probability

VS_score = 50 + (value_edge × 500)   # ±10% edge = ±50 points
```

**Interpretation:**
- VS > 70: BETMAN estimates this runner is underpriced (positive expected value)
- VS < 30: BETMAN estimates this runner is overpriced
- VS = 50: price and model agree

---

## 9. BETMAN Confidence (BC)

**Purpose:** Overall win probability estimate — the headline number.

```
BC = model(
  race_form_vector,     # L1 features
  market_features,      # L2 features
  env_features,         # L3 features
  heatmap_features,     # L4 features
  pedigree_features,    # L5 features
  human_features,       # L6 features
  behaviour_features,   # L7 features
  GAS, TBI              # L8+L9
)

Output: probability 0–1, displayed as 0–100
```

**Model:** Initially a trained XGBoost classifier on historical race outcomes. Retrained nightly by the Discovery Engine on accumulated data.

---

## 10. Alpha Score (α)

**Purpose:** The combined signal — the single number that summarises BETMAN's view.

```
α = weighted_average(
  BC   × 0.25,   # base probability
  MIS  × 0.20,   # market intelligence
  VS   × 0.20,   # value
  SIS  × 0.10,   # stable intent
  GAS  × 0.10,   # gate advantage
  TBI  × 0.05,   # track bias
  HFS  × 0.05,   # physical readiness (if available)
  WAS  × 0.03,   # weather affinity
  BMS  × 0.02    # pedigree match
)
```

**Interpretation:**
- α > 75: Strong signal — multiple layers aligned
- α 60–75: Positive signal — worth attention
- α 40–60: Neutral — no clear edge
- α < 40: Negative signal — layers suggest underperformance

**The Alpha Score is the BETMAN edge made visible in a single number.**
