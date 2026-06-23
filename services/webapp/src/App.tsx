import { useMemo, useState } from 'react'
import type { ColDef, ValueGetterParams } from 'ag-grid-community'
import { useMutation, useQueries, useQuery } from '@tanstack/react-query'
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
  type AssistantResponse,
  type BarrierResponse,
  type HeatmapResponse,
  type OddsResponse,
  type PeopleResponse,
  type RaceDetail,
  type SignalsResponseItem,
  type StatsOverview,
} from './lib/api'
import { cn, formatBytes, formatDateTime, formatNumber, formatPercent } from './lib/utils'

const navigation = [
  { to: '/', label: 'Overview', icon: Database },
  { to: '/today', label: 'Today', icon: Gauge },
  { to: '/signals', label: 'Signals', icon: Sparkles },
  { to: '/gates', label: 'Gates', icon: Map },
  { to: '/people', label: 'People', icon: Users },
  { to: '/ask', label: 'Ask BETMAN', icon: Search },
]

function App() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-7xl flex-col px-4 py-4 sm:px-6 lg:px-8">
        <header className="mb-6 rounded-2xl border border-slate-800 bg-slate-950/90 p-4">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.35em] text-cyan-400">BETMAN_DATA</p>
              <h1 className="text-3xl font-semibold text-white">Data Viewer</h1>
              <p className="text-sm text-slate-400">The live internal console for the global space bookie.</p>
            </div>
            <nav className="grid gap-2 sm:grid-cols-3 lg:flex">
              {navigation.map(({ to, label, icon: Icon }) => (
                <NavLink
                  key={to}
                  to={to}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition',
                      isActive
                        ? 'border-cyan-500 bg-cyan-500/10 text-cyan-300'
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
      </div>
    </div>
  )
}

function OverviewView() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['stats-overview'],
    queryFn: api.getStatsOverview,
    refetchInterval: POLLING_INTERVALS.stats,
  })

  const chartOption = useMemo(() => buildWarehouseChart(data), [data])

  return (
    <div className="space-y-4">
      <SectionHeader title="Warehouse overview" subtitle="Live database health, ingestion velocity, and freshness." />
      <ErrorBanner error={error} />
      <div className="grid gap-4 lg:grid-cols-4">
        <MetricCard label="Meetings today" value={formatNumber(data?.counts.meetings_today)} loading={isLoading} />
        <MetricCard label="Races today" value={formatNumber(data?.counts.races_today)} loading={isLoading} />
        <MetricCard label="Runners today" value={formatNumber(data?.counts.runners_today)} loading={isLoading} />
        <MetricCard label="DB size" value={formatBytes(data?.database.total_size_bytes)} loading={isLoading} />
      </div>
      <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
        <Card className="min-h-[420px]">
          <PanelTitle title="Warehouse" subtitle="Per-table size and row estimates." />
          <div className="mt-4 h-[320px]">
            <Grid
              rows={data?.tables ?? []}
              columns={[
                { field: 'table_name', headerName: 'Table' },
                { field: 'approx_rows', headerName: 'Rows' },
                { field: 'total_bytes', headerName: 'Total bytes' },
              ]}
            />
          </div>
        </Card>
        <Card>
          <PanelTitle title="Storage profile" subtitle="Largest warehouse tables by footprint." />
          <div className="mt-4 h-[360px]">
            <ReactECharts option={chartOption} style={{ height: '100%' }} />
          </div>
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
  const today = new Date().toISOString().slice(0, 10)
  const meetingsQuery = useQuery({
    queryKey: ['meetings', today],
    queryFn: () => api.getMeetings(today),
    refetchInterval: POLLING_INTERVALS.meetings,
  })
  const racesQuery = useQuery({
    queryKey: ['races', today],
    queryFn: api.getRaces,
    refetchInterval: POLLING_INTERVALS.meetings,
  })
  const [selectedRaceId, setSelectedRaceId] = useState<number | null>(null)

  const raceId = selectedRaceId ?? racesQuery.data?.races[0]?.id ?? null
  const [raceDetail, odds] = useQueries({
    queries: [
      {
        queryKey: ['race', raceId],
        queryFn: () => api.getRace(raceId as number),
        enabled: raceId !== null,
      },
      {
        queryKey: ['odds', raceId],
        queryFn: () => api.getRaceOddsDrift(raceId as number),
        enabled: raceId !== null,
        refetchInterval: POLLING_INTERVALS.odds,
      },
    ],
  })

  return (
    <div className="space-y-4">
      <SectionHeader title="Today" subtitle="Meetings, fields, and live-feel odds drift." />
      <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
        <Card>
          <PanelTitle title="Meetings by track" subtitle={today} />
          <div className="mt-4 space-y-3">
            {meetingsQuery.data?.meetings.length ? (
              meetingsQuery.data.meetings.map((meeting) => (
                <button
                  key={meeting.id}
                  type="button"
                  onClick={() => setSelectedRaceId(meeting.races[0]?.id ?? null)}
                  className="w-full rounded-lg border border-slate-800 bg-slate-900/80 p-3 text-left hover:border-cyan-500"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium text-white">{meeting.track_name}</div>
                      <div className="text-xs text-slate-400">{meeting.surface ?? 'surface unknown'} • {meeting.jurisdiction ?? 'N/A'}</div>
                    </div>
                    <div className="text-sm text-cyan-300">{meeting.race_count} races</div>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-400">
                    {meeting.races.map((race) => (
                      <span
                        key={race.id}
                        className="rounded bg-slate-800 px-2 py-1"
                        onClick={(event) => {
                          event.stopPropagation()
                          setSelectedRaceId(race.id)
                        }}
                      >
                        R{race.race_number} {race.name ?? 'Unnamed'}
                      </span>
                    ))}
                  </div>
                </button>
              ))
            ) : (
              <EmptyState title="No meetings yet" description="When race data lands, the board will light up here." />
            )}
          </div>
        </Card>
        <Card>
          <PanelTitle title={raceDetail.data?.name ?? 'Race detail'} subtitle={raceDetail.data?.meeting.track_name ?? 'Select a race'} />
          <div className="mt-4 h-[220px]">
            <Grid
              rows={raceDetail.data?.entries ?? []}
              columns={[
                { field: 'barrier_number', headerName: 'Barrier' },
                {
                  field: 'runner.name',
                  headerName: 'Runner',
                  valueGetter: (
                    params: ValueGetterParams<Record<string, unknown>>,
                  ) =>
                    ((params.data as RaceDetail['entries'][number] | undefined)?.runner
                      .name ?? ''),
                },
                { field: 'jockey_or_driver', headerName: 'Jockey' },
                { field: 'trainer', headerName: 'Trainer' },
                { field: 'weight_kg', headerName: 'Wt' },
              ]}
            />
          </div>
          <div className="mt-4 h-[260px]">
            <ReactECharts option={buildOddsChart(odds.data)} style={{ height: '100%' }} />
          </div>
        </Card>
      </div>
    </div>
  )
}

