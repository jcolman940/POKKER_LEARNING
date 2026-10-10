/** A card slot on the table: your two cards, the board, or a rival's optional cards. */
export type CardSlotRef =
  | { group: 'hero' | 'board'; index: number }
  | { group: 'seat'; position: string; index: number }

export function sameSlot(a: CardSlotRef | null, b: CardSlotRef): boolean {
  if (!a || a.group !== b.group || a.index !== b.index) return false
  return a.group !== 'seat' || (b.group === 'seat' && a.position === b.position)
}
