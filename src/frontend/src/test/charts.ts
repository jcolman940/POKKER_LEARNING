import type { Chart } from '../ranges/types'

let nextId = 1

/** A valid chart for tests: cash 6-max BTN RFI 100bb raising AA unless overridden. */
export function makeChart(o: Partial<Chart> = {}): Chart {
  const raise = Array<number>(169).fill(0)
  raise[0] = 1
  return {
    id: nextId++,
    name: 'BTN RFI 100bb',
    source: 'pokalab',
    game_format: 'cash',
    players: 6,
    position: 'BTN',
    vs_position: null,
    stack_bb: 100,
    situation: 'rfi',
    open_size_bb: 2.5,
    rake: null,
    ante_bb: 0,
    note: '',
    actions: { raise },
    created_at: '2026-10-01T00:00:00',
    updated_at: '2026-10-01T00:00:00',
    ...o,
  }
}