function SignalsView() {
  const [steamers, drifters, smartMoney, patterns] = useQueries({
    queries: [
      { queryKey: ['steamers'], queryFn: api.getSteamers, refetchInterval: POLLING_INTERVALS.signals },
      { queryKey: ['drifters'], queryFn: api.getDrifters, refetchInterval: POLLING_INTERVALS.signals },
      { queryKey: ['smart-money'], queryFn: api.getSmartMoney, refetchInterval: POLLING_INTERVALS.signals },
      { queryKey: ['patterns'], queryFn: api.getDiscoveryPatterns, refetchInterval: POLLING_INTERVALS.signals },
    ],
  })
  const combined = [...(steamers.data ?? []), ...(drifters.data ?? [])]

  return (
    <div className="space-y-4">
      <SectionHeader title="Signals" subtitle="Every market pulse we can surface from the warehouse." />
      <div className="grid gap-4 lg:grid-cols-4">
        <MetricCard label="Steamers" value={formatNumber(steamers.data?.length)} />
        <MetricCard label="Drifters" value={formatNumber(drifters.data?.length)} />
        <MetricCard label="Smart money" value={formatNumber(smartMoney.data?.length)} />
        <MetricCard label="Patterns" value={formatNumber(patterns.data?.length)} />
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
        <Card>
          <PanelTitle title="Signal stream" subtitle="Live-updating movement board." />
          <div className="mt-4 space-y-2">
            {[...combined, ...(smartMoney.data ?? [])].slice(0, 10).map((item, index) => (
              <div key={`${item.runner_name ?? 'signal'}-${index}`} className="rounded-lg border border-slate-800 bg-slate-900/80 p-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-white">{item.runner_name ?? item.description ?? 'Signal'}</span>
                  <span className="text-cyan-300">{item.signal_type ?? item.indicator_type ?? item.pattern_type}</span>
                </div>
                <div className="mt-1 text-xs text-slate-400">{formatDateTime(item.detected_at)}</div>
              </div>
            ))}
          </div>
        </Card>
        <Card>
          <PanelTitle title="Movement magnitude" subtitle="Steamers and drifters at a glance." />
          <div className="mt-4 h-[360px]">
            <ReactECharts option={buildSignalChart(combined)} style={{ height: '100%' }} />
          </div>
        </Card>
      </div>
    </div>
  )
}

