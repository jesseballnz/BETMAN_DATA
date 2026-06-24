/**
 * Bundled demo/pitch fixtures — fully self-contained, no backend required.
 * Used by all six tabs when the app is in Demo mode.
 */

import type {
  AssistantResponse,
  BarrierResponse,
  HeatmapResponse,
  HorseScores,
  MeetingsResponse,
  OddsResponse,
  PeopleResponse,
  RaceDetail,
  RaceListResponse,
  SignalPerformanceItem,
  SignalsResponseItem,
  StatsOverview,
  TracksResponse,
} from './api'

// ---------------------------------------------------------------------------
// Overview
// ---------------------------------------------------------------------------

export const DEMO_STATS_OVERVIEW: StatsOverview = {
  database: { name: 'betman_warehouse', total_size_bytes: 7_340_032_000, table_count: 47 },
  counts: {
    meetings_today: 8,
    races_today: 78,
    runners_today: 692,
    total_runners: 1_847_224,
    total_races: 94_312,
    total_meetings: 11_608,
  },
  freshness: {
    latest_odds_snapshot: new Date(Date.now() - 4 * 60_000).toISOString(),
    latest_meeting: new Date(Date.now() - 11 * 60_000).toISOString(),
    latest_signal: new Date(Date.now() - 2 * 60_000).toISOString(),
  },
  ingestion_last_24h: {
    odds_snapshots_24h: 24_847,
    weather_readings_24h: 312,
    media_segments_24h: 89,
    race_entries_24h: 692,
  },
  tables: [
    { table_name: 'odds_snapshots', approx_rows: 8_241_007, total_bytes: 2_684_354_560, table_bytes: 2_516_582_400, index_bytes: 167_772_160 },
    { table_name: 'race_entries', approx_rows: 1_847_224, total_bytes: 1_073_741_824, table_bytes: 989_855_744, index_bytes: 83_886_080 },
    { table_name: 'media_segments', approx_rows: 412_087, total_bytes: 2_147_483_648, table_bytes: 2_013_265_920, index_bytes: 134_217_728 },
    { table_name: 'horse_scores', approx_rows: 724_831, total_bytes: 524_288_000, table_bytes: 471_859_200, index_bytes: 52_428_800 },
    { table_name: 'runners', approx_rows: 284_114, total_bytes: 209_715_200, table_bytes: 188_743_680, index_bytes: 20_971_520 },
    { table_name: 'races', approx_rows: 94_312, total_bytes: 104_857_600, table_bytes: 94_371_840, index_bytes: 10_485_760 },
    { table_name: 'meetings', approx_rows: 11_608, total_bytes: 52_428_800, table_bytes: 47_185_920, index_bytes: 5_242_880 },
    { table_name: 'market_signals', approx_rows: 318_442, total_bytes: 262_144_000, table_bytes: 235_929_600, index_bytes: 26_214_400 },
    { table_name: 'track_condition_readings', approx_rows: 47_218, total_bytes: 31_457_280, table_bytes: 28_311_552, index_bytes: 3_145_728 },
    { table_name: 'trainer_stats', approx_rows: 8_847, total_bytes: 20_971_520, table_bytes: 18_874_368, index_bytes: 2_097_152 },
  ],
}

// ---------------------------------------------------------------------------
// Today
// ---------------------------------------------------------------------------

const TODAY = new Date().toISOString().slice(0, 10)

export const DEMO_MEETINGS: MeetingsResponse = {
  date: TODAY,
  meetings: [
    {
      id: 1001,
      track_name: 'Ellerslie',
      meeting_date: TODAY,
      surface: 'Turf',
      jurisdiction: 'NZ',
      status: 'Open',
      race_count: 9,
      running_races: 2,
      finished_races: 3,
      races: [
        { id: 2001, race_number: 1, name: '3YO Maiden', distance_m: 1200, status: 'Finished' },
        { id: 2002, race_number: 2, name: 'Benchmark 65', distance_m: 1400, status: 'Finished' },
        { id: 2003, race_number: 3, name: 'Benchmark 72', distance_m: 1600, status: 'Open' },
        { id: 2004, race_number: 4, name: 'Listed Race – NZ Bloodstock', distance_m: 1400, status: 'Open' },
        { id: 2005, race_number: 5, name: 'Group 3 – Eclipse Stakes', distance_m: 1600, status: 'Open' },
      ],
    },
    {
      id: 1002,
      track_name: 'Flemington',
      meeting_date: TODAY,
      surface: 'Turf',
      jurisdiction: 'VIC',
      status: 'Open',
      race_count: 10,
      running_races: 1,
      finished_races: 5,
      races: [
        { id: 2011, race_number: 1, name: 'Maiden Plate', distance_m: 1000, status: 'Finished' },
        { id: 2012, race_number: 2, name: 'Class 1', distance_m: 1200, status: 'Open' },
        { id: 2013, race_number: 3, name: 'BM78', distance_m: 1400, status: 'Open' },
        { id: 2014, race_number: 4, name: 'Group 2 – Gilded Dragon', distance_m: 1600, status: 'Open' },
      ],
    },
    {
      id: 1003,
      track_name: 'Doomben',
      meeting_date: TODAY,
      surface: 'Turf',
      jurisdiction: 'QLD',
      status: 'Open',
      race_count: 8,
      running_races: 0,
      finished_races: 4,
      races: [
        { id: 2021, race_number: 1, name: 'Maiden', distance_m: 1050, status: 'Finished' },
        { id: 2022, race_number: 2, name: 'BM65', distance_m: 1350, status: 'Open' },
        { id: 2023, race_number: 3, name: 'BM75', distance_m: 1600, status: 'Open' },
      ],
    },
  ],
}

