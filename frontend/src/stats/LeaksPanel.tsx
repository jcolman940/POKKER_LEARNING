import { useEffect, useRef, useState } from 'react'
import { getJson } from '../api/client'
import { ACTION_LABEL } from '../ranges/labels'
import { RangeMatrix } from '../ranges/RangeMatrix'
import type { InitialFilters } from '../trainer/types'
import { type Filters, filterQuery } from './filters'

interface ActionLeak {
  action: string
  observed: number
  expected: number
  ci_low: number
  ci_high: number
  diff: number
  significant: boolean
}

interface LeakGroup {
  key: string
  label: string
  game_format: string
  table_size: number
  position: string
  situation: string
  vs_position: string | null
  stack_bucket: string
  source: string
  approximate: boolean
  notes: string[]
  n: number
  insufficient: boolean
  actions: ActionLeak[]
  impact: number
  impact_unit: string
  ev_loss_bb: number | null
}

interface LeakReport {
  total_hands: number
  min_sample: number
  leaks: LeakGroup[]
  insufficient: LeakGroup[]
  other: LeakGroup[]
  warnings: string[]
}

interface TopClass {
  hand_class: string
  n: number
  observed: number
  expected: number
  diff: number
}

interface LeakDetail {
  group: LeakGroup
  action: string
  top_classes: TopClass[]
  grid: (number | null)[]
}

const SITUATION_TEXT: Record<string, string> = {
  rfi: 'RFI',
  vs_open: 'vs open',
  vs_3bet: 'vs 3-bet',
  vs_4bet: 'vs 4-bet',
  squeeze: 'squeeze',
  bvb: 'ciega vs ciega',
  vs_allin: 'vs all-in',
}

const pct = (v: number) => `${Math.round(v * 100)}%`
const impactText = (g: LeakGroup) => `${g.impact.toFixed(1).replace('.', ',')} ${g.impact_unit}`
const actionName = (a: string) => ACTION_LABEL[a] ?? a

function spotText(g: LeakGroup): string {
  const vs = g.vs_position ? ` vs ${g.vs_position}` : ''
  const sit = SITUATION_TEXT[g.situation] ?? g.situation
  return `${g.position} · ${sit}${vs} · ${g.game_format} ${g.table_size} · ${g.stack_bucket}bb`
}

