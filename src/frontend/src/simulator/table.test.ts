import { describe, expect, it } from 'vitest'
import { seat } from '../test/tables'
import { heroSeat, newSeat, rotateFromHero, seatPoint, seatsFor, setRole, updateSeat, villainSeats } from './table'

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
