import type { GameFormat, ScenarioInput, Street } from './types'

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

export const BOARD_CARDS: Record<Street, number> = { preflop: 0, flop: 3, turn: 4, river: 5 }
export const STREET_LABEL: Record<Street, string> = { preflop: 'Preflop', flop: 'Flop', turn: 'Turn', river: 'River' }

export function streetFromBoard(board: string): Street {
  const n = Math.floor(board.length / 2)
  return n >= 5 ? 'river' : n === 4 ? 'turn' : n === 3 ? 'flop' : 'preflop'
}

export function boardForStreet(board: string, street: Street): string {
  return board.slice(0, BOARD_CARDS[street] * 2)
}

const inPlay = (s: Seat) => s.role !== 'empty'

export function totalPot(t: TableState): number {
  return round2(t.pot_bb + t.seats.filter(inPlay).reduce((sum, s) => sum + s.bet_bb, 0))
}

export type BetPreset = 'third' | 'half' | 'twothirds' | 'pot' | 'allin'
const PRESET_SHARE: Record<Exclude<BetPreset, 'allin'>, number> = { third: 1 / 3, half: 1 / 2, twothirds: 2 / 3, pot: 1 }

export function presetBet(t: TableState, position: string, preset: BetPreset): number {
  const s = t.seats.find((x) => x.position === position)
  if (!s) return 0
  if (preset === 'allin') return s.stack_bb
  return round2(Math.min(s.stack_bb, totalPot(t) * PRESET_SHARE[preset]))
}

/** "CO bet 4, BTN call 4": table order; the opener bets (raises preflop), more raises, the same or less calls. */
export function previousActionFrom(t: TableState): string {
  const typed = t.advanced.previous_action.trim()
  if (typed) return typed
  let top = 0
  const parts: string[] = []
  for (const s of t.seats) {
    if (!inPlay(s) || s.bet_bb <= 0) continue
    const verb = top === 0 ? (t.street === 'preflop' ? 'raise' : 'bet') : s.bet_bb > top ? 'raise' : 'call'
    parts.push(`${s.position} ${verb} ${round2(s.bet_bb)}`)
    top = Math.max(top, s.bet_bb)
  }
  return parts.join(', ')
}

export function tableToScenario(t: TableState): ScenarioInput {
  const hero = heroSeat(t.seats)
  const villains = villainSeats(t.seats)
  const heroStack = hero?.stack_bb ?? 0
  const topBet = Math.max(0, ...t.seats.filter(inPlay).map((s) => s.bet_bb))
  const tournament = t.format !== 'cash'
  return {
    format: t.format,
    num_players: t.num_players,
    hero_position: hero?.position ?? null,
    hero_hand: t.hero_hand,
    villains: villains.map((v) => ({ position: v.position, range: v.range, hand: v.hand })),
    board: boardForStreet(t.board, t.street),
    pot_bb: totalPot(t),
    to_call_bb: round2(Math.min(heroStack, Math.max(0, topBet - (hero?.bet_bb ?? 0)))),
    effective_stack_bb: villains.length ? Math.min(heroStack, Math.max(...villains.map((v) => v.stack_bb))) : heroStack,
    previous_action: previousActionFrom(t),
    situation: t.advanced.situation,
    ante_bb: t.advanced.ante_bb,
    bb_ante_bb: t.advanced.bb_ante_bb,
    stacks_bb: tournament ? Object.fromEntries(t.seats.filter(inPlay).map((s) => [s.position, s.stack_bb])) : {},
    payouts: tournament ? t.advanced.payouts : [],
    hero_range: t.advanced.hero_range || null,
    ranges_approximate: t.advanced.ranges_approximate,
    solver_preset: t.advanced.solver_preset,
  }
}

/** First reason the table cannot be analyzed, or null. */
export function validateTable(t: TableState): string | null {
  if (t.seats.filter((s) => s.role === 'hero').length !== 1) return 'Elegí tu asiento: tocá un asiento y marcá "Vos".'
  const villains = villainSeats(t.seats)
  if (villains.length === 0) return 'Marcá al menos un rival en la mesa.'
  if (t.hero_hand.length !== 4) return 'Elegí tus dos cartas (o repartí al azar).'
  const need = BOARD_CARDS[t.street]
  if (Math.floor(t.board.length / 2) < need) {
    return `Faltan cartas del board: el ${STREET_LABEL[t.street].toLowerCase()} lleva ${need}.`
  }
  const over = t.seats.find((s) => inPlay(s) && s.bet_bb > s.stack_bb)
  if (over) return `La apuesta de ${over.position} supera su stack.`
  const cards = [t.hero_hand, boardForStreet(t.board, t.street), ...villains.map((v) => v.hand ?? '')].join('').match(/.{2}/g) ?? []
  if (new Set(cards).size !== cards.length) return 'Hay cartas repetidas.'
  return null
}

