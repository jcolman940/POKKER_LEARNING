import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/fetchMock'
import { SimulatorPage } from './SimulatorPage'
import type { Analysis } from './types'

afterEach(() => {
  vi.unstubAllGlobals()
  window.localStorage.clear()
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
      { action: 'raise', frequency: 0.75, ev: null, label: null, amount_bb: null },
      { action: 'fold', frequency: 0.25, ev: null, label: null, amount_bb: null },
    ],
    ev_unit: null,
    reference: 'Fuente externa: Pokalab · BTN RFI',
    explanation: ['Valor: la mano está en la mitad fuerte de tu rango de raise.'],
    warnings: ['Stack del rango: 100bb (escenario: 40bb)'],
    pending_job: null,
    strategy_grid: [],
  },
}

function baseRoutes(extra: Parameters<typeof mockApi>[0] = {}) {
  return mockApi({
    'GET /api/simulator/positions': () => ({ json: POSITIONS }),
    'POST /api/ranges/parse': () => ({ json: { valid: true, error: null, combos: 1326, grid: Array(169).fill(1) } }),
    ...extra,
  })
}

const seatButton = (name: RegExp) => screen.getByRole('button', { name })

describe('SimulatorPage', () => {
  it('draws the table: you on BTN at the bottom against the BB', async () => {
    baseRoutes()
    render(<SimulatorPage />)
    await screen.findByRole('button', { name: /^LJ · Fold/ })
    expect(seatButton(/^BTN · Vos · 100 bb/)).toBeInTheDocument()
    expect(seatButton(/^BB · Rival/)).toBeInTheDocument()
  })

  it('picks cards with the picker and disables cards already used', () => {
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

  it('keeps Analizar disabled with the reason until the table is complete', () => {
    baseRoutes()
    render(<SimulatorPage />)
    expect(screen.getByRole('button', { name: 'Analizar' })).toBeDisabled()
    expect(screen.getByText('Elegí tus dos cartas (o repartí al azar).')).toBeInTheDocument()
  })

  it('deals, follows the street of the dealt board and shows the analysis', async () => {
    const fetchMock = baseRoutes({
      'POST /api/simulator/deal': () => ({ json: { hero_hand: 'AhAd', board: 'Kh7s2c3d', villain_hands: [null] } }),
      'POST /api/simulator/analyze': () => ({ json: ANALYSIS }),
    })
    render(<SimulatorPage />)
    await screen.findByRole('button', { name: /^LJ · Fold/ })
    fireEvent.click(screen.getByRole('button', { name: 'Todo al azar' }))
    expect(await screen.findByRole('button', { name: 'Hero carta 1: A de corazones' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Turn: 3 de diamantes' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Turn' })).toBeChecked()

    fireEvent.click(screen.getByRole('button', { name: 'Analizar' }))
    expect(await screen.findByText('70.0%', { selector: '.big-number' })).toBeInTheDocument()
    expect(screen.getByText('Fuente externa: Pokalab · BTN RFI')).toBeInTheDocument()

    const call = fetchMock.mock.calls.find(([url]) => String(url) === '/api/simulator/analyze')
    const sent = JSON.parse(String(call?.[1]?.body))
    expect(sent).toMatchObject({ hero_position: 'BTN', hero_hand: 'AhAd', board: 'Kh7s2c3d', pot_bb: 6.5, to_call_bb: 0 })
    expect(sent.villains).toEqual([{ position: 'BB', range: 'random', hand: null }])
  })

  it('builds the scenario from the seats: BB facing CO bet and BTN call', async () => {
    const fetchMock = baseRoutes({ 'POST /api/simulator/analyze': () => ({ json: ANALYSIS }) })
    render(<SimulatorPage initial={{ hero_position: 'BB', hero_hand: 'AhKs', board: 'Kh7c2d', pot_bb: 6.5, villains: [] }} />)
    await screen.findByRole('button', { name: /^LJ · Fold/ })

    for (const pos of ['CO', 'BTN']) {
      fireEvent.click(seatButton(new RegExp(`^${pos} ·`)))
      const dialog = screen.getByRole('dialog', { name: `Asiento ${pos}` })
      fireEvent.click(within(dialog).getByRole('radio', { name: 'Rival' }))
      fireEvent.change(within(dialog).getByLabelText('Apuesta (bb)'), { target: { value: '4' } })
      fireEvent.click(within(dialog).getByRole('button', { name: 'Listo' }))
    }
    expect(screen.getByText('Total con apuestas: 14,5 bb')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Analizar' }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([u]) => String(u) === '/api/simulator/analyze')).toBe(true))
    const call = fetchMock.mock.calls.find(([url]) => String(url) === '/api/simulator/analyze')
    expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({
      hero_position: 'BB',
      pot_bb: 14.5,
      to_call_bb: 4,
      previous_action: 'CO bet 4, BTN call 4',
      villains: [
        { position: 'CO', range: 'random', hand: null },
        { position: 'BTN', range: 'random', hand: null },
      ],
    })
  })

  it('moves you to another seat and rotates the table', async () => {
    baseRoutes()
    render(<SimulatorPage />)
    await screen.findByRole('button', { name: /^LJ · Fold/ })
    fireEvent.click(seatButton(/^SB ·/))
    fireEvent.click(within(screen.getByRole('dialog', { name: 'Asiento SB' })).getByRole('radio', { name: 'Vos' }))
    expect(seatButton(/^SB · Vos/)).toBeInTheDocument()
    expect(seatButton(/^BTN · Fold/)).toBeInTheDocument()
    const mesa = screen.getByRole('group', { name: 'Mesa' })
    const first = within(mesa).getAllByRole('button').find((b) => / · /.test(b.getAttribute('aria-label') ?? ''))
    expect(first).toHaveAccessibleName(/^SB · Vos/)
  })

  it('remembers the table and drops a corrupt stored one', async () => {
    baseRoutes()
    const first = render(<SimulatorPage />)
    await screen.findByRole('button', { name: /^LJ · Fold/ })
    fireEvent.change(screen.getByLabelText('Pozo (bb)'), { target: { value: '20' } })
    first.unmount()
    render(<SimulatorPage />)
    expect(screen.getByLabelText('Pozo (bb)')).toHaveValue(20)
  })

  it('a corrupt stored table falls back to the default', () => {
    baseRoutes()
    window.localStorage.setItem('pokker.simulator.table', '{"format":"cash","seats":[{"position":1}]}')
    render(<SimulatorPage />)
    expect(screen.getByLabelText('Pozo (bb)')).toHaveValue(6.5)
  })

  it('starts with the players of the Preflop filters when nothing is stored', async () => {
    mockApi({
      'GET /api/simulator/positions/9': () => ({
        json: ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB'],
      }),
      'POST /api/ranges/parse': () => ({ json: { valid: true, error: null, combos: 1326, grid: [] } }),
    })
    window.localStorage.setItem(
      'pokker.preflop.filters',
      JSON.stringify({ format: 'mtt', source: 'all', rake: 'all', players: 9 }),
    )
    render(<SimulatorPage />)
    expect(await screen.findByRole('button', { name: /^UTG\+2 · Fold/ })).toBeInTheDocument()
    expect(screen.getByText(/Torneo \(MTT\) · 9-max/)).toBeInTheDocument()
  })

  it('shows API validation errors in Spanish', async () => {
    baseRoutes({
      'POST /api/simulator/deal': () => ({ json: { hero_hand: 'AhAd', board: 'AsKs', villain_hands: [null] } }),
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
