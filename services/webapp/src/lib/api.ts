export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/v1'
const API_BEARER_TOKEN = import.meta.env.VITE_API_BEARER_TOKEN

export const POLLING_INTERVALS = {
  stats: 15000,
  meetings: 15000,
  odds: 10000,
  signals: 12000,
  barriers: 30000,
  people: 30000,
} as const

export interface StatsOverview {
  database: { name: string; total_size_bytes: number; table_count: number }
  counts: Record<string, number>
  freshness: Record<string, string | null>
  ingestion_last_24h: Record<string, number>
  tables: Array<{ table_name: string; approx_rows: number; total_bytes: number; table_bytes: number; index_bytes: number }>
}

export interface HealthResponse {
  status: string
  version: string
  environment: string
  timestamp: string
  db: string
  redis: string
}

export interface MeetingsResponse {
  date: string | null
  meetings: Array<{ id: number; track_name: string; meeting_date: string; surface: string | null; jurisdiction: string | null; status: string; race_count: number; running_races: number; finished_races: number; races: Array<{ id: number; race_number: number; name: string | null; distance_m: number | null; status: string }> }>
}

export interface RaceListResponse {
  races: Array<{ id: number; race_number: number; name: string | null; distance_m: number | null; race_class_code: string | null; race_class_group: string | null; scheduled_start_time: string | null; actual_start_time: string | null; status: string; meeting: { id: number; track_name: string; meeting_date: string; surface: string | null; jurisdiction: string | null } }>
  total: number
  limit: number
  offset: number
}

export interface RaceDetail {
  id: number
  race_number: number
  name: string | null
  distance_m: number | null
  status: string
  meeting: { track_name: string; meeting_date: string; surface: string | null }
  entries: Array<{ id: number; saddle_cloth: string | null; barrier_number: number | null; jockey_or_driver: string | null; trainer: string | null; weight_kg: number | null; final_position: number | null; scratched: boolean; runner: { id: number; name: string; type: string | null; country_of_origin: string | null } }>
}

export interface OddsResponse {
  race_id: number
  actual_start_time: string | null
  entries: Array<{ race_entry_id: number; saddle_cloth: string; runner_name: string; snapshots: Array<{ captured_at: string; offset_ms: number; win_price: number | null; place_price: number | null; source: string }> }>
}

export interface SignalsResponseItem {
  id?: number
  race_id?: number
  race_entry_id?: number | null
  runner_name?: string | null
  signal_type?: string
  indicator_type?: string
  magnitude?: number
  confidence?: number
  detected_at?: string
  pattern_type?: string
  description?: string
  roi?: number | null
}

export interface TracksResponse {
  tracks: Array<{ track_name: string; surface: string | null; race_count: number; meeting_count: number; barrier_sample_size: number; heatmap_cell_count: number }>
}

export interface BarrierResponse {
  track_name: string
  surface: string
  sample_size: number
  barriers: Array<{ barrier_number: number; relative_barrier: string | null; total_runners: number; wins: number; places: number; win_rate: number; place_rate: number; rank_by_win_rate: number }>
}

export interface HeatmapResponse {
  track_name: string
  cells: Array<{ zone: string; distance_from_finish_band: string | null; win_rate: number; place_rate: number; intensity: number }>
}

export interface PeopleResponse {
  role: string
  filters: Record<string, string | number | null>
  items: Array<{ person: string; split_value: string | null; runners: number; wins: number; places: number; win_rate: number; place_rate: number; roi: number | null }>
}

export interface AssistantResponse {
  question: string
  provider: string
  sql: string
  parameters: Array<string | number | string[]>
  rows: Array<Record<string, string | number | boolean | null>>
  summary: string
  confidence: number
  chart: { type: string; x?: string; y?: string }
  disclaimer?: string
}

export interface SearchResponse {
  query: string
  results: Array<Record<string, string | number | boolean | null>>
}

export interface HorseScores {
  race_id: number
  race_entry_id: number
  runner_id: number
  runner_name: string
  barrier: number | null
  bc_score: number | null
  gas_score: number | null
  mis_score: number | null
  sis_score: number | null
  hfs_score: number | null
  was_score: number | null
  bms_score: number | null
  tbi_score: number | null
  value_score: number | null
  alpha_score: number | null
  market_price: number | null
  implied_probability: number | null
  betman_probability: number | null
  calculated_at: string | null
}

export interface PreRaceIntelligence {
  race_id: number
  race_name: string
  scores: HorseScores[]
  track_bias: Record<string, number> | null
  track_conditions: string | null
  dominant_pattern: string | null
  top_signal: string | null
}

export interface SignalPerformanceItem {
  signal_type: string
  period_days: number
  bets: number
  winners: number
  roi: number | null
  strike_rate: number | null
  edge: number | null
}

interface RaceQueryOptions {
  date?: string
  track?: string
  race_class?: string
  race_class_group?: string
  status?: string
  limit?: number
  offset?: number
}

interface BarrierQueryOptions {
  condition?: string
  condition_category?: string
  surface?: string
  distance_min?: number
  distance_max?: number
  race_class_group?: string
  field_size_min?: number
  since?: string
}

