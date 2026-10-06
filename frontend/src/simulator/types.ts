export type GameFormat = 'cash' | 'mtt' | 'sng' | 'spin'
export type Street = 'preflop' | 'flop' | 'turn' | 'river'

export interface VillainInput {
  position: string | null
  range: string
  hand: string | null
}

export interface ScenarioInput {
  format: GameFormat
  num_players: number
  hero_position: string | null
  hero_hand: string
  villains: VillainInput[]
  board: string
  pot_bb: number
  to_call_bb: number
  effective_stack_bb: number
  previous_action: string
  situation: string | null
  ante_bb: number
  bb_ante_bb: number
  stacks_bb: Record<string, number>
  payouts: number[]
}

export interface RecommendedAction {
  action: string
  frequency: number
  ev: number | null
}

export interface Recommendation {
  available: boolean
  message: string | null
  source: 'chart' | 'nash' | 'solver' | 'heuristic' | null
  confidence: 'exact' | 'approximate' | null
  hand_class: string | null
  actions: RecommendedAction[]
  ev_unit: string | null
  reference: string | null
  explanation: string[]
  warnings: string[]
}

export interface PlayerEquity {
  equity: number
  win: number
  tie: number
  lose: number
  std_error: number
}

export interface EquityResult {
  hero: PlayerEquity
  villains: PlayerEquity[]
  exact: boolean
  samples: number
}

export interface Outs {
  available: boolean
  currently_ahead: boolean | null
  hero_share: number | null
  cards: string[]
  count: number
  unseen: number
}

export interface Metrics {
  pot_odds: number | null
  required_equity: number | null
  mdf: number | null
  spr: number | null
}

export interface Analysis {
  street: Street
  equity: EquityResult
  equity_vs_hands: EquityResult | null
  outs: Outs
  metrics: Metrics
  ranges: { text: string; combos: number }[]
  recommendation: Recommendation
}

export interface DealRequest {
  street: Street
  hero_hand: string
  board: string
  villain_hands: (string | null)[]
  deal_villains: number[]
}

export interface DealResult {
  hero_hand: string
  board: string
  villain_hands: (string | null)[]
}

export interface RangeParse {
  valid: boolean
  error: string | null
  combos: number
  grid: number[]
}
