/** Sets `action` to `value` at cell `i`, scaling the other actions down if needed. */
export function paintCell(
  actions: Record<string, number[]>,
  action: string,
  i: number,
  value: number,
): Record<string, number[]> {
  const next: Record<string, number[]> = {}
  const others = Object.keys(actions).filter((a) => a !== action)
  const othersTotal = others.reduce((s, a) => s + actions[a][i], 0)
  const room = 1 - value
  for (const [a, grid] of Object.entries(actions)) {
    const g = [...grid]
    if (a === action) g[i] = value
    else if (othersTotal > room) g[i] = othersTotal > 0 ? (g[i] * room) / othersTotal : 0
    next[a] = g
  }
  return next
}
