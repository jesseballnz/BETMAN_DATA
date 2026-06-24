import { useEffect, useMemo, useState, type ReactNode } from 'react'
import type { ColDef, ValueGetterParams } from 'ag-grid-community'
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { AgGridReact } from 'ag-grid-react'
import ReactECharts from 'echarts-for-react'
import { Database, Gauge, Map, Search, Sparkles, Users } from 'lucide-react'
import { NavLink, Route, Routes } from 'react-router-dom'

import { Button } from './components/ui/button'
import { Card } from './components/ui/card'
import { Input } from './components/ui/input'
import { Select } from './components/ui/select'
import {
  POLLING_INTERVALS,
  api,
  buildLiveWebSocketUrl,
  type AssistantResponse,
  type BarrierResponse,
  type HealthResponse,
  type HeatmapResponse,
  type HorseScores,
  type OddsResponse,
  type PeopleResponse,
  type RaceDetail,
  type SignalPerformanceItem,
  type StatsOverview,
} from './lib/api'
import {
  DEMO_ANSWERS,
  DEMO_EXAMPLE_QUESTIONS,
  DEMO_BARRIERS,
  DEMO_DRIFTERS,
  DEMO_HEATMAP,
  DEMO_INTELLIGENCE_LEADERBOARD,
  DEMO_JOCKEYS,
  DEMO_MEETINGS,
  DEMO_ODDS,
  DEMO_PATTERNS,
  DEMO_RACE_DETAIL,
  DEMO_RACE_LIST,
  DEMO_SIGNAL_PERFORMANCE,
  DEMO_SMART_MONEY,
  DEMO_STATS_OVERVIEW,
  DEMO_STEAMERS,
  DEMO_TRACKS,
  DEMO_TRAINERS,
} from './lib/demoData'
import { useMode } from './lib/ModeContext'
import { cn, formatBytes, formatDateTime, formatNumber, formatPercent } from './lib/utils'

const navigation = [
  { to: '/', label: 'Overview', icon: Database },
  { to: '/today', label: 'Today', icon: Gauge },
  { to: '/signals', label: 'Signals', icon: Sparkles },
  { to: '/gates', label: 'Gates', icon: Map },
  { to: '/people', label: 'People', icon: Users },
  { to: '/ask', label: 'Ask BETMAN', icon: Search },
]

const distancePresets: Array<{ key: string; label: string; min?: number; max?: number }> = [
  { key: 'all', label: 'All distances' },
  { key: 'sprint', label: 'Sprint 900m-1200m', min: 900, max: 1200 },
  { key: 'mile', label: 'Mile 1201m-1600m', min: 1201, max: 1600 },
  { key: 'staying', label: 'Staying 1601m+', min: 1601 },
]
const MIN_HEATMAP_SCALE = 12
const DEFAULT_SUPPORT_HIT_TEXT = 'Search result item'
const BARRIER_HEATMAP_COLORS = ['#13293d', '#0ea5e9', '#22d3ee', '#67e8f9']
const TRACK_HEATMAP_COLORS = ['#1e1b4b', '#1d4ed8', '#0891b2', '#67e8f9']

function getSignalType(item: { signal_type?: string; indicator_type?: string; pattern_type?: string }) {
  return item.signal_type ?? item.indicator_type ?? item.pattern_type ?? 'signal'
}

function App() {
  const { mode, setMode } = useMode()
  const queryClient = useQueryClient()
  const [hintDismissed, setHintDismissed] = useState(() => {
    try {
      return localStorage.getItem('betman_mode_hint_dismissed') === 'true'
    } catch {
      return false
    }
  })
  const health = useQuery({
    queryKey: ['health', mode],
    queryFn: api.getHealth,
    enabled: mode === 'live',
    refetchInterval: mode === 'live' ? 15000 : false,
    staleTime: 0,
    retry: false,
  })
  const liveSocket = useLiveSocket(mode, queryClient)

  const dismissHint = () => {
    setHintDismissed(true)
    try {
      localStorage.setItem('betman_mode_hint_dismissed', 'true')
    } catch {}
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-7xl flex-col px-4 py-4 sm:px-6 lg:px-8">
        <header className="mb-6 rounded-2xl border border-cyan-900/40 bg-slate-950/90 p-4 shadow-[0_0_40px_rgba(34,211,238,0.12)]">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-center gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.35em] text-cyan-400">BETMAN_DATA</p>
                <h1 className="text-3xl font-semibold text-white">Data Viewer</h1>
                <p className="text-sm text-slate-400">Live command center for finding order in market chaos.</p>
              </div>
              <div className="flex flex-col items-start gap-1.5">
                <div className="flex rounded-lg border border-slate-700 bg-slate-900 p-0.5" role="tablist" aria-label="Demo and Live mode">
                  <button
                    type="button"
                    onClick={() => setMode('demo')}
                    role="tab"
                    aria-selected={mode === 'demo'}
                    aria-pressed={mode === 'demo'}
                    aria-label="Switch to Demo mode"
                    className={cn(
                      'rounded-md px-4 py-1.5 text-xs font-semibold uppercase tracking-widest transition duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400',
                      mode === 'demo'
                        ? 'bg-cyan-500 text-slate-950 shadow-[0_0_12px_rgba(34,211,238,0.5)]'
                        : 'text-slate-400 hover:text-slate-200',
                    )}
                  >
                    Demo
                  </button>
                  <button
                    type="button"
                    onClick={() => setMode('live')}
                    role="tab"
                    aria-selected={mode === 'live'}
                    aria-pressed={mode === 'live'}
                    aria-label="Switch to Live mode"
                    className={cn(
                      'rounded-md px-4 py-1.5 text-xs font-semibold uppercase tracking-widest transition duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400',
                      mode === 'live'
                        ? 'bg-emerald-500 text-slate-950 shadow-[0_0_12px_rgba(16,185,129,0.5)]'
                        : 'text-slate-400 hover:text-slate-200',
                    )}
                  >
                    Live
                  </button>
                </div>
                {mode === 'demo' && (
                  <span className="rounded-full bg-cyan-500/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.2em] text-cyan-400 ring-1 ring-cyan-500/30">
                    ● Pitch mode — sample data
                  </span>
                )}
                {mode === 'live' && (
                  <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.2em] text-emerald-400 ring-1 ring-emerald-500/30">
                    ● Live — {liveSocket.connected ? 'socket + polling fallback' : 'polling API'}
                  </span>
                )}
              </div>
            </div>
            <nav className="grid gap-2 sm:grid-cols-3 lg:flex">
              {navigation.map(({ to, label, icon: Icon }) => (
                <NavLink
                  key={to}
                  to={to}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition duration-300',
                      isActive
                        ? 'border-cyan-500 bg-cyan-500/10 text-cyan-300 shadow-[0_0_16px_rgba(34,211,238,0.25)]'
                        : 'border-slate-800 bg-slate-900/80 text-slate-400 hover:border-slate-700 hover:text-slate-100',
                    )
                  }
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </NavLink>
              ))}
            </nav>
          </div>
          <div className="mt-4 flex flex-col gap-3">
            <ConnectionStatus mode={mode} socketConnected={liveSocket.connected} health={health.data} error={health.error as Error | null} />
            {!hintDismissed ? (
              <div className="flex items-start justify-between gap-3 rounded-xl border border-cyan-900/40 bg-slate-900/80 px-4 py-3 text-sm text-slate-300">
                <p>
                  <span className="font-semibold text-cyan-300">First run:</span> Demo mode uses bundled fixtures for pitches and onboarding.
                  Switch to Live when your API and proxy key are ready.
                </p>
                <button
                  type="button"
                  onClick={dismissHint}
                  className="shrink-0 rounded-md border border-slate-700 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-slate-300 transition hover:border-slate-500 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
                >
                  Dismiss
                </button>
              </div>
            ) : null}
            {mode === 'live' && health.error ? (
              <EmptyState
                title="API unreachable — Live mode is empty"
                description="The API health check failed. Switch back to Demo mode for bundled fixtures while the platform comes online."
                action={
                  <Button type="button" onClick={() => setMode('demo')}>
                    Switch to Demo
                  </Button>
                }
              />
            ) : null}
          </div>
        </header>

        <main className="flex-1 pb-8">
          <Routes>
            <Route path="/" element={<OverviewView />} />
            <Route path="/today" element={<TodayView />} />
            <Route path="/signals" element={<SignalsView />} />
            <Route path="/gates" element={<GatesView />} />
            <Route path="/people" element={<PeopleView />} />
            <Route path="/ask" element={<AskBetmanView />} />
          </Routes>
        </main>
        <footer className="border-t border-slate-800/80 pt-4 text-xs text-slate-500">
          BETMAN provides racing data and insights, not betting advice. Wager responsibly and only where lawful.
        </footer>
      </div>
    </div>
  )
}

