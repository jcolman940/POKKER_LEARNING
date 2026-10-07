export const ACTIONS = ['raise', 'limp', 'call', '3bet', '4bet', '5bet', 'allin'] as const
export type ChartAction = (typeof ACTIONS)[number]

export const ACTION_LABEL: Record<string, string> = {
  raise: 'Raise',
  limp: 'Limp',
  call: 'Call',
  '3bet': '3-bet',
  '4bet': '4-bet',
  '5bet': '5-bet',
  allin: 'All-in',
  fold: 'Fold',
  check: 'Check',
  bet: 'Bet',
}

export const SITUATIONS = [
  ['rfi', 'RFI (foldean hasta vos)'],
  ['vs_open', 'vs open'],
  ['vs_3bet', 'vs 3-bet'],
  ['vs_4bet', 'vs 4-bet'],
  ['squeeze', 'Squeeze'],
  ['bvb', 'Ciega vs ciega'],
  ['vs_allin', 'vs all-in'],
] as const
export type Situation = (typeof SITUATIONS)[number][0]
export const SITUATION_LABEL: Record<string, string> = Object.fromEntries(SITUATIONS)

export const SOURCES = [
  ['pokalab', 'Pokalab'],
  ['preflopranges', 'preflopranges.app'],
  ['custom', 'Propio'],
  ['computed', 'Calculado'],
] as const
export type ChartSource = (typeof SOURCES)[number][0]
export const SOURCE_LABEL: Record<string, string> = Object.fromEntries(SOURCES)

export const FORMATS = [
  ['cash', 'Cash'],
  ['mtt', 'Torneo (MTT)'],
  ['sng', 'Sit & Go'],
  ['spin', 'Spin & Go'],
] as const
export const FORMAT_LABEL: Record<string, string> = Object.fromEntries(FORMATS)

export function pctOfHands(grid: number[]): number {
  let combos = 0
  grid.forEach((w, i) => {
    const row = Math.floor(i / 13)
    const col = i % 13
    combos += w * (row === col ? 6 : row < col ? 4 : 12)
  })
  return combos / 1326
}
