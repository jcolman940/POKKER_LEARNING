import { describe, expect, it } from 'vitest'
import { actionLabel, chartToText, formatPct, gridToNotation, rangeStats } from './notation'

function grid(entries: Record<number, number>): number[] {
  const g = Array<number>(169).fill(0)
  for (const [i, w] of Object.entries(entries)) g[Number(i)] = w
  return g
}

describe('gridToNotation', () => {
  it('lists hand classes in matrix order with PioViewer weights', () => {
    // 0 = AA, 1 = AKs, 13 = AKo, 14 = KK
    expect(gridToNotation(grid({ 0: 1, 1: 0.5, 13: 0.25, 14: 1 }))).toBe('AA,AKs:0.5,AKo:0.25,KK')
  })

  it('rounds weights to 3 decimals and skips zeros', () => {
    expect(gridToNotation(grid({ 0: 0.33333, 1: 0 }))).toBe('AA:0.333')
  })

  it('is empty for an empty grid', () => {
    expect(gridToNotation(grid({}))).toBe('')
  })
})

describe('chartToText', () => {
  it('writes one line per action that has hands, with its label', () => {
    expect(chartToText({ raise: grid({ 0: 1 }), call: grid({}), '3bet': grid({ 1: 0.5 }) })).toBe(
      'Raise: AA\n3-bet: AKs:0.5',
    )
  })
})

describe('rangeStats', () => {
  it('counts played combos and ignores explicit fold layers', () => {
    // AA = 6 combos; fold on KK must not count
    const s = rangeStats({ raise: grid({ 0: 1 }), fold: grid({ 14: 1 }) })
    expect(s.combos).toBe(6)
    expect(s.pct).toBeCloseTo(6 / 1326, 6)
  })

  it('caps a cell at 100% when several actions overlap', () => {
    const s = rangeStats({ raise: grid({ 0: 0.8 }), call: grid({ 0: 0.8 }) })
    expect(s.combos).toBe(6)
  })
})

describe('labels and percentages', () => {
  it('uses the Spanish label and falls back to the raw action', () => {
    expect(actionLabel('3bet')).toBe('3-bet')
    expect(actionLabel('minraise')).toBe('minraise')
  })

  it('formats with a decimal comma', () => {
    expect(formatPct(0.421)).toBe('42,1%')
    expect(formatPct(0)).toBe('0,0%')
  })
})
