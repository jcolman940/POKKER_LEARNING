export interface PendingJob {
  id: number
  status: string
  iteration: number
  exploitability: number | null
  position: number | null
}

export interface StrategyLayer {
  action: string
  label: string
  grid: number[]
}

export interface SolverJob {
  id: number
  label: string
  origin: 'simulator' | 'batch' | 'library'
  priority: number
  status: 'queued' | 'running' | 'done' | 'failed' | 'cancelled'
  iteration: number
  exploitability: number | null
  error: string | null
  position: number | null
  spot_hash: string
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface SolverStatus {
  configured: boolean
  path: string | null
  threads: number
  paused: boolean
  cache_entries: number
  cache_bytes: number
  presets: { name: string; label: string }[]
}

export interface PrefillRange {
  text: string | null
  approximate: boolean
  notes: string[]
  missing: string | null
}

export interface PrefillResponse {
  aggressor: PrefillRange
  caller: PrefillRange
}

export interface LibraryEntry {
  flop: string
  status: 'solved' | 'queued' | 'running' | 'missing_chart' | 'outdated' | 'pending'
  spot_hash: string | null
  job_id: number | null
}

export interface LibraryLine {
  id: string
  label: string
  missing: string[]
  approximate: boolean
  entries: LibraryEntry[]
}

export interface LibraryFamily {
  id: string
  label: string
  preset: string
  lines: LibraryLine[]
}

export interface SolverNodeAction {
  index: number
  kind: string
  label: string
  amount_bb: number | null
  frequency: number
  has_child: boolean
}

export interface SolverNode {
  player: 'oop' | 'ip'
  path: string
  actions: SolverNodeAction[]
  layers: StrategyLayer[]
}
