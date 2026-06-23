# BETMAN_DATA — Intelligence Layers

> *"The end game isn't a database. The end game is that BETMAN_DATA becomes the racing equivalent of a hedge fund research platform, continuously discovering relationships between physiology, environment, pedigree, market behaviour and results that nobody else in New Zealand can see."*

This document defines all 12 intelligence layers of the BETMAN_DATA platform and describes the entities, signals, computed scores, and questions each layer is designed to answer.

---

## The Stack

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 12 — AI Discovery Engine        (nightly pattern mining) │
│  Layer 11 — Knowledge Graph            (entity relationships)   │
├─────────────────────────────────────────────────────────────────┤
│  Layer 10 — Betting Intelligence       (subscriber signals)     │
│  Layer  9 — Track Intelligence / TBI   (track personality)      │
│  Layer  8 — Gate Intelligence / GAS    (barrier advantage)      │
│  Layer  7 — Horse Behaviour            (parade, loading, style) │
│  Layer  6 — Human Intelligence         (trainers, jockeys)      │
│  Layer  5 — Pedigree Intelligence      (bloodlines, affinities) │
│  Layer  4 — Heatmap Intelligence       (infrared + CSI sensors) │
│  Layer  3 — Environmental Intelligence (weather + soil probes)  │
│  Layer  2 — Market Intelligence        (every odds tick)        │
│  Layer  1 — Race Data                  (stored forever)         │
└─────────────────────────────────────────────────────────────────┘
```

Each layer feeds every layer above it. The Alpha Score at the top is a function of all 12 layers.

---

## Layer 1 — Race Data
*Store forever. This is the permanent record.*

Every race, every runner, every result — the immutable ledger that all intelligence builds on.

### Entities
| Entity | Key fields |
|---|---|
| `races` | track, date, race number, distance, class, stake, track direction, rail position |
| `race_entries` | horse, barrier, weight, jockey, trainer, gear changes, age, sex, career starts |
| `race_results` | finish position, margins (lengths), sectionals, time |
| `speed_ratings` | calculated rating per runner per race |
| `race_sectionals` | split times at defined checkpoints (200m, 400m, 600m, 800m, final) |

### Design principles
- **Store forever.** No purging, no archiving of results data.
- **Sectional times** are the key to understanding pace — where a race was won or lost.
- **Gear changes** are a signal layer in themselves (blinkers on = trainer trying something).
- **Rail position** directly affects effective running distances by gate.

---

## Layer 2 — Market Intelligence
*This is where edges appear.*

Every odds movement from market open to race jump, captured and analysed for smart money signals.

### Entities
| Entity | Key fields |
|---|---|
| `fixed_odds_ticks` | race entry, timestamp, price, source, time_to_jump_s |
| `tote_pools` | pool type (win/place/exacta/trifecta/first four), pool size, dividend |
| `market_signals` | signal type, magnitude, detected_at, time_to_jump_s |
| `smart_money_indicators` | indicator type, runner, confidence, evidence_ids |
| `odds_analytics` | opening, closing, min, max, steam detected, blowout detected |

### Signal types
| Signal | Definition |
|---|---|
| **Price compression** | Market shortens dramatically across all runners — field compression before jump |
| **Steamer** | Specific runner firms rapidly (>20% in <5 min) |
| **Drifter** | Specific runner lengthens rapidly (>20% in <5 min) |
| **Late money** | Significant firming inside 10 minutes of scheduled jump |
| **Smart money** | Correlated movement across fixed and tote simultaneously |

### Questions this layer answers
- Which trainers consistently attract smart money?
- Which tracks see the biggest late moves before the jump?
- Which gates get backed more than their statistical strike rate justifies?
- Does price compression predict race competitiveness?

---

## Layer 3 — Environmental Intelligence
*Most punters ignore this. BETMAN should not.*

Full atmospheric and track surface intelligence, from WeatherLink stations and multi-probe soil arrays.

### Entities
| Entity | Key fields |
|---|---|
| `weather_readings` | temperature, humidity, wind speed/direction, rainfall, pressure, UV |
| `soil_moisture_readings` | moisture_pct per probe (rail/inside/centre/outside at multiple distances) |
| `track_condition_readings` | official rating, penetrometer, irrigation flag |
| `track_sensor_readings` | rail temperature, track surface temperature, air temperature (future sensor layer) |

### Future sensor layer
When physical sensors are installed at tracks:
- Rail temperature probes
- Track surface temperature probes (infrared)
- Multi-point humidity sensors
- Penetrometer automation

### Questions this layer answers
- Which horses improve when humidity exceeds 80%?
- Which trainers outperform after 20mm+ of rainfall in 24h?
- Which gates become disadvantaged when soil moisture at rail probe exceeds 45%?
- Does rail temperature above 35°C affect outside draws?

---

## Layer 4 — Heatmap Intelligence
*The crown jewels. Largely untapped in New Zealand racing.*

Pre-race physiological signals captured via infrared camera and CSI (Cardiovascular + Stress Index) sensors.

### Infrared data
| Measure | Description |
|---|---|
| `sweating_score` | 0–10 score derived from heat signature around neck/flanks |
| `hot_zones` | Identified body regions with elevated temperature (JSONB map) |
| `symmetry_score` | Left/right thermal symmetry — asymmetry may indicate discomfort |
| `recovery_profile` | Temperature curve from stable to post-parade — how fast a horse cools |

### CSI sensor data
| Measure | Description |
|---|---|
| `heart_rate` | Beats per minute at parade ring |
| `heart_rate_variability` | HRV — low HRV = high stress |
| `breathing_rate` | Breaths per minute |
| `motion_score` | Accelerometer-based agitation score |
| `signal_quality` | Sensor confidence 0–1 |

### Entities
| Entity | Key fields |
|---|---|
| `heatmap_sessions` | horse, race, captured_at, operator |
| `heatmap_scores` | sweating_score, hot_zones_json, symmetry_score, recovery_score |
| `csi_readings` | heart_rate, hrv, breathing_rate, motion_score, captured_at |

### Questions this layer answers
- Do winners systematically show lower heart rates pre-race than losers?
- Do horses with high sweating scores underperform their market price?
- Which horses consistently present calm (low motion score, good symmetry) before wins?
- Which stable's horses show stress patterns before non-competitive runs?

---

## Layer 5 — Pedigree Intelligence
*Massive opportunity in New Zealand racing.*

Bloodline data enriched with computed affinities across track, distance, surface, and conditions.

### Entities
| Entity | Key fields |
|---|---|
| `pedigrees` | horse, sire, dam, damsire, grandparent sires, family line |
| `pedigree_affinities` | sire line, affinity type, track/condition/distance context, score, sample_size |
| `bloodline_performance` | sire, track, surface, condition, wins, runners, win_rate, roi |

### Computed affinities
| Affinity | What it measures |
|---|---|
| `wet_track_affinity` | Progeny win rate on soft/heavy vs their overall win rate |
| `distance_affinity` | Optimal distance band for a sire line |
| `track_affinity` | Specific track performance above/below expectation |
| `barrier_affinity` | Whether a sire line outperforms from wide/inside draws |
| `age_progression` | Whether a sire line improves or regresses with age |

### Questions this layer answers
- Which sire lines excel at Ruakaka on soft tracks?
- Which bloodlines consistently improve on Heavy 10 compared to Good 4?
- Does the X sire's progeny outperform the market by 10%+ on wet days?
- Which damsire lines are undervalued by the market at sprint distances?

---

## Layer 6 — Human Intelligence
*People create edges. Track the people.*

Trainer and jockey performance patterns across every meaningful dimension.

### Trainer intelligence
| Pattern | What to track |
|---|---|
| Track performance | Strike rate and ROI at each track |
| Barrier performance | Do they saddle more winners from certain draws? |
| First-up | Win rate when a horse is first-up from a spell |
| Second-up | Win rate when a horse is resuming after one run |
| Distance changes | Performance after stepping up or down in distance |
| Class changes | After dropping or rising in class |
| Gear changes | Win rate when applying blinkers/tongue tie for first time |

### Jockey intelligence
| Pattern | What to track |
|---|---|
| Gate performance | Strike rate from different barrier zones |
| Front running | Win rate as leader vs follower |
| Back markers | Ability to produce late runs |
| Wet track | Comparative performance on soft/heavy |
| First ride | Performance on first ride for a trainer |

### Stable signals
The most powerful pattern: **when does a stable bet?**
- Identify races where the trainer's runners firm significantly late
- Cross-reference with trainer strike rate in those scenarios
- Build a `stable_intent_score` that predicts trainer confidence

### Entities
| Entity | Key fields |
|---|---|
| `trainer_stats` | trainer, track, surface, condition, distance_band, class_group, wins, runners, win_rate, roi |
| `trainer_patterns` | trainer, pattern_type (first_up, second_up, gear_change, class_drop), win_rate, roi, sample |
| `jockey_stats` | jockey, track, gate_zone, going, front_running, wins, runners, win_rate |
| `stable_signals` | trainer, race_id, signal_type (bet/drift), confidence, detected_at |

### Questions this layer answers
- Which trainers have >25% first-up strike rate at Te Rapa?
- Which jockeys outperform from outside draws at Ellerslie?
- When does Stable X bet vs drift their runners?
- Which trainers systematically target specific tracks for their best horses?

---

## Layer 7 — Horse Behaviour Intelligence
*Largely untapped. Massive signal value.*

Systematic capture of pre-race behaviour in the parade ring and at the barriers.

### Parade ring observations
| Attribute | Scale |
|---|---|
| `sweating_level` | 0 (none) → 5 (saturated) |
| `agitation_score` | 0 (calm) → 5 (fractious) |
| `head_carriage` | low, normal, high, erratic |
| `coat_condition` | dull, average, gleaming |
| `muscle_tone` | flat, average, well-muscled |
| `walk_rhythm` | stilted, normal, flowing |

### Barrier loading
| Attribute | Description |
|---|---|
| `loading_speed` | fast, normal, slow, refused |
| `loading_attempts` | number of attempts required |
| `reluctance_flag` | boolean — showed reluctance to load |
| `handler_interventions` | number of handler assists needed |

### Race style
Derived from sectional and position-at-call data:
- `leader` — led from the front
- `on_pace` — tracked the leader within 2 lengths
- `midfield` — settled middle of the field
- `backmarker` — settled >5 lengths off the pace

### Entities
| Entity | Key fields |
|---|---|
| `behaviour_observations` | race_entry, stage (parade/loading/race), attribute, value, captured_at |
| `race_style_profiles` | runner, track, distance_band, dominant_style, sample_size |

### Questions this layer answers
- Which horses consistently win when they present calm (sweating ≤1, agitation ≤1)?
- Do horses that load slowly underperform their market price?
- Which horses require cover (race style: backmarker) and fail when forced to lead?
- Which horses deteriorate in coat condition before poor runs?

---

## Layer 8 — Gate Intelligence / Gate Advantage Score (GAS)
*You already identified this. Build it properly.*

The Gate Advantage Score quantifies the expected performance uplift or penalty for each barrier position at each track, distance, condition, and field size combination.

### Gate Advantage Score (GAS)
```
GAS = (observed_win_rate / expected_win_rate) - 1
```
Where `expected_win_rate = 1 / field_size`.

A GAS of +0.15 means that gate delivers 15% more winners than chance predicts.

### Computation inputs
- `barrier_outcomes` (raw results by gate, condition, distance)
- `barrier_statistics` (pre-aggregated for speed)
- `weather_readings` at race time (wet track modifies GAS)
- `soil_moisture_readings` at rail probe (rail moisture modifies inside draw GAS)
- `rail_position` (rail moved in = inside gates shorter effective trip)

### Entities
| Entity | Key fields |
|---|---|
| `gate_advantage_scores` | track, surface, distance_band, condition_category, field_size_band, barrier, GAS, sample_size, updated_at |

### Questions this layer answers
- Which gates outperform statistical expectation at Trentham over 1400m on soft tracks?
- Which gates are "poison" over 1200m at Ellerslie regardless of conditions?
- Which gates become gold on wet tracks when the rail is out 3m?
- Does barrier 1 advantage increase or decrease as field size grows?

---

## Layer 9 — Track Intelligence / Track Bias Index (TBI)
*Every track develops its own personality. Read it in real time.*

The Track Bias Index captures the current running bias of a track on a given day — is the rail hot? Is the outside lane superior? Is there a headwind in the straight?

### Track Bias Index (TBI)
```
TBI = weighted average of position advantage across all races on a given day/surface/condition
```
Components:
- **Rail bias**: Do leaders drawn inside win at a higher-than-expected rate?
- **Outside bias**: Do wide runners (barrier >field_size*0.6) outperform?
- **Pace bias**: Are front-runners winning or getting run down?
- **Wind adjustment**: Is there a headwind/tailwind in the straight (from weather station)?

### Entities
| Entity | Key fields |
|---|---|
| `track_bias_records` | track, race_date, race_id, bias_type, magnitude, confidence, source |
| `track_bias_index` | track, race_date, TBI_rail, TBI_outside, TBI_pace, TBI_composite, updated_at |
| `track_wind_records` | track, recorded_at, wind_speed_kmh, wind_direction_deg, straight_wind_effect (headwind/tailwind/crosswind) |

### Questions this layer answers
- Is the Ellerslie rail hot today based on the first 4 races?
- Is the outside lane at Trentham superior this meeting (heavy rainfall softened rail)?
- Is there a headwind in the Te Rapa straight making front runners vulnerable?
- Which meeting days show the strongest rail bias correlating to specific rail positions?

---

## Layer 10 — Betting Intelligence
*Track your own subscribers. Anonymised. This is gold.*

Aggregate subscriber betting behaviour to understand which BETMAN signals generate actual returns, and to surface crowd intelligence.

### Entities
| Entity | Key fields |
|---|---|
| `subscriber_bets` | subscriber_hash (anonymised), race_id, runner_id, bet_type, stake, price_taken, result |
| `signal_performance` | signal_type, period, bets, winners, roi, edge, sample_size |
| `signal_combinations` | signal_a, signal_b, bets, roi, edge |

### Privacy
- Subscribers are identified only by a one-way hash of their ID
- No PII is stored in this table
- Aggregated views only in the API

### Questions this layer answers
- Which BETMAN signals (GAS, TBI, market steam) produce the highest ROI?
- Which signal combinations are multiplicative in edge?
- Is there crowd alpha — do certain subscriber groups predict outcomes better than the market?
- Which races attract the highest subscriber bet volume (confidence signals)?

---

## Layer 11 — Knowledge Graph
*This is the billion-dollar component.*

Instead of querying tables independently, the Knowledge Graph treats every entity as a node and every relationship as a directed edge. This enables complex multi-hop queries that no table join can efficiently express.

### Node types
```
Horse → Trained By → Trainer
Horse → Ridden By  → Jockey
Horse → Drawn      → Barrier
Horse → Ran At     → Track
Horse → Ran In     → Weather
Horse → Showed     → Heatmap
Horse → Was In     → Market Move
Horse → Produced   → Result
Horse → Has        → Pedigree → Sire
```

### Sample Knowledge Graph query
> *"Show me horses drawn barrier 1–3 at Trentham over 1400m on wet tracks where the trainer has a >20% first-up strike rate and the horse showed a below-average breathing rate in the last 90 days."*

In graph form:
```
MATCH (h:Horse)-[:DRAWN]->(b:Barrier {number: 1..3})
  -[:AT]->(t:Track {name: "Trentham"})
  -[:OVER]->(d:Distance {range: "1200-1600"})
  -[:ON]->(c:Condition {category: "wet"})