export const DEMO_RACE_LIST: RaceListResponse = {
  races: [
    { id: 2001, race_number: 1, name: '3YO Maiden', distance_m: 1200, race_class_code: 'MDN', race_class_group: null, scheduled_start_time: `${TODAY}T11:00:00Z`, actual_start_time: null, status: 'Finished', meeting: { id: 1001, track_name: 'Ellerslie', meeting_date: TODAY, surface: 'Turf', jurisdiction: 'NZ' } },
    { id: 2002, race_number: 2, name: 'Benchmark 65', distance_m: 1400, race_class_code: 'BM65', race_class_group: null, scheduled_start_time: `${TODAY}T11:40:00Z`, actual_start_time: null, status: 'Finished', meeting: { id: 1001, track_name: 'Ellerslie', meeting_date: TODAY, surface: 'Turf', jurisdiction: 'NZ' } },
    { id: 2004, race_number: 4, name: 'Listed Race – NZ Bloodstock', distance_m: 1400, race_class_code: 'LR', race_class_group: null, scheduled_start_time: `${TODAY}T13:10:00Z`, actual_start_time: null, status: 'Open', meeting: { id: 1001, track_name: 'Ellerslie', meeting_date: TODAY, surface: 'Turf', jurisdiction: 'NZ' } },
    { id: 2012, race_number: 2, name: 'Class 1', distance_m: 1200, race_class_code: 'C1', race_class_group: null, scheduled_start_time: `${TODAY}T12:10:00Z`, actual_start_time: null, status: 'Open', meeting: { id: 1002, track_name: 'Flemington', meeting_date: TODAY, surface: 'Turf', jurisdiction: 'VIC' } },
    { id: 2014, race_number: 4, name: 'Group 2 – Gilded Dragon', distance_m: 1600, race_class_code: 'G2', race_class_group: null, scheduled_start_time: `${TODAY}T13:30:00Z`, actual_start_time: null, status: 'Open', meeting: { id: 1002, track_name: 'Flemington', meeting_date: TODAY, surface: 'Turf', jurisdiction: 'VIC' } },
    { id: 2022, race_number: 2, name: 'BM65', distance_m: 1350, race_class_code: 'BM65', race_class_group: null, scheduled_start_time: `${TODAY}T12:45:00Z`, actual_start_time: null, status: 'Open', meeting: { id: 1003, track_name: 'Doomben', meeting_date: TODAY, surface: 'Turf', jurisdiction: 'QLD' } },
  ],
  total: 6,
  limit: 20,
  offset: 0,
}

export const DEMO_RACE_DETAIL: RaceDetail = {
  id: 2004,
  race_number: 4,
  name: 'Listed Race – NZ Bloodstock',
  distance_m: 1400,
  status: 'Open',
  meeting: { track_name: 'Ellerslie', meeting_date: TODAY, surface: 'Turf' },
  entries: [
    { id: 3001, saddle_cloth: '1', barrier_number: 5, jockey_or_driver: 'O. Bosson', trainer: 'J. Richards', weight_kg: 57.0, final_position: null, scratched: false, runner: { id: 101, name: 'Phantom Flight', type: 'Horse', country_of_origin: 'NZ' } },
    { id: 3002, saddle_cloth: '2', barrier_number: 3, jockey_or_driver: 'S. Collett', trainer: 'T. Pike', weight_kg: 56.5, final_position: null, scratched: false, runner: { id: 102, name: 'Storm Protocol', type: 'Horse', country_of_origin: 'AUS' } },
    { id: 3003, saddle_cloth: '3', barrier_number: 7, jockey_or_driver: 'R. Elliot', trainer: 'M. Baker', weight_kg: 56.0, final_position: null, scratched: false, runner: { id: 103, name: 'Dark Matter', type: 'Horse', country_of_origin: 'NZ' } },
    { id: 3004, saddle_cloth: '4', barrier_number: 1, jockey_or_driver: 'L. Ferraris', trainer: 'A. Forsman', weight_kg: 55.5, final_position: null, scratched: false, runner: { id: 104, name: 'Quantum Edge', type: 'Horse', country_of_origin: 'NZ' } },
    { id: 3005, saddle_cloth: '5', barrier_number: 9, jockey_or_driver: 'J. McDonald', trainer: 'C. Waller', weight_kg: 58.5, final_position: null, scratched: false, runner: { id: 105, name: 'Southern Cross', type: 'Horse', country_of_origin: 'AUS' } },
    { id: 3006, saddle_cloth: '6', barrier_number: 4, jockey_or_driver: 'K. Asano', trainer: 'J. Richards', weight_kg: 55.0, final_position: null, scratched: false, runner: { id: 106, name: 'Night Vision', type: 'Horse', country_of_origin: 'NZ' } },
    { id: 3007, saddle_cloth: '7', barrier_number: 6, jockey_or_driver: 'C. Murray', trainer: 'T. Pike', weight_kg: 54.5, final_position: null, scratched: false, runner: { id: 107, name: 'Turbo Boost', type: 'Horse', country_of_origin: 'AUS' } },
    { id: 3008, saddle_cloth: '8', barrier_number: 11, jockey_or_driver: 'W. Beel', trainer: 'R. Lapointe', weight_kg: 54.0, final_position: null, scratched: false, runner: { id: 108, name: 'Silver Lining', type: 'Horse', country_of_origin: 'NZ' } },
  ],
}