function OverviewView() {
  const { mode } = useMode()
  const { data, isLoading, error } = useQuery({
    queryKey: ['stats-overview', mode],
    queryFn: mode === 'demo' ? () => Promise.resolve(DEMO_STATS_OVERVIEW) : api.getStatsOverview,
    refetchInterval: mode === 'demo' ? false : POLLING_INTERVALS.stats,
    staleTime: mode === 'demo' ? Infinity : 0,
  })
  const [livePulse, setLivePulse] = useState<number[]>([])

  useEffect(() => {
    if (!data) return
    const pulsePoint = Object.values(data.ingestion_last_24h).reduce((acc, value) => {
      return typeof value === 'number' ? acc + value : acc
    }, 0)
    setLivePulse((current) => [...current.slice(-29), pulsePoint])
  }, [data])

  const chartOption = useMemo(() => buildWarehouseChart(data), [data])
  const pulseOption = useMemo(() => buildOverviewPulseChart(livePulse), [livePulse])

  const latestOdds = data?.freshness.latest_odds_snapshot
  const freshnessMinutes = latestOdds ? Math.max(0, Math.round((Date.now() - new Date(latestOdds).getTime()) / 60000)) : null

  return (
    <div className="space-y-4">
      <SectionHeader title="Overview" subtitle="Mission dashboard: ingestion, freshness, and warehouse intelligence in one frame." />
      <ErrorBanner error={error} />

      <Card className="relative overflow-hidden border-cyan-900/40 bg-gradient-to-br from-slate-950 to-slate-900/90">
        <div className="absolute -right-16 -top-16 h-52 w-52 rounded-full bg-cyan-500/12 blur-3xl" />
        <div className="absolute -left-10 bottom-0 h-32 w-32 rounded-full bg-indigo-500/12 blur-2xl" />
        <div className="relative z-10 grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
          <div>
            <p className="text-xs uppercase tracking-[0.35em] text-cyan-400">Live Control Surface</p>
            <h3 className="mt-2 text-3xl font-semibold text-white">Overlay the noise, expose the edge.</h3>
            <p className="mt-2 text-sm text-slate-300">Auto-refreshing telemetry from the BETMAN warehouse with visual cues for freshness and ingestion pulse.</p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <SmallStat label="Warehouse" value={formatBytes(data?.database.total_size_bytes)} />
              <SmallStat label="Tables" value={formatNumber(data?.database.table_count)} />
              <SmallStat label="Rows surfaced" value={formatNumber(data?.tables.reduce((acc, table) => acc + table.approx_rows, 0))} />
              <SmallStat label="Freshness" value={freshnessMinutes === null ? 'No odds yet' : `${freshnessMinutes} min ago`} />
            </div>
          </div>
          <div className="h-[280px] rounded-xl border border-cyan-900/40 bg-slate-950/70 p-2">
            <ReactECharts option={pulseOption} style={{ height: '100%' }} />
          </div>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-4">
        <MetricCard label="Warehouse size" value={formatBytes(data?.database.total_size_bytes)} loading={isLoading} tone="cyan" />
        <MetricCard label="Races today" value={formatNumber(data?.counts.races_today)} loading={isLoading} tone="indigo" />
        <MetricCard
          label="Ingestion / 24h"
          value={formatNumber((data?.ingestion_last_24h.odds_snapshots_24h ?? 0) + (data?.ingestion_last_24h.weather_readings_24h ?? 0) + (data?.ingestion_last_24h.media_segments_24h ?? 0))}
          loading={isLoading}
          tone="teal"
        />
        <MetricCard
          label="Live freshness"
          value={freshnessMinutes === null ? '—' : `${freshnessMinutes} min`}
          loading={isLoading}
          tone={freshnessMinutes !== null && freshnessMinutes <= 10 ? 'emerald' : 'amber'}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
        <Card className="min-h-[420px]">
          <PanelTitle title="Warehouse footprint" subtitle="Largest tables and row density." />
          <div className="mt-4 h-[320px]">
            {isLoading ? (
              <ChartSkeleton />
            ) : (
              <Grid
                rows={data?.tables ?? []}
                columns={[
                  { field: 'table_name', headerName: 'Table' },
                  { field: 'approx_rows', headerName: 'Rows' },
                  { field: 'total_bytes', headerName: 'Total bytes' },
                ]}
              />
            )}
          </div>
        </Card>
        <Card>
          <PanelTitle title="Storage profile" subtitle="Top table sizes (live)." />
          <div className="mt-4 h-[360px]">{isLoading ? <ChartSkeleton /> : <ReactECharts option={chartOption} style={{ height: '100%' }} />}</div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <SmallStat label="Odds snapshots / 24h" value={formatNumber(data?.ingestion_last_24h.odds_snapshots_24h)} />
            <SmallStat label="Weather / 24h" value={formatNumber(data?.ingestion_last_24h.weather_readings_24h)} />
            <SmallStat label="Media / 24h" value={formatNumber(data?.ingestion_last_24h.media_segments_24h)} />
            <SmallStat label="Freshest odds" value={formatDateTime(data?.freshness.latest_odds_snapshot)} />
          </div>
        </Card>
      </div>
    </div>
  )
}

function TodayView() {
  const { mode } = useMode()
  const today = new Date().toISOString().slice(0, 10)
  const meetingsQuery = useQuery({
    queryKey: ['meetings', today, mode],
    queryFn: mode === 'demo' ? () => Promise.resolve(DEMO_MEETINGS) : () => api.getMeetings(today),
    refetchInterval: mode === 'demo' ? false : POLLING_INTERVALS.meetings,
    staleTime: mode === 'demo' ? Infinity : 0,
  })
  const racesQuery = useQuery({
    queryKey: ['races', today, mode],
    queryFn: mode === 'demo' ? () => Promise.resolve(DEMO_RACE_LIST) : () => api.getRaces({ date: today }),
    refetchInterval: mode === 'demo' ? false : POLLING_INTERVALS.meetings,
    staleTime: mode === 'demo' ? Infinity : 0,
  })
  const [selectedRaceId, setSelectedRaceId] = useState<number | null>(null)

  const raceId = selectedRaceId ?? racesQuery.data?.races[0]?.id ?? null
  const [raceDetail, odds] = useQueries({
    queries: [
      {
        queryKey: ['race', raceId, mode],
        queryFn: mode === 'demo' ? () => Promise.resolve(DEMO_RACE_DETAIL) : () => api.getRace(raceId as number),
        enabled: raceId !== null,
        staleTime: mode === 'demo' ? Infinity : 0,
      },
      {
        queryKey: ['odds', raceId, mode],
        queryFn: mode === 'demo' ? () => Promise.resolve(DEMO_ODDS) : () => {
          if (raceId === null) throw new Error('Race id required')
          return api.getRaceOddsDrift(raceId)
        },
        enabled: raceId !== null,
        refetchInterval: mode === 'demo' ? false : POLLING_INTERVALS.odds,
        staleTime: mode === 'demo' ? Infinity : 0,
      },
    ],
  })

  return (
    <div className="space-y-4">
      <SectionHeader title="Today" subtitle="Meetings, fields, and near-live market movement." />
      <ErrorBanner error={(meetingsQuery.error as Error | null) ?? (racesQuery.error as Error | null) ?? (raceDetail.error as Error | null) ?? (odds.error as Error | null)} />
      <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
        <Card>
          <PanelTitle title="Meetings by track" subtitle={today} />
          <div className="mt-4 space-y-3">
            {meetingsQuery.isLoading ? (
              <LoadingTile />
            ) : meetingsQuery.data?.meetings.length ? (
              meetingsQuery.data.meetings.map((meeting) => (
                <button
                  key={meeting.id}
                  type="button"
                  onClick={() => setSelectedRaceId(meeting.races[0]?.id ?? null)}
                  aria-label={`Open ${meeting.track_name} meeting`}
                  className="w-full rounded-lg border border-slate-800 bg-slate-900/80 p-3 text-left transition hover:border-cyan-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium text-white">{meeting.track_name}</div>
                      <div className="text-xs text-slate-400">{meeting.surface ?? 'surface unknown'} • {meeting.jurisdiction ?? 'N/A'}</div>
                    </div>
                    <div className="text-sm text-cyan-300">{meeting.race_count} races</div>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-400" role="list" aria-label={`${meeting.track_name} races`}>
                    {meeting.races.map((race) => (
                      <button
                        key={race.id}
                        type="button"
                        role="listitem"
                        aria-label={`Select race ${race.race_number} ${race.name ?? 'Unnamed'}`}
                        className="rounded bg-slate-800 px-2 py-1 transition hover:bg-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
                        onClick={(event) => {
                          event.stopPropagation()
                          setSelectedRaceId(race.id)
                        }}
                      >
                        R{race.race_number} {race.name ?? 'Unnamed'}
                      </button>
                    ))}
                  </div>
                </button>
              ))
            ) : (
              <EmptyState title="No meetings yet" description="When race data lands, this board will light up." />
            )}
          </div>
        </Card>
        <Card>
          <PanelTitle title={raceDetail.data?.name ?? 'Race detail'} subtitle={raceDetail.data?.meeting.track_name ?? 'Select a race'} />
          <div className="mt-4 h-[220px]">
            {raceDetail.isLoading ? (
              <ChartSkeleton />
            ) : raceDetail.data?.entries?.length ? (
              <Grid
                rows={raceDetail.data?.entries ?? []}
                columns={[
                  { field: 'barrier_number', headerName: 'Barrier' },
                  {
                    field: 'runner.name',
                    headerName: 'Runner',
                    valueGetter: (params: ValueGetterParams<Record<string, unknown>>) =>
                      (params.data as RaceDetail['entries'][number] | undefined)?.runner.name ?? '',
                  },
                  { field: 'jockey_or_driver', headerName: 'Jockey' },
                  { field: 'trainer', headerName: 'Trainer' },
                  { field: 'weight_kg', headerName: 'Wt' },
                ]}
              />
            ) : (
              <EmptyState title="No race selected" description="Choose a meeting or race chip to view runners and market drift." />
            )}
          </div>
          <div className="mt-4 h-[260px]">
            {odds.isLoading ? <ChartSkeleton /> : <ReactECharts option={buildOddsChart(odds.data)} style={{ height: '100%' }} />}
          </div>
        </Card>
      </div>
    </div>
  )
}

