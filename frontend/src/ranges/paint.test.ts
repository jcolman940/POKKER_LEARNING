import { describe, expect, it } from 'vitest'
import { paintCell } from './paint'

const zeros = () => Array<number>(169).fill(0)

describe('paintCell', () => {
  it('sets the action and leaves other cells alone', () => {
    const out = paintCell({ raise: zeros() }, 'raise', 3, 0.6)
    expect(out.raise[3]).toBe(0.6)
    expect(out.raise[4]).toBe(0)
  })

  it('scales other actions down so a hand never exceeds 100%', () => {
    const start = { raise: zeros(), call: zeros() }
    start.call[0] = 1
    const out = paintCell(start, 'raise', 0, 0.3)
    expect(out.raise[0]).toBeCloseTo(0.3)
    expect(out.call[0]).toBeCloseTo(0.7)
  })

  it('keeps other actions when there is room', () => {
    const start = { raise: zeros(), call: zeros() }
    start.call[0] = 0.4
    const out = paintCell(start, 'raise', 0, 0.5)
    expect(out.call[0]).toBeCloseTo(0.4)
  })
})
