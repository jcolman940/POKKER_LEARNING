import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/fetchMock'
import { SimulatorPage } from './SimulatorPage'
import type { Analysis } from './types'

afterEach(() => {
  vi.unstubAllGlobals()
})

const POSITIONS = ['LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']

const equity = (hero: number) => ({
  hero: { equity: hero, win: hero, tie: 0, lose: 1 - hero, std_error: 0 },
  villains: [{ equity: 1 - hero, win: 1 - hero, tie: 0, lose: hero, std_error: 0 }],
  exact: true,
  samples: 44,
})

const ANALYSIS: Analysis = {
  street: 'turn',
  equity: equity(0.7),
  equity_vs_hands: equity(2 / 44),
  outs: { available: true, currently_ahead: true, hero_share: 0.67, cards: [], count: 0, unseen: 44 },
  metrics: { pot_odds: 2, required_equity: 1 / 3, mdf: 0.5, spr: 4 },
  ranges: [{ text: 'KK,QQ', combos: 9 }],
  recommendation: {
    available: true,
    message: null,
    source: 'chart',
    confidence: 'approximate',
    hand_class: 'AA',
    actions: [
      { action: 'raise', frequency: 0.75, ev: null },
      { action: 'fold', frequency: 0.25, ev: null },
    ],
    ev_unit: null,
    reference: 'Fuente externa: Pokalab · BTN RFI',
    explanation: ['Valor: la mano está en la mitad fuerte de tu rango de raise.'],
    warnings: ['Stack del rango: 100bb (escenario: 40bb)'],
  },
}

function baseRoutes(extra: Parameters<typeof mockApi>[0] = {}) {
  return mockApi({
    'GET /api/simulator/positions': () => ({ json: POSITIONS }),
    'POST /api/ranges/parse': () => ({
      json: { valid: true, error: null, combos: 1326, grid: Array(169).fill(1) },
    }),
    ...extra,
  })
}

describe('SimulatorPage', () => {
  it('picks cards with the picker and disables cards already used', async () => {
    baseRoutes()
    render(<SimulatorPage />)
    fireEvent.click(screen.getByRole('button', { name: 'Hero carta 1: vacía' }))
    const picker = screen.getByRole('dialog', { name: 'Elegir carta' })
    fireEvent.click(within(picker).getByRole('button', { name: 'A de corazones' }))
    expect(screen.getByRole('button', { name: 'Hero carta 1: A de corazones' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Flop 1: vacía' }))
    const picker2 = screen.getByRole('dialog', { name: 'Elegir carta' })
    expect(within(picker2).getByRole('button', { name: 'A de corazones' })).toBeDisabled()
  })

  it('asks for hero cards before analyzing', async () => {
    baseRoutes()
    render(<SimulatorPage />)
    fireEvent.click(screen.getByRole('button', { name: 'Analizar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('dos cartas de Hero')
  })

  it('deals random cards and shows the analysis against the range', async () => {
    const fetchMock = baseRoutes({
      'POST /api/simulator/deal': () => ({
        json: { hero_hand: 'AhAd', board: 'Kh7s2c3d', villain_hands: [null] },
      }),
      'POST /api/simulator/analyze': () => ({ json: ANALYSIS }),
    })
    render(<SimulatorPage />)
    await waitFor(() => expect(screen.getAllByRole('option', { name: 'BTN' }).length).toBeGreaterThan(0))

    fireEvent.click(screen.getByRole('button', { name: 'Todo al azar' }))
    expect(await screen.findByRole('button', { name: 'Hero carta 1: A de corazones' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Turn: 3 de diamantes' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Analizar' }))
    expect(await screen.findByText('70.0%', { selector: '.big-number' })).toBeInTheDocument()
    expect(screen.getByText(/Contra esta mano puntual tenías/)).toHaveTextContent('4.5%')
    expect(screen.getByText('2.0 : 1')).toBeInTheDocument()
    expect(screen.getByText('Aproximado')).toBeInTheDocument()
    expect(screen.getByText('Fuente externa: Pokalab · BTN RFI')).toBeInTheDocument()
    expect(screen.getByText('Stack del rango: 100bb (escenario: 40bb)')).toBeInTheDocument()

    const analyzeCall = fetchMock.mock.calls.find(([url]) => String(url) === '/api/simulator/analyze')
    const sent = JSON.parse(String(analyzeCall?.[1]?.body))
    expect(sent.hero_hand).toBe('AhAd')
    expect(sent.board).toBe('Kh7s2c3d')
    expect(sent.villains[0]).toMatchObject({ position: 'BB', range: 'random', hand: null })
  })

  it('shows API validation errors in Spanish', async () => {
    baseRoutes({
      'POST /api/simulator/deal': () => ({
        json: { hero_hand: 'AhAd', board: 'AsKs', villain_hands: [null] },
      }),
      'POST /api/simulator/analyze': () => ({
        status: 422,
        json: { detail: [{ msg: 'Value error, El board debe tener 0, 3, 4 o 5 cartas' }] },
      }),
    })
    render(<SimulatorPage />)
    fireEvent.click(screen.getByRole('button', { name: 'Completar al azar' }))
    await screen.findByRole('button', { name: 'Hero carta 1: A de corazones' })
    fireEvent.click(screen.getByRole('button', { name: 'Analizar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('El board debe tener 0, 3, 4 o 5 cartas')
  })
})