function SignalsView() {
  const { mode } = useMode()
  const today = new Date().toISOString().slice(0, 10)
  const races = useQuery({
    queryKey: ['signal-races', today, mode],
    queryFn: mode === 'demo' ? () => Promise.resolve(DEMO_RACE_LIST) : () => api.getRaces({ date: today, limit: 80 }),
    refetchInterval: mode === 'demo' ? false : POLLING_INTERVALS.signals,
    staleTime: mode === 'demo' ? Infinity : 0,
  })
  const [selectedRaceId, setSelectedRaceId] = useState<number | null>(null)

  useEffect(() => {
    if (selectedRaceId !== null) return
    const firstRace = races.data?.races[0]
    if (firstRace) setSelectedRaceId(firstRace.id)
  }, [races.data, selectedRaceId])

  const raceId = selectedRaceId ?? races.data?.races[0]?.id ?? null

  const [odds, steamers, drifters, smartMoney, patterns, intelligence, signalPerf] = useQueries({
    queries: [
      {
        queryKey: ['signal-odds-drift', raceId, mode],
        queryFn: mode === 'demo' ? () => Promise.resolve(DEMO_ODDS) : () => {
          if (raceId === null) throw new Error('Race id required')
          return api.getRaceOddsDrift(raceId)
        },
        enabled: raceId !== null,
        refetchInterval: mode === 'demo' ? false : POLLING_INTERVALS.odds,
        staleTime: mode === 'demo' ? Infinity : 0,
      },
      { queryKey: ['steamers', mode], queryFn: mode === 'demo' ? () => Promise.resolve(DEMO_STEAMERS) : api.getSteamers, refetchInterval: mode === 'demo' ? false : POLLING_INTERVALS.signals, staleTime: mode === 'demo' ? Infinity : 0 },
      { queryKey: ['drifters', mode], queryFn: mode === 'demo' ? () => Promise.resolve(DEMO_DRIFTERS) : api.getDrifters, refetchInterval: mode === 'demo' ? false : POLLING_INTERVALS.signals, staleTime: mode === 'demo' ? Infinity : 0 },
      { queryKey: ['smart-money', mode], queryFn: mode === 'demo' ? () => Promise.resolve(DEMO_SMART_MONEY) : api.getSmartMoney, refetchInterval: mode === 'demo' ? false : POLLING_INTERVALS.signals, staleTime: mode === 'demo' ? Infinity : 0 },
      { queryKey: ['patterns', mode], queryFn: mode === 'demo' ? () => Promise.resolve(DEMO_PATTERNS) : api.getDiscoveryPatterns, refetchInterval: mode === 'demo' ? false : POLLING_INTERVALS.signals, staleTime: mode === 'demo' ? Infinity : 0 },
      { queryKey: ['intelligence-leaderboard', mode], queryFn: mode === 'demo' ? () => Promise.resolve(DEMO_INTELLIGENCE_LEADERBOARD) : () => api.getIntelligenceLeaderboard(today), refetchInterval: mode === 'demo' ? false : POLLING_INTERVALS.signals, staleTime: mode === 'demo' ? Infinity : 0 },
      { queryKey: ['signal-performance', mode], queryFn: mode === 'demo' ? () => Promise.resolve(DEMO_SIGNAL_PERFORMANCE) : () => api.getSignalPerformance(), refetchInterval: mode === 'demo' ? false : POLLING_INTERVALS.barriers, staleTime: mode === 'demo' ? Infinity : 0 },
    ],
  })

  const movers = useMemo(() => {
    return (odds.data?.entries ?? [])
      .map((entry) => {
        const firstWin = entry.snapshots.find((snapshot) => snapshot.win_price !== null)?.win_price ?? null
        const lastWin = [...entry.snapshots].reverse().find((snapshot) => snapshot.win_price !== null)?.win_price ?? null
        const movementPct = firstWin && lastWin ? ((lastWin - firstWin) / firstWin) * 100 : 0
        return {
          runner: entry.runner_name,
          movementPct,
          direction: movementPct < 0 ? 'steaming' : 'drifting',
        }
      })
      .sort((a, b) => Math.abs(b.movementPct) - Math.abs(a.movementPct))
      .slice(0, 8)
  }, [odds.data])

  const intellScores = intelligence.data ?? []
  const topIntelScores = intellScores.slice(0, 8)

  return (
    <div className="space-y-4">
      <SectionHeader title="Signals" subtitle="BETMAN intelligence layer: proprietary scores, market edge, and odds movement." />

      {/* ── BETMAN Intelligence showcase ── */}
      <Card className="relative overflow-hidden border-cyan-900/40 bg-gradient-to-br from-slate-950 to-slate-900/90">
        <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-cyan-500/8 blur-3xl" />
        <div className="absolute -left-12 bottom-0 h-40 w-40 rounded-full bg-violet-500/8 blur-2xl" />
        <div className="relative z-10">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-500/20 ring-1 ring-cyan-500/40">
              <Sparkles className="h-4 w-4 text-cyan-400" />
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.35em] text-cyan-400">BETMAN Intelligence</p>
              <h3 className="text-lg font-semibold text-white">Proprietary scoring engine — where we see edge the market doesn't</h3>
            </div>
          </div>
          <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_1.4fr]">
            {/* Alpha / Value leaderboard */}
            <div>
              <p className="mb-3 text-sm font-medium text-slate-300">Alpha leaderboard — top-scored runners today</p>
              <div className="space-y-2" role="list" aria-label="Alpha leaderboard — top-scored runners today">
                {topIntelScores.slice(0, 6).map((horse, index) => {
                  const edge = (horse.betman_probability ?? 0) - (horse.implied_probability ?? 0)
                  const edgePositive = edge > 0
                  return (
                    <div
                      key={horse.race_entry_id}
                      className="flex items-center gap-3 rounded-lg border border-slate-800 bg-slate-900/70 px-3 py-2"
                      role="listitem"
                      aria-label={`${horse.runner_name}, alpha score ${horse.alpha_score?.toFixed(1) ?? 'N/A'}, edge ${edgePositive ? '+' : ''}${edge.toFixed(1)}%`}
                    >
                      <span className="w-5 text-xs font-bold text-cyan-500" aria-hidden="true">#{index + 1}</span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2">
                          <h4 className="truncate text-sm font-semibold text-white">{horse.runner_name}</h4>
                          <span className="shrink-0 text-xs text-slate-400" aria-label={`Alpha score ${horse.alpha_score?.toFixed(1) ?? 'N/A'}`}>α {horse.alpha_score?.toFixed(1)}</span>
                        </div>
                        <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
                          <div
                            className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-violet-500"
                            style={{ width: `${Math.min(100, (horse.alpha_score ?? 0))}%` }}
                          />
                        </div>
                        <div className="mt-1 flex items-center gap-2 text-[10px]">
                          <span className="text-slate-500">Market {formatPercent(horse.implied_probability ?? 0)}</span>
                          <span className={cn('font-semibold', edgePositive ? 'text-emerald-400' : 'text-rose-400')}>
                            BETMAN {formatPercent(horse.betman_probability ?? 0)} {edgePositive ? '↑' : '↓'}
                          </span>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className={cn('text-sm font-bold', edgePositive ? 'text-emerald-400' : 'text-rose-400')}>
                          {edgePositive ? '+' : ''}{edge.toFixed(1)}%
                        </div>
                        <div className="text-[10px] text-slate-500">edge</div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
            {/* BETMAN edge chart */}
            <div>
              <p className="mb-3 text-sm font-medium text-slate-300">BETMAN probability vs market-implied probability</p>
              <div className="h-[320px] rounded-xl border border-cyan-900/30 bg-slate-950/60 p-2">
                <ReactECharts option={buildIntelligenceEdgeChart(topIntelScores)} style={{ height: '100%' }} />
              </div>
            </div>
          </div>
          {/* Signal performance ROI strip */}
          {(signalPerf.data as SignalPerformanceItem[] | undefined)?.length ? (
            <div className="mt-4 grid gap-3 border-t border-slate-800/60 pt-4 sm:grid-cols-4">
              {(signalPerf.data as SignalPerformanceItem[]).map((sp) => (
                <div key={sp.signal_type} className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
                  <div className="text-xs uppercase tracking-[0.2em] text-slate-500">{sp.signal_type}</div>
                  <div className={cn('mt-1 text-lg font-bold', (sp.roi ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400')}>
                    {(sp.roi ?? 0) >= 0 ? '+' : ''}{sp.roi?.toFixed(1)}% ROI
                  </div>
                  <div className="mt-0.5 text-xs text-slate-400">
                    {sp.strike_rate?.toFixed(1)}% SR • {sp.bets} bets
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-4">
        <MetricCard label="Steamers" value={formatNumber(steamers.data?.length)} tone="cyan" />
        <MetricCard label="Drifters" value={formatNumber(drifters.data?.length)} tone="rose" />
        <MetricCard label="Smart money" value={formatNumber(smartMoney.data?.length)} tone="violet" />
        <MetricCard label="Patterns" value={formatNumber(patterns.data?.length)} tone="indigo" />
      </div>
      <div className="grid gap-4 lg:grid-cols-[0.95fr_1.05fr]">
        <Card>
          <PanelTitle title="Race focus" subtitle="Pick a race and watch runner price curves react." />
          <div className="mt-4 grid gap-3">
            <Select value={raceId?.toString() ?? ''} onChange={(event) => setSelectedRaceId(Number(event.target.value))}>
              {(races.data?.races ?? []).map((race) => (
                <option key={race.id} value={race.id}>
                  {race.meeting.track_name} R{race.race_number} • {race.name ?? 'Unnamed race'}
                </option>
              ))}
            </Select>
            <div className="grid gap-2">
              {movers.length ? (
                movers.map((mover) => (
                  <div key={mover.runner} className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900/70 px-3 py-2 text-sm">
                    <span className="font-medium text-white">{mover.runner}</span>
                    <span className={cn('rounded-full px-2 py-0.5 text-xs', mover.direction === 'steaming' ? 'bg-cyan-500/20 text-cyan-300' : 'bg-rose-500/20 text-rose-300')}>
                      {mover.direction} {formatPercent(Math.abs(mover.movementPct))}
                    </span>
                  </div>
                ))
              ) : (
                <EmptyState title="Awaiting movement" description="When odds snapshots arrive, top movers appear here." />
              )}
            </div>
          </div>
        </Card>
        <Card>
          <PanelTitle title="Odds movement matrix" subtitle="Win and place curves per runner with trend highlights." />
          <div className="mt-4 h-[420px]">
            {odds.isLoading ? <ChartSkeleton /> : <ReactECharts option={buildLiveOddsMovementChart(odds.data)} style={{ height: '100%' }} />}
          </div>
        </Card>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <PanelTitle title="Signal stream" subtitle="Latest market calls." />
          <div className="mt-4 space-y-2">
            {[...(steamers.data ?? []), ...(drifters.data ?? []), ...(smartMoney.data ?? [])].slice(0, 10).map((item, index) => (
              <div key={`${item.runner_name ?? 'signal'}-${index}`} className="rounded-lg border border-slate-800 bg-slate-900/70 p-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-white">{item.runner_name ?? 'Signal'}</span>
                  <span className="text-cyan-300">{getSignalType(item)}</span>
                </div>
                <div className="mt-1 text-xs text-slate-400">{formatDateTime(item.detected_at)}</div>
              </div>
            ))}
          </div>
        </Card>
        <Card>
          <PanelTitle title="Discovery board" subtitle="AI-discovered pattern opportunities." />
          <div className="mt-4 space-y-2">
            {(patterns.data ?? []).slice(0, 8).map((item) => (
              <div key={`${item.id ?? item.description}`} className="rounded-lg border border-slate-800 bg-slate-900/70 p-3">
                <div className="text-sm font-medium text-white">{item.description ?? item.pattern_type ?? 'Pattern'}</div>
                <div className="mt-1 text-xs text-slate-400">ROI {formatPercent(item.roi ?? 0)} • confidence {formatPercent((item.confidence ?? 0) * 100)}</div>
              </div>
            ))}
            {!patterns.data?.length ? <EmptyState title="No live patterns" description="Pattern runs will populate this board once discovery jobs complete." /> : null}
          </div>
        </Card>
      </div>
    </div>
  )
}

function GatesView() {
  const { mode } = useMode()
  const tracks = useQuery({
    queryKey: ['tracks', mode],
    queryFn: mode === 'demo' ? () => Promise.resolve(DEMO_TRACKS) : api.getTracks,
    staleTime: mode === 'demo' ? Infinity : 0,
  })
  const [trackName, setTrackName] = useState<string>('')
  const [surface, setSurface] = useState<string>('turf')
  const [conditionCategory, setConditionCategory] = useState<string>('all')
  const [distancePreset, setDistancePreset] = useState<string>('all')

  const selectedTrack = trackName || tracks.data?.tracks[0]?.track_name || ''
  const selectedDistance = distancePresets.find((preset) => preset.key === distancePreset) ?? distancePresets[0]

  const [barriers, heatmap] = useQueries({
    queries: [
      {
        queryKey: ['barriers', selectedTrack, surface, conditionCategory, selectedDistance.key, mode],
        queryFn: mode === 'demo'
          ? () => Promise.resolve(DEMO_BARRIERS)
          : () => api.getBarrierAnalysis(selectedTrack, {
              surface,
              condition_category: conditionCategory === 'all' ? undefined : conditionCategory,
              distance_min: selectedDistance.min,
              distance_max: selectedDistance.max,
            }),
        enabled: selectedTrack.length > 0,
        refetchInterval: mode === 'demo' ? false : POLLING_INTERVALS.barriers,
        staleTime: mode === 'demo' ? Infinity : 0,
      },
      {
        queryKey: ['heatmap', selectedTrack, surface, conditionCategory, mode],
        queryFn: mode === 'demo'
          ? () => Promise.resolve(DEMO_HEATMAP)
          : () => api.getHeatmap(selectedTrack, {
              surface,
              condition_category: conditionCategory === 'all' ? undefined : conditionCategory,
            }),
        enabled: selectedTrack.length > 0,
        refetchInterval: mode === 'demo' ? false : POLLING_INTERVALS.barriers,
        staleTime: mode === 'demo' ? Infinity : 0,
      },
    ],
  })

  return (
    <div className="space-y-4">
      <SectionHeader title="Gates" subtitle="Barrier heat intelligence by track, surface, and distance context." />
      <Card>
        <div className="grid gap-3 lg:grid-cols-4">
          <Select value={selectedTrack} onChange={(event) => setTrackName(event.target.value)}>
            {(tracks.data?.tracks ?? []).map((track) => (
              <option key={track.track_name} value={track.track_name}>{track.track_name}</option>
            ))}
          </Select>
          <Select value={surface} onChange={(event) => setSurface(event.target.value)}>
            <option value="turf">Turf</option>
            <option value="synthetic">Synthetic</option>
            <option value="dirt">Dirt</option>
          </Select>
          <Select value={conditionCategory} onChange={(event) => setConditionCategory(event.target.value)}>
            <option value="all">All conditions</option>
            <option value="firm">Firm</option>
            <option value="good">Good</option>
            <option value="soft">Soft</option>
            <option value="heavy">Heavy</option>
          </Select>
          <Select value={distancePreset} onChange={(event) => setDistancePreset(event.target.value)}>
            {distancePresets.map((preset) => (
              <option key={preset.key} value={preset.key}>{preset.label}</option>
            ))}
          </Select>
        </div>
      </Card>
      <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
        <Card>
          <PanelTitle title="Barrier performance heatmap" subtitle="Win and place intensity by gate." />
          <div className="mt-4 h-[360px]">
            {barriers.isLoading ? <ChartSkeleton /> : <ReactECharts option={buildBarrierHeatmapChart(barriers.data)} style={{ height: '100%' }} />}
          </div>
        </Card>
        <Card>
          <PanelTitle title="Track zone heatmap" subtitle="Zone intensity by finish split." />
          <div className="mt-4 h-[360px]">
            {heatmap.isLoading ? <ChartSkeleton /> : <ReactECharts option={buildTrackHeatmapChart(heatmap.data)} style={{ height: '100%' }} />}
          </div>
        </Card>
      </div>
      <div className="grid gap-4 lg:grid-cols-[0.95fr_1.05fr]">
        <Card>
          <PanelTitle title="Barrier leaderboard" subtitle="Live sortable panel for gate edge." />
          <div className="mt-4 h-[240px]">
            <Grid
              rows={barriers.data?.barriers ?? []}
              columns={[
                { field: 'barrier_number', headerName: 'Gate' },
                { field: 'win_rate', headerName: 'Win %' },
                { field: 'place_rate', headerName: 'Place %' },
                { field: 'total_runners', headerName: 'Sample' },
              ]}
            />
          </div>
        </Card>
        <Card>
          <PanelTitle title="Barrier trend" subtitle="Win vs place rate profile." />
          <div className="mt-4 h-[260px]">
            <ReactECharts option={buildBarrierChart(barriers.data)} style={{ height: '100%' }} />
          </div>
        </Card>
      </div>
    </div>
  )
}

function PeopleView() {
  const { mode } = useMode()
  const tracks = useQuery({
    queryKey: ['people-tracks', mode],
    queryFn: mode === 'demo' ? () => Promise.resolve(DEMO_TRACKS) : api.getTracks,
    staleTime: mode === 'demo' ? Infinity : 0,
  })
  const [trackName, setTrackName] = useState<string>('')
  const [trainerRates, jockeyRates] = useQueries({
    queries: [
      {
        queryKey: ['trainer-rates', trackName, mode],
        queryFn: mode === 'demo' ? () => Promise.resolve(DEMO_TRAINERS) : () => api.getTrainerWinRates({ track: trackName || undefined, limit: 20 }),
        refetchInterval: mode === 'demo' ? false : POLLING_INTERVALS.people,
        staleTime: mode === 'demo' ? Infinity : 0,
      },
      {
        queryKey: ['jockey-rates', trackName, mode],
        queryFn: mode === 'demo' ? () => Promise.resolve(DEMO_JOCKEYS) : () => api.getJockeyWinRates({ track: trackName || undefined, limit: 20 }),
        refetchInterval: mode === 'demo' ? false : POLLING_INTERVALS.people,
        staleTime: mode === 'demo' ? Infinity : 0,
      },
    ],
  })

  const topTrainer = trainerRates.data?.items[0]
  const topJockey = jockeyRates.data?.items[0]

  return (
    <div className="space-y-4">
      <SectionHeader title="People" subtitle="Trainer and jockey leaderboards with visual win-rate context." />
      <Card className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <PanelTitle title="Filter context" subtitle="Track-level splits with live recalculation." />
        <div className="w-full max-w-sm">
          <Select value={trackName} onChange={(event) => setTrackName(event.target.value)}>
            <option value="">All tracks</option>
            {(tracks.data?.tracks ?? []).map((track) => (
              <option key={track.track_name} value={track.track_name}>{track.track_name}</option>
            ))}
          </Select>
        </div>
      </Card>
      <div className="grid gap-4 lg:grid-cols-4">
        <MetricCard label="Top trainer" value={topTrainer?.person ?? 'Awaiting data'} tone="cyan" />
        <MetricCard label="Trainer win rate" value={topTrainer ? formatPercent(topTrainer.win_rate) : '—'} tone="teal" />
        <MetricCard label="Top jockey" value={topJockey?.person ?? 'Awaiting data'} tone="indigo" />
        <MetricCard label="Jockey win rate" value={topJockey ? formatPercent(topJockey.win_rate) : '—'} tone="violet" />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <PeoplePanel title="Trainer board" data={trainerRates.data} />
        <PeoplePanel title="Jockey board" data={jockeyRates.data} />
      </div>
    </div>
  )
}

function AskBetmanView() {
  const { mode } = useMode()
  const [question, setQuestion] = useState(DEMO_EXAMPLE_QUESTIONS[0])
  const [activeQuery, setActiveQuery] = useState('')
  const [demoResult, setDemoResult] = useState<AssistantResponse | undefined>(undefined)
  const [isThinking, setIsThinking] = useState(false)

  const mutation = useMutation({ mutationFn: api.askBetman })

  const [ocrResults, transcriptResults] = useQueries({
    queries: [
      {
        queryKey: ['search-ocr', activeQuery],
        queryFn: () => api.searchOcr(activeQuery, 6),
        enabled: activeQuery.length > 0 && mode === 'live',
      },
      {
        queryKey: ['search-transcripts', activeQuery],
        queryFn: () => api.searchTranscripts(activeQuery, 6),
        enabled: activeQuery.length > 0 && mode === 'live',
      },
    ],
  })

  const runQuery = () => {
    if (!question.trim()) return
    setActiveQuery(question)
    if (mode === 'demo') {
      setIsThinking(true)
      setDemoResult(undefined)
      setTimeout(() => {
        const q = question.trim().toLowerCase()
        const match = Object.entries(DEMO_ANSWERS).find(([key]) => key.toLowerCase() === q)
        const result = match ? match[1] : DEMO_ANSWERS[DEMO_EXAMPLE_QUESTIONS[0]]
        setDemoResult({ ...result, question })
        setIsThinking(false)
      }, 1600)
    } else {
      mutation.mutate(question)
    }
  }

  const activeResult = mode === 'demo' ? demoResult : mutation.data
  const isPending = mode === 'demo' ? isThinking : mutation.isPending

  return (
    <div className="space-y-4">
      <SectionHeader title="Ask BETMAN" subtitle="BETMAN's AI/LLM core — natural-language questions answered with evidence, confidence, and live charts." />
      <Card className="space-y-4 border-cyan-900/40 bg-gradient-to-br from-slate-950 to-slate-900/90">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-500/20 ring-1 ring-cyan-500/40">
            <Search className="h-4 w-4 text-cyan-400" />
          </div>
          <PanelTitle title="Natural-language analysis" subtitle="BETMAN synthesises SQL, executes against the warehouse, and narrates the answer." />
        </div>
        <div className="grid gap-3 lg:grid-cols-[1fr_auto]">
          <Input value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => event.key === 'Enter' && runQuery()} />
          <Button onClick={runQuery} disabled={isPending}>{isPending ? 'Analysing…' : 'Ask BETMAN'}</Button>
        </div>
        <div className="flex flex-wrap gap-2">
          {DEMO_EXAMPLE_QUESTIONS.map((example) => (
            <button
              key={example}
              type="button"
              className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300 transition hover:border-cyan-500 hover:text-cyan-300"
              onClick={() => { setQuestion(example); }}
            >
              {example}
            </button>
          ))}
        </div>
      </Card>
      <ErrorBanner error={mode === 'live' ? mutation.error : null} />
      {isPending ? (
        <Card className="border-cyan-900/40 bg-gradient-to-br from-slate-950 to-slate-900/90">
          <div className="flex items-center gap-3 py-2">
            <div className="flex gap-1">
              {[0, 1, 2].map((i) => (
                <span
                  key={i}
                  className="h-2 w-2 animate-bounce rounded-full bg-cyan-400"
                  style={{ animationDelay: `${i * 0.15}s` }}
                />
              ))}
            </div>
            <span className="text-sm text-cyan-300">BETMAN is reasoning across the warehouse…</span>
          </div>
          <div className="mt-3 space-y-2">
            <div className="h-2 w-3/4 animate-pulse rounded bg-slate-800" />
            <div className="h-2 w-1/2 animate-pulse rounded bg-slate-800" />
            <div className="h-2 w-2/3 animate-pulse rounded bg-slate-800" />
          </div>
        </Card>
      ) : null}
      <AssistantResult result={activeResult} supportHits={(ocrResults.data?.results ?? []).concat(transcriptResults.data?.results ?? [])} />
    </div>
  )
}

function AssistantResult({ result, supportHits }: { result?: AssistantResponse; supportHits: Array<Record<string, unknown>> }) {
  if (!result) {
    return (
      <Card className="border-dashed border-slate-700 bg-slate-900/30">
        <div className="py-6 text-center">
          <Search className="mx-auto mb-3 h-8 w-8 text-slate-600" />
          <div className="text-sm font-medium text-white">Ask BETMAN anything about the race data</div>
          <p className="mt-1 text-sm text-slate-400">Try one of the example prompts above, or type your own question.</p>
        </div>
      </Card>
    )
  }

  const columnNames = Object.keys(result.rows[0] ?? {})
  const chartOption = buildAssistantChart(result)
  const confidencePct = Math.round(result.confidence * 100)
  const confidenceColor = confidencePct >= 85 ? 'emerald' : confidencePct >= 70 ? 'cyan' : 'amber'

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
      <Card>
        <div className="flex items-start justify-between gap-4">
          <PanelTitle title="BETMAN analysis" subtitle={`Provider: ${result.provider}`} />
          <div className="shrink-0 text-right">
            <div className="text-xs uppercase tracking-[0.2em] text-slate-500">Confidence</div>
            <div className={cn('text-2xl font-bold', confidenceColor === 'emerald' ? 'text-emerald-400' : confidenceColor === 'cyan' ? 'text-cyan-400' : 'text-amber-400')}>
              {confidencePct}%
            </div>
            <div className="mt-1 h-1.5 w-16 overflow-hidden rounded-full bg-slate-800">
              <div
                className={cn('h-full rounded-full transition-all duration-700', confidenceColor === 'emerald' ? 'bg-emerald-400' : confidenceColor === 'cyan' ? 'bg-cyan-400' : 'bg-amber-400')}
                style={{ width: `${confidencePct}%` }}
              />
            </div>
          </div>
        </div>
        <div className="mt-4 rounded-lg border border-cyan-900/40 bg-cyan-500/5 p-3 text-sm text-slate-200 italic">"{result.question}"</div>
        <p className="mt-3 text-sm leading-relaxed text-slate-300">{result.summary}</p>
        <details className="mt-4 rounded-lg border border-slate-800 bg-slate-900/60 p-3">
          <summary className="cursor-pointer text-sm text-cyan-300">Show reasoning (generated SQL)</summary>
          <pre className="mt-3 overflow-x-auto text-xs text-slate-300">{result.sql}</pre>
        </details>
      </Card>
      <Card>
        <PanelTitle title="Supporting chart" subtitle={result.chart.type} />
        <div className="mt-4 h-[320px]">
          <ReactECharts option={chartOption} style={{ height: '100%' }} />
        </div>
      </Card>
      <Card>
        <PanelTitle title="Key entities" subtitle="Top surfaced dimensions from answer rows." />
        <div className="mt-4 grid gap-2">
          {columnNames.slice(0, 5).map((name) => (
            <div key={name} className="rounded-lg border border-slate-800 bg-slate-900/70 px-3 py-2 text-sm">
              <span className="text-slate-400">{name}</span>
              <span className="ml-2 text-white">{String(result.rows[0]?.[name] ?? '—')}</span>
            </div>
          ))}
        </div>
      </Card>
      <Card>
        <PanelTitle title="Context hits" subtitle="Search endpoint companion results." />
        <div className="mt-4 space-y-2">
          {supportHits.length ? (
            supportHits.slice(0, 6).map((hit, index) => (
              <div key={index} className="rounded-lg border border-slate-800 bg-slate-900/70 p-3 text-sm text-slate-300">
                {formatSupportHit(hit)}
              </div>
            ))
          ) : (
            <EmptyState title="No extra context" description="Search indexes are ready; related hits will appear when populated." />
          )}
        </div>
      </Card>
      <Card className="lg:col-span-2">
        <PanelTitle title="Result grid" subtitle={`${result.rows.length} rows`} />
        <div className="mt-4 h-[320px]">
          <Grid rows={result.rows} columns={columnNames.map((name) => ({ field: name, headerName: name }))} />
        </div>
      </Card>
    </div>
  )
}

function PeoplePanel({ title, data }: { title: string; data?: PeopleResponse }) {
  const top = (data?.items ?? []).slice(0, 3)
  return (
    <Card>
      <PanelTitle title={title} subtitle="Win %, place %, ROI, and ranking momentum." />
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        {top.length
          ? top.map((item, index) => (
              <div key={item.person} className="rounded-lg border border-slate-800 bg-slate-900/70 p-3">
                <div className="text-xs uppercase tracking-[0.22em] text-cyan-400">#{index + 1}</div>
                <div className="mt-1 text-sm font-semibold text-white">{item.person}</div>
                <div className="mt-1 text-xs text-slate-400">Win {formatPercent(item.win_rate)} • ROI {formatPercent(item.roi ?? 0)}</div>
              </div>
            ))
          : [1, 2, 3].map((placeholder) => <LoadingTile key={placeholder} />)}
      </div>
      <div className="mt-4 h-[260px]">
        <ReactECharts option={buildPeopleChart(data)} style={{ height: '100%' }} />
      </div>
      <div className="mt-4 h-[220px]">
        <Grid
          rows={data?.items ?? []}
          columns={[
            { field: 'person', headerName: 'Name' },
            { field: 'runners', headerName: 'Runners' },
            { field: 'wins', headerName: 'Wins' },
            { field: 'win_rate', headerName: 'Win %' },
            { field: 'roi', headerName: 'ROI %' },
          ]}
        />
      </div>
    </Card>
  )
}

function Grid({
  rows,
  columns,
}: {
  rows: Array<Record<string, unknown>>
  columns: Array<ColDef<Record<string, unknown>>>
}) {
  return (
    <div className="ag-theme-quartz-dark h-full w-full overflow-hidden rounded-lg border border-slate-800">
      <AgGridReact rowData={rows} columnDefs={columns} pagination={rows.length > 12} domLayout="normal" />
    </div>
  )
}

function MetricCard({
  label,
  value,
  loading = false,
  tone = 'cyan',
}: {
  label: string
  value: string
  loading?: boolean
  tone?: 'cyan' | 'teal' | 'indigo' | 'rose' | 'violet' | 'emerald' | 'amber'
}) {
  const toneClass = {
    cyan: 'from-cyan-500/20 to-cyan-500/0 border-cyan-900/40',
    teal: 'from-teal-500/20 to-teal-500/0 border-teal-900/40',
    indigo: 'from-indigo-500/20 to-indigo-500/0 border-indigo-900/40',
    rose: 'from-rose-500/20 to-rose-500/0 border-rose-900/40',
    violet: 'from-violet-500/20 to-violet-500/0 border-violet-900/40',
    emerald: 'from-emerald-500/20 to-emerald-500/0 border-emerald-900/40',
    amber: 'from-amber-500/20 to-amber-500/0 border-amber-900/40',
  }[tone]

  return (
    <Card className={cn('bg-gradient-to-br transition hover:-translate-y-0.5 hover:shadow-[0_0_20px_rgba(34,211,238,0.12)]', toneClass)}>
      <div className="text-xs uppercase tracking-[0.3em] text-slate-400">{label}</div>
      <div className="mt-2 text-3xl font-semibold text-white">{loading ? '…' : value}</div>
    </Card>
  )
}

function SmallStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3 transition hover:border-cyan-800/80">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">{label}</div>
      <div className="mt-1 text-sm text-slate-200">{value}</div>
    </div>
  )
}

function PanelTitle({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div>
      <h2 className="text-lg font-semibold text-white">{title}</h2>
      <p className="text-sm text-slate-400">{subtitle}</p>
    </div>
  )
}

function SectionHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="space-y-1">
      <h2 className="text-2xl font-semibold text-white">{title}</h2>
      <p className="text-sm text-slate-400">{subtitle}</p>
    </div>
  )
}

function ConnectionStatus({
  mode,
  socketConnected,
  health,
  error,
}: {
  mode: 'demo' | 'live'
  socketConnected: boolean
  health?: HealthResponse
  error: Error | null
}) {
  if (mode === 'demo') {
    return <div className="text-xs uppercase tracking-[0.25em] text-cyan-400">Demo mode — bundled fixtures active</div>
  }

  const connected = !error && health?.status === 'ok'
  return (
    <div
      className={cn(
        'inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em]',
        connected
          ? 'bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30'
          : 'bg-rose-500/15 text-rose-300 ring-1 ring-rose-500/30',
      )}
    >
      <span aria-hidden="true">{connected ? '●' : '○'}</span>
      {connected
        ? `Live connected${socketConnected ? ' via websocket' : ' via polling'}`
        : 'Live API unreachable'}
    </div>
  )
}

function ErrorBanner({ error }: { error: Error | null }) {
  if (!error) return null
  return <div className="rounded-lg border border-rose-900 bg-rose-950/40 p-3 text-sm text-rose-200">{error.message}</div>
}

function EmptyState({
  title,
  description,
  action,
}: {
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <div className="rounded-lg border border-dashed border-slate-700 bg-slate-900/30 p-4">
      <div className="text-sm font-medium text-white">{title}</div>
      <p className="mt-1 text-sm text-slate-400">{description}</p>
      {action ? <div className="mt-3">{action}</div> : null}
    </div>
  )
}

function ChartSkeleton() {
  return <div className="h-full w-full animate-pulse rounded-lg border border-slate-800 bg-slate-900/60" />
}

function LoadingTile() {
  return <div className="h-[86px] animate-pulse rounded-lg border border-slate-800 bg-slate-900/60" />
}

function useLiveSocket(mode: 'demo' | 'live', queryClient: ReturnType<typeof useQueryClient>) {
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    if (mode !== 'live') {
      setConnected(false)
      return
    }

    const socket = new WebSocket(buildLiveWebSocketUrl(1))
    socket.onopen = () => setConnected(true)
    socket.onclose = () => setConnected(false)
    socket.onerror = () => setConnected(false)
    socket.onmessage = () => {
      queryClient.invalidateQueries({ queryKey: ['meetings'] })
      queryClient.invalidateQueries({ queryKey: ['races'] })
      queryClient.invalidateQueries({ queryKey: ['stats-overview'] })
    }

    return () => socket.close()
  }, [mode, queryClient])

  return { connected }
}

function buildWarehouseChart(data?: StatsOverview) {
  const topTables = [...(data?.tables ?? [])].slice(0, 10).reverse()
  return {
    backgroundColor: 'transparent',
    xAxis: {
      type: 'value',
      axisLabel: { color: '#94a3b8', formatter: (value: number) => formatBytes(value) },
      splitLine: { lineStyle: { color: '#1e293b' } },
    },
    yAxis: { type: 'category', axisLabel: { color: '#e2e8f0' }, data: topTables.map((table) => table.table_name) },
    series: [
      {
        type: 'bar',
        data: topTables.map((table) => table.total_bytes),
        itemStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 1,
            y2: 0,
            colorStops: [
              { offset: 0, color: '#0ea5e9' },
              { offset: 1, color: '#22d3ee' },
            ],
          },
          borderRadius: [0, 8, 8, 0],
        },
      },
    ],
    grid: { top: 12, left: 140, right: 24, bottom: 18 },
    tooltip: { trigger: 'axis' },
    animationDuration: 700,
  }
}