WHERE h-[:TRAINED_BY]->(tr:Trainer {first_up_rate: >0.20})
  AND h-[:HAS_CSI]->(csi:CSI {breathing_rate: <avg, period: "last_90_days"})
RETURN h.name, h.latest_price, tr.name
ORDER BY h.latest_price ASC
```

No human can find this manually. BETMAN can.

### Implementation approach
Phase 1 (now): Store relationships as typed rows in `entity_relationships`. Query via PostgreSQL recursive CTEs.
Phase 2: Export to Neo4j or Apache AGE (PostgreSQL graph extension) for native Cypher queries.

### Entities
| Entity | Key fields |
|---|---|
| `entity_relationships` | from_type, from_id, relationship, to_type, to_id, weight, valid_from, valid_to, properties_json |
| `graph_query_log` | query_text, executed_at, result_count, duration_ms |

---

## Layer 12 — AI Discovery Engine
*Every night. Continuously hunting for what nobody else can see.*

The Discovery Engine runs scheduled analysis jobs over all 11 layers, looking for statistically significant patterns that haven't been observed before. It outputs structured signals that feed into the BETMAN Alpha Score and can be surfaced as alerts.

### Nightly discovery jobs
| Job | What it looks for |
|---|---|
| `gate_bias_scan` | Emerging gate biases over rolling 30/60/90-day windows |
| `trainer_trend_scan` | Trainers outperforming market expectation in the last 30 days |
| `sire_trend_scan` | Sire lines showing emerging track/condition affinity |
| `market_anomaly_scan` | Market pricing inefficiencies by race class, track, condition |
| `heatmap_pattern_scan` | Physiological signals correlating with results |
| `weather_correlation_scan` | Environmental factors correlating with undervalued runners |
| `combination_scan` | Multi-factor signal combinations producing ROI > 0 |

### Output format
Every discovered pattern produces a `discovered_patterns` record:
```json
{
  "pattern_type": "gate_bias",
  "description": "Barrier 2 at Awapuni is +18% ROI over last 90 days on Good 4 tracks",
  "track": "Awapuni",
  "condition": "G4",
  "barrier": 2,
  "roi": 0.18,
  "sample_size": 47,
  "confidence": 0.91,
  "first_detected": "2024-03-01",
  "valid_until": "2024-06-01"
}
```

### Pattern examples
- *"Barrier 2 at Awapuni is +18% ROI over last 90 days."*
- *"Progeny of Savabeel outperform market expectation by 14% on Soft tracks at Ellerslie."*
- *"Horses with breathing rate >22bpm pre-race are underperforming market expectation by 22%."*
- *"Trainer X's runners firm >15% in last 10 minutes when strike rate exceeds 30% at the venue."*
- *"Rail bias at Trentham increases by 0.08 TBI units for every 10mm of rainfall in 24h."*

### Entities
| Entity | Key fields |
|---|---|
| `discovery_runs` | job_type, started_at, finished_at, patterns_found, status |
| `discovered_patterns` | pattern_type, description, parameters_json, roi, confidence, sample_size, first_detected, valid_until |
| `pattern_signals` | pattern_id, race_id, runner_id, signal_strength, generated_at |

---

## BETMAN Proprietary Scores

Ten computed scores, each refreshed on new data. Together they form the **Alpha Score**.

| Score | Symbol | Description | Key inputs |
|---|---|---|---|
| BETMAN Confidence | BC | Overall win probability | All layers |
| Gate Advantage Score | GAS | Barrier bias for this runner's draw | L1, L3, L8, L9 |
| Market Intelligence Score | MIS | Smart money confidence | L2 |
| Stable Intent Score | SIS | Trainer confidence this run | L2, L6 |
| Heatmap Fitness Score | HFS | Physical readiness | L4, L7 |
| Weather Affinity Score | WAS | Environmental suitability | L3, L5 |
| Bloodline Match Score | BMS | Pedigree fit for conditions | L5 |
| Track Bias Index | TBI | Current track pattern advantage | L9 |
| Value Score | VS | Price vs combined probability | L1, L2, all scores |
| **Alpha Score** | **α** | **Combined signal** | **All 10 scores** |

See [betman-scores.md](betman-scores.md) for full computation methodology.
