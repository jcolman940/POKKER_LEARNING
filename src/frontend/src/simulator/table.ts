import type { GameFormat, Street } from './types'

export type SeatRole = 'hero' | 'villain' | 'folded' | 'empty'

export interface Seat {
  position: string
  role: SeatRole
  bet_bb: number
  stack_bb: number
  range: string
  hand: string | null
}

export interface AdvancedOptions {
  ante_bb: number
  bb_ante_bb: number
  payouts: number[]
  hero_range: string
  ranges_approximate: boolean
  solver_preset: string
  situation: string | null
  /** Typed by hand; empty = built from the bets on the table. */
  previous_action: string
}

export interface TableState {
  format: GameFormat
  num_players: number
  street: Street
  seats: Seat[]
  /** Pot from previous streets; the current bets are on the seats. */
  pot_bb: number
  board: string
  hero_hand: string
  advanced: AdvancedOptions
}

export const DEFAULT_ADVANCED: AdvancedOptions = {
  ante_bb: 0,
  bb_ante_bb: 0,
  payouts: [],
  hero_range: '',
  ranges_approximate: false,
  solver_preset: 'chico',
  situation: null,
  previous_action: '',
}

export function newSeat(position: string, stack = 100): Seat {
  return { position, role: 'folded', bet_bb: 0, stack_bb: stack, range: 'random', hand: null }
}

/** Seats in `positions` order, keeping what each position already had; there is always a hero. */
export function seatsFor(positions: string[], previous: Seat[], defaultStack: number): Seat[] {
  if (positions.length === 0) return previous
  const byPosition = new Map(previous.map((s) => [s.position, s]))
  const seats = positions.map((p) => byPosition.get(p) ?? newSeat(p, defaultStack))
  if (!seats.some((s) => s.role === 'hero')) {
    const i = Math.max(0, positions.indexOf('BTN'))
    seats[i] = { ...seats[i], role: 'hero', hand: null }
  }
  return seats
}

export function setRole(seats: Seat[], position: string, role: SeatRole): Seat[] {
  return seats.map((s) => {
    if (s.position === position) {
      const out = { ...s, role }
      if (role === 'folded' || role === 'empty') out.bet_bb = 0
      if (role === 'hero') out.hand = null // your cards live in TableState.hero_hand
      return out
    }
    if (role === 'hero' && s.role === 'hero') return { ...s, role: 'folded', bet_bb: 0 }
    return s
  })
}

export function updateSeat(seats: Seat[], position: string, patch: Partial<Seat>): Seat[] {
  return seats.map((s) => (s.position === position ? { ...s, ...patch } : s))
}

export function heroSeat(seats: Seat[]): Seat | undefined {
  return seats.find((s) => s.role === 'hero')
}

export function villainSeats(seats: Seat[]): Seat[] {
  return seats.filter((s) => s.role === 'villain')
}

/** Drawing order: the hero first (bottom centre), then clockwise in table order. */
export function rotateFromHero(seats: Seat[]): Seat[] {
  const h = seats.findIndex((s) => s.role === 'hero')
  return h <= 0 ? seats : [...seats.slice(h), ...seats.slice(0, h)]
}

const round2 = (n: number) => Math.round(n * 100) / 100

/** Seat k of n on the oval, as % of the stage; k = 0 is the bottom centre, then clockwise. */
export function seatPoint(k: number, n: number, scale = 1): { left: number; top: number } {
  const a = Math.PI / 2 + (2 * Math.PI * k) / n
  return { left: round2(50 + 42 * scale * Math.cos(a)), top: round2(48 + 40 * scale * Math.sin(a)) }
}
