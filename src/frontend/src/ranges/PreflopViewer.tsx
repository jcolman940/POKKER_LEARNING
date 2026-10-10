import { useEffect, useMemo, useState } from 'react'
import { getJson } from '../api/client'
import { handClassName } from '../simulator/cards'
import type { InitialScenario } from '../simulator/SimulatorPage'
import type { GameFormat } from '../simulator/types'
import type { InitialFilters } from '../trainer/types'
import { Button, Card, Chip, PillGroup, SegmentList, Select, Stat } from '../ui'
import { SOURCE_LABEL } from './labels'
import { actionLabel, chartToText, formatPct, rangeStats } from './notation'
import { applyFilters, filtersSummary, type PreflopFilters } from './preflopFilters'
import {
  DEFAULT_SELECTION,
  draftFor,
  NO_RIVAL,
  matchingCharts,
  resolveSelection,
  situationText,
  type ViewerSelection,
  viewerOptions,
} from './preflopSelection'
import { RangeMatrix } from './RangeMatrix'
import type { Chart, ChartData } from './types'

export interface PreflopViewerProps {
  charts: Chart[]
  filters: PreflopFilters
  onChangeFilters: () => void
  onEdit: (chart: Chart) => void
  onCreate: (draft: ChartData) => void
  onManage: () => void
  onOpenSimulator: (scenario: InitialScenario) => void
  onTrain: (filters: InitialFilters) => void
  /** Selection to start from when the viewer mounts again (after editing or managing charts). */
  initialSelection?: ViewerSelection
  onSelectionChange?: (selection: ViewerSelection) => void
}

function cellText(chart: Chart, index: number): string[] {
  const parts = Object.entries(chart.actions)
    .filter(([action, grid]) => action !== 'fold' && (grid[index] ?? 0) > 0)
    .map(([action, grid]) => `${actionLabel(action)} ${Math.round(grid[index] * 100)}%`)
  const played = Object.entries(chart.actions)
    .filter(([action]) => action !== 'fold')
    .reduce((s, [, grid]) => s + (grid[index] ?? 0), 0)
  if (played < 0.999) parts.push(`Fold ${Math.round((1 - Math.min(1, played)) * 100)}%`)
  return parts
}