export const SIM_TABLE_KEY = 'pokker.simulator.table'
const FORMATS: GameFormat[] = ['cash', 'mtt', 'sng', 'spin']
const ROLES: SeatRole[] = ['hero', 'villain', 'folded', 'empty']

/** Cash/6-max unless the Preflop filters say otherwise: you on BTN against the BB, on the flop. */
export function defaultTable(filters: { format: string; players: number } | null): TableState {
  const format = filters && FORMATS.includes(filters.format as GameFormat) ? (filters.format as GameFormat) : 'cash'
  return {
    format,
    num_players: filters?.players ?? 6,
    street: 'flop',
    seats: [
      { ...newSeat('BTN'), role: 'hero' },
      { ...newSeat('BB'), role: 'villain' },
    ],
    pot_bb: 6.5,
    board: '',
    hero_hand: '',
    advanced: { ...DEFAULT_ADVANCED },
  }
}

/**
 * A scenario sent by Preflop or the replayer. The amount to call goes on the first rival as its
 * bet and the rest stays as pot, so tableToScenario gives back the same pot and price.
 */
export function tableFromInitial(i: Partial<ScenarioInput>, base: TableState): TableState {
  const stack = i.effective_stack_bb ?? 100
  const stackOf = (p: string) => i.stacks_bb?.[p] ?? stack
  const heroPos = i.hero_position ?? null
  const seats: Seat[] = []
  if (heroPos) seats.push({ ...newSeat(heroPos, stackOf(heroPos)), role: 'hero' })
  for (const v of i.villains ?? []) {
    if (!v.position || v.position === heroPos || seats.some((s) => s.position === v.position)) continue
    seats.push({ ...newSeat(v.position, stackOf(v.position)), role: 'villain', range: v.range || 'random', hand: v.hand ?? null })
  }
  const toCall = i.to_call_bb ?? 0
  const firstRival = seats.find((s) => s.role === 'villain')
  if (firstRival && toCall > 0) firstRival.bet_bb = toCall
  const board = i.board ?? ''
  const pot = i.pot_bb ?? (board === '' ? 1.5 : base.pot_bb)
  return {
    format: i.format ?? base.format,
    num_players: i.num_players ?? base.num_players,
    street: streetFromBoard(board),
    seats: seats.length ? seats : base.seats,
    pot_bb: round2(Math.max(0, pot - (firstRival ? toCall : 0))),
    board,
    hero_hand: i.hero_hand ?? '',
    advanced: {
      ...DEFAULT_ADVANCED,
      ante_bb: i.ante_bb ?? 0,
      bb_ante_bb: i.bb_ante_bb ?? 0,
      payouts: i.payouts ?? [],
      hero_range: i.hero_range ?? '',
      ranges_approximate: i.ranges_approximate ?? false,
      solver_preset: i.solver_preset ?? 'chico',
      situation: i.situation ?? null,
      previous_action: i.previous_action ?? '',
    },
  }
}

function isSeat(v: unknown): v is Seat {
  if (typeof v !== 'object' || v === null) return false
  const o = v as Record<string, unknown>
  return (
    typeof o.position === 'string' &&
    ROLES.includes(o.role as SeatRole) &&
    typeof o.bet_bb === 'number' &&
    typeof o.stack_bb === 'number' &&
    typeof o.range === 'string' &&
    (o.hand === null || typeof o.hand === 'string')
  )
}

export function isTableState(v: unknown): v is TableState {
  if (typeof v !== 'object' || v === null) return false
  const o = v as Record<string, unknown>
  const a = o.advanced as Record<string, unknown> | null | undefined
  return (
    FORMATS.includes(o.format as GameFormat) &&
    typeof o.num_players === 'number' &&
    typeof o.street === 'string' &&
    o.street in BOARD_CARDS &&
    Array.isArray(o.seats) &&
    o.seats.every(isSeat) &&
    typeof o.pot_bb === 'number' &&
    typeof o.board === 'string' &&
    typeof o.hero_hand === 'string' &&
    typeof a === 'object' &&
    a !== null &&
    typeof a.ante_bb === 'number' &&
    typeof a.bb_ante_bb === 'number' &&
    Array.isArray(a.payouts) &&
    typeof a.hero_range === 'string' &&
    typeof a.ranges_approximate === 'boolean' &&
    typeof a.solver_preset === 'string' &&
    (a.situation === null || typeof a.situation === 'string') &&
    typeof a.previous_action === 'string'
  )
}