function buildOverviewPulseChart(points: number[]) {
  const data = points.length ? points : [0]
  return {
    backgroundColor: 'transparent',
    title: { text: 'Ingestion pulse', left: 12, top: 8, textStyle: { color: '#e2e8f0', fontSize: 14, fontWeight: 600 } },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: data.map((_, index) => `T-${data.length - index}`), axisLabel: { color: '#64748b' }, boundaryGap: false },
    yAxis: { type: 'value', axisLabel: { color: '#64748b' }, splitLine: { lineStyle: { color: '#1e293b' } } },
    series: [
      {
        name: 'Events',
        type: 'line',
        smooth: true,
        showSymbol: false,
        data,
        lineStyle: { width: 3, color: '#22d3ee' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(34,211,238,0.45)' },
              { offset: 1, color: 'rgba(34,211,238,0.05)' },
            ],
          },
        },
      },
    ],
    grid: { left: 44, right: 20, top: 48, bottom: 28 },
    animationDuration: 600,
  }
}

function buildOddsChart(data?: OddsResponse) {
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: { textStyle: { color: '#cbd5e1' } },
    xAxis: {
      type: 'category',
      data: data?.entries[0]?.snapshots.map((snapshot) => `${Math.round(snapshot.offset_ms / 60000)}m`) ?? [],
      axisLabel: { color: '#94a3b8' },
    },
    yAxis: { type: 'value', axisLabel: { color: '#94a3b8' } },
    series: (data?.entries ?? []).slice(0, 6).map((entry) => ({ name: entry.runner_name, type: 'line', smooth: true, data: entry.snapshots.map((snapshot) => snapshot.win_price) })),
    grid: { left: 40, right: 20, top: 40, bottom: 30 },
  }
}