function GatesView() {
  const tracks = useQuery({ queryKey: ['tracks'], queryFn: api.getTracks })
  const [trackName, setTrackName] = useState<string>('')
  const selectedTrack = trackName || tracks.data?.tracks[0]?.track_name || ''
  const [barriers, heatmap] = useQueries({
    queries: [
      { queryKey: ['barriers', selectedTrack], queryFn: () => api.getBarrierAnalysis(selectedTrack), enabled: selectedTrack.length > 0, refetchInterval: POLLING_INTERVALS.barriers },
      { queryKey: ['heatmap', selectedTrack], queryFn: () => api.getHeatmap(selectedTrack), enabled: selectedTrack.length > 0, refetchInterval: POLLING_INTERVALS.barriers },
    ],
  })

  return (
    <div className="space-y-4">
      <SectionHeader title="Gates" subtitle="Track gate bias, rendered as a live track-side heat board." />
      <Card>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <PanelTitle title="Track picker" subtitle="Swap venues and compare their barrier DNA." />
          <div className="w-full max-w-sm">
            <Select value={selectedTrack} onChange={(event) => setTrackName(event.target.value)}>
              {(tracks.data?.tracks ?? []).map((track) => (
                <option key={track.track_name} value={track.track_name}>{track.track_name}</option>
              ))}
            </Select>
          </div>
        </div>
      </Card>
      <div className="grid gap-4 lg:grid-cols-[0.95fr_1.05fr]">
        <Card>
          <PanelTitle title="Track diagram" subtitle={selectedTrack || 'Awaiting track data'} />
          <TrackDiagram heatmap={heatmap.data} />
        </Card>
        <Card>
          <PanelTitle title="Barrier leaderboard" subtitle="Win and place rates by gate." />
          <div className="mt-4 h-[220px]">
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
          <div className="mt-4 h-[260px]">
            <ReactECharts option={buildBarrierChart(barriers.data)} style={{ height: '100%' }} />
          </div>
        </Card>
      </div>
    </div>
  )
}

function PeopleView() {
  const tracks = useQuery({ queryKey: ['people-tracks'], queryFn: api.getTracks })
  const [trackName, setTrackName] = useState<string>('')
  const [trainerRates, jockeyRates] = useQueries({
    queries: [
      { queryKey: ['trainer-rates', trackName], queryFn: () => api.getTrainerWinRates(trackName || undefined), refetchInterval: POLLING_INTERVALS.people },
      { queryKey: ['jockey-rates', trackName], queryFn: () => api.getJockeyWinRates(trackName || undefined), refetchInterval: POLLING_INTERVALS.people },
    ],
  })

  return (
    <div className="space-y-4">
      <SectionHeader title="People" subtitle="On-demand trainer and jockey edge, straight from results and SPs." />
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
      <div className="grid gap-4 lg:grid-cols-2">
        <PeoplePanel title="Trainer board" data={trainerRates.data} />
        <PeoplePanel title="Jockey board" data={jockeyRates.data} />
      </div>
    </div>
  )
}

