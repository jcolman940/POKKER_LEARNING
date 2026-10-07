import type { Feedback } from './types'

export const SITUATION_TEXT: Record<string, string> = {
  rfi: 'Foldean hasta vos',
  vs_open: 'vs open',
  vs_3bet: 'vs 3-bet',
  vs_4bet: 'vs 4-bet',
  squeeze: 'Squeeze',
  bvb: 'Ciega vs ciega',
  vs_allin: 'vs all-in',
}

export const VERDICT_LABEL: Record<Feedback['verdict'], string> = {
  correct: 'Correcto',
  acceptable: 'Aceptable',
  error: 'Error',
}

const AGGRESSIVE = ['raise', 'allin', '3bet', '4bet', '5bet', 'bet']

/** Maps a pressed key to one of the offered actions (F fold, C call/limp, R first aggressive, 1-9 by index). */
export function actionForKey(key: string, offered: string[]): string | null {
  const k = key.toLowerCase()
  if (k === 'f') return offered.includes('fold') ? 'fold' : null
  if (k === 'c') return offered.find((a) => a === 'call' || a === 'limp' || a === 'check') ?? null
  if (k === 'r') return offered.find((a) => AGGRESSIVE.includes(a)) ?? null
  if (/^[1-9]$/.test(k)) return offered[Number(k) - 1] ?? null
  return null
}

export function lossText(fb: Feedback): string {
  if (fb.loss_unit === 'freq') return `Error de frecuencia ${Math.round(fb.loss * 100)}%`
  if (fb.verdict === 'correct' && fb.loss === 0) return 'Sin pérdida'
  const amount = fb.loss.toFixed(2).replace('.', ',')
  return `−${amount} ${fb.loss_unit}`
}