function buildLiveOddsMovementChart(data?: OddsResponse) {
  const entries = (data?.entries ?? []).filter((entry) => entry.snapshots.length > 0).slice(0, 4)
  const series = entries.flatMap((entry) => {
    const firstWin = entry.snapshots.find((snapshot) => snapshot.win_price !== null)?.win_price
    const lastWin = [...entry.snapshots].reverse().find((snapshot) => snapshot.win_price !== null)?.win_price
    const isSteaming = Boolean(firstWin && lastWin && lastWin < firstWin)
    const trendColor = isSteaming ? '#22d3ee' : '#fb7185'
    return [
      {
        name: `${entry.runner_name} (win)`,
        type: 'line',
        smooth: true,
        showSymbol: false,
        emphasis: { focus: 'series' },
        lineStyle: { width: 3, color: trendColor },
        areaStyle: { opacity: 0.1, color: trendColor },
        data: entry.snapshots
          .filter((snapshot) => snapshot.win_price !== null)
          .map((snapshot) => [snapshot.captured_at, snapshot.win_price]),
      },
      {
        name: `${entry.runner_name} (place)`,
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, type: 'dashed', color: isSteaming ? '#67e8f9' : '#fda4af' },
        data: entry.snapshots
          .filter((snapshot) => snapshot.place_price !== null)
          .map((snapshot) => [snapshot.captured_at, snapshot.place_price]),
      },
    ]
  })

  return {
    backgroundColor: 'transparent',
    legend: { top: 4, textStyle: { color: '#cbd5e1', fontSize: 11 } },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'time', axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { color: '#1e293b' } } },
    yAxis: { type: 'value', axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { color: '#1e293b' } } },
    series,
    grid: { top: 48, left: 48, right: 20, bottom: 34 },
    animationDuration: 700,
  }
}

