import { handClassName } from '../simulator/cards'
import { ACTION_LABEL, pctOfHands } from './labels'

/** `AA,AKs:0.5,...` in matrix order (PioViewer / ProPokerTools weights). */
export function gridToNotation(grid: number[]): string {
  const parts: string[] = []
  grid.forEach((w, i) => {
    if (w <= 0) return
    const rounded = Math.round(w * 1000) / 1000
    parts.push(rounded >= 1 ? handClassName(i) : `${handClassName(i)}:${rounded}`)
  })
  return parts.join(',')
}

export function actionLabel(action: string): string {
  return ACTION_LABEL[action] ?? action
}

/** One line per action that has hands: `Raise: AA,AKs:0.5`. */
export function chartToText(actions: Record<string, number[]>): string {
  return Object.entries(actions)
    .map(([action, grid]) => [action, gridToNotation(grid)] as const)
    .filter(([, notation]) => notation !== '')
    .map(([action, notation]) => `${actionLabel(action)}: ${notation}`)
    .join('\n')
}

/** Share of the 1326 combos played (any action but fold), each cell capped at 100%. */
export function rangeStats(actions: Record<string, number[]>): { pct: number; combos: number } {
  const played = Array<number>(169).fill(0)
  for (const [action, grid] of Object.entries(actions)) {
    if (action === 'fold') continue
    grid.forEach((w, i) => {
      played[i] = Math.min(1, played[i] + w)
    })
  }
  const pct = pctOfHands(played)
  return { pct, combos: Math.round(pct * 1326) }
}

export function formatPct(fraction: number): string {
  return `${(fraction * 100).toFixed(1).replace('.', ',')}%`
}
