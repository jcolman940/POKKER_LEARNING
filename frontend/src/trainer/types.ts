import type { Recommendation } from '../simulator/types'

export type TrainerSource = 'pushfold' | 'chart' | 'range'
export type Mode = 'normal' | 'review' | 'frequent'

export interface SourceStatus {
  available: boolean
  reason: string | null
}
export type Sources = Record<TrainerSource, SourceStatus>

export interface Payout {
  id: number
  name: string
  payouts: number[]
  builtin: boolean
}

export interface SessionRequest {
  sources: TrainerSource[]
  formats: string[]
  positions: string[]
  situations: string[]
  stack_buckets: string[]
  mode: Mode
  difficulty: number
  payout_id: number | null
  card_ids?: number[]
  prefer_due?: boolean
}

export interface InitialFilters {
  positions?: string[]
  situations?: string[]
  formats?: string[]
  sources?: string[]
  preferDue?: boolean // serve overdue cards before new spots (leaks bridge)
}

export interface SpotScenario {
  format: string
  num_players: number
  hero_position: string | null
  hero_hand: string
  villains: { position: string | null; range: string; hand: string | null }[]
  situation: string | null
  effective_stack_bb: number
  ante_bb: number
  bb_ante_bb?: number
  stacks_bb: Record<string, number>
}

export interface Spot {
  spot_id: string
  kind: 'hand' | 'range'
  source: string
  scenario: SpotScenario | null
  offered: string[]
  title: string
  card_id: number | null
  review: boolean
}

export interface Feedback {
  verdict: 'correct' | 'acceptable' | 'error'
  loss: number
  loss_unit: string
  approximate: boolean
  chosen: string | null
  best: string | null
  recommendation: Recommendation | null
  reference_layers: { action: string; grid: number[] }[]
  hand_index: number | null
  range?: RangeFeedback | null
}

export interface Summary {
  spots: number
  correct: number
  acceptable: number
  error: number
  ev_loss_bb: number
  avg_freq_error: number | null
  avg_precision: number | null
}

export interface FrequentError {
  card_id: number
  key: string
  source: string
  label: string
  lapses: number
  reps: number
}

export interface RangeFeedback {
  target: number[]
  diff_grid: number[]
  top_classes: { hand_class: string; target: number; painted: number; weight: number }[]
  precision: number
}

export type AnswerBody = { action: string } | { painted: number[] }