// Generate snapshot times going back ~60 minutes in 5-min steps
function makeSnapshots(basePrice: number, endPrice: number, count = 12) {
  const now = Date.now()
  return Array.from({ length: count }, (_, i) => {
    const t = now - (count - 1 - i) * 5 * 60_000
    const frac = i / (count - 1)
    const mid = basePrice + (endPrice - basePrice) * (frac + (Math.random() - 0.5) * 0.05)
    return {
      captured_at: new Date(t).toISOString(),
      offset_ms: -(count - 1 - i) * 5 * 60_000,
      win_price: Math.round(mid * 20) / 20,
      place_price: Math.round((mid * 0.28) * 20) / 20,
      source: 'TAB',
    }
  })
}

export const DEMO_ODDS: OddsResponse = {
  race_id: 2004,
  actual_start_time: null,
  entries: [
    { race_entry_id: 3001, saddle_cloth: '1', runner_name: 'Phantom Flight', snapshots: makeSnapshots(4.5, 2.8) },
    { race_entry_id: 3002, saddle_cloth: '2', runner_name: 'Storm Protocol', snapshots: makeSnapshots(8.5, 6.7) },
    { race_entry_id: 3003, saddle_cloth: '3', runner_name: 'Dark Matter', snapshots: makeSnapshots(2.8, 3.4) },
    { race_entry_id: 3004, saddle_cloth: '4', runner_name: 'Quantum Edge', snapshots: makeSnapshots(11.0, 14.5) },
    { race_entry_id: 3005, saddle_cloth: '5', runner_name: 'Southern Cross', snapshots: makeSnapshots(5.5, 5.2) },
    { race_entry_id: 3006, saddle_cloth: '6', runner_name: 'Night Vision', snapshots: makeSnapshots(9.0, 8.7) },
  ],
}

// ---------------------------------------------------------------------------
// Signals
// ---------------------------------------------------------------------------

export const DEMO_STEAMERS: SignalsResponseItem[] = [
  { id: 1, race_id: 2004, race_entry_id: 3001, runner_name: 'Phantom Flight', signal_type: 'steamer', magnitude: 37.8, confidence: 0.91, detected_at: new Date(Date.now() - 8 * 60_000).toISOString() },
  { id: 2, race_id: 2014, race_entry_id: 3012, runner_name: 'Ellerslie Ace', signal_type: 'steamer', magnitude: 24.3, confidence: 0.85, detected_at: new Date(Date.now() - 14 * 60_000).toISOString() },
  { id: 3, race_id: 2004, race_entry_id: 3002, runner_name: 'Storm Protocol', signal_type: 'steamer', magnitude: 21.4, confidence: 0.78, detected_at: new Date(Date.now() - 22 * 60_000).toISOString() },
  { id: 4, race_id: 2022, race_entry_id: 3022, runner_name: 'Red Horizon', signal_type: 'steamer', magnitude: 18.9, confidence: 0.74, detected_at: new Date(Date.now() - 31 * 60_000).toISOString() },
  { id: 5, race_id: 2012, race_entry_id: 3031, runner_name: 'Velocity Prime', signal_type: 'steamer', magnitude: 15.2, confidence: 0.69, detected_at: new Date(Date.now() - 42 * 60_000).toISOString() },
  { id: 6, race_id: 2023, race_entry_id: 3041, runner_name: 'Night Shift', signal_type: 'steamer', magnitude: 11.7, confidence: 0.64, detected_at: new Date(Date.now() - 55 * 60_000).toISOString() },
]

export const DEMO_DRIFTERS: SignalsResponseItem[] = [
  { id: 10, race_id: 2004, race_entry_id: 3004, runner_name: 'Quantum Edge', signal_type: 'drifter', magnitude: 31.8, confidence: 0.82, detected_at: new Date(Date.now() - 18 * 60_000).toISOString() },
  { id: 11, race_id: 2014, race_entry_id: 3015, runner_name: 'Market Leader', signal_type: 'drifter', magnitude: 22.4, confidence: 0.75, detected_at: new Date(Date.now() - 27 * 60_000).toISOString() },
  { id: 12, race_id: 2022, race_entry_id: 3025, runner_name: 'Early Dawn', signal_type: 'drifter', magnitude: 16.1, confidence: 0.68, detected_at: new Date(Date.now() - 39 * 60_000).toISOString() },
  { id: 13, race_id: 2003, race_entry_id: 3033, runner_name: 'Silver Lining', signal_type: 'drifter', magnitude: 12.8, confidence: 0.61, detected_at: new Date(Date.now() - 51 * 60_000).toISOString() },
]