function buildBarrierChart(data?: BarrierResponse) {
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: { textStyle: { color: '#cbd5e1' } },
    xAxis: { type: 'category', data: (data?.barriers ?? []).map((item) => item.barrier_number), axisLabel: { color: '#94a3b8' } },
    yAxis: { type: 'value', axisLabel: { color: '#94a3b8' } },
    series: [
      { name: 'Win %', type: 'bar', data: (data?.barriers ?? []).map((item) => item.win_rate), itemStyle: { color: '#22d3ee' } },
      { name: 'Place %', type: 'line', smooth: true, data: (data?.barriers ?? []).map((item) => item.place_rate), itemStyle: { color: '#a78bfa' }, lineStyle: { width: 3 } },
    ],
    grid: { left: 40, right: 24, top: 34, bottom: 24 },
  }
}

function buildBarrierHeatmapChart(data?: BarrierResponse) {
  const barriers = data?.barriers ?? []
  const values = barriers.flatMap((item, index) => [
    [index, 0, item.win_rate],
    [index, 1, item.place_rate],
  ])

  return {
    backgroundColor: 'transparent',
    tooltip: { position: 'top' },
    xAxis: {
      type: 'category',
      data: barriers.map((item) => `B${item.barrier_number}`),
      axisLabel: { color: '#94a3b8' },
      splitArea: { show: true, areaStyle: { color: ['rgba(15,23,42,0.4)', 'rgba(15,23,42,0.2)'] } },
    },
    yAxis: {
      type: 'category',
      data: ['Win %', 'Place %'],
      axisLabel: { color: '#cbd5e1' },
      splitArea: { show: true, areaStyle: { color: ['rgba(15,23,42,0.4)', 'rgba(15,23,42,0.2)'] } },
    },
    visualMap: {
      min: 0,
      max: barriers.reduce((max, item) => Math.max(max, item.place_rate), MIN_HEATMAP_SCALE),
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      textStyle: { color: '#cbd5e1' },
      inRange: { color: BARRIER_HEATMAP_COLORS },
    },
    series: [{ type: 'heatmap', data: values, label: { show: true, color: '#f8fafc', formatter: (params: { value: [number, number, number] }) => `${params.value[2].toFixed(1)}%` } }],
    grid: { top: 20, left: 56, right: 20, bottom: 72 },
    animationDuration: 600,
  }
}