function AskBetmanView() {
  const [question, setQuestion] = useState("best jockeys at Flemington on soft tracks in the last 180 days")
  const examples = [
    "best trainer win rates in the last 180 days",
    "best jockeys at Flemington on soft tracks in the last 180 days",
    "gate bias at Trentham",
    "today's steamers",
  ]
  const mutation = useMutation({ mutationFn: api.askBetman })

  return (
    <div className="space-y-4">
      <SectionHeader title="Ask BETMAN" subtitle="Natural language to guarded SQL with transparent outputs." />
      <Card className="space-y-4">
        <PanelTitle title="Query surface" subtitle="Exact-search answers from the warehouse, not static dashboards." />
        <div className="grid gap-3 lg:grid-cols-[1fr_auto]">
          <Input value={question} onChange={(event) => setQuestion(event.target.value)} />
          <Button onClick={() => mutation.mutate(question)} disabled={mutation.isPending}>Run query</Button>
        </div>
        <div className="flex flex-wrap gap-2">
          {examples.map((example) => (
            <button key={example} type="button" className="rounded-full border border-slate-800 px-3 py-1 text-xs text-slate-300 hover:border-cyan-500 hover:text-cyan-300" onClick={() => setQuestion(example)}>
              {example}
            </button>
          ))}
        </div>
      </Card>
      <ErrorBanner error={mutation.error} />
      <AssistantResult result={mutation.data} />
    </div>
  )
}

function AssistantResult({ result }: { result?: AssistantResponse }) {
  if (!result) {
    return <EmptyState title="No query yet" description="Run a natural-language query to see SQL, results, and an auto chart." />
  }

  const columnNames = Object.keys(result.rows[0] ?? {})
  const chartOption = buildAssistantChart(result)

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
      <Card>
        <PanelTitle title="Answer" subtitle={`Confidence ${formatPercent(result.confidence * 100)}`} />
        <p className="mt-4 text-sm text-slate-300">{result.summary}</p>
        <details className="mt-4 rounded-lg border border-slate-800 bg-slate-900/60 p-3">
          <summary className="cursor-pointer text-sm text-cyan-300">Generated SQL</summary>
          <pre className="mt-3 overflow-x-auto text-xs text-slate-300">{result.sql}</pre>
        </details>
      </Card>
      <Card>
        <PanelTitle title="Auto chart" subtitle={result.chart.type} />
        <div className="mt-4 h-[320px]">
          <ReactECharts option={chartOption} style={{ height: '100%' }} />
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
  return (
    <Card>
      <PanelTitle title={title} subtitle="Win %, place %, ROI, and sample size." />
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
      <div className="mt-4 h-[260px]">
        <ReactECharts option={buildPeopleChart(data)} style={{ height: '100%' }} />
      </div>
    </Card>
  )
}

function TrackDiagram({ heatmap }: { heatmap?: HeatmapResponse }) {
  const cells = heatmap?.cells ?? []
  return (
    <div className="mt-4 grid gap-4 lg:grid-cols-[0.95fr_1.05fr]">
      <svg viewBox="0 0 520 260" className="h-[280px] w-full rounded-xl border border-slate-800 bg-slate-900/70 p-4">
        <ellipse cx="260" cy="130" rx="220" ry="88" fill="none" stroke="#1e293b" strokeWidth="20" />
        {cells.length ? cells.map((cell, index) => (
          <rect
            key={`${cell.zone}-${cell.distance_from_finish_band}-${index}`}
            x={60 + (index % 4) * 105}
            y={42 + Math.floor(index / 4) * 58}
            width="84"
            height="34"
            rx="10"
            fill={`rgba(34,211,238,${Math.max(0.14, cell.intensity)})`}
            stroke="#67e8f9"
          />
        )) : null}
        <text x="260" y="135" textAnchor="middle" fill="#e2e8f0" fontSize="18">{heatmap?.track_name ?? 'Track heatmap'}</text>
      </svg>
      <div className="grid gap-3">
        {cells.length ? cells.map((cell) => (
          <div key={`${cell.zone}-${cell.distance_from_finish_band}`} className="rounded-lg border border-slate-800 bg-slate-900/70 p-3">
            <div className="text-sm font-medium text-white">{cell.zone} • {cell.distance_from_finish_band ?? 'all splits'}</div>
            <div className="mt-1 text-xs text-slate-400">Win {formatPercent(cell.win_rate)} • Place {formatPercent(cell.place_rate)}</div>
          </div>
        )) : <EmptyState title="No heatmap yet" description="When track_heatmap_cells is populated, gate zones render here." />}
      </div>
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
      <AgGridReact rowData={rows} columnDefs={columns} pagination={rows.length > 12} domLayout="normal" />
    </div>
  )
}

