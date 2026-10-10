import { describe, expect, it } from 'vitest'
import { makeChart } from '../test/charts'
import {
  ALL,
  applyFilters,
  defaultFilters,
  filterOptions,
  filtersSummary,
  isPreflopFilters,
  type PreflopFilters,
} from './preflopFilters'

const CHARTS = [
  makeChart({ game_format: 'cash', players: 6, source: 'pokalab', rake: 'GG NL50' }),
  makeChart({ game_format: 'cash', players: 6, source: 'custom', rake: null }),
  makeChart({ game_format: 'cash', players: 9, source: 'pokalab', rake: 'GG NL50' }),
  makeChart({ game_format: 'mtt', players: 9, source: 'computed', rake: null }),
]

const CASH6: PreflopFilters = { format: 'cash', source: ALL, rake: ALL, players: 6 }
const count = (opts: { value: string; count?: number }[], value: string) => opts.find((o) => o.value === value)?.count

describe('applyFilters', () => {
  it('keeps charts matching every filter; "all" ignores source and rake', () => {
    expect(applyFilters(CHARTS, CASH6)).toHaveLength(2)
  })

  it('a specific rake drops charts without rake', () => {
    expect(applyFilters(CHARTS, { ...CASH6, rake: 'GG NL50' })).toHaveLength(1)
  })
})

describe('filterOptions', () => {
  it('always lists the 4 game formats, counted against the other filters', () => {
    const o = filterOptions(CHARTS, CASH6)
    expect(o.formats.map((x) => x.label)).toEqual(['Cash', 'Torneos', 'Sit & Go', 'Spin & Go'])
    expect(count(o.formats, 'cash')).toBe(2) // cash with 6 players
    expect(count(o.formats, 'mtt')).toBe(0) // the mtt chart is 9-max
  })

  it('counts players across formats only within the chosen format', () => {
    const o = filterOptions(CHARTS, CASH6)
    expect(o.players.map((x) => x.label)).toEqual(['6-max', '9-max'])
    expect(count(o.players, '6')).toBe(2)
    expect(count(o.players, '9')).toBe(1)
  })

  it('lists present sources and rakes after the "all" option', () => {
    const o = filterOptions(CHARTS, CASH6)
    expect(o.sources.map((x) => x.value)).toEqual([ALL, 'pokalab', 'custom', 'computed'])
    expect(o.sources[0].label).toBe('Todas')
    expect(count(o.sources, ALL)).toBe(2)
    expect(o.rakes.map((x) => x.value)).toEqual([ALL, 'GG NL50'])
    expect(o.rakes[0].label).toBe('Todos')
  })

  it('keeps a stored value that no longer exists, with count 0', () => {
    const o = filterOptions(CHARTS, { ...CASH6, rake: 'PS NL10', players: 8 })
    expect(o.rakes.find((x) => x.value === 'PS NL10')).toMatchObject({ count: 0 })
    expect(o.players.find((x) => x.value === '8')).toMatchObject({ label: '8-max', count: 0 })
  })

  it('offers 6-max and 9-max when there are no charts', () => {
    expect(filterOptions([], CASH6).players.map((x) => x.value)).toEqual(['6', '9'])
  })
})

describe('defaultFilters', () => {
  it('picks the first format with charts and its most common table size', () => {
    expect(defaultFilters(CHARTS)).toEqual({ format: 'cash', source: ALL, rake: ALL, players: 6 })
    expect(defaultFilters([makeChart({ game_format: 'mtt', players: 9 })])).toMatchObject({
      format: 'mtt',
      players: 9,
    })
  })

  it('falls back to cash 6-max with no charts', () => {
    expect(defaultFilters([])).toEqual(CASH6)
  })
})

describe('isPreflopFilters', () => {
  it('accepts a valid object and rejects anything else', () => {
    expect(isPreflopFilters(CASH6)).toBe(true)
    expect(isPreflopFilters({ ...CASH6, players: '6' })).toBe(false)
    expect(isPreflopFilters({ ...CASH6, players: 1 })).toBe(false)
    expect(isPreflopFilters({ format: 'cash' })).toBe(false)
    expect(isPreflopFilters(null)).toBe(false)
    expect(isPreflopFilters('cash')).toBe(false)
  })
})

describe('filtersSummary', () => {
  it('reads like the mockup chip', () => {
    expect(filtersSummary(CASH6)).toBe('Cash · Todas las fuentes · Todos los stakes · 6-max')
    expect(filtersSummary({ format: 'mtt', source: 'pokalab', rake: 'GG NL50', players: 9 })).toBe(
      'Torneos · Pokalab · GG NL50 · 9-max',
    )
  })
})