function buildTrackHeatmapChart(data?: HeatmapResponse) {
  const cells = data?.cells ?? []
  const zones = Array.from(new Set(cells.map((cell) => cell.zone)))
  const splits = Array.from(new Set(cells.map((cell) => cell.distance_from_finish_band ?? 'all')))
  const matrix = cells.map((cell) => [zones.indexOf(cell.zone), splits.indexOf(cell.distance_from_finish_band ?? 'all'), cell.intensity * 100])

  return {
    backgroundColor: 'transparent',
    tooltip: {
      formatter: (params: { value: [number, number, number] }) => {
        const [zoneIndex, splitIndex, intensity] = params.value
        return `${zones[zoneIndex]} • ${splits[splitIndex]}<br/>Intensity: ${intensity.toFixed(1)}`
      },
    },
    xAxis: { type: 'category', data: zones, axisLabel: { color: '#94a3b8' } },
    yAxis: { type: 'category', data: splits, axisLabel: { color: '#94a3b8' } },
    visualMap: {
      min: 0,
      max: Math.max(100, ...matrix.map((item) => item[2])),
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      textStyle: { color: '#cbd5e1' },
      inRange: { color: TRACK_HEATMAP_COLORS },
    },
    series: [{ type: 'heatmap', data: matrix, label: { show: true, color: '#f8fafc', formatter: (params: { value: [number, number, number] }) => params.value[2].toFixed(0) } }],
    grid: { top: 12, left: 58, right: 20, bottom: 70 },
    animationDuration: 600,
  }
}

