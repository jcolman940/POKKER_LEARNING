import { deleteJson, getJson, postJson } from '../api/client'
import type {
  LibraryFamily,
  PrefillResponse,
  SolverJob,
  SolverNode,
  SolverStatus,
} from './types'

const BASE = '/api/solver'

export const fetchSolverStatus = () => getJson<SolverStatus>(`${BASE}/status`)
export const fetchJobs = () => getJson<SolverJob[]>(`${BASE}/jobs`)
export const fetchJob = (id: number) => getJson<SolverJob>(`${BASE}/jobs/${id}`)
export const cancelJob = (id: number) => postJson<SolverJob>(`${BASE}/jobs/${id}/cancel`, {})
export const retryJob = (id: number) => postJson<SolverJob>(`${BASE}/jobs/${id}/retry`, {})
export const pauseQueue = () => postJson<{ paused: boolean }>(`${BASE}/queue/pause`, {})
export const resumeQueue = () => postJson<{ paused: boolean }>(`${BASE}/queue/resume`, {})
export const clearCache = () => deleteJson(`${BASE}/cache`)
export const fetchLibrary = () => getJson<LibraryFamily[]>(`${BASE}/library`)
export const enqueueLibrary = (family: string, line: string | null) =>
  postJson<{ enqueued: number; missing: string[] }>(`${BASE}/library/enqueue`, { family, line })
export interface BatchRequest {
  game_format: string
  players: number
  ante_total_bb: number
  preset: string
  line: {
    aggressor: string
    caller: string
    pot_type: 'srp' | '3bet'
    stack_bb: number
    open_size_bb: number
    threebet_size_bb?: number
  }
  flops: string[] | null
}
export const enqueueBatch = (body: BatchRequest) =>
  postJson<{ enqueued: number; missing: string[] }>(`${BASE}/batch`, body)
export const deleteCached = (hash: string) => deleteJson(`${BASE}/cache/${hash}`)
export const fetchNode = (hash: string, path: string) =>
  getJson<SolverNode>(`${BASE}/results/${hash}/node?path=${encodeURIComponent(path)}`)

export interface PrefillRequest {
  game_format: string
  players: number
  aggressor: string
  caller: string
  pot_type: 'srp' | '3bet'
  stack_bb: number
  ante_bb: number
}

export const prefillRanges = (body: PrefillRequest) =>
  postJson<PrefillResponse>(`${BASE}/prefill-ranges`, body)
