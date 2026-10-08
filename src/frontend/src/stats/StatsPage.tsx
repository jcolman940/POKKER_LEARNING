import { useEffect, useState } from 'react'
import { getJson } from '../api/client'
import { FilterBar } from './FilterBar'
import { EMPTY_FILTERS, type Filters, filterQuery } from './filters'
import type { InitialFilters } from '../trainer/types'
import { LeaksPanel } from './LeaksPanel'
import { type GraphPoint, WinningsChart } from './WinningsChart'

interface Metric {
  key: string
  label: string
  value: number | null
  n: number
  ci_low: number | null
  ci_high: number | null
  unit: string
  insufficient: boolean
}

interface StatsGroup {
  group: string
  hands: number
  metrics: Metric[]
}

interface StatsOut {
  min_sample: number
  groups: StatsGroup[]
}

interface TournamentStats {
  tournaments: number
  cost: number
  prizes: number
  profit: number
  roi: Metric
  itm: Metric
  chips_per_tournament: Metric
}

const GROUPS = [
  ['none', 'Sin agrupar'],
  ['position', 'Posición'],
  ['table_size', 'Tamaño de mesa'],
  ['game_type', 'Formato'],
  ['stack', 'Profundidad de stack'],
  ['month', 'Mes'],
  ['hand', 'Mano'],
] as const

function num(v: number | null, unit: string): string {
  if (v === null) return '—'
  const digits = unit === 'x' ? 2 : 1
  return `${v.toFixed(digits)}${unit === '%' ? '%' : ''}`
}

function MetricValue({ m }: { m: Metric }) {
  return (
    <span className={m.insufficient ? 'metric-low' : undefined}>
      {num(m.value, m.unit)}
      {m.insufficient && (
        <span className="metric-flag" title="Muestra insuficiente">
          {' '}
          *
        </span>
      )}
    </span>
  )
}

function ci(m: Metric): string {
  if (m.ci_low === null || m.ci_high === null) return '—'
  return `${num(m.ci_low, m.unit)} – ${num(m.ci_high, m.unit)}`
}

export function StatsPage({ onTrain }: { onTrain?: (f: InitialFilters) => void }) {
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS)
  const [groupBy, setGroupBy] = useState('none')
  const [stats, setStats] = useState<StatsOut | null>(null)
  const [graph, setGraph] = useState<GraphPoint[]>([])
  const [tournaments, setTournaments] = useState<TournamentStats | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    const q = filterQuery(filters)
    Promise.all([
      getJson<StatsOut>(`/api/stats${filterQuery(filters, { group_by: groupBy })}`, controller.signal),
      getJson<GraphPoint[]>(`/api/stats/graph${q}`, controller.signal),
      getJson<TournamentStats | null>(`/api/stats/tournaments${q}`, controller.signal),
    ])
      .then(([s, g, t]) => {
        setStats(s)
        setGraph(g)
        setTournaments(t)
        setError(null)
      })
      .catch((e: unknown) => {
        if (!controller.signal.aborted) setError(e instanceof Error ? e.message : String(e))
      })
    return () => controller.abort()
  }, [filters, groupBy])

  const groups = stats?.groups ?? []
  const metricKeys = groups[0]?.metrics ?? []

  return (
    <div className="stats-page">
      <section className="panel">
        <FilterBar value={filters} onChange={setFilters} />
        <label>
          Agrupar por
          <select value={groupBy} onChange={(e) => setGroupBy(e.target.value)}>
            {GROUPS.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </label>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </section>

      <section className="panel" aria-labelledby="metrics-title">
        <h3 id="metrics-title">Métricas</h3>
        {groups.length === 0 ? (
          <p className="muted">No hay manos con estos filtros. Importalas en Historiales.</p>
        ) : groupBy === 'none' ? (
          <table className="metrics-table">
            <thead>
              <tr>
                <th scope="col">Métrica</th>
                <th scope="col" className="num">
                  Valor
                </th>
                <th scope="col" className="num">
                  IC 95%
                </th>
                <th scope="col" className="num">
                  Muestra
                </th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row">Manos</th>
                <td className="num">{groups[0].hands}</td>
                <td />
                <td />
              </tr>
              {groups[0].metrics.map((m) => (
                <tr key={m.key}>
                  <th scope="row">
                    {m.label}
                    {m.unit === 'bb/100' && <span className="muted small"> (bb/100)</span>}
                  </th>
                  <td className="num">
                    <MetricValue m={m} />
                  </td>
                  <td className="num muted">{ci(m)}</td>
                  <td className="num">{m.n}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="table-scroll">
            <table className="metrics-table">
              <thead>
                <tr>
                  <th scope="col">{GROUPS.find(([v]) => v === groupBy)?.[1]}</th>
                  <th scope="col" className="num">
                    Manos
                  </th>
                  {metricKeys.map((m) => (
                    <th key={m.key} scope="col" className="num">
                      {m.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {groups.map((g) => (
                  <tr key={g.group}>
                    <th scope="row">{g.group}</th>
                    <td className="num">{g.hands}</td>
                    {g.metrics.map((m) => (
                      <td key={m.key} className="num" title={`IC 95%: ${ci(m)} · n=${m.n}`}>
                        <MetricValue m={m} />
                        <span className="ci-line">{ci(m)}</span>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {stats && (
          <p className="small muted">
            * Muestra insuficiente: menos de {stats.min_sample} oportunidades (o {stats.min_sample * 10} manos
            para el winrate). IC 95%: Wilson para porcentajes, normal para bb/100.
          </p>
        )}
      </section>

      <LeaksPanel filters={filters} onTrain={(f) => onTrain?.(f)} />

      <section className="panel">
        <WinningsChart points={graph} />
        <p className="small muted">
          All-in EV: las manos con all-in antes del river y cartas conocidas cuentan por su equity, no por el
          resultado.
        </p>
      </section>

      {tournaments && (
        <section className="panel" aria-labelledby="tour-title">
          <h3 id="tour-title">Torneos</h3>
          <dl className="metrics">
            <div>
              <dt>Torneos</dt>
              <dd>{tournaments.tournaments}</dd>
            </div>
            <div>
              <dt>Resultado</dt>
              <dd>{tournaments.profit.toFixed(2)}</dd>
            </div>
            {[tournaments.roi, tournaments.itm, tournaments.chips_per_tournament].map((m) => (
              <div key={m.key}>
                <dt>{m.label}</dt>
                <dd>
                  <MetricValue m={m} />
                </dd>
                <dd className="small muted">
                  IC {ci(m)} · n={m.n}
                </dd>
              </div>
            ))}
          </dl>
        </section>
      )}
    </div>
  )
}
