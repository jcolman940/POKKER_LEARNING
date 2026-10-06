import type { ScenarioInput } from '../simulator/types'

export interface ImportReport {
  totals: { files: number; hands_found: number; imported: number; duplicates: number; failed: number }
  files: { name: string; site: string | null; hands: number; imported: number; duplicates: number; failed: number }[]
  errors: { file: string; message: string; hand: number | null; line: number | null; excerpt: string | null }[]
  errors_truncated: boolean
}

export interface ImportOut {
  id: number
  created_at: string
  report: ImportReport
}

export interface HandSummary {
  id: number
  site: string
  hand_id: string
  played_at: string
  game_type: string
  table_size: number
  position: string | null
  hero_cards: string | null
  stack_bb: number
  net_bb: number
  allin_adj_bb: number
  showdown: boolean
}

export interface HandPage {
  total: number
  items: HandSummary[]
}

export interface ReplayPlayer {
  name: string
  seat: number
  position: string
  stack_bb: number
  is_hero: boolean
  cards: string | null
}

export interface ReplayStep {
  index: number
  street: 'preflop' | 'flop' | 'turn' | 'river'
  description: string
  actor: string | null
  board: string
  pot_bb: number
  stacks_bb: Record<string, number>
  bets_bb: Record<string, number>
  folded: string[]
  hero_equity: { equity: number; std_error: number; exact: boolean } | null
  scenario: Partial<ScenarioInput> | null
}

export interface Replay {
  site: string
  hand_id: string
  game_type: string
  bb: number
  players: ReplayPlayer[]
  ranges: Record<string, string>
  steps: ReplayStep[]
  result: Record<string, number>
}