function buildPeopleChart(data?: PeopleResponse) {
  const items = (data?.items ?? []).slice(0, 10).reverse()
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: { textStyle: { color: '#cbd5e1' } },
    xAxis: { type: 'value', axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { color: '#1e293b' } } },
    yAxis: { type: 'category', axisLabel: { color: '#e2e8f0' }, data: items.map((item) => item.person) },
    series: [
      { name: 'Win %', type: 'bar', data: items.map((item) => item.win_rate), itemStyle: { color: '#06b6d4' } },
      { name: 'Place %', type: 'bar', data: items.map((item) => item.place_rate), itemStyle: { color: '#818cf8' } },
    ],
    grid: { left: 132, right: 20, top: 20, bottom: 20 },
  }
}

function buildAssistantChart(result: AssistantResponse) {
  if (!result.chart.x || !result.chart.y) {
    return {
      xAxis: { type: 'category', data: [] },
      yAxis: { type: 'value' },
      series: [{ type: 'bar', data: [] }],
    }
  }

  const xData = result.rows.map((row) => String(row[result.chart.x as keyof typeof row] ?? ''))
  const yData = result.rows.map((row) => Number(row[result.chart.y as keyof typeof row] ?? 0))
  const chartType = result.chart.type === 'line' ? 'line' : 'bar'

  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: xData, axisLabel: { color: '#94a3b8', rotate: xData.length > 8 ? 25 : 0 } },
    yAxis: { type: 'value', axisLabel: { color: '#94a3b8' } },
    series: [
      {
        type: chartType,
        smooth: chartType === 'line',
        data: yData,
        itemStyle: { color: '#22d3ee' },
        lineStyle: { width: 3, color: '#22d3ee' },
        areaStyle: chartType === 'line' ? { opacity: 0.14, color: '#22d3ee' } : undefined,
      },
    ],
    grid: { left: 40, right: 20, top: 20, bottom: 60 },
  }
}

function formatSupportHit(hit: Record<string, unknown>) {
  const preferredKeys = ['title', 'description', 'text', 'content', 'source', 'scene', 'date', 'track_name']
  const preferredParts = preferredKeys
    .map((key) => {
      const value = hit[key]
      return value === undefined || value === null || value === '' ? null : `${key.replace(/_/g, ' ')}: ${String(value)}`
    })
    .filter((value): value is string => Boolean(value))

  if (preferredParts.length > 0) {
    return preferredParts.join(' • ')
  }

  const fallbackEntries = Object.entries(hit)
    .slice(0, 3)
    .map(([key, value]) => `${key.replace(/_/g, ' ')}: ${String(value)}`)
  return fallbackEntries.length > 0 ? fallbackEntries.join(' • ') : DEFAULT_SUPPORT_HIT_TEXT
}

function buildIntelligenceEdgeChart(scores: HorseScores[]) {
  const items = scores.slice(0, 8)
  const names = items.map((s) => s.runner_name)
  const betmanProb = items.map((s) => Number((s.betman_probability ?? 0).toFixed(1)))
  const marketProb = items.map((s) => Number((s.implied_probability ?? 0).toFixed(1)))

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      formatter: (params: Array<{ seriesName: string; value: number; name: string }>) =>
        params.map((p) => `${p.seriesName}: ${p.value}%`).join('<br/>'),
    },
    legend: {
      data: ['BETMAN %', 'Market %'],
      top: 4,
      textStyle: { color: '#cbd5e1', fontSize: 11 },
    },
    xAxis: {
      type: 'category',
      data: names,
      axisLabel: { color: '#94a3b8', rotate: names.length > 5 ? 18 : 0, interval: 0, fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#94a3b8', formatter: (v: number) => `${v}%` },
      splitLine: { lineStyle: { color: '#1e293b' } },
    },
    series: [
      {
        name: 'BETMAN %',
        type: 'bar',
        data: betmanProb.map((v, i) => ({
          value: v,
          itemStyle: {
            color: v > marketProb[i]
              ? { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#22d3ee' }, { offset: 1, color: '#0ea5e9' }] }
              : { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#6366f1' }, { offset: 1, color: '#4338ca' }] },
          },
        })),
        barGap: '10%',
        label: { show: true, position: 'top', color: '#e2e8f0', fontSize: 10, formatter: (p: { value: number }) => `${p.value}%` },
        borderRadius: [4, 4, 0, 0],
      },
      {
        name: 'Market %',
        type: 'bar',
        data: marketProb,
        itemStyle: { color: 'rgba(148,163,184,0.35)', borderRadius: [4, 4, 0, 0] },
        label: { show: true, position: 'top', color: '#64748b', fontSize: 10, formatter: (p: { value: number }) => `${p.value}%` },
      },
    ],
    grid: { top: 48, left: 44, right: 20, bottom: names.length > 5 ? 68 : 34 },
    animationDuration: 800,
  }
}

export default App
