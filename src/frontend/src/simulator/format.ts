export function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return '—'
  return `${(value * 100).toFixed(digits)}%`
}

export function num(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return '—'
  return value.toFixed(digits)
}

/** Colour of an action segment in the frequency bars; fold gets its own grey so it shows on the card. */
export function barColor(action: string): string {
  return action === 'fold' ? 'var(--action-fold-bar)' : `var(--action-${action}, var(--text-dim))`
}
