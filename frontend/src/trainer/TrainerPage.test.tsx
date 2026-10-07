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
  it('creates a single session on a double click of Empezar', async () => {
    const fetchMock = mockApi(routes())
    render(<TrainerPage />)
    const button = await screen.findByRole('button', { name: 'Empezar' })
    fireEvent.click(button)
    fireEvent.click(button)
    await screen.findByText('Foldean hasta vos', { exact: false })
    const created = fetchMock.mock.calls.filter(
      ([url, init]) => String(url) === '/api/trainer/sessions' && init?.method === 'POST',
    )
    expect(created).toHaveLength(1)
  })

  it('discards an answer that resolves after a new session started', async () => {
    const fetchMock = mockApi(routes())
    const base = fetchMock.getMockImplementation() as (u: RequestInfo | URL, i?: RequestInit) => Promise<Response>
    let release: () => void = () => {}
    const gate = new Promise<void>((r) => {
      release = r
    })
    vi.stubGlobal(
      'fetch',
      vi.fn(async (u: RequestInfo | URL, i?: RequestInit) => {
        if (String(u).includes('/answer')) await gate
        return base(u, i)
      }),
    )
    await start()
    await user.keyboard('f')
    await user.click(screen.getByRole('button', { name: 'Empezar' }))
    await waitFor(() => expect(screen.queryByText('Preparando spot…')).not.toBeInTheDocument())
    await act(async () => {
      release()
      await gate
    })
    await act(async () => {})
    expect(screen.queryByText('Error', { selector: '.verdict' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Fold/ })).toBeInTheDocument()
  })

  it('ignores shortcuts while typing in a field', async () => {
    const fetchMock = mockApi(routes())
    await start()
    await user.click(screen.getByRole('button', { name: 'Mostrar' }))
    fireEvent.keyDown(screen.getByRole('combobox', { name: /Modo/ }), { key: 'f' })
    await act(async () => {})
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/answer'))).toBe(false)
  })

  it('shows the server message when the session cannot be created', async () => {
    mockApi(
      routes({
        'POST /api/trainer/sessions': () => ({ status: 422, json: { detail: 'Elegí al menos una fuente' } }),
      }),
    )
    render(<TrainerPage />)
    fireEvent.click(await screen.findByRole('button', { name: 'Empezar' }))
    expect(await screen.findByText('Elegí al menos una fuente')).toBeInTheDocument()
  })

  it('clears the old spot when a new session fails to start', async () => {
    let fail = false
    mockApi(
      routes({
        'POST /api/trainer/sessions': () =>
          fail
            ? { status: 422, json: { detail: 'Elegí al menos una fuente' } }
            : { status: 201, json: { id: 1, filters: {} } },
      }),
    )
    await start()
    fail = true
    await user.click(screen.getByRole('button', { name: 'Empezar' }))
    await screen.findByText('Elegí al menos una fuente')
    expect(screen.queryByRole('button', { name: /Fold/ })).not.toBeInTheDocument()
  })

  it('reports a failure loading sources and does not enable them', async () => {
    mockApi(routes({ 'GET /api/trainer/sources': () => ({ status: 500, json: { detail: 'boom' } }) }))
    render(<TrainerPage />)
    expect(await screen.findByText(/No se pudieron cargar las fuentes/)).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: /Tablas/ })).toBeDisabled()
  })

  it('reports a failure loading payouts', async () => {
    mockApi(routes({ 'GET /api/trainer/payouts': () => ({ status: 500, json: { detail: 'boom' } }) }))
    render(<TrainerPage />)
    expect(await screen.findByText(/No se pudieron cargar las estructuras de premios/)).toBeInTheDocument()
  })
})

const RANGE_SPOT = {
  spot_id: 'rng',
  kind: 'range',
  source: 'range',
  scenario: null,
  offered: ['raise'],
  title: 'Pintá el rango de raise: BTN RFI',
  card_id: 9,
  review: false,
}

function rangeFeedback() {
  const diff = Array(169).fill(0)
  diff[0] = -1 // AA missing
  diff[2] = 1 // extra
  return {
    verdict: 'acceptable',
    loss: 0.18,
    loss_unit: 'freq',
    approximate: true,
    chosen: null,
    best: 'raise',
    recommendation: null,
    reference_layers: [],
    hand_index: null,
    range: {
      target: Array(169).fill(0),
      diff_grid: diff,
      top_classes: [
        { hand_class: 'A5s', target: 1, painted: 0, weight: 4 },
        { hand_class: 'K9o', target: 0, painted: 1, weight: 12 },
      ],
      precision: 0.82,
    },
    card: { interval_days: 1, due_at: null, ease: 2.5 },
  }
}

function rangeRoutes(extra: Record<string, () => { status?: number; json: unknown }> = {}) {
  return routes({
    'POST /api/trainer/sessions/1/next': () => ({ json: RANGE_SPOT }),
    'POST /api/trainer/spots/rng/answer': () => ({ json: rangeFeedback() }),
    ...extra,
  })
}

async function startRange() {
  render(<TrainerPage />)
  await user.click(await screen.findByRole('button', { name: 'Empezar' }))
  await screen.findByText('Pintá el rango de raise: BTN RFI')
}

