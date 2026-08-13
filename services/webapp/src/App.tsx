import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import { AllCommunityModule, ModuleRegistry, type ColDef, type ValueGetterParams } from 'ag-grid-community'
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { AgGridReact } from 'ag-grid-react'
import ReactECharts from 'echarts-for-react'
import { Database, Gauge, KeyRound, Map, Search, Sparkles, Users } from 'lucide-react'
import { NavLink, Route, Routes } from 'react-router-dom'

import { Button } from './components/ui/button'
import { Card } from './components/ui/card'
import { Input } from './components/ui/input'
import { Select } from './components/ui/select'
import {
  POLLING_INTERVALS,
  api,
  buildLiveWebSocketUrl,
  clearDataToken,
  getDataToken,
  loginWithData,
  setDataToken,
  type AssistantResponse,
  type BarrierResponse,
  type HealthResponse,
  type HeatmapResponse,
  type HorseScores,
  type OddsResponse,
  type PeopleResponse,
  type RaceDetail,
  type RacingPulseResponse,
  type SignalPerformanceItem,
  type StatsOverview,
  type WarehouseOverview,
  type WarehouseTable,
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

ModuleRegistry.registerModules([AllCommunityModule])

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
const DEFAULT_RACING_WINDOW_DAYS = 60
const DEFAULT_SUPPORT_HIT_TEXT = 'Search result item'
const BARRIER_HEATMAP_COLORS = ['#13293d', '#0ea5e9', '#22d3ee', '#67e8f9']
const TRACK_HEATMAP_COLORS = ['#1e1b4b', '#1d4ed8', '#0891b2', '#67e8f9']

function getSignalType(item: { signal_type?: string; indicator_type?: string; pattern_type?: string }) {
  return item.signal_type ?? item.indicator_type ?? item.pattern_type ?? 'signal'
}

function formatLocalDate(date: Date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function localDateDaysAgo(days: number) {
  const date = new Date()
  date.setDate(date.getDate() - days)
  return formatLocalDate(date)
}

function formatSurfaceLabel(surface: string | null) {
  if (!surface) return 'Unknown'
  return surface.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase())
}

function App() {
  const [token, setToken] = useState(() => getDataToken())
  if (!token) return <LoginPage onLogin={setToken} />
  return <AuthenticatedApp onLogout={() => {
    clearDataToken()
    setToken(null)
  }} />
}

function AuthenticatedApp({ onLogout }: { onLogout: () => void }) {
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
              <button
                type="button"
                onClick={onLogout}
                className="flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-900/80 px-3 py-2 text-sm text-slate-400 transition duration-300 hover:border-slate-700 hover:text-slate-100"
              >
                Sign out
              </button>
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

function LoginPage({ onLogin }: { onLogin: (token: string) => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [setupLoading, setSetupLoading] = useState(false)
  const [scrollFade, setScrollFade] = useState(1)

  useEffect(() => {
    const updateFade = () => {
      const progress = Math.min(window.scrollY / 260, 1)
      setScrollFade(1 - progress * 0.92)
    }
    updateFade()
    window.addEventListener('scroll', updateFade, { passive: true })
    return () => window.removeEventListener('scroll', updateFade)
  }, [])

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      const result = await loginWithData(username, password)
      setDataToken(result.access_token)
      onLogin(result.access_token)
    } catch {
      setError('Invalid username or password. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const requestPasswordSetup = async () => {
    setError('')
    const email = username.trim()
    if (!email) {
      setError('Enter your account email first, then choose Set password.')
      return
    }
    setSetupLoading(true)
    try {
      const response = await fetch('/password-setup-link', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ email }),
      })
      const result = await response.json().catch(() => ({}))
      if (!response.ok || result?.ok === false) {
        if (result?.error === 'subscription_required' && result?.paymentLink) {
          setError('Subscription required. Activate your plan from the signup page, then set your password.')
        } else if (result?.error === 'user_not_found') {
          setError('No Stripe account found for that email.')
        } else {
          setError(`Setup failed: ${result?.error || 'unknown_error'}.`)
        }
        return
      }
      if (result?.setupLink) {
        window.location.href = result.setupLink
        return
      }
      setError('Setup failed: no setup link returned.')
    } catch {
      setError('Setup unavailable. Please try again.')
    } finally {
      setSetupLoading(false)
    }
  }

  return (
    <div className="flex min-h-[145vh] items-start justify-center bg-gray-950 px-4 pt-[14vh] text-gray-100 sm:pt-[18vh]">
      <div
        className="w-full max-w-sm transition-[opacity,transform] duration-700 ease-out"
        style={{
          opacity: scrollFade,
          transform: `translateY(-${(1 - scrollFade) * 18}px)`,
          pointerEvents: scrollFade < 0.18 ? 'none' : 'auto',
        }}
      >
        <div className="mb-8 flex flex-col items-center">
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-orange-500/40 bg-orange-500/20">
            <Database className="h-7 w-7 text-orange-400" />
          </div>
          <h1 className="text-2xl font-bold tracking-wide text-white">
            BETMAN <span className="text-orange-400">Data</span>
          </h1>
          <p className="mt-1 text-sm text-gray-400">Sign in to continue</p>
          <p className="mt-1 text-xs font-bold uppercase tracking-wide text-gray-500">Private warehouse access</p>
        </div>

        <form onSubmit={submit} className="flex flex-col gap-5 rounded-xl border border-gray-800 bg-gray-900 p-6">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="username" className="text-sm font-medium text-gray-300">Username</label>
            <Input
              id="username"
              type="text"
              autoComplete="username"
              autoFocus
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              disabled={loading}
              placeholder="Enter your username"
              className="border-gray-700 bg-gray-800 text-white placeholder:text-gray-500 focus:border-orange-500 focus:ring-orange-500"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="password" className="text-sm font-medium text-gray-300">Password</label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              disabled={loading}
              placeholder="Enter your password"
              className="border-gray-700 bg-gray-800 text-white placeholder:text-gray-500 focus:border-orange-500 focus:ring-orange-500"
            />
          </div>
          {error ? <p className="rounded-lg border border-red-400/20 bg-red-400/10 px-3 py-2 text-sm text-red-400">{error}</p> : null}
          <button
            type="submit"
            disabled={loading || setupLoading || !username || !password}
            className="w-full rounded-lg bg-orange-500 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-orange-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
          <div className="border-t border-gray-800 pt-4 text-center">
            <p className="text-xs text-gray-400">New after Stripe checkout? Enter your email, then set your password.</p>
            <button
              type="button"
              onClick={requestPasswordSetup}
              disabled={loading || setupLoading || !username.trim()}
              className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-lg border border-orange-500/40 px-4 py-2.5 text-sm font-semibold text-orange-300 transition-colors hover:border-orange-400 hover:bg-orange-500/10 hover:text-orange-200"
            >
              <KeyRound className="h-4 w-4" />
              {setupLoading ? 'Requesting setup...' : 'Set password'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function OverviewView() {
  const { mode } = useMode()
  const pulseDateFrom = useMemo(() => localDateDaysAgo(DEFAULT_RACING_WINDOW_DAYS), [])
  const { data, isLoading, error } = useQuery({
    queryKey: ['stats-overview', mode],
    queryFn: mode === 'demo' ? () => Promise.resolve(DEMO_STATS_OVERVIEW) : api.getStatsOverview,
    refetchInterval: mode === 'demo' ? false : POLLING_INTERVALS.stats,
    staleTime: mode === 'demo' ? Infinity : 0,
  })
  const warehouse = useQuery({
    queryKey: ['warehouse-overview', mode],
    queryFn: mode === 'demo' ? () => Promise.resolve(null) : api.getWarehouseOverview,
    enabled: mode === 'live',
    refetchInterval: mode === 'demo' ? false : POLLING_INTERVALS.stats,
    staleTime: mode === 'demo' ? Infinity : 0,
  })
  const pulse = useQuery({
    queryKey: ['racing-pulse', pulseDateFrom, mode],
    queryFn: mode === 'demo' ? () => Promise.resolve(null) : () => api.getRacingPulse({ date_from: pulseDateFrom, limit: 12 }),
    enabled: mode === 'live',
    refetchInterval: mode === 'demo' ? false : POLLING_INTERVALS.stats,
    staleTime: mode === 'demo' ? Infinity : 0,
  })
  const chartOption = useMemo(() => buildWarehouseChart(data), [data])
  const architectureOption = useMemo(() => buildWarehouseArchitectureChart(warehouse.data ?? undefined), [warehouse.data])
  const systemSizeOption = useMemo(() => buildWarehouseSystemSizeChart(warehouse.data ?? undefined), [warehouse.data])
  const racingCoverageOption = useMemo(() => buildRacingCoverageChart(pulse.data ?? undefined), [pulse.data])

  const latestOdds = data?.freshness.latest_odds_snapshot
  const freshnessMinutes = latestOdds ? Math.max(0, Math.round((Date.now() - new Date(latestOdds).getTime()) / 60000)) : null
  const warehouseRows = warehouse.data?.databases.reduce((acc, database) => acc + database.row_count, 0) ?? data?.tables.reduce((acc, table) => acc + table.approx_rows, 0)
  const warehouseSize = warehouse.data?.databases.reduce((acc, database) => acc + database.total_size_bytes, 0) ?? data?.database.total_size_bytes
  const hotTables = warehouse.data?.hot_tables ?? []
  const largeTables = warehouse.data?.large_tables ?? []
  const bottlenecks = warehouse.data?.bottlenecks ?? []

  return (
    <div className="space-y-4">
      <SectionHeader title="Warehouse" subtitle="System architecture, database inventory, hot tables, large tables, and operational pressure points." />
      <ErrorBanner error={(error as Error | null) ?? (warehouse.error as Error | null) ?? (pulse.error as Error | null)} />

      <Card className="relative overflow-hidden border-cyan-900/40 bg-gradient-to-br from-slate-950 to-slate-900/90">
        <div className="relative z-10 grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
          <div>
            <p className="text-xs uppercase tracking-[0.35em] text-cyan-400">Warehouse Control Surface</p>
            <h3 className="mt-2 text-3xl font-semibold text-white">See the data estate, not just the tables.</h3>
            <p className="mt-2 text-sm text-slate-300">BETMAN Data, Core, Heatmap, LineForge, and RuView in one operations view with source freshness and bottleneck flags.</p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <SmallStat label="Databases" value={formatNumber(warehouse.data?.databases.length ?? 1)} />
              <SmallStat label="Warehouse size" value={formatBytes(warehouseSize)} />
              <SmallStat label="Rows surfaced" value={formatNumber(warehouseRows)} />
              <SmallStat label="Freshness" value={freshnessMinutes === null ? 'No odds yet' : `${freshnessMinutes} min ago`} />
            </div>
          </div>
          <div className="h-[300px] rounded-xl border border-cyan-900/40 bg-slate-950/70 p-2">
            {warehouse.isLoading ? <ChartSkeleton /> : <ReactECharts option={architectureOption} style={{ height: '100%' }} />}
          </div>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-4">
        <MetricCard label="Warehouse size" value={formatBytes(warehouseSize)} loading={isLoading || warehouse.isLoading} tone="cyan" />
        <MetricCard label="Databases" value={formatNumber(warehouse.data?.databases.length ?? 1)} loading={warehouse.isLoading} tone="indigo" />
        <MetricCard
          label="Hot tables"
          value={formatNumber(hotTables.filter((table) => table.read_ops > 0).length)}
          loading={warehouse.isLoading}
          tone="teal"
        />
        <MetricCard
          label="Bottlenecks"
          value={formatNumber(bottlenecks.length)}
          loading={warehouse.isLoading}
          tone={bottlenecks.some((item) => item.severity === 'high') ? 'rose' : bottlenecks.length ? 'amber' : 'emerald'}
        />
      </div>

      <Card className="border-emerald-900/40 bg-slate-950/80">
        <div className="grid gap-5 lg:grid-cols-[0.95fr_1.05fr]">
          <div>
            <PanelTitle title="Live thoroughbred racing pulse" subtitle={`Last ${DEFAULT_RACING_WINDOW_DAYS} days from TAB race fields, results, people, tracks, and market prices.`} />
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <SmallStat label="Races" value={formatNumber(pulse.data?.totals.races)} />
              <SmallStat label="Runners" value={formatNumber(pulse.data?.totals.runners)} />
              <SmallStat label="Jockeys" value={formatNumber(pulse.data?.totals.jockeys)} />
              <SmallStat label="Trainers" value={formatNumber(pulse.data?.totals.trainers)} />
              <SmallStat label="Tracks" value={formatNumber(pulse.data?.totals.tracks)} />
              <SmallStat label="Latest race date" value={pulse.data?.totals.latest_meeting_date ?? 'Awaiting live data'} />
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <SmallStat label="Priced runners" value={formatNumber(pulse.data?.market.priced_runners)} />
              <SmallStat label="Favourite strike" value={pulse.data?.market.favourite_win_rate === null || pulse.data?.market.favourite_win_rate === undefined ? '—' : formatPercent(pulse.data.market.favourite_win_rate)} />
              <SmallStat label="Avg closing price" value={pulse.data?.market.avg_closing_price ? `$${pulse.data.market.avg_closing_price.toFixed(2)}` : '—'} />
              <SmallStat label="Freshest price" value={formatDateTime(pulse.data?.market.latest_price_at)} />
            </div>
          </div>
          <div className="h-[360px]">
            {pulse.isLoading ? <ChartSkeleton /> : <ReactECharts option={racingCoverageOption} style={{ height: '100%' }} />}
          </div>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-[0.95fr_1.05fr]">
        <Card>
          <PanelTitle title="People in form" subtitle="Top live thoroughbred jockeys and trainers by wins in the warehouse." />
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <PulsePeopleList title="Jockeys" rows={pulse.data?.top_jockeys ?? []} />
            <PulsePeopleList title="Trainers" rows={pulse.data?.top_trainers ?? []} />
          </div>
        </Card>
        <Card>
          <PanelTitle title="Busy tracks and race classes" subtitle="Where the racing data volume is concentrated." />
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <div className="h-[260px]">
              <Grid
                rows={(pulse.data?.track_activity ?? []) as unknown as Array<Record<string, unknown>>}
                columns={[
                  { field: 'track_name', headerName: 'Track', minWidth: 170 },
                  { field: 'runners', headerName: 'Runners' },
                  { field: 'races', headerName: 'Races' },
                  { field: 'avg_field_size', headerName: 'Avg field' },
                ]}
              />
            </div>
            <div className="h-[260px]">
              <Grid
                rows={(pulse.data?.race_class_activity ?? []) as unknown as Array<Record<string, unknown>>}
                columns={[
                  { field: 'race_class', headerName: 'Class', minWidth: 140 },
                  { field: 'runners', headerName: 'Runners' },
                  { field: 'races', headerName: 'Races' },
                  { field: 'avg_field_size', headerName: 'Avg field' },
                ]}
              />
            </div>
          </div>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
        <Card className="min-h-[420px]">
          <PanelTitle title="Database estate" subtitle="Core systems, engines, hosts, size, and row coverage." />
          <div className="mt-4 grid gap-3">
            {(warehouse.data?.databases ?? []).map((database) => (
              <div key={`${database.system}-${database.name}`} className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-white">{database.system}</div>
                    <div className="text-xs text-slate-400">{database.engine} • {database.name} • {database.host}</div>
                  </div>
                  <div className="text-right text-xs text-slate-300">
                    <div>{formatBytes(database.total_size_bytes)}</div>
                    <div>{formatNumber(database.table_count)} tables</div>
                  </div>
                </div>
                <div className="mt-3 grid gap-2 sm:grid-cols-3">
                  <SmallStat label="Rows" value={formatNumber(database.row_count)} />
                  <SmallStat label="Hot" value={formatNumber(database.hot_tables.filter((table) => table.read_ops > 0).length)} />
                  <SmallStat label="Source" value={database.source.replace(/_/g, ' ')} />
                </div>
              </div>
            ))}
            {!warehouse.data?.databases.length && <EmptyState title="Live warehouse map unavailable" description="Switch to Live mode to inspect connected databases." />}
          </div>
        </Card>
        <Card>
          <PanelTitle title="System weight" subtitle="Storage share across BETMAN databases." />
          <div className="mt-4 h-[380px]">{warehouse.isLoading ? <ChartSkeleton /> : <ReactECharts option={systemSizeOption} style={{ height: '100%' }} />}</div>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <Card className="min-h-[420px]">
          <PanelTitle title="Hot tables" subtitle="Read pressure and access activity across the estate." />
          <div className="mt-4 h-[340px]">
            {warehouse.isLoading ? (
              <ChartSkeleton />
            ) : (
              <WarehouseTableGrid rows={hotTables} />
            )}
          </div>
        </Card>
        <Card>
          <PanelTitle title="Bottleneck watch" subtitle="Visible pressure points from table stats and inventory." />
          <div className="mt-4 space-y-2">
            {bottlenecks.length ? bottlenecks.slice(0, 8).map((item) => (
              <div key={`${item.system}-${item.table_name}-${item.message}`} className="rounded-lg border border-slate-800 bg-slate-900/70 p-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-white">{item.system} / {item.table_name}</div>
                    <div className="text-xs text-slate-400">{item.message}</div>
                  </div>
                  <span className={cn('rounded px-2 py-1 text-[10px] font-bold uppercase tracking-[0.2em]', bottleneckTone(item.severity))}>{item.severity}</span>
                </div>
                <div className="mt-2 flex flex-wrap gap-2 text-[10px] uppercase tracking-[0.16em] text-slate-400">
                  {(item.flags ?? []).map((flag) => <span key={flag} className="rounded bg-slate-800 px-2 py-1">{flag.replace(/_/g, ' ')}</span>)}
                </div>
              </div>
            )) : <EmptyState title="No obvious bottlenecks" description="No high-pressure tables are visible from current stats." />}
          </div>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
        <Card className="min-h-[420px]">
          <PanelTitle title="Large tables" subtitle="Biggest storage consumers across BETMAN data systems." />
          <div className="mt-4 h-[320px]">
            {warehouse.isLoading ? <ChartSkeleton /> : <WarehouseTableGrid rows={largeTables} />}
          </div>
        </Card>
        <Card>
          <PanelTitle title="BETMAN Data storage profile" subtitle="Top warehouse table sizes in live Postgres." />
          <div className="mt-4 h-[300px]">{isLoading ? <ChartSkeleton /> : <ReactECharts option={chartOption} style={{ height: '100%' }} />}</div>
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
  const today = formatLocalDate(new Date())
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

  const meetings = meetingsQuery.data?.meetings ?? []
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
            ) : meetings.length ? (
              meetings.map((meeting) => {
                const meetingRaces = Array.isArray(meeting.races) ? meeting.races : []
                return (
                <button
                  key={meeting.id}
                  type="button"
                  onClick={() => setSelectedRaceId(meetingRaces[0]?.id ?? null)}
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
                    {meetingRaces.map((race) => (
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
                )
              })
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
  const today = formatLocalDate(new Date())
  const sixtyDaysAgo = useMemo(() => localDateDaysAgo(DEFAULT_RACING_WINDOW_DAYS), [])
  const races = useQuery({
    queryKey: ['signal-races', sixtyDaysAgo, today, mode],
    queryFn: mode === 'demo' ? () => Promise.resolve(DEMO_RACE_LIST) : () => api.getRaces({ date_from: sixtyDaysAgo, date_to: today, limit: 80 }),
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
      { queryKey: ['intelligence-leaderboard', sixtyDaysAgo, today, mode], queryFn: mode === 'demo' ? () => Promise.resolve(DEMO_INTELLIGENCE_LEADERBOARD) : () => api.getIntelligenceLeaderboard(undefined, 70, 20, sixtyDaysAgo, today), refetchInterval: mode === 'demo' ? false : POLLING_INTERVALS.signals, staleTime: mode === 'demo' ? Infinity : 0 },
      { queryKey: ['signal-performance', DEFAULT_RACING_WINDOW_DAYS, mode], queryFn: mode === 'demo' ? () => Promise.resolve(DEMO_SIGNAL_PERFORMANCE) : () => api.getSignalPerformance(DEFAULT_RACING_WINDOW_DAYS), refetchInterval: mode === 'demo' ? false : POLLING_INTERVALS.barriers, staleTime: mode === 'demo' ? Infinity : 0 },
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
  const [surface, setSurface] = useState<string>('')
  const [conditionCategory, setConditionCategory] = useState<string>('all')
  const [distancePreset, setDistancePreset] = useState<string>('all')

  const trackContexts = tracks.data?.tracks ?? []
  const trackNames = useMemo(() => Array.from(new Set(trackContexts.map((track) => track.track_name))), [trackContexts])
  const selectedTrack = trackName || trackNames[0] || ''
  const availableSurfaces = useMemo(
    () => Array.from(new Set(trackContexts.filter((track) => track.track_name === selectedTrack).map((track) => track.surface ?? 'unknown'))),
    [trackContexts, selectedTrack],
  )
  const selectedSurface = availableSurfaces.includes(surface) ? surface : availableSurfaces[0] ?? 'unknown'
  const selectedDistance = distancePresets.find((preset) => preset.key === distancePreset) ?? distancePresets[0]

  const [barriers, heatmap] = useQueries({
    queries: [
      {
        queryKey: ['barriers', selectedTrack, selectedSurface, conditionCategory, selectedDistance.key, mode],
        queryFn: mode === 'demo'
          ? () => Promise.resolve(DEMO_BARRIERS)
          : () => api.getBarrierAnalysis(selectedTrack, {
              surface: selectedSurface,
              condition_category: conditionCategory === 'all' ? undefined : conditionCategory,
              distance_min: selectedDistance.min,
              distance_max: selectedDistance.max,
            }),
        enabled: selectedTrack.length > 0 && selectedSurface.length > 0,
        refetchInterval: mode === 'demo' ? false : POLLING_INTERVALS.barriers,
        staleTime: mode === 'demo' ? Infinity : 0,
      },
      {
        queryKey: ['heatmap', selectedTrack, selectedSurface, conditionCategory, selectedDistance.key, mode],
        queryFn: mode === 'demo'
          ? () => Promise.resolve(DEMO_HEATMAP)
          : () => api.getHeatmap(selectedTrack, {
              surface: selectedSurface,
              condition_category: conditionCategory === 'all' ? undefined : conditionCategory,
              distance_band: selectedDistance.key === 'all' ? undefined : selectedDistance.key,
            }),
        enabled: selectedTrack.length > 0 && selectedSurface.length > 0,
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
          <Select value={selectedTrack} onChange={(event) => {
            setTrackName(event.target.value)
            setSurface('')
          }}>
            {trackNames.map((name) => (
              <option key={name} value={name}>{name}</option>
            ))}
          </Select>
          <Select value={selectedSurface} onChange={(event) => setSurface(event.target.value)}>
            {availableSurfaces.map((item) => (
              <option key={item} value={item}>{formatSurfaceLabel(item)}</option>
            ))}
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
  const [windowDays, setWindowDays] = useState<string>(String(DEFAULT_RACING_WINDOW_DAYS))
  const dateFrom = useMemo(() => {
    if (windowDays === 'all') return undefined
    return localDateDaysAgo(Number(windowDays))
  }, [windowDays])
  const [trainerRates, jockeyRates] = useQueries({
    queries: [
      {
        queryKey: ['trainer-rates', trackName, dateFrom, mode],
        queryFn: mode === 'demo' ? () => Promise.resolve(DEMO_TRAINERS) : () => api.getTrainerWinRates({ track: trackName || undefined, date_from: dateFrom, limit: 30, min_runners: 3, order_by: 'wins' }),
        refetchInterval: mode === 'demo' ? false : POLLING_INTERVALS.people,
        staleTime: mode === 'demo' ? Infinity : 0,
      },
      {
        queryKey: ['jockey-rates', trackName, dateFrom, mode],
        queryFn: mode === 'demo' ? () => Promise.resolve(DEMO_JOCKEYS) : () => api.getJockeyWinRates({ track: trackName || undefined, date_from: dateFrom, limit: 30, min_runners: 3, order_by: 'wins' }),
        refetchInterval: mode === 'demo' ? false : POLLING_INTERVALS.people,
        staleTime: mode === 'demo' ? Infinity : 0,
      },
    ],
  })

  const topTrainer = trainerRates.data?.items[0]
  const topJockey = jockeyRates.data?.items[0]

  return (
    <div className="space-y-4">
      <SectionHeader title="People" subtitle="Trainer and jockey leaderboards from real thoroughbred fields, results, and prices." />
      <Card className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <PanelTitle title="Filter context" subtitle="Recent form windows with live recalculation." />
        <div className="grid w-full gap-3 sm:grid-cols-2 lg:max-w-xl">
          <Select value={trackName} onChange={(event) => setTrackName(event.target.value)}>
            <option value="">All tracks</option>
            {(tracks.data?.tracks ?? []).map((track) => (
              <option key={track.track_name} value={track.track_name}>{track.track_name}</option>
            ))}
          </Select>
          <Select value={windowDays} onChange={(event) => setWindowDays(event.target.value)}>
            <option value="60">Last 60 days</option>
            <option value="30">Last 30 days</option>
            <option value="14">Last 14 days</option>
            <option value="7">Last 7 days</option>
            <option value="all">All loaded data</option>
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
        queryFn: () => api.searchOcr(activeQuery, 6, 60),
        enabled: activeQuery.length > 0 && mode === 'live',
      },
      {
        queryKey: ['search-transcripts', activeQuery],
        queryFn: () => api.searchTranscripts(activeQuery, 6, 60),
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

function PulsePeopleList({ title, rows }: { title: string; rows: PeopleResponse['items'] }) {
  const topRows = rows.slice(0, 6)
  return (
    <div className="space-y-2">
      <div className="text-xs uppercase tracking-[0.22em] text-slate-500">{title}</div>
      {topRows.length ? topRows.map((item, index) => (
        <div key={`${title}-${item.person}`} className="rounded-lg border border-slate-800 bg-slate-900/70 p-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-xs text-cyan-400">#{index + 1}</div>
              <div className="text-sm font-semibold text-white">{item.person}</div>
            </div>
            <div className="text-right text-xs text-slate-300">
              <div>{formatNumber(item.wins)} wins</div>
              <div>{formatPercent(item.win_rate)}</div>
            </div>
          </div>
          <div className="mt-2 grid grid-cols-3 gap-2 text-xs text-slate-400">
            <span>{formatNumber(item.runners)} runners</span>
            <span>{formatNumber(item.places)} places</span>
            <span>ROI {item.roi === null ? '—' : formatPercent(item.roi)}</span>
          </div>
        </div>
      )) : <EmptyState title="No people data" description="Live thoroughbred results will appear here once loaded." />}
    </div>
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
      <AgGridReact rowData={rows} columnDefs={columns} pagination={rows.length > 12} domLayout="normal" theme="legacy" />
    </div>
  )
}

function WarehouseTableGrid({ rows }: { rows: WarehouseTable[] }) {
  return (
    <Grid
      rows={rows as unknown as Array<Record<string, unknown>>}
      columns={[
        { field: 'system', headerName: 'System', minWidth: 140 },
        { field: 'database', headerName: 'DB', minWidth: 120 },
        { field: 'table_name', headerName: 'Table', minWidth: 180 },
        { field: 'approx_rows', headerName: 'Rows', valueFormatter: (params) => formatNumber(Number(params.value ?? 0)) },
        { field: 'total_bytes', headerName: 'Size', valueFormatter: (params) => formatBytes(Number(params.value ?? 0)) },
        { field: 'read_ops', headerName: 'Reads', valueFormatter: (params) => formatNumber(Number(params.value ?? 0)) },
        { field: 'seq_scan', headerName: 'Seq', valueFormatter: (params) => formatNumber(Number(params.value ?? 0)) },
        { field: 'idx_scan', headerName: 'Idx', valueFormatter: (params) => formatNumber(Number(params.value ?? 0)) },
      ]}
    />
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

function bottleneckTone(severity: string) {
  if (severity === 'high') return 'bg-rose-500/20 text-rose-300 ring-1 ring-rose-500/30'
  if (severity === 'medium') return 'bg-amber-500/20 text-amber-300 ring-1 ring-amber-500/30'
  if (severity === 'low') return 'bg-cyan-500/20 text-cyan-300 ring-1 ring-cyan-500/30'
  return 'bg-slate-700 text-slate-300'
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

function buildWarehouseArchitectureChart(data?: WarehouseOverview) {
  const nodes = data?.architecture.nodes ?? []
  const edges = data?.architecture.edges ?? []
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      formatter: (params: { dataType?: string; data?: { id?: string; database?: string; engine?: string; host?: string; label?: string; source?: string; target?: string; size_bytes?: number; row_count?: number } }) => {
        if (params.dataType === 'edge') return `${params.data?.source} → ${params.data?.target}<br/>${params.data?.label ?? ''}`
        return `${params.data?.id}<br/>${params.data?.engine ?? ''} ${params.data?.database ?? ''}<br/>${params.data?.host ?? ''}<br/>${formatBytes(params.data?.size_bytes)} • ${formatNumber(params.data?.row_count)} rows`
      },
    },
    series: [
      {
        type: 'graph',
        layout: 'force',
        roam: false,
        draggable: true,
        force: { repulsion: 360, edgeLength: 130 },
        label: { show: true, color: '#e2e8f0', fontSize: 11 },
        lineStyle: { color: '#475569', width: 1.5, curveness: 0.18 },
        edgeLabel: { show: false },
        data: nodes.map((node) => ({
          ...node,
          name: node.id,
          symbolSize: Math.max(36, Math.min(78, 32 + Math.log2((node.size_bytes ?? 1) + 1) * 3)),
          itemStyle: {
            color:
              node.id === 'BETMAN Data'
                ? '#22d3ee'
                : node.id === 'BETMAN Core'
                  ? '#818cf8'
                  : node.id === 'BETMAN Heatmap'
                    ? '#34d399'
                    : node.kind === 'source'
                      ? '#f59e0b'
                      : '#94a3b8',
          },
        })),
        links: edges.map((edge) => ({ source: edge.source, target: edge.target, label: edge.label })),
      },
    ],
  }
}

function buildWarehouseSystemSizeChart(data?: WarehouseOverview) {
  const databases = data?.databases ?? []
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      formatter: (params: { name: string; value: number; data?: { row_count?: number; table_count?: number } }) =>
        `${params.name}<br/>${formatBytes(params.value)}<br/>${formatNumber(params.data?.row_count)} rows • ${formatNumber(params.data?.table_count)} tables`,
    },
    series: [
      {
        type: 'treemap',
        roam: false,
        breadcrumb: { show: false },
        label: { show: true, color: '#f8fafc', formatter: '{b}' },
        upperLabel: { show: true, color: '#f8fafc' },
        itemStyle: { borderColor: '#0f172a', borderWidth: 2, gapWidth: 2 },
        levels: [
          { itemStyle: { borderColor: '#0f172a', gapWidth: 2 } },
          { colorSaturation: [0.35, 0.75], itemStyle: { gapWidth: 1 } },
        ],
        data: databases.map((database) => ({
          name: database.system,
          value: Math.max(database.total_size_bytes, 1),
          row_count: database.row_count,
          table_count: database.table_count,
          itemStyle: {
            color:
              database.system === 'BETMAN Data'
                ? '#0891b2'
                : database.system === 'BETMAN Core'
                  ? '#4f46e5'
                  : database.system === 'BETMAN Heatmap'
                    ? '#059669'
                    : '#475569',
          },
        })),
      },
    ],
  }
}

function buildRacingCoverageChart(data?: RacingPulseResponse | null) {
  const rows = data?.coverage ?? []
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: { textStyle: { color: '#cbd5e1' } },
    grid: { left: 42, right: 22, top: 42, bottom: 34 },
    xAxis: {
      type: 'category',
      data: rows.map((row) => row.date?.slice(5) ?? row.date),
      axisLabel: { color: '#94a3b8' },
      axisLine: { lineStyle: { color: '#334155' } },
    },
    yAxis: [
      {
        type: 'value',
        name: 'Runners',
        axisLabel: { color: '#94a3b8' },
        splitLine: { lineStyle: { color: '#1e293b' } },
      },
      {
        type: 'value',
        name: 'Races',
        axisLabel: { color: '#94a3b8' },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: 'Runners',
        type: 'bar',
        data: rows.map((row) => row.runners),
        itemStyle: { color: '#22d3ee' },
      },
      {
        name: 'Jockeys',
        type: 'line',
        smooth: true,
        data: rows.map((row) => row.jockeys),
        itemStyle: { color: '#a78bfa' },
        lineStyle: { width: 3 },
      },
      {
        name: 'Races',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        data: rows.map((row) => row.races),
        itemStyle: { color: '#34d399' },
        lineStyle: { width: 3 },
      },
    ],
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
