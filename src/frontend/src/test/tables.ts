import { DEFAULT_ADVANCED, newSeat, type Seat, type SeatRole, type TableState } from '../simulator/table'

export function seat(position: string, role: SeatRole = 'folded', extra: Partial<Seat> = {}): Seat {
  return { ...newSeat(position), role, ...extra }
}

/** 6-max cash table on the flop: Hero BTN vs BB, everyone else folded, pot 6.5bb, no bets. */
export function makeTable(o: Partial<TableState> = {}): TableState {
  return {
    format: 'cash',
    num_players: 6,
    street: 'flop',
    seats: [
      seat('LJ'),
      seat('HJ'),
      seat('CO'),
      seat('BTN', 'hero'),
      seat('SB'),
      seat('BB', 'villain'),
    ],
    pot_bb: 6.5,
    board: 'Kh7c2d',
    hero_hand: 'AhKs',
    advanced: { ...DEFAULT_ADVANCED },
    ...o,
  }
}
