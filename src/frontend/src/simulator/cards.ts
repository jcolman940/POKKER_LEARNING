export const RANKS = 'AKQJT98765432'.split('') // display order, aces first
export const SUITS = ['s', 'h', 'd', 'c'] as const
export type Suit = (typeof SUITS)[number]

export const SUIT_SYMBOL: Record<Suit, string> = { s: '♠', h: '♥', d: '♦', c: '♣' }
export const SUIT_NAME: Record<Suit, string> = {
  s: 'picas',
  h: 'corazones',
  d: 'diamantes',
  c: 'tréboles',
}

export const STREET_BOARD_SIZE = { preflop: 0, flop: 3, turn: 4, river: 5 } as const

/** A card slot holds a card like "Ah" or null when empty. */
export type Slot = string | null

export function splitCards(text: string | null | undefined): string[] {
  const out: string[] = []
  const compact = (text ?? '').replace(/[\s,]/g, '')
  for (let i = 0; i + 1 < compact.length; i += 2) out.push(compact.slice(i, i + 2))
  return out
}

export function toSlots(text: string | null | undefined, size: number): Slot[] {
  const cards = splitCards(text)
  return Array.from({ length: size }, (_, i) => cards[i] ?? null)
}

export function joinSlots(slots: Slot[]): string {
  return slots.filter((s): s is string => s !== null).join('')
}

/** 13x13 grid labels in the same order as the backend: aces first, suited above the diagonal. */
export function handClassName(index: number): string {
  const row = Math.floor(index / 13)
  const col = index % 13
  if (row === col) return RANKS[row] + RANKS[col]
  if (row < col) return RANKS[row] + RANKS[col] + 's'
  return RANKS[col] + RANKS[row] + 'o'
}
