import type { Option } from '../ui'
import { SOURCE_LABEL, SOURCES } from './labels'
import type { Chart } from './types'

export const ALL = 'all'
export const PREFLOP_FILTERS_KEY = 'pokker.preflop.filters'

export interface PreflopFilters {
  format: string
  source: string
  rake: string
  players: number
}

export const FORMAT_LABELS = [
  ['cash', 'Cash'],
  ['mtt', 'Torneos'],
  ['sng', 'Sit & Go'],
  ['spin', 'Spin & Go'],
] as const

export function chartMatches(c: Chart, f: PreflopFilters, ignore?: keyof PreflopFilters): boolean {
  return (
    (ignore === 'format' || c.game_format === f.format) &&
    (ignore === 'source' || f.source === ALL || c.source === f.source) &&
    (ignore === 'rake' || f.rake === ALL || c.rake === f.rake) &&
    (ignore === 'players' || c.players === f.players)
  )
}

export function applyFilters(charts: Chart[], f: PreflopFilters): Chart[] {
  return charts.filter((c) => chartMatches(c, f))
}

export interface FilterOptions {
  formats: Option<string>[]
  sources: Option<string>[]
  rakes: Option<string>[]
  players: Option<string>[]
}

function unique<T>(values: T[]): T[] {
  return [...new Set(values)]
}

/** Each card counts the charts that match the other three filters. */
export function filterOptions(charts: Chart[], f: PreflopFilters): FilterOptions {
  const count = (ignore: keyof PreflopFilters, pred: (c: Chart) => boolean) =>
    charts.filter((c) => chartMatches(c, f, ignore) && pred(c)).length
  const withCurrent = (opts: Option<string>[], current: string, label: string) =>
    opts.some((o) => o.value === current) ? opts : [...opts, { value: current, label, count: 0 }]

  const formats = FORMAT_LABELS.map(([value, label]) => ({
    value,
    label,
    count: count('format', (c) => c.game_format === value),
  }))

  const known = SOURCES.map(([v]) => v as string)
  const present = unique(charts.map((c) => c.source))
  const sourceValues = [...known.filter((v) => present.includes(v)), ...present.filter((v) => !known.includes(v))]
  const sources = withCurrent(
    [
      { value: ALL, label: 'Todas', count: count('source', () => true) },
      ...sourceValues.map((v) => ({ value: v, label: SOURCE_LABEL[v] ?? v, count: count('source', (c) => c.source === v) })),
    ],
    f.source,
    SOURCE_LABEL[f.source] ?? f.source,
  )

  const rakeValues = unique(charts.map((c) => c.rake).filter((r): r is string => !!r)).sort()
  const rakes = withCurrent(
    [
      { value: ALL, label: 'Todos', count: count('rake', () => true) },
      ...rakeValues.map((v) => ({ value: v, label: v, count: count('rake', (c) => c.rake === v) })),
    ],
    f.rake,
    f.rake,
  )

  const presentPlayers = unique(charts.map((c) => c.players)).sort((a, b) => a - b)
  const playerValues = presentPlayers.length ? presentPlayers : [6, 9]
  const players = withCurrent(
    playerValues.map((n) => ({ value: String(n), label: `${n}-max`, count: count('players', (c) => c.players === n) })),
    String(f.players),
    `${f.players}-max`,
  )

  return { formats, sources, rakes, players }
}

export function defaultFilters(charts: Chart[]): PreflopFilters {
  const format = FORMAT_LABELS.find(([v]) => charts.some((c) => c.game_format === v))?.[0] ?? 'cash'
  const sizes = new Map<number, number>()
  for (const c of charts) if (c.game_format === format) sizes.set(c.players, (sizes.get(c.players) ?? 0) + 1)
  const players = [...sizes].sort((a, b) => b[1] - a[1] || a[0] - b[0])[0]?.[0] ?? 6
  return { format, source: ALL, rake: ALL, players }
}

export function isPreflopFilters(v: unknown): v is PreflopFilters {
  if (typeof v !== 'object' || v === null) return false
  const o = v as Record<string, unknown>
  return (
    typeof o.format === 'string' &&
    typeof o.source === 'string' &&
    typeof o.rake === 'string' &&
    typeof o.players === 'number' &&
    Number.isInteger(o.players) &&
    o.players >= 2 &&
    o.players <= 10
  )
}

export function filtersSummary(f: PreflopFilters): string {
  const format = FORMAT_LABELS.find(([v]) => v === f.format)?.[1] ?? f.format
  const source = f.source === ALL ? 'Todas las fuentes' : (SOURCE_LABEL[f.source] ?? f.source)
  const rake = f.rake === ALL ? 'Todos los stakes' : f.rake
  return `${format} · ${source} · ${rake} · ${f.players}-max`
}
