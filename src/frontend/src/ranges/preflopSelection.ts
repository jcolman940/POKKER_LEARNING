import type { Option } from '../ui'
import { SITUATIONS } from './labels'
import { ALL, type PreflopFilters } from './preflopFilters'
import type { Chart, ChartData } from './types'

export interface ViewerSelection {
  situation: string
  position: string
  vsPosition: string | null
  stack: number | null
}

export const DEFAULT_SELECTION: ViewerSelection = { situation: 'rfi', position: 'BTN', vsPosition: null, stack: 100 }

const SITUATION_TEXT: Record<string, string> = {
  rfi: 'Open raise (RFI)',
  vs_open: 'vs open',
  vs_3bet: 'vs 3-bet',
  vs_4bet: 'vs 4-bet',
  squeeze: 'Squeeze',
  bvb: 'Ciega vs ciega',
  vs_allin: 'vs all-in',
}

export function situationText(s: string): string {
  return SITUATION_TEXT[s] ?? s
}

export interface ViewerOptions {
  situations: Option<string>[]
  positions: Option<string>[]
  vsPositions: Option<string>[]
  stacks: number[]
}

function unique<T>(values: T[]): T[] {
  return [...new Set(values)]
}

function tableOrder(positions: string[], charts: Chart[]): string[] {
  return unique([...positions, ...charts.map((c) => c.position)])
}

export function viewerOptions(charts: Chart[], positions: string[], sel: ViewerSelection): ViewerOptions {
  const order = tableOrder(positions, charts)
  const inSituation = charts.filter((c) => c.situation === sel.situation)
  const atPosition = inSituation.filter((c) => c.position === sel.position)

  const situations = SITUATIONS.map(([value]) => ({
    value,
    label: situationText(value),
    disabled: !charts.some((c) => c.situation === value),
  }))
  const positionOpts = order.map((p) => ({ value: p, label: p, disabled: !inSituation.some((c) => c.position === p) }))

  const rivals =
    sel.situation === 'rfi'
      ? []
      : unique(atPosition.map((c) => c.vs_position).filter((v): v is string => !!v)).sort(
          (a, b) => order.indexOf(a) - order.indexOf(b),
        )
  const vsPositions = rivals.map((v) => ({ value: v, label: v }))

  const forStack = rivals.length === 0 ? atPosition : atPosition.filter((c) => c.vs_position === sel.vsPosition)
  const stacks = unique(forStack.map((c) => c.stack_bb)).sort((a, b) => a - b)

  return { situations, positions: positionOpts, vsPositions, stacks }
}

function closest(values: number[], target: number | null): number {
  if (target === null) return values[values.length - 1]
  return values.reduce((best, v) => {
    const d = Math.abs(v - target)
    const bd = Math.abs(best - target)
    return d < bd || (d === bd && v > best) ? v : best
  })
}

/** Each control falls back to the first available value when the current one has no charts. */
export function resolveSelection(charts: Chart[], positions: string[], sel: ViewerSelection): ViewerSelection {
  const s = { ...sel }
  const firstEnabled = (opts: Option<string>[]) => opts.find((o) => !o.disabled)?.value

  let o = viewerOptions(charts, positions, s)
  if (o.situations.find((x) => x.value === s.situation)?.disabled !== false) {
    s.situation = firstEnabled(o.situations) ?? s.situation
    o = viewerOptions(charts, positions, s)
  }
  if (o.positions.find((x) => x.value === s.position)?.disabled !== false) {
    s.position = firstEnabled(o.positions) ?? s.position
    o = viewerOptions(charts, positions, s)
  }
  if (o.vsPositions.length === 0) s.vsPosition = null
  else if (!o.vsPositions.some((x) => x.value === s.vsPosition)) s.vsPosition = o.vsPositions[0].value
  o = viewerOptions(charts, positions, s)
  if (o.stacks.length > 0 && (s.stack === null || !o.stacks.includes(s.stack))) s.stack = closest(o.stacks, s.stack)
  return s
}

export function matchingCharts(charts: Chart[], sel: ViewerSelection): Chart[] {
  return charts
    .filter(
      (c) =>
        c.situation === sel.situation &&
        c.position === sel.position &&
        (c.vs_position ?? null) === sel.vsPosition &&
        c.stack_bb === sel.stack,
    )
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
}

/** Editor draft for "Nuevo" / "Crear este rango": the visible context as a custom chart. */
export function draftFor(filters: PreflopFilters, sel: ViewerSelection): ChartData {
  return {
    name: '',
    source: 'custom',
    game_format: filters.format,
    players: filters.players,
    position: sel.position,
    vs_position: sel.vsPosition,
    stack_bb: sel.stack ?? 100,
    situation: sel.situation,
    open_size_bb: sel.situation === 'rfi' ? 2.5 : null,
    rake: filters.rake === ALL ? null : filters.rake,
    ante_bb: 0,
    note: '',
    actions: { raise: Array<number>(169).fill(0) },
  }
}

export const NEW_CHART: ChartData = draftFor({ format: 'cash', source: ALL, rake: ALL, players: 6 }, DEFAULT_SELECTION)