export const DEMO_SMART_MONEY: SignalsResponseItem[] = [
  { id: 20, race_id: 2004, race_entry_id: 3001, runner_name: 'Phantom Flight', signal_type: 'smart_money', magnitude: 42.1, confidence: 0.94, detected_at: new Date(Date.now() - 6 * 60_000).toISOString() },
  { id: 21, race_id: 2014, race_entry_id: 3012, runner_name: 'Ellerslie Ace', signal_type: 'smart_money', magnitude: 28.7, confidence: 0.88, detected_at: new Date(Date.now() - 12 * 60_000).toISOString() },
  { id: 22, race_id: 2012, race_entry_id: 3031, runner_name: 'Velocity Prime', signal_type: 'smart_money', magnitude: 19.4, confidence: 0.79, detected_at: new Date(Date.now() - 24 * 60_000).toISOString() },
]

export const DEMO_PATTERNS: SignalsResponseItem[] = [
  { id: 30, race_id: 2004, runner_name: 'Phantom Flight', pattern_type: 'late_support_cascade', description: 'Strong late-market support cascade: $4.50→$2.80 over 60 min with volume spike at T-18 min. Pattern confidence: HIGH.', confidence: 0.92, roi: 18.4, detected_at: new Date(Date.now() - 4 * 60_000).toISOString() },
  { id: 31, race_id: 2005, runner_name: null, pattern_type: 'field_inversion', description: 'Field inversion detected at Ellerslie R5: market overweighting favourite at 1.90 vs BETMAN 2.40 model probability.', confidence: 0.84, roi: 14.2, detected_at: new Date(Date.now() - 19 * 60_000).toISOString() },
  { id: 32, race_id: 2014, runner_name: 'Ellerslie Ace', pattern_type: 'barrier_draw_edge', description: 'Barrier 5 draw at Ellerslie 1400m heavy. Historical edge: +8.9% over field average win rate from this gate in these conditions.', confidence: 0.89, roi: 22.1, detected_at: new Date(Date.now() - 33 * 60_000).toISOString() },
  { id: 33, race_id: 2022, runner_name: null, pattern_type: 'trainer_form_cycle', description: 'Jamie Richards strikerate last 14 days: 42.9% vs market implied 28.3%. Structural edge, not noise.', confidence: 0.81, roi: 16.7, detected_at: new Date(Date.now() - 47 * 60_000).toISOString() },
]

// ---------------------------------------------------------------------------
// Gates
// ---------------------------------------------------------------------------

export const DEMO_TRACKS: TracksResponse = {
  tracks: [
    { track_name: 'Ellerslie', surface: 'Turf', race_count: 3847, meeting_count: 482, barrier_sample_size: 3847, heatmap_cell_count: 48 },
    { track_name: 'Flemington', surface: 'Turf', race_count: 6214, meeting_count: 778, barrier_sample_size: 6214, heatmap_cell_count: 60 },
    { track_name: 'Randwick', surface: 'Turf', race_count: 5891, meeting_count: 737, barrier_sample_size: 5891, heatmap_cell_count: 56 },
    { track_name: 'Doomben', surface: 'Turf', race_count: 2947, meeting_count: 369, barrier_sample_size: 2947, heatmap_cell_count: 40 },
    { track_name: 'Riccarton', surface: 'Turf', race_count: 2104, meeting_count: 264, barrier_sample_size: 2104, heatmap_cell_count: 36 },
  ],
}

export const DEMO_BARRIERS: BarrierResponse = {
  track_name: 'Ellerslie',
  surface: 'Turf',
  sample_size: 1287,
  barriers: [
    { barrier_number: 1, relative_barrier: 'rail', total_runners: 127, wins: 10, places: 28, win_rate: 7.9, place_rate: 22.0, rank_by_win_rate: 11 },
    { barrier_number: 2, relative_barrier: 'near_rail', total_runners: 122, wins: 14, places: 33, win_rate: 11.5, place_rate: 27.0, rank_by_win_rate: 8 },
    { barrier_number: 3, relative_barrier: 'near_rail', total_runners: 119, wins: 16, places: 34, win_rate: 13.4, place_rate: 28.6, rank_by_win_rate: 5 },
    { barrier_number: 4, relative_barrier: 'mid_field', total_runners: 118, wins: 18, places: 37, win_rate: 15.3, place_rate: 31.4, rank_by_win_rate: 3 },
    { barrier_number: 5, relative_barrier: 'mid_field', total_runners: 127, wins: 24, places: 44, win_rate: 18.9, place_rate: 34.6, rank_by_win_rate: 1 },
    { barrier_number: 6, relative_barrier: 'mid_field', total_runners: 122, wins: 21, places: 41, win_rate: 17.2, place_rate: 33.6, rank_by_win_rate: 2 },
    { barrier_number: 7, relative_barrier: 'mid_field', total_runners: 118, wins: 19, places: 36, win_rate: 16.1, place_rate: 30.5, rank_by_win_rate: 4 },
    { barrier_number: 8, relative_barrier: 'wide', total_runners: 112, wins: 14, places: 31, win_rate: 12.5, place_rate: 27.7, rank_by_win_rate: 7 },
    { barrier_number: 9, relative_barrier: 'wide', total_runners: 104, wins: 10, places: 24, win_rate: 9.6, place_rate: 23.1, rank_by_win_rate: 9 },
    { barrier_number: 10, relative_barrier: 'wide', total_runners: 98, wins: 8, places: 21, win_rate: 8.2, place_rate: 21.4, rank_by_win_rate: 10 },
    { barrier_number: 11, relative_barrier: 'extreme_wide', total_runners: 90, wins: 6, places: 18, win_rate: 6.7, place_rate: 20.0, rank_by_win_rate: 12 },
    { barrier_number: 12, relative_barrier: 'extreme_wide', total_runners: 80, wins: 5, places: 15, win_rate: 6.3, place_rate: 18.8, rank_by_win_rate: 13 },
  ],
}

