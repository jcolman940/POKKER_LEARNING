import { describe, expect, it } from 'vitest'
import { makeChart } from '../test/charts'
import { ALL } from './preflopFilters'
import {
  DEFAULT_SELECTION,
  draftFor,
  matchingCharts,
  resolveSelection,
  situationText,
  viewerOptions,
} from './preflopSelection'

const SIX = ['LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']
const CHARTS = [
  makeChart({ id: 1, position: 'BTN', situation: 'rfi', stack_bb: 100 }),
  makeChart({ id: 2, position: 'BTN', situation: 'rfi', stack_bb: 40 }),
  makeChart({ id: 3, position: 'CO', situation: 'rfi', stack_bb: 100 }),
  makeChart({ id: 4, position: 'BB', situation: 'vs_open', vs_position: 'BTN', stack_bb: 100 }),
  makeChart({ id: 5, position: 'BB', situation: 'vs_open', vs_position: 'CO', stack_bb: 100 }),
]

describe('viewerOptions', () => {
  it('lists situations in spec order and dims those without charts', () => {
    const o = viewerOptions(CHARTS, SIX, DEFAULT_SELECTION)
    expect(o.situations.map((s) => s.label)).toEqual([
      'Open raise (RFI)',
      'vs open',
      'vs 3-bet',
      'vs 4-bet',
      'Squeeze',
      'Ciega vs ciega',
      'vs all-in',
    ])
    expect(o.situations.filter((s) => !s.disabled).map((s) => s.value)).toEqual(['rfi', 'vs_open'])
  })

  it('dims positions without a chart for the situation; no rival row in RFI', () => {
    const o = viewerOptions(CHARTS, SIX, DEFAULT_SELECTION)
    expect(o.positions.filter((p) => !p.disabled).map((p) => p.value)).toEqual(['CO', 'BTN'])
    expect(o.vsPositions).toEqual([])
    expect(o.stacks).toEqual([40, 100])
  })

  it('offers rivals in table order for situations that have one', () => {
    const o = viewerOptions(CHARTS, SIX, { situation: 'vs_open', position: 'BB', vsPosition: 'CO', stack: 100 })
    expect(o.vsPositions.map((v) => v.value)).toEqual(['CO', 'BTN'])
  })

  it('falls back to the positions found in the charts when the endpoint list is empty', () => {
    const o = viewerOptions(CHARTS, [], DEFAULT_SELECTION)
    expect(o.positions.map((p) => p.value)).toEqual(['BTN', 'CO', 'BB'])
  })
})

describe('resolveSelection', () => {
  it('keeps a valid selection', () => {
    expect(resolveSelection(CHARTS, SIX, DEFAULT_SELECTION)).toEqual(DEFAULT_SELECTION)
  })

  it('cascades: missing position → first available, missing rival → first rival', () => {
    const s = resolveSelection(CHARTS, SIX, { situation: 'vs_open', position: 'BTN', vsPosition: null, stack: 100 })
    expect(s).toEqual({ situation: 'vs_open', position: 'BB', vsPosition: 'CO', stack: 100 })
  })

  it('moves to the first situation with charts and the closest stack', () => {
    const s = resolveSelection(CHARTS, SIX, { situation: 'squeeze', position: 'BTN', vsPosition: 'SB', stack: 50 })
    expect(s).toEqual({ situation: 'rfi', position: 'BTN', vsPosition: null, stack: 40 })
  })

  it('leaves the selection alone when nothing matches the filters', () => {
    expect(resolveSelection([], SIX, DEFAULT_SELECTION)).toEqual(DEFAULT_SELECTION)
  })
})

describe('matchingCharts', () => {
  it('returns duplicates newest first', () => {
    const older = makeChart({ id: 10, source: 'pokalab', updated_at: '2026-10-01T00:00:00' })
    const newer = makeChart({ id: 11, source: 'custom', updated_at: '2026-10-05T00:00:00' })
    expect(matchingCharts([older, newer], DEFAULT_SELECTION).map((c) => c.id)).toEqual([11, 10])
  })

  it('matches the rival exactly', () => {
    const sel = { situation: 'vs_open', position: 'BB', vsPosition: 'BTN', stack: 100 }
    expect(matchingCharts(CHARTS, sel).map((c) => c.id)).toEqual([4])
  })
})

describe('draftFor', () => {
  it('pre-fills a custom chart with the visible context', () => {
    const d = draftFor(
      { format: 'mtt', source: ALL, rake: 'GG NL50', players: 9 },
      { situation: 'vs_open', position: 'BB', vsPosition: 'BTN', stack: 40 },
    )
    expect(d).toMatchObject({
      source: 'custom',
      game_format: 'mtt',
      players: 9,
      position: 'BB',
      vs_position: 'BTN',
      situation: 'vs_open',
      stack_bb: 40,
      open_size_bb: null,
      rake: 'GG NL50',
    })
    expect(d.actions.raise).toHaveLength(169)
  })

  it('has an open size for RFI and no rake for "all"', () => {
    const d = draftFor({ format: 'cash', source: ALL, rake: ALL, players: 6 }, DEFAULT_SELECTION)
    expect(d.open_size_bb).toBe(2.5)
    expect(d.rake).toBeNull()
  })
})

describe('situationText', () => {
  it('uses the viewer labels', () => {
    expect(situationText('bvb')).toBe('Ciega vs ciega')
  })
})