interface HeatmapQueryOptions {
  condition_category?: string
  surface?: string
  distance_band?: string
}

interface PeopleQueryOptions {
  track?: string
  limit?: number
  min_runners?: number
  order_by?: string
  group_by?: string
}

function withQuery(path: string, query: Record<string, string | number | null | undefined>) {
  const params = new URLSearchParams()
  Object.entries(query).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return
    params.set(key, String(value))
  })
  const queryString = params.toString()
  return queryString ? `${path}?${queryString}` : path
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  headers.set('Content-Type', 'application/json')
  if (API_BEARER_TOKEN) {
    headers.set('Authorization', 'Bearer ' + API_BEARER_TOKEN)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `Request failed: ${response.status}`)
  }
  return (await response.json()) as T
}

export function buildLiveWebSocketUrl(feedId: string | number) {
  const baseUrl = new URL(API_BASE_URL, window.location.origin)
  baseUrl.protocol = baseUrl.protocol === 'https:' ? 'wss:' : 'ws:'
  baseUrl.pathname = `${baseUrl.pathname.replace(/\/$/, '')}/live/${feedId}`
  if (API_BEARER_TOKEN) {
    baseUrl.searchParams.set('api_key', API_BEARER_TOKEN)
  }
  return baseUrl.toString()
}

export const api = {
  getHealth: () => request<HealthResponse>('/health'),
  getStatsOverview: () => request<StatsOverview>('/stats/overview'),
  getMeetings: (date?: string) => request<MeetingsResponse>(`/meetings${date ? `?date=${date}` : ''}`),
  getRaces: (options: RaceQueryOptions = {}) =>
    request<RaceListResponse>(
      withQuery('/races', {
        date: options.date,
        track: options.track,
        race_class: options.race_class,
        race_class_group: options.race_class_group,
        status: options.status,
        limit: options.limit,
        offset: options.offset,
      }),
    ),
  getRace: (raceId: number) => request<RaceDetail>(`/races/${raceId}`),
  getRaceOddsDrift: (raceId: number) => request<OddsResponse>(`/races/${raceId}/odds-drift`),
  getSteamers: () => request<SignalsResponseItem[]>('/market/steamers'),
  getDrifters: () => request<SignalsResponseItem[]>('/market/drifters'),
  getSmartMoney: () => request<SignalsResponseItem[]>('/market/smart-money'),
  getDiscoveryPatterns: () => request<SignalsResponseItem[]>('/discovery/patterns'),
  getTracks: () => request<TracksResponse>('/tracks'),
  getBarrierAnalysis: (trackName: string, options: BarrierQueryOptions = {}) =>
    request<BarrierResponse>(
      withQuery(`/tracks/${encodeURIComponent(trackName)}/barriers`, {
        condition: options.condition,
        condition_category: options.condition_category,
        surface: options.surface,
        distance_min: options.distance_min,
        distance_max: options.distance_max,
        race_class_group: options.race_class_group,
        field_size_min: options.field_size_min,
        since: options.since,
      }),
    ),
  getHeatmap: (trackName: string, options: HeatmapQueryOptions = {}) =>
    request<HeatmapResponse>(
      withQuery(`/tracks/${encodeURIComponent(trackName)}/heatmap`, {
        condition_category: options.condition_category,
        surface: options.surface,
        distance_band: options.distance_band,
      }),
    ),
  getTrainerWinRates: (options: PeopleQueryOptions = {}) =>
    request<PeopleResponse>(
      withQuery('/analytics/trainer-win-rates', {
        track: options.track,
        limit: options.limit,
        min_runners: options.min_runners,
        order_by: options.order_by,
        group_by: options.group_by,
      }),
    ),
  getJockeyWinRates: (options: PeopleQueryOptions = {}) =>
    request<PeopleResponse>(
      withQuery('/analytics/jockey-win-rates', {
        track: options.track,
        limit: options.limit,
        min_runners: options.min_runners,
        order_by: options.order_by,
        group_by: options.group_by,
      }),
    ),
  askBetman: (question: string) => request<AssistantResponse>('/assistant/query', { method: 'POST', body: JSON.stringify({ question }) }),
  searchOcr: (query: string, limit = 20) => request<SearchResponse>(withQuery('/search/ocr', { q: query, limit })),
  searchTranscripts: (query: string, limit = 20) => request<SearchResponse>(withQuery('/search/transcripts', { q: query, limit })),
  getIntelligenceLeaderboard: (raceDate?: string, minAlpha = 70, limit = 20) =>
    request<HorseScores[]>(withQuery('/intelligence/scores/leaderboard', { race_date: raceDate, min_alpha: minAlpha, limit })),
  getRaceIntelligence: (raceId: number) => request<PreRaceIntelligence>(`/intelligence/races/${raceId}/intelligence`),
  getSignalPerformance: (periodDays = 30) => request<SignalPerformanceItem[]>(withQuery('/intelligence/signals/performance', { period_days: periodDays })),
}