export const DEMO_HEATMAP: HeatmapResponse = {
  track_name: 'Ellerslie',
  cells: [
    { zone: 'Rail zone (1-3)', distance_from_finish_band: '0-400m', win_rate: 32.4, place_rate: 58.1, intensity: 84.2 },
    { zone: 'Rail zone (1-3)', distance_from_finish_band: '400-800m', win_rate: 28.1, place_rate: 52.4, intensity: 71.8 },
    { zone: 'Rail zone (1-3)', distance_from_finish_band: '800-1200m', win_rate: 24.6, place_rate: 47.8, intensity: 63.4 },
    { zone: 'Rail zone (1-3)', distance_from_finish_band: '1200m+', win_rate: 19.2, place_rate: 41.0, intensity: 48.7 },
    { zone: 'Mid zone (4-7)', distance_from_finish_band: '0-400m', win_rate: 41.8, place_rate: 67.2, intensity: 97.4 },
    { zone: 'Mid zone (4-7)', distance_from_finish_band: '400-800m', win_rate: 38.4, place_rate: 62.9, intensity: 89.1 },
    { zone: 'Mid zone (4-7)', distance_from_finish_band: '800-1200m', win_rate: 34.7, place_rate: 59.3, intensity: 82.6 },
    { zone: 'Mid zone (4-7)', distance_from_finish_band: '1200m+', win_rate: 29.1, place_rate: 54.4, intensity: 71.4 },
    { zone: 'Wide zone (8-10)', distance_from_finish_band: '0-400m', win_rate: 21.4, place_rate: 44.8, intensity: 52.1 },
    { zone: 'Wide zone (8-10)', distance_from_finish_band: '400-800m', win_rate: 18.7, place_rate: 40.2, intensity: 44.8 },
    { zone: 'Wide zone (8-10)', distance_from_finish_band: '800-1200m', win_rate: 15.4, place_rate: 36.9, intensity: 37.6 },
    { zone: 'Wide zone (8-10)', distance_from_finish_band: '1200m+', win_rate: 11.8, place_rate: 32.1, intensity: 28.4 },
    { zone: 'Extreme (11+)', distance_from_finish_band: '0-400m', win_rate: 12.4, place_rate: 29.1, intensity: 28.7 },
    { zone: 'Extreme (11+)', distance_from_finish_band: '400-800m', win_rate: 9.8, place_rate: 24.4, intensity: 22.1 },
    { zone: 'Extreme (11+)', distance_from_finish_band: '800-1200m', win_rate: 7.2, place_rate: 20.8, intensity: 14.7 },
    { zone: 'Extreme (11+)', distance_from_finish_band: '1200m+', win_rate: 5.4, place_rate: 17.3, intensity: 9.8 },
  ],
}

// ---------------------------------------------------------------------------
// People
// ---------------------------------------------------------------------------

export const DEMO_TRAINERS: PeopleResponse = {
  role: 'trainer',
  filters: { track: null },
  items: [
    { person: 'Jamie Richards', split_value: null, runners: 84, wins: 36, places: 57, win_rate: 42.9, place_rate: 67.9, roi: 18.4 },
    { person: 'Murray Baker', split_value: null, runners: 71, wins: 28, places: 44, win_rate: 39.4, place_rate: 62.0, roi: 14.7 },
    { person: 'Tony Pike', split_value: null, runners: 68, wins: 24, places: 41, win_rate: 35.3, place_rate: 60.3, roi: 11.2 },
    { person: 'Andrew Forsman', split_value: null, runners: 62, wins: 20, places: 37, win_rate: 32.3, place_rate: 59.7, roi: 9.8 },
    { person: 'Chris Waller', split_value: null, runners: 114, wins: 36, places: 68, win_rate: 31.6, place_rate: 59.6, roi: 12.4 },
    { person: 'John Thompson', split_value: null, runners: 79, wins: 24, places: 47, win_rate: 30.4, place_rate: 59.5, roi: 7.9 },
    { person: 'John Sargent', split_value: null, runners: 54, wins: 16, places: 31, win_rate: 29.6, place_rate: 57.4, roi: 6.2 },
    { person: 'Gai Waterhouse', split_value: null, runners: 88, wins: 25, places: 51, win_rate: 28.4, place_rate: 58.0, roi: 5.8 },
    { person: 'James Cummings', split_value: null, runners: 97, wins: 27, places: 55, win_rate: 27.8, place_rate: 56.7, roi: 4.9 },
    { person: 'Peter Moody', split_value: null, runners: 73, wins: 19, places: 41, win_rate: 26.0, place_rate: 56.2, roi: 3.4 },
  ],
}