describe('range drill', () => {
  it('offers the range source', async () => {
    mockApi(routes())
    render(<TrainerPage />)
    expect(await screen.findByRole('checkbox', { name: /Pintá tu rango/ })).toBeEnabled()
  })

  it('sends 169 values with the two painted cells at 1 and shows the precision', async () => {
    const fetchMock = mockApi(rangeRoutes())
    await startRange()
    fireEvent.pointerDown(screen.getByRole('button', { name: /^AA:/ }))
    fireEvent.pointerDown(screen.getByRole('button', { name: /^AKs:/ }))
    fireEvent.pointerUp(window)
    await user.click(screen.getByRole('button', { name: 'Enviar' }))
    expect(await screen.findByText(/82\s*%/)).toBeInTheDocument()
    const call = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/spots/rng/answer'))
    const painted = JSON.parse(String(call?.[1]?.body)).painted as number[]
    expect(painted).toHaveLength(169)
    expect(painted.filter((v) => v === 1)).toHaveLength(2)
    expect(painted.filter((v) => v === 0)).toHaveLength(167)
    expect(screen.getByText(/Faltan: A5s \(4 combos\)/)).toBeInTheDocument()
    expect(screen.getByText(/Sobran: K9o \(12 combos\)/)).toBeInTheDocument()
    expect(screen.getByText('Aceptable', { selector: '.verdict' })).toBeInTheDocument()
  })

  it('clears the painting and ignores hand shortcuts', async () => {
    const fetchMock = mockApi(rangeRoutes())
    await startRange()
    fireEvent.pointerDown(screen.getByRole('button', { name: /^AA:/ }))
    fireEvent.pointerUp(window)
    await user.click(screen.getByRole('button', { name: 'Limpiar' }))
    await user.keyboard('f')
    await user.keyboard('1')
    await act(async () => {})
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/answer'))).toBe(false)
    await user.click(screen.getByRole('button', { name: 'Enviar' }))
    await screen.findByText(/82\s*%/)
    const call = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/spots/rng/answer'))
    expect((JSON.parse(String(call?.[1]?.body)).painted as number[]).every((v) => v === 0)).toBe(true)
  })

  it('asks for the next spot with Enter after the feedback', async () => {
    const fetchMock = mockApi(rangeRoutes())
    await startRange()
    await user.click(screen.getByRole('button', { name: 'Enviar' }))
    await screen.findByText(/82\s*%/)
    await user.keyboard('{Enter}')
    await waitFor(() => {
      const nexts = fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/sessions/1/next'))
      expect(nexts).toHaveLength(2)
    })
  })
})

describe('payout structures', () => {
  it('lists builtin structures without a delete button and deletes custom ones', async () => {
    const fetchMock = mockApi(
      routes({
        'GET /api/trainer/payouts': () => ({
          json: [
            { id: 1, name: 'Top 3', payouts: [50, 30, 20], builtin: true },
            { id: 2, name: 'Mi sat', payouts: [70, 30], builtin: false },
          ],
        }),
        'DELETE /api/trainer/payouts/2': () => ({ json: null }),
      }),
    )
    render(<TrainerPage />)
    await screen.findByText('Mi sat', { selector: '.payout-name' })
    expect(screen.queryByRole('button', { name: 'Borrar Top 3' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Borrar Mi sat' }))
    await waitFor(() => expect(screen.queryByText('Mi sat', { selector: '.payout-name' })).not.toBeInTheDocument())
    expect(fetchMock.mock.calls.some(([u, i]) => String(u).endsWith('/payouts/2') && i?.method === 'DELETE')).toBe(true)
  })

  it('creates a structure with POST /payouts', async () => {
    const fetchMock = mockApi(
      routes({
        'POST /api/trainer/payouts': () => ({
          status: 201,
          json: { id: 5, name: 'Heads up', payouts: [65, 35], builtin: false },
        }),
      }),
    )
    render(<TrainerPage />)
    await screen.findByText('Top 3', { selector: '.payout-name' })
    fireEvent.change(screen.getByLabelText('Nombre de la estructura'), { target: { value: 'Heads up' } })
    fireEvent.change(screen.getByLabelText('Premios (separados por coma)'), { target: { value: '65, 35' } })
    await user.click(screen.getByRole('button', { name: 'Agregar estructura' }))
    expect(await screen.findByText('Heads up', { selector: '.payout-name' })).toBeInTheDocument()
    const call = fetchMock.mock.calls.find(([u, i]) => String(u) === '/api/trainer/payouts' && i?.method === 'POST')
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ name: 'Heads up', payouts: [65, 35] })
  })

  it('rejects non numeric prizes without calling the API', async () => {
    const fetchMock = mockApi(routes())
    render(<TrainerPage />)
    await screen.findByText('Top 3', { selector: '.payout-name' })
    fireEvent.change(screen.getByLabelText('Nombre de la estructura'), { target: { value: 'X' } })
    fireEvent.change(screen.getByLabelText('Premios (separados por coma)'), { target: { value: '50, abc' } })
    await user.click(screen.getByRole('button', { name: 'Agregar estructura' }))
    expect(await screen.findByText(/números/)).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([u, i]) => String(u) === '/api/trainer/payouts' && i?.method === 'POST')).toBe(false)
  })
})