function MetricCard({ label, value, loading = false }: { label: string; value: string; loading?: boolean }) {
  return (
    <Card>
      <div className="text-xs uppercase tracking-[0.3em] text-slate-500">{label}</div>
      <div className="mt-2 text-3xl font-semibold text-white">{loading ? '…' : value}</div>
    </Card>
  )
}

function SmallStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
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

function ErrorBanner({ error }: { error: Error | null }) {
  if (!error) return null
  return <div className="rounded-lg border border-rose-900 bg-rose-950/40 p-3 text-sm text-rose-200">{error.message}</div>
}

function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <Card>
      <div className="text-sm font-medium text-white">{title}</div>
      <p className="mt-1 text-sm text-slate-400">{description}</p>
    </Card>
  )
}

function buildWarehouseChart(data?: StatsOverview) {
  const topTables = [...(data?.tables ?? [])].slice(0, 8).reverse()
  return {
    backgroundColor: 'transparent',
    xAxis: { type: 'value', axisLabel: { color: '#94a3b8', formatter: (value: number) => formatBytes(value) } },
    yAxis: { type: 'category', axisLabel: { color: '#e2e8f0' }, data: topTables.map((table) => table.table_name) },
    series: [{ type: 'bar', data: topTables.map((table) => table.total_bytes), itemStyle: { color: '#22d3ee' } }],
    grid: { top: 10, left: 120, right: 20, bottom: 20 },
    tooltip: { trigger: 'axis' },
  }
}

function buildOddsChart(data?: OddsResponse) {
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: { textStyle: { color: '#cbd5e1' } },
    xAxis: { type: 'category', data: data?.entries[0]?.snapshots.map((snapshot) => `${Math.round(snapshot.offset_ms / 60000)}m`) ?? [], axisLabel: { color: '#94a3b8' } },
    yAxis: { type: 'value', axisLabel: { color: '#94a3b8' } },
    series: (data?.entries ?? []).slice(0, 6).map((entry) => ({ name: entry.runner_name, type: 'line', smooth: true, data: entry.snapshots.map((snapshot) => snapshot.win_price) })),
    grid: { left: 40, right: 20, top: 40, bottom: 30 },
  }
}

function buildSignalChart(items: SignalsResponseItem[]) {
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item' },
    xAxis: { type: 'category', data: items.map((item) => item.runner_name ?? item.signal_type ?? 'signal'), axisLabel: { color: '#94a3b8', rotate: 20 } },
    yAxis: { type: 'value', axisLabel: { color: '#94a3b8' } },
    series: [{ type: 'bar', data: items.map((item) => item.magnitude ?? item.confidence ?? 0), itemStyle: { color: '#38bdf8' } }],
    grid: { left: 40, right: 20, top: 20, bottom: 80 },
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
      { name: 'Place %', type: 'bar', data: (data?.barriers ?? []).map((item) => item.place_rate), itemStyle: { color: '#818cf8' } },
    ],
  }
}

function buildPeopleChart(data?: PeopleResponse) {
  const items = (data?.items ?? []).slice(0, 10).reverse()
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'value', axisLabel: { color: '#94a3b8' } },
    yAxis: { type: 'category', axisLabel: { color: '#e2e8f0' }, data: items.map((item) => item.person) },
    series: [{ type: 'bar', data: items.map((item) => item.win_rate), itemStyle: { color: '#06b6d4' } }],
    grid: { left: 130, right: 20, top: 20, bottom: 20 },
  }
}

function buildAssistantChart(result: AssistantResponse) {
  if (result.chart.type !== 'bar' || !result.chart.x || !result.chart.y) {
    return { xAxis: { type: 'category', data: [] }, yAxis: { type: 'value' }, series: [{ type: 'bar', data: [] }] }
  }
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: result.rows.map((row) => String(row[result.chart.x as keyof typeof row] ?? '')), axisLabel: { color: '#94a3b8', rotate: 20 } },
    yAxis: { type: 'value', axisLabel: { color: '#94a3b8' } },
    series: [{ type: 'bar', data: result.rows.map((row) => Number(row[result.chart.y as keyof typeof row] ?? 0)), itemStyle: { color: '#22d3ee' } }],
    grid: { left: 40, right: 20, top: 20, bottom: 60 },
  }
}

export default App