export function PreflopViewer(props: PreflopViewerProps) {
  const { charts, filters, onChangeFilters, onEdit, onCreate, onManage, onOpenSimulator, onTrain } = props
  const { initialSelection = DEFAULT_SELECTION, onSelectionChange } = props
  const visible = useMemo(() => applyFilters(charts, filters), [charts, filters])

  const [positions, setPositions] = useState<string[]>([])
  useEffect(() => {
    const controller = new AbortController()
    getJson<string[]>(`/api/simulator/positions/${filters.players}`, controller.signal)
      .then(setPositions)
      .catch(() => {
        // Without the table order the viewer falls back to the positions found in the charts.
        if (!controller.signal.aborted) setPositions([])
      })
    return () => controller.abort()
  }, [filters.players])

  const [wanted, setWanted] = useState<ViewerSelection>(initialSelection)
  const [pickedId, setPickedId] = useState<number | null>(null)
  const [hover, setHover] = useState<number | null>(null)
  const [note, setNote] = useState<string | null>(null)

  const sel = resolveSelection(visible, positions, wanted)
  const options = viewerOptions(visible, positions, sel)
  const matches = matchingCharts(visible, sel)
  const chart = matches.find((c) => c.id === pickedId) ?? matches[0] ?? null

  function change(patch: Partial<ViewerSelection>) {
    const next = { ...sel, ...patch }
    setWanted(next)
    onSelectionChange?.(next)
    setPickedId(null)
    setNote(null)
  }

  async function copy() {
    if (!chart) return
    try {
      if (!navigator.clipboard) throw new Error('clipboard unavailable')
      await navigator.clipboard.writeText(chartToText(chart.actions))
      setNote('Rango copiado.')
    } catch {
      setNote('No se pudo copiar el rango.')
    }
  }

  const layers = chart ? Object.entries(chart.actions).map(([action, grid]) => ({ action, grid })) : []
  const stats = chart ? rangeStats(chart.actions) : null
  const spot = `${sel.position}${sel.vsPosition ? ` vs ${sel.vsPosition}` : ''} · ${situationText(sel.situation)} · ${sel.stack ?? '?'}bb`

  return (
    <div className="preflop-viewer">
      <div className="preflop-top">
        <Chip actionLabel="Cambiar" onAction={onChangeFilters}>
          {filtersSummary(filters)}
        </Chip>
        <div className="preflop-tools">
          <Button size="sm" disabled={!chart} onClick={() => void copy()}>
            ⧉ Copiar rango
          </Button>
          <Button size="sm" disabled={!chart} onClick={() => chart && onEdit(chart)}>
            ✎ Editar
          </Button>
          <Button size="sm" onClick={() => onCreate(draftFor(filters, sel))}>
            ＋ Nuevo
          </Button>
          <Button size="sm" onClick={onManage}>
            ⇅ Importar / exportar
          </Button>
        </div>
      </div>
      {note && (
        <p className="small" role="status">
          {note}
        </p>
      )}

      <div className="preflop-body">
        <aside className="preflop-left">
          <SegmentList
            legend="Secuencia"
            options={options.situations}
            value={sel.situation}
            onChange={(situation) => change({ situation })}
          />
          {options.stacks.length > 0 && (
            <Select
              label="Stack efectivo"
              value={String(sel.stack)}
              onChange={(e) => change({ stack: Number(e.target.value) })}
            >
              {options.stacks.map((s) => (
                <option key={s} value={s}>
                  {s} BB
                </option>
              ))}
            </Select>
          )}
        </aside>

        <div className="preflop-center">
          <PillGroup
            legend="Tu posición"
            options={options.positions}
            value={sel.position}
            onChange={(position) => change({ position })}
          />
          {options.vsPositions.length > 0 && (
            <PillGroup
              legend="Rival"
              options={options.vsPositions}
              value={sel.vsPosition ?? NO_RIVAL}
              onChange={(v) => change({ vsPosition: v === NO_RIVAL ? null : v })}
            />
          )}
          {matches.length > 1 && chart && (
            <Select
              label={`${matches.length} rangos`}
              value={String(chart.id)}
              onChange={(e) => setPickedId(Number(e.target.value))}
            >
              {matches.map((c) => (
                <option key={c.id} value={c.id}>
                  {SOURCE_LABEL[c.source] ?? c.source} · {c.name}
                </option>
              ))}
            </Select>
          )}
          {chart && stats ? (
            <>
              <ul className="preflop-legend" aria-label="Leyenda">
                {layers
                  .filter(({ action }) => action !== 'fold')
                  .map(({ action, grid }) => (
                    <li key={action}>
                      <span className="swatch" style={{ background: `var(--action-${action})` }} />
                      {actionLabel(action)}
                      <span className="preflop-legend-pct">{formatPct(rangeStats({ [action]: grid }).pct)}</span>
                    </li>
                  ))}
                <li>
                  <span className="swatch" style={{ background: 'var(--grid-empty)' }} />
                  Fold
                  <span className="preflop-legend-pct">{formatPct(1 - stats.pct)}</span>
                </li>
              </ul>
              <RangeMatrix layers={layers} caption={`Rango ${chart.name}`} onHover={setHover} />
              {chart.note && <p className="muted small">{chart.note}</p>}
            </>
          ) : (
            <div className="panel preflop-missing">
              <p>No hay un rango para {spot}.</p>
              <Button variant="primary" onClick={() => onCreate(draftFor(filters, sel))}>
                Crear este rango
              </Button>
            </div>
          )}
        </div>

        <aside className="preflop-right">
          {chart && stats && (
            <Card>
              <Stat label="Rango" value={formatPct(stats.pct)} detail={`${stats.combos} combos`} />
            </Card>
          )}
          {chart && hover !== null && (
            <Card title={`Mano: ${handClassName(hover)}`}>
              {cellText(chart, hover).map((line) => (
                <p key={line}>{line}</p>
              ))}
            </Card>
          )}
          <Card title="Abrir en" className="preflop-links">
            <Button
              variant="ghost"
              onClick={() =>
                onOpenSimulator({
                  format: filters.format as GameFormat,
                  num_players: filters.players,
                  hero_position: sel.position,
                  effective_stack_bb: sel.stack ?? 100,
                  situation: sel.situation,
                  // The chart's rival; in RFI the big blind defends (small blind if you are the BB).
                  villains: [
                    { position: sel.vsPosition ?? (sel.position === 'BB' ? 'SB' : 'BB'), range: 'random', hand: null },
                  ],
                })
              }
            >
              ⬭ Abrir en Simulador →
            </Button>
            <Button
              variant="ghost"
              onClick={() =>
                onTrain({
                  positions: [sel.position],
                  situations: [sel.situation],
                  formats: [filters.format],
                  sources: ['chart'],
                })
              }
            >
              ✎ Entrenar este spot →
            </Button>
          </Card>
        </aside>
      </div>
    </div>
  )
}