export const DEMO_JOCKEYS: PeopleResponse = {
  role: 'jockey',
  filters: { track: null },
  items: [
    { person: 'Opie Bosson', split_value: null, runners: 94, wins: 26, places: 48, win_rate: 27.7, place_rate: 51.1, roi: 9.4 },
    { person: 'Sam Collett', split_value: null, runners: 87, wins: 23, places: 42, win_rate: 26.4, place_rate: 48.3, roi: 7.2 },
    { person: 'Ryan Elliott', split_value: null, runners: 78, wins: 19, places: 38, win_rate: 24.4, place_rate: 48.7, roi: 5.9 },
    { person: 'James McDonald', split_value: null, runners: 103, wins: 24, places: 49, win_rate: 23.3, place_rate: 47.6, roi: 8.1 },
    { person: 'Damian Lane', split_value: null, runners: 91, wins: 21, places: 44, win_rate: 23.1, place_rate: 48.4, roi: 6.8 },
    { person: 'Craig Williams', split_value: null, runners: 86, wins: 19, places: 40, win_rate: 22.1, place_rate: 46.5, roi: 4.4 },
    { person: 'Michael Dee', split_value: null, runners: 82, wins: 18, places: 38, win_rate: 22.0, place_rate: 46.3, roi: 3.7 },
    { person: 'Mark Zahra', split_value: null, runners: 79, wins: 17, places: 37, win_rate: 21.5, place_rate: 46.8, roi: 2.9 },
    { person: 'Kerrin McEvoy', split_value: null, runners: 77, wins: 16, places: 36, win_rate: 20.8, place_rate: 46.8, roi: 1.4 },
    { person: 'Tim Clark', split_value: null, runners: 74, wins: 15, places: 34, win_rate: 20.3, place_rate: 45.9, roi: 0.8 },
  ],
}

// ---------------------------------------------------------------------------
// Intelligence
// ---------------------------------------------------------------------------

export const DEMO_INTELLIGENCE_LEADERBOARD: HorseScores[] = [
  { race_id: 2004, race_entry_id: 3001, runner_id: 101, runner_name: 'Phantom Flight', barrier: 5, bc_score: 91.2, gas_score: 88.4, mis_score: 87.6, sis_score: 85.3, hfs_score: 92.1, was_score: 89.7, bms_score: 90.4, tbi_score: 86.8, value_score: 87.3, alpha_score: 94.2, market_price: 2.8, implied_probability: 22.2, betman_probability: 38.7, calculated_at: new Date(Date.now() - 3 * 60_000).toISOString() },
  { race_id: 2014, race_entry_id: 3012, runner_id: 112, runner_name: 'Ellerslie Ace', barrier: 5, bc_score: 88.7, gas_score: 85.1, mis_score: 84.3, sis_score: 82.9, hfs_score: 89.4, was_score: 86.2, bms_score: 87.8, tbi_score: 83.4, value_score: 84.1, alpha_score: 91.7, market_price: 3.2, implied_probability: 31.3, betman_probability: 41.2, calculated_at: new Date(Date.now() - 5 * 60_000).toISOString() },
  { race_id: 2004, race_entry_id: 3002, runner_id: 102, runner_name: 'Storm Protocol', barrier: 3, bc_score: 84.3, gas_score: 81.7, mis_score: 80.9, sis_score: 79.4, hfs_score: 85.8, was_score: 82.4, bms_score: 83.6, tbi_score: 80.1, value_score: 79.8, alpha_score: 88.4, market_price: 6.7, implied_probability: 14.9, betman_probability: 24.1, calculated_at: new Date(Date.now() - 4 * 60_000).toISOString() },
  { race_id: 2004, race_entry_id: 3003, runner_id: 103, runner_name: 'Dark Matter', barrier: 7, bc_score: 81.9, gas_score: 79.2, mis_score: 78.4, sis_score: 77.1, hfs_score: 82.3, was_score: 79.8, bms_score: 81.4, tbi_score: 77.6, value_score: 76.2, alpha_score: 85.3, market_price: 3.4, implied_probability: 29.4, betman_probability: 27.2, calculated_at: new Date(Date.now() - 4 * 60_000).toISOString() },
  { race_id: 2012, race_entry_id: 3031, runner_id: 131, runner_name: 'Quantum Edge', barrier: 1, bc_score: 78.6, gas_score: 76.1, mis_score: 75.3, sis_score: 74.2, hfs_score: 79.7, was_score: 77.4, bms_score: 78.8, tbi_score: 74.9, value_score: 72.4, alpha_score: 82.1, market_price: 12.0, implied_probability: 8.3, betman_probability: 16.8, calculated_at: new Date(Date.now() - 7 * 60_000).toISOString() },
  { race_id: 2022, race_entry_id: 3022, runner_id: 122, runner_name: 'Red Horizon', barrier: 4, bc_score: 76.4, gas_score: 74.2, mis_score: 73.1, sis_score: 72.4, hfs_score: 77.6, was_score: 75.8, bms_score: 76.4, tbi_score: 73.3, value_score: 68.9, alpha_score: 80.7, market_price: 5.5, implied_probability: 18.2, betman_probability: 21.4, calculated_at: new Date(Date.now() - 9 * 60_000).toISOString() },
  { race_id: 2023, race_entry_id: 3041, runner_id: 141, runner_name: 'Night Shift', barrier: 6, bc_score: 74.1, gas_score: 72.4, mis_score: 71.8, sis_score: 70.7, hfs_score: 75.4, was_score: 73.1, bms_score: 74.3, tbi_score: 71.6, value_score: 65.4, alpha_score: 78.9, market_price: 9.0, implied_probability: 11.1, betman_probability: 13.7, calculated_at: new Date(Date.now() - 11 * 60_000).toISOString() },
  { race_id: 2014, race_entry_id: 3015, runner_id: 115, runner_name: 'Velocity Prime', barrier: 2, bc_score: 72.8, gas_score: 70.7, mis_score: 69.4, sis_score: 69.1, hfs_score: 73.2, was_score: 71.6, bms_score: 72.4, tbi_score: 70.1, value_score: 63.8, alpha_score: 77.2, market_price: 15.0, implied_probability: 6.7, betman_probability: 11.2, calculated_at: new Date(Date.now() - 12 * 60_000).toISOString() },
]

