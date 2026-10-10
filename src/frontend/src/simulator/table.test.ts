import { describe, expect, it } from 'vitest'
import { makeTable, seat } from '../test/tables'
import {
  BOARD_CARDS,
  boardForStreet,
  heroSeat,
  newSeat,
  presetBet,
  previousActionFrom,
  rotateFromHero,
  seatPoint,
  seatsFor,
  setRole,
  streetFromBoard,
  tableToScenario,
  totalPot,
  updateSeat,
  validateTable,
  villainSeats,
} from './table'

const SIX = ['LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']

describe('seats', () => {
  it('new seats are folded, 100bb deep and play any hand', () => {
    expect(newSeat('CO')).toEqual({ position: 'CO', role: 'folded', bet_bb: 0, stack_bb: 100, range: 'random', hand: null })
  })

  it('builds the table in position order and keeps what each position had', () => {
    const seats = seatsFor(SIX, [seat('BB', 'villain', { range: 'QQ+' }), seat('BTN', 'hero')], 100)
    expect(seats.map((s) => s.position)).toEqual(SIX)
    expect(seats.find((s) => s.position === 'BB')).toMatchObject({ role: 'villain', range: 'QQ+' })
    expect(heroSeat(seats)?.position).toBe('BTN')
  })

  it('moves the hero to BTN when its position no longer exists (9-max → 6-max)', () => {
    const seats = seatsFor(SIX, [seat('UTG+2', 'hero'), seat('UTG', 'villain')], 40)
    expect(heroSeat(seats)?.position).toBe('BTN')
    expect(villainSeats(seats)).toEqual([])
    // positions that disappear are dropped; every seat is new, with the default stack
    expect(seats.every((s) => s.stack_bb === 40)).toBe(true)
  })

  it('uses the default stack for new seats', () => {
    expect(seatsFor(SIX, [], 40).find((s) => s.position === 'CO')?.stack_bb).toBe(40)
  })

  it('keeps the seats as they are while positions are unknown', () => {
    const prev = [seat('BTN', 'hero')]
    expect(seatsFor([], prev, 100)).toBe(prev)
  })
})

describe('roles', () => {
  const table = SIX.map((p) => seat(p, p === 'BTN' ? 'hero' : p === 'BB' ? 'villain' : 'folded'))

  it('picking "Vos" on another seat folds the old hero seat and clears the new one\'s cards', () => {
    const withHand = updateSeat(table, 'BB', { hand: 'AsAd', bet_bb: 3 })
    const seats = setRole(withHand, 'BB', 'hero')
    expect(heroSeat(seats)).toMatchObject({ position: 'BB', hand: null, bet_bb: 3 })
    expect(seats.find((s) => s.position === 'BTN')).toMatchObject({ role: 'folded', bet_bb: 0 })
  })

  it('folding or emptying a seat takes back its bet', () => {
    const seats = setRole(updateSeat(table, 'BB', { bet_bb: 4 }), 'BB', 'folded')
    expect(seats.find((s) => s.position === 'BB')).toMatchObject({ role: 'folded', bet_bb: 0 })
  })

  it('lists rivals in table order', () => {
    const seats = setRole(table, 'CO', 'villain')
    expect(villainSeats(seats).map((s) => s.position)).toEqual(['CO', 'BB'])
  })
})

describe('geometry', () => {
  it('starts the drawing order at the hero, then clockwise', () => {
    const seats = SIX.map((p) => seat(p, p === 'BB' ? 'hero' : 'folded'))
    expect(rotateFromHero(seats).map((s) => s.position)).toEqual(['BB', 'LJ', 'HJ', 'CO', 'BTN', 'SB'])
  })

  it('puts the hero at the bottom centre and the next seat to the lower left', () => {
    expect(seatPoint(0, 6)).toEqual({ left: 50, top: 88 })
    const next = seatPoint(1, 6)
    expect(next.left).toBeLessThan(50)
    expect(next.top).toBeGreaterThan(48)
    const across = seatPoint(3, 6)
    expect(across).toEqual({ left: 50, top: 8 })
  })

  it('scales towards the centre for bets', () => {
    expect(seatPoint(0, 6, 0.5)).toEqual({ left: 50, top: 68 })
  })
})

// BB (hero) faces CO bet 4 and BTN call 4 on the flop, pot 6.5 before the bets.
function bbVsTwo() {
  return makeTable({
    seats: [
      seat('LJ'),
      seat('HJ'),
      seat('CO', 'villain', { bet_bb: 4, stack_bb: 93 }),
      seat('BTN', 'villain', { bet_bb: 4, stack_bb: 93 }),
      seat('SB'),
      seat('BB', 'hero', { stack_bb: 96 }),
    ],
  })
}

describe('streets', () => {
  it('maps board size to a street and cuts the board to the street', () => {
    expect(BOARD_CARDS).toEqual({ preflop: 0, flop: 3, turn: 4, river: 5 })
    expect(streetFromBoard('')).toBe('preflop')
    expect(streetFromBoard('AsKs')).toBe('preflop')
    expect(streetFromBoard('Kh7s2c')).toBe('flop')
    expect(streetFromBoard('Kh7s2c3d')).toBe('turn')
    expect(streetFromBoard('Kh7s2c3d9h')).toBe('river')
    expect(boardForStreet('Kh7s2c3d9h', 'flop')).toBe('Kh7s2c')
    expect(boardForStreet('Kh7s2c3d9h', 'preflop')).toBe('')
  })
})

