import { deleteJson, getJson, postJson } from '../api/client'
import type {
  AnswerBody,
  Feedback,
  FrequentError,
  Payout,
  SessionRequest,
  Sources,
  Spot,
  Summary,
} from './types'

export const fetchSources = (signal?: AbortSignal) => getJson<Sources>('/api/trainer/sources', signal)
export const fetchPayouts = (signal?: AbortSignal) => getJson<Payout[]>('/api/trainer/payouts', signal)
export const fetchFrequentErrors = (signal?: AbortSignal) =>
  getJson<FrequentError[]>('/api/trainer/frequent-errors', signal)
export const createSession = (body: SessionRequest) =>
  postJson<{ id: number; filters: unknown }>('/api/trainer/sessions', body)
export const nextSpot = (sessionId: number) => postJson<Spot>(`/api/trainer/sessions/${sessionId}/next`, {})
export const answerSpot = (spotId: string, body: AnswerBody) =>
  postJson<Feedback>(`/api/trainer/spots/${spotId}/answer`, body)
export const createPayout = (name: string, payouts: number[]) =>
  postJson<Payout>('/api/trainer/payouts', { name, payouts })
export const deletePayout = (id: number) => deleteJson(`/api/trainer/payouts/${id}`)
export const fetchSummary = (sessionId: number) => getJson<Summary>(`/api/trainer/sessions/${sessionId}`)
