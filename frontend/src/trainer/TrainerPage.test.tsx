import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/fetchMock'
import { TrainerPage } from './TrainerPage'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const SOURCES = {
  pushfold: { available: true, reason: null },
  chart: { available: false, reason: 'Importá una tabla de rangos primero' },
  range: { available: true, reason: null },
}

const SPOT = {
  spot_id: 'abc',
  kind: 'hand',
  source: 'pushfold',
  scenario: {
    format: 'mtt',
    num_players: 6,
    hero_position: 'BTN',
    hero_hand: 'AsKd',
    villains: [{ position: 'CO', range: 'random', hand: null }],
    situation: 'rfi',
    effective_stack_bb: 8,
    ante_bb: 0.125,
    stacks_bb: {},
  },
  offered: ['fold', 'allin'],
  title: 'Push/fold',
  card_id: 7,
  review: false,
}

const FEEDBACK = {
  verdict: 'error',
  loss: 1.2,
  loss_unit: 'bb',
  approximate: false,
  chosen: 'fold',
  best: 'allin',
  recommendation: {
    available: true,
    message: null,
    source: 'nash',
    confidence: 'exact',
    hand_class: 'AKo',
    actions: [
      { action: 'allin', frequency: 0.9, ev: 0.5 },
      { action: 'fold', frequency: 0.1, ev: -0.1 },
    ],
    ev_unit: 'bb',
    reference: null,
    explanation: ['Con AKo conviene empujar'],
    warnings: [],
    pending_job: null,
    strategy_grid: [],
  },
  reference_layers: [{ action: 'allin', grid: Array(169).fill(0.5) }],
  hand_index: 1,
  card: { interval_days: 1, due_at: null, ease: 2.5 },
}

const SUMMARY = { spots: 1, correct: 0, acceptable: 0, error: 1, ev_loss_bb: 1.2, avg_freq_error: null, avg_precision: null }

function routes(extra: Record<string, () => { status?: number; json: unknown }> = {}) {
  return {
    'GET /api/trainer/sources': () => ({ json: SOURCES }),
    'GET /api/trainer/payouts': () => ({ json: [{ id: 1, name: 'Top 3', payouts: [50, 30, 20], builtin: true }] }),
    'GET /api/trainer/frequent-errors': () => ({ json: [] }),
    'POST /api/trainer/sessions/1/next': () => ({ json: SPOT }),
    'POST /api/trainer/sessions': () => ({ status: 201, json: { id: 1, filters: {} } }),
    'POST /api/trainer/spots/abc/answer': () => ({ json: FEEDBACK }),
    'GET /api/trainer/sessions/1': () => ({ json: SUMMARY }),
    ...extra,
  }
}

const user = {
  click: async (el: HTMLElement) => {
    fireEvent.click(el)
  },
  keyboard: async (keys: string) => {
    const key = keys === '{Enter}' ? 'Enter' : keys
    await act(async () => {}) // let passive effects (key listener) catch up with the last render
    fireEvent.keyDown(document.body, { key })
  },
}

async function start() {
  render(<TrainerPage />)
  const button = await screen.findByRole('button', { name: 'Empezar' })
  await user.click(button)
  await screen.findByText('Foldean hasta vos', { exact: false })
}

describe('TrainerPage', () => {
  it('shows the spot without any frequency or EV before answering', async () => {
    mockApi(routes())
    await start()
    expect(screen.getByRole('button', { name: /Fold/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /All-in/ })).toBeInTheDocument()
    expect(screen.queryByText(/\d\s*%/)).not.toBeInTheDocument()
    expect(screen.queryByText(/EV \d/)).not.toBeInTheDocument()
    expect(screen.queryByText('Recomendación')).not.toBeInTheDocument()
  })

  it('answers fold with the F key and shows verdict and bars', async () => {
    mockApi(routes())
    await start()
    await user.keyboard('f')
    expect(await screen.findByText('Error', { selector: '.verdict' })).toBeInTheDocument()
    expect(screen.getByText(/Tu acción: Fold/)).toBeInTheDocument()
    expect(screen.getByText(/−1,20 bb/)).toBeInTheDocument()
    expect(screen.getByText('90%')).toBeInTheDocument()
    expect(screen.getByRole('group', { name: /Referencia/ })).toBeInTheDocument()
  })

  it('asks for the next spot with Enter', async () => {
    const fetchMock = mockApi(routes())
    await start()
    await user.keyboard('f')
    await screen.findByText('Error', { selector: '.verdict' })
    await user.keyboard('{Enter}')
    await waitFor(() => {
      const nexts = fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/sessions/1/next'))
      expect(nexts).toHaveLength(2)
    })
  })

  it('disables a source with the reason from the backend', async () => {
    mockApi(routes())
    render(<TrainerPage />)
    const box = await screen.findByRole('checkbox', { name: /Tablas/ })
    expect(box).toBeDisabled()
    expect(screen.getByText('Importá una tabla de rangos primero')).toBeInTheDocument()
  })

  it('shows the no-spots message and clears filters', async () => {
    mockApi(
      routes({
        'POST /api/trainer/sessions/1/next': () => ({ status: 409, json: { detail: 'No hay spots' } }),
      }),
    )
    render(<TrainerPage />)
    await user.click(await screen.findByRole('button', { name: 'Empezar' }))
    expect(await screen.findByText('No hay spots para estos filtros')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Limpiar filtros' })).toBeInTheDocument()
  })

  it('trains only the frequent errors', async () => {
    const fetchMock = mockApi(
      routes({
        'GET /api/trainer/frequent-errors': () => ({
          json: [
            { card_id: 3, key: 'k3', source: 'pushfold', label: 'BTN AKo 8bb', lapses: 2, reps: 4 },
            { card_id: 5, key: 'k5', source: 'pushfold', label: 'SB 72o 6bb', lapses: 1, reps: 2 },
          ],
        }),
      }),
    )
    render(<TrainerPage />)
    await user.click(await screen.findByRole('button', { name: 'Entrenar solo estas' }))
    await waitFor(() => {
      const call = fetchMock.mock.calls.find(
        ([url, init]) => String(url) === '/api/trainer/sessions' && init?.method === 'POST',
      )
      expect(call).toBeTruthy()
      expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({ mode: 'frequent', card_ids: [3, 5] })
    })
  })
})
