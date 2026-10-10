import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { mockApi } from './test/fetchMock'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const POSITIONS = ['LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']

describe('App', () => {
  it('shows backend version and opens the simulator', async () => {
    mockApi({
      'GET /api/version': () => ({ json: { app: '0.1.0', core: '0.1.0' } }),
      'GET /api/simulator/positions': () => ({ json: POSITIONS }),
      'POST /api/ranges/parse': () => ({ json: { valid: true, error: null, combos: 1326, grid: [] } }),
    })
    render(<App />)
    expect(screen.getByRole('heading', { name: 'POKKER' })).toBeInTheDocument()
    expect(await screen.findByText('Backend 0.1.0 · núcleo 0.1.0')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Simulador' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('button', { name: /Entrenador/ })).toBeEnabled()
  })

  it('reports when the backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('down')))
    vi.spyOn(console, 'error').mockImplementation(() => {})
    render(<App />)
    expect(await screen.findByText('Backend no disponible')).toBeInTheDocument()
  })

  it('bridges a leak to the trainer with its filters and due cards first', async () => {
    const group = {
      key: 'mtt|6|BTN|rfi|-|9-11|nash',
      label: 'MTT 6-max · BTN RFI · 9-11 bb',
      game_format: 'mtt',
      table_size: 6,
      position: 'BTN',
      situation: 'rfi',
      vs_position: null,
      stack_bucket: '9-11',
      source: 'nash',
      approximate: false,
      notes: [],
      n: 80,
      insufficient: false,
      actions: [
        { action: 'allin', observed: 0.1, expected: 0.4, ci_low: 0.05, ci_high: 0.2, diff: -0.3, significant: true },
        { action: 'fold', observed: 0.9, expected: 0.6, ci_low: 0.8, ci_high: 0.95, diff: 0.3, significant: false },
      ],
      impact: 2,
      impact_unit: 'bb/100',
      ev_loss_bb: 1,
    }
    const m = { key: 'x', label: 'X', value: 0, n: 0, ci_low: 0, ci_high: 0, unit: '%', insufficient: true }
    const fetchMock = mockApi({
      'GET /api/version': () => ({ json: { app: '0.1.0', core: '0.1.0' } }),
      'GET /api/leaks/detail': () => ({
        json: { group, action: 'allin', top_classes: [], grid: Array(169).fill(null) },
      }),
      'GET /api/leaks': () => ({
        json: { total_hands: 80, min_sample: 30, leaks: [group], insufficient: [], other: [], warnings: [] },
      }),
      'GET /api/stats/graph': () => ({ json: [] }),
      'GET /api/stats/tournaments': () => ({ json: {
          tournaments: 0,
          cost: 0,
          prizes: 0,
          profit: 0,
          roi: m,
          itm: m,
          chips_per_tournament: m,
        },
      }),
      'GET /api/stats': () => ({ json: { min_sample: 100, groups: [] } }),
      'GET /api/trainer/sources': () => ({
        json: {
          pushfold: { available: true, reason: null },
          chart: { available: true, reason: null },
          range: { available: true, reason: null },
        },
      }),
      'GET /api/trainer/payouts': () => ({ json: [] }),
      'GET /api/trainer/frequent-errors': () => ({ json: [] }),
      'POST /api/trainer/sessions': () => ({ status: 201, json: { id: 1, filters: {} } }),
      'POST /api/trainer/sessions/1/next': () => ({ status: 409, json: { detail: 'No hay spots' } }),
    })
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Estadísticas' }))
    fireEvent.click(await screen.findByRole('button', { name: /BTN · RFI · mtt 6/ }))
    fireEvent.click(await screen.findByRole('button', { name: 'Entrenar este spot' }))

    expect(screen.getByRole('button', { name: /Entrenador/ })).toHaveAttribute('aria-current', 'page')
    expect(await screen.findByRole('checkbox', { name: 'BTN' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: /^RFI/ })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Torneo (MTT)' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Push/fold' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Tablas preflop' })).not.toBeChecked()

    fireEvent.click(screen.getByRole('button', { name: 'Empezar' }))
    await waitFor(() => {
      const call = fetchMock.mock.calls.find(
        ([url, init]) => String(url) === '/api/trainer/sessions' && init?.method === 'POST',
      )
      expect(call).toBeTruthy()
      expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({
        sources: ['pushfold'],
        positions: ['BTN'],
        situations: ['rfi'],
        formats: ['mtt'],
        prefer_due: true,
      })
    })
  })

  it('remembers the collapsed menu and survives a broken localStorage', () => {
    mockApi({
      'GET /api/version': () => ({ json: { app: '0.1.0', core: '0.1.0' } }),
      'GET /api/simulator/positions': () => ({ json: POSITIONS }),
      'POST /api/ranges/parse': () => ({ json: { valid: true, error: null, combos: 1326, grid: [] } }),
    })
    window.localStorage.setItem('pokker.sidebar.collapsed', 'true')
    const { unmount } = render(<App />)
    expect(screen.getByRole('navigation', { name: 'Secciones' })).toHaveClass('sidebar-collapsed')
    fireEvent.click(screen.getByRole('button', { name: 'Desplegar menú' }))
    expect(window.localStorage.getItem('pokker.sidebar.collapsed')).toBe('false')
    unmount()

    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    render(<App />)
    expect(screen.getByRole('navigation', { name: 'Secciones' })).not.toHaveClass('sidebar-collapsed')
    window.localStorage.clear()
  })

  it('opens a preflop spot in the simulator with the position preset', async () => {
    const raise = Array<number>(169).fill(0)
    raise[0] = 1
    mockApi({
      'GET /api/version': () => ({ json: { app: '0.1.0', core: '0.1.0' } }),
      'GET /api/charts': () => ({
        json: [
          {
            id: 1, name: 'CO open', source: 'pokalab', game_format: 'cash', players: 6, position: 'CO',
            vs_position: null, stack_bb: 100, situation: 'rfi', open_size_bb: 2.5, rake: null, ante_bb: 0,
            note: '', actions: { raise }, created_at: '2026-10-01T00:00:00', updated_at: '2026-10-01T00:00:00',
          },
        ],
      }),
      'GET /api/simulator/positions': () => ({ json: POSITIONS }),
      'POST /api/ranges/parse': () => ({ json: { valid: true, error: null, combos: 1326, grid: [] } }),
    })
    window.localStorage.setItem(
      'pokker.preflop.filters',
      JSON.stringify({ format: 'cash', source: 'all', rake: 'all', players: 6 }),
    )
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Preflop' }))
    fireEvent.click(await screen.findByRole('button', { name: /Abrir en Simulador/ }))
    expect(screen.getByRole('button', { name: 'Simulador' })).toHaveAttribute('aria-current', 'page')
    // Hero and each rival have a "Posición" select; the hero one is #hero-pos.
    await waitFor(() => expect(document.getElementById('hero-pos')).toHaveValue('CO'))
    window.localStorage.clear()
  })
})