function LeakDetailView({
  group,
  filters,
  onTrain,
}: {
  group: LeakGroup
  filters: Filters
  onTrain: (f: InitialFilters) => void
}) {
  const [detail, setDetail] = useState<LeakDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    getJson<LeakDetail>(
      `/api/leaks/detail${filterQuery(filters, { key: group.key })}`,
      controller.signal,
    )
      .then((d) => {
        setDetail(d)
        setError(null)
      })
      .catch((e: unknown) => {
        if (!controller.signal.aborted) setError(e instanceof Error ? e.message : String(e))
      })
    return () => controller.abort()
  }, [filters, group.key])

  const more = detail ? detail.grid.map((v) => (v !== null && v > 0 ? Math.min(1, v) : 0)) : []
  const less = detail ? detail.grid.map((v) => (v !== null && v < 0 ? Math.min(1, -v) : 0)) : []
  const significant = group.actions.filter((a) => a.significant)

  return (
    <div className="leak-detail">
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {group.notes.map((n) => (
        <p key={n} className="small muted">
          {n}
        </p>
      ))}
      {detail && (
        <>
          <p>
            {significant.length > 0
              ? `Jugás ${actionName(detail.action)} distinto a lo esperado en ${spotText(group)}.`
              : `Sin desvíos significativos en ${spotText(group)}.`}
          </p>
          {detail.top_classes.length > 0 && (
            <table className="metrics-table">
              <thead>
                <tr>
                  <th scope="col">Mano</th>
                  <th scope="col" className="num">
                    Veces
                  </th>
                  <th scope="col" className="num">
                    Observado
                  </th>
                  <th scope="col" className="num">
                    Esperado
                  </th>
                </tr>
              </thead>
              <tbody>
                {detail.top_classes.map((c) => (
                  <tr key={c.hand_class}>
                    <th scope="row">{c.hand_class}</th>
                    <td className="num">{c.n}</td>
                    <td className="num">{pct(c.observed)}</td>
                    <td className="num">{pct(c.expected)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <RangeMatrix
            layers={[
              { action: 'raise', grid: more },
              { action: 'call', grid: less },
            ]}
            caption={`Desvío en ${actionName(detail.action)} por mano`}
            implicitFold={false}
          />
          <p className="small muted">
            Rojo: jugás {actionName(detail.action)} más de lo esperado. Verde: menos de lo esperado.
          </p>
        </>
      )}
      <button
        type="button"
        onClick={() =>
          onTrain({
            positions: [group.position],
            situations: [group.situation],
            formats: [group.game_format],
            sources: group.source === 'nash' ? ['pushfold'] : ['chart'],
          })
        }
      >
        Entrenar este spot
      </button>
    </div>
  )
}

function LeakRow({
  group,
  open,
  onToggle,
  filters,
  onTrain,
}: {
  group: LeakGroup
  open: boolean
  onToggle: () => void
  filters: Filters
  onTrain: (f: InitialFilters) => void
}) {
  const significant = group.actions.filter((a) => a.significant)
  return (
    <li className="leak-row">
      <button type="button" className="leak-head" aria-expanded={open} onClick={onToggle}>
        <strong>{spotText(group)}</strong>
        <span className="small muted">n={group.n}</span>
        <span className="num">{impactText(group)}</span>
        {group.approximate && <span className="badge badge-warn">Aproximado</span>}
        {group.source === 'nash' && <span className="badge">Nash (chip EV)</span>}
      </button>
      {significant.length > 0 && (
        <ul className="small">
          {significant.map((a) => (
            <li key={a.action}>
              {actionName(a.action)}: Observado {pct(a.observed)} (IC {Math.round(a.ci_low * 100)}–
              {pct(a.ci_high)}) · Esperado {pct(a.expected)}
            </li>
          ))}
        </ul>
      )}
      {open && <LeakDetailView group={group} filters={filters} onTrain={onTrain} />}
    </li>
  )
}

export function LeaksPanel({
  filters,
  onTrain,
}: {
  filters: Filters
  onTrain: (f: InitialFilters) => void
}) {
  const [report, setReport] = useState<LeakReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [openKey, setOpenKey] = useState<string | null>(null)
  const request = useRef(0)

  useEffect(() => {
    const id = ++request.current
    const controller = new AbortController()
    getJson<LeakReport>(`/api/leaks${filterQuery(filters)}`, controller.signal)
      .then((r) => {
        if (id !== request.current) return
        setReport(r)
        setError(null)
        setOpenKey(null)
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted || id !== request.current) return
        setError(e instanceof Error ? e.message : String(e))
      })
    return () => controller.abort()
  }, [filters])

  const renderRows = (groups: LeakGroup[]) => (
    <ul className="leak-list">
      {groups.map((g) => (
        <LeakRow
          key={g.key}
          group={g}
          open={openKey === g.key}
          onToggle={() => setOpenKey(openKey === g.key ? null : g.key)}
          filters={filters}
          onTrain={onTrain}
        />
      ))}
    </ul>
  )

  const empty =
    report !== null && report.leaks.length + report.insufficient.length + report.other.length === 0

  return (
    <section className="panel" aria-labelledby="leaks-title">
      <h3 id="leaks-title">Leaks</h3>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {report?.warnings.map((w) => (
        <p key={w} className="muted">
          {w}
        </p>
      ))}
      {report && report.leaks.length > 0 && renderRows(report.leaks)}
      {report && report.leaks.length === 0 && !empty && (
        <p className="muted">No hay leaks significativos con estos filtros.</p>
      )}
      {empty && <p className="muted">Importá tus historiales en Historiales para ver tus leaks.</p>}
      {report && report.insufficient.length > 0 && (
        <details>
          <summary>Muestra insuficiente</summary>
          {renderRows(report.insufficient)}
        </details>
      )}
      {report && report.other.length > 0 && (
        <details>
          <summary>Sin desvíos</summary>
          {renderRows(report.other)}
        </details>
      )}
    </section>
  )
}