export const DEMO_SIGNAL_PERFORMANCE: SignalPerformanceItem[] = [
  { signal_type: 'steamer', period_days: 30, bets: 89, winners: 24, roi: 18.4, strike_rate: 27.0, edge: 17.0 },
  { signal_type: 'smart_money', period_days: 30, bets: 34, winners: 11, roi: 24.7, strike_rate: 32.4, edge: 22.4 },
  { signal_type: 'pattern', period_days: 30, bets: 42, winners: 10, roi: 12.1, strike_rate: 23.8, edge: 13.8 },
  { signal_type: 'drifter', period_days: 30, bets: 67, winners: 14, roi: -8.3, strike_rate: 20.9, edge: 10.9 },
]

// ---------------------------------------------------------------------------
// Ask BETMAN – scripted answers
// ---------------------------------------------------------------------------

export const DEMO_EXAMPLE_QUESTIONS = [
  "today's steamers",
  "best barrier on a heavy 10 at Ellerslie over 1400m",
  "which trainers are over-performing the market this week",
  "top value runners in today's card",
]

export const DEMO_ANSWERS: Record<string, AssistantResponse> = {
  "today's steamers": {
    question: "today's steamers",
    provider: 'betman-core-v3',
    sql: `SELECT om.runner_name, om.movement_pct, om.from_price, om.to_price\nFROM odds_movements om\nJOIN races r ON r.id = om.race_id\nWHERE DATE(r.scheduled_start_time) = CURRENT_DATE\n  AND om.movement_type = 'steam'\nORDER BY ABS(om.movement_pct) DESC\nLIMIT 10`,
    parameters: [],
    rows: [
      { runner_name: 'Phantom Flight', movement_pct: -37.8, from_price: 4.5, to_price: 2.8 },
      { runner_name: 'Ellerslie Ace', movement_pct: -24.3, from_price: 4.2, to_price: 3.18 },
      { runner_name: 'Storm Protocol', movement_pct: -21.4, from_price: 8.5, to_price: 6.68 },
      { runner_name: 'Red Horizon', movement_pct: -18.9, from_price: 7.0, to_price: 5.68 },
      { runner_name: 'Velocity Prime', movement_pct: -15.2, from_price: 14.0, to_price: 11.87 },
      { runner_name: 'Night Shift', movement_pct: -11.7, from_price: 10.0, to_price: 8.83 },
    ],
    summary: 'Six runners are showing significant steam today. Phantom Flight leads with a 37.8% contraction from $4.50 to $2.80, signalling heavy professional backing ahead of the NZ Bloodstock Listed Race at Ellerslie. Ellerslie Ace and Storm Protocol follow with 24% and 21% moves respectively. Smart money appears concentrated in the 1400m middle-distance races — this is a coherent pattern, not random noise.',
    confidence: 0.91,
    chart: { type: 'bar', x: 'runner_name', y: 'movement_pct' },
  },
  'best barrier on a heavy 10 at Ellerslie over 1400m': {
    question: 'best barrier on a heavy 10 at Ellerslie over 1400m',
    provider: 'betman-core-v3',
    sql: `SELECT b.barrier_number, b.win_rate, b.place_rate, b.total_runners AS sample_size\nFROM barrier_statistics b\nJOIN tracks t ON t.track_name = b.track_name\nWHERE b.track_name = 'Ellerslie'\n  AND b.condition_category = 'heavy'\n  AND b.distance_min >= 1300\n  AND b.distance_max <= 1500\nORDER BY b.win_rate DESC`,
    parameters: ['Ellerslie', 'heavy', 1300, 1500],
    rows: [
      { barrier_number: 5, win_rate: 18.9, place_rate: 34.6, sample_size: 127 },
      { barrier_number: 6, win_rate: 17.2, place_rate: 33.6, sample_size: 122 },
      { barrier_number: 7, win_rate: 16.1, place_rate: 30.5, sample_size: 118 },
      { barrier_number: 4, win_rate: 15.3, place_rate: 31.4, sample_size: 118 },
      { barrier_number: 3, win_rate: 13.4, place_rate: 28.6, sample_size: 119 },
      { barrier_number: 2, win_rate: 11.5, place_rate: 27.0, sample_size: 122 },
    ],
    summary: 'On a heavy 10 track rating at Ellerslie over 1300–1500m, Barrier 5 is the clear standout with an 18.9% win rate from 127 starts — nearly double the field average of ~9.5%. The mid-draw bias (barriers 4–7) is pronounced on heavy ground at this track, likely due to the camber and drainage profile. Runners drawn wide (barrier 8+) lose roughly 8–10% win equity versus the mid-draw.',
    confidence: 0.94,
    chart: { type: 'bar', x: 'barrier_number', y: 'win_rate' },
  },
  'which trainers are over-performing the market this week': {
    question: 'which trainers are over-performing the market this week',
    provider: 'betman-core-v3',
    sql: `SELECT re.trainer, COUNT(*) AS runners,\n  COUNT(*) FILTER (WHERE re.final_position = 1) AS wins,\n  ROUND(AVG(hs.betman_probability - hs.implied_probability), 1) AS avg_edge\nFROM race_entries re\nJOIN horse_scores hs ON hs.race_entry_id = re.id\nJOIN races r ON r.id = re.race_id\nWHERE r.scheduled_start_time >= NOW() - INTERVAL '7 days'\nGROUP BY re.trainer\nHAVING COUNT(*) >= 6\nORDER BY avg_edge DESC\nLIMIT 8`,
    parameters: [7],
    rows: [
      { trainer: 'Jamie Richards', runners: 14, wins: 6, win_rate: 42.9, market_win_rate: 28.3, edge: 14.6 },
      { trainer: 'Tony Pike', runners: 11, wins: 4, win_rate: 36.4, market_win_rate: 24.1, edge: 12.3 },
      { trainer: 'Andrew Forsman', runners: 9, wins: 3, win_rate: 33.3, market_win_rate: 22.8, edge: 10.5 },
      { trainer: 'Murray Baker', runners: 8, wins: 3, win_rate: 37.5, market_win_rate: 29.1, edge: 8.4 },
    ],
    summary: 'Jamie Richards leads the market-beating trainers this week with a 14.6% edge over implied probability — runners the market expected to win at 28% are converting at 43%. Tony Pike and Andrew Forsman also show meaningful positive edge. This pattern suggests these stables are either tactically withholding form, or the market is systematically under-rating their recent conditioning improvements. BETMAN probability models had all four in the top tier before races ran.',
    confidence: 0.87,
    chart: { type: 'bar', x: 'trainer', y: 'edge' },
  },
  "top value runners in today's card": {
    question: "top value runners in today's card",
    provider: 'betman-core-v3',
    sql: `SELECT run.name AS runner_name, hs.alpha_score, hs.value_score,\n  hs.market_price, hs.implied_probability, hs.betman_probability,\n  (hs.betman_probability - hs.implied_probability) AS edge_pct\nFROM horse_scores hs\nJOIN race_entries re ON re.id = hs.race_entry_id\nJOIN races r ON r.id = hs.race_id\nJOIN meetings m ON m.id = r.meeting_id\nJOIN runners run ON run.id = hs.runner_id\nWHERE m.meeting_date = CURRENT_DATE\n  AND hs.betman_probability > hs.implied_probability\nORDER BY (hs.betman_probability - hs.implied_probability) DESC\nLIMIT 6`,
    parameters: [],
    rows: [
      { runner_name: 'Phantom Flight', alpha_score: 94.2, value_score: 87.3, market_price: 2.8, betman_probability: 38.7, implied_probability: 22.2, edge_pct: 16.5 },
      { runner_name: 'Ellerslie Ace', alpha_score: 91.7, value_score: 84.1, market_price: 3.2, betman_probability: 41.2, implied_probability: 31.3, edge_pct: 9.9 },
      { runner_name: 'Quantum Edge', alpha_score: 82.1, value_score: 72.4, market_price: 12.0, betman_probability: 16.8, implied_probability: 8.3, edge_pct: 8.5 },
      { runner_name: 'Storm Protocol', alpha_score: 88.4, value_score: 79.8, market_price: 6.7, betman_probability: 24.1, implied_probability: 14.9, edge_pct: 9.2 },
      { runner_name: 'Velocity Prime', alpha_score: 77.2, value_score: 63.8, market_price: 15.0, betman_probability: 11.2, implied_probability: 6.7, edge_pct: 4.5 },
      { runner_name: 'Red Horizon', alpha_score: 80.7, value_score: 68.9, market_price: 5.5, betman_probability: 21.4, implied_probability: 18.2, edge_pct: 3.2 },
    ],
    summary: "Today's top value runners show significant positive edges where BETMAN's probability models diverge from market-implied odds. Phantom Flight leads with a 16.5% edge — the market has it at 22% but BETMAN models give it a 38.7% chance based on barrier draw, trainer form cycle, and track-condition fit. Quantum Edge at $12.00 is the standout long-price value — BETMAN sees a 16.8% chance vs the market's 8.3%. These are the runners worth isolating.",
    confidence: 0.89,
    chart: { type: 'bar', x: 'runner_name', y: 'edge_pct' },
  },
}
