export interface Filters {
  game_types: string[]
  positions: string[]
  table_sizes: number[]
  stack_min: string
  stack_max: string
  date_from: string
  date_to: string
}

export const EMPTY_FILTERS: Filters = {
  game_types: [],
  positions: [],
  table_sizes: [],
  stack_min: '',
  stack_max: '',
  date_from: '',
  date_to: '',
}

export function filterQuery(f: Filters, extra: Record<string, string | number> = {}): string {
  const q = new URLSearchParams()
  f.game_types.forEach((v) => q.append('game_types', v))
  f.positions.forEach((v) => q.append('positions', v))
  f.table_sizes.forEach((v) => q.append('table_sizes', String(v)))
  if (f.stack_min) q.set('stack_min', f.stack_min)
  if (f.stack_max) q.set('stack_max', f.stack_max)
  if (f.date_from) q.set('date_from', f.date_from)
  if (f.date_to) q.set('date_to', nextDay(f.date_to)) // inclusive end date
  Object.entries(extra).forEach(([k, v]) => q.set(k, String(v)))
  const s = q.toString()
  return s ? `?${s}` : ''
}

function nextDay(date: string): string {
  const d = new Date(`${date}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() + 1)
  return d.toISOString().slice(0, 10)
}