describe('tableToScenario', () => {
  it('adds every current bet to the pot and computes what you face', () => {
    const s = tableToScenario(bbVsTwo())
    expect(s).toMatchObject({
      format: 'cash',
      num_players: 6,
      hero_position: 'BB',
      hero_hand: 'AhKs',
      board: 'Kh7c2d',
      pot_bb: 14.5,
      to_call_bb: 4,
      effective_stack_bb: 93,
      previous_action: 'CO bet 4, BTN call 4',
      stacks_bb: {},
      payouts: [],
      hero_range: null,
      solver_preset: 'chico',
    })
    expect(s.villains).toEqual([
      { position: 'CO', range: 'random', hand: null },
      { position: 'BTN', range: 'random', hand: null },
    ])
  })

  it('counts your own bet in the pot and subtracts it from what you face', () => {
    const t = bbVsTwo()
    t.seats = updateSeat(t.seats, 'BB', { bet_bb: 4 })
    t.seats = updateSeat(t.seats, 'CO', { bet_bb: 12 })
    t.seats = updateSeat(t.seats, 'BTN', { bet_bb: 0 })
    const s = tableToScenario(t)
    expect(s.pot_bb).toBe(22.5)
    expect(s.to_call_bb).toBe(8)
    expect(s.previous_action).toBe('CO bet 12, BB call 4')
  })

  it('caps what you face at your stack (short all-in)', () => {
    const t = bbVsTwo()
    t.seats = updateSeat(t.seats, 'BB', { stack_bb: 3 })
    expect(tableToScenario(t).to_call_bb).toBe(3)
  })

  it('a rival all-in for less than the top bet reads as a call', () => {
    const t = bbVsTwo()
    t.seats = updateSeat(t.seats, 'BTN', { bet_bb: 2, stack_bb: 2 })
    expect(previousActionFrom(t)).toBe('CO bet 4, BTN call 2')
  })

  it('opens with raise preflop and prefers the text typed by hand', () => {
    const t = makeTable({ street: 'preflop', board: '', seats: [seat('CO', 'villain', { bet_bb: 2.5 }), seat('BTN', 'hero')] })
    expect(previousActionFrom(t)).toBe('CO raise 2.5')
    t.advanced = { ...t.advanced, previous_action: 'CO abre 2.5bb' }
    expect(tableToScenario(t).previous_action).toBe('CO abre 2.5bb')
  })

  it('sends stacks and payouts only in tournaments', () => {
    const t = makeTable({ format: 'mtt' })
    t.advanced = { ...t.advanced, payouts: [50, 30, 20] }
    const s = tableToScenario(t)
    expect(s.stacks_bb).toMatchObject({ BTN: 100, BB: 100, CO: 100 })
    expect(s.payouts).toEqual([50, 30, 20])
  })

  it('ignores empty seats in pot and stacks', () => {
    const t = makeTable({ format: 'mtt' })
    t.seats = updateSeat(t.seats, 'LJ', { role: 'empty', bet_bb: 5 })
    const s = tableToScenario(t)
    expect(s.pot_bb).toBe(6.5)
    expect(s.stacks_bb).not.toHaveProperty('LJ')
  })
})

describe('bet presets', () => {
  it('sizes on the total pot, capped at the stack; all-in is the stack', () => {
    const t = bbVsTwo() // total pot 14.5
    expect(presetBet(t, 'BB', 'half')).toBe(7.25)
    expect(presetBet(t, 'BB', 'pot')).toBe(14.5)
    expect(presetBet(t, 'BB', 'third')).toBe(4.83)
    expect(presetBet(t, 'BB', 'twothirds')).toBe(9.67)
    expect(presetBet(t, 'BB', 'allin')).toBe(96)
    t.seats = updateSeat(t.seats, 'BB', { stack_bb: 10 })
    expect(presetBet(t, 'BB', 'pot')).toBe(10)
  })

  it('the total pot adds the bets to the previous streets', () => {
    expect(totalPot(bbVsTwo())).toBe(14.5)
  })
})

describe('validateTable', () => {
  it('accepts a complete table', () => {
    expect(validateTable(bbVsTwo())).toBeNull()
  })

  it('needs exactly one hero and at least one rival', () => {
    const t = bbVsTwo()
    expect(validateTable({ ...t, seats: updateSeat(t.seats, 'BB', { role: 'folded' }) })).toMatch(/Elegí tu asiento/)
    const noRival = t.seats.map((s) => (s.role === 'villain' ? { ...s, role: 'folded' as const } : s))
    expect(validateTable({ ...t, seats: noRival })).toMatch(/al menos un rival/)
  })

  it('needs your two cards and the board of the street', () => {
    expect(validateTable({ ...bbVsTwo(), hero_hand: 'Ah' })).toMatch(/tus dos cartas/)
    expect(validateTable({ ...bbVsTwo(), street: 'turn' })).toBe('Faltan cartas del board: el turn lleva 4.')
    expect(validateTable({ ...bbVsTwo(), street: 'preflop', board: '' })).toBeNull()
  })

  it('rejects a bet bigger than the stack', () => {
    const t = bbVsTwo()
    expect(validateTable({ ...t, seats: updateSeat(t.seats, 'CO', { bet_bb: 120 }) })).toBe(
      'La apuesta de CO supera su stack.',
    )
  })

  it('rejects repeated cards across hand, board and rivals', () => {
    const t = bbVsTwo()
    expect(validateTable({ ...t, board: 'AhQc2d' })).toBe('Hay cartas repetidas.')
    expect(validateTable({ ...t, seats: updateSeat(t.seats, 'CO', { hand: 'Kh9s' }) })).toBe('Hay cartas repetidas.')
  })
})
