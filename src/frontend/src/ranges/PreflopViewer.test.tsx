import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { makeChart } from '../test/charts'
import { mockApi } from '../test/fetchMock'
import { ALL } from './preflopFilters'
import { PreflopViewer, type PreflopViewerProps } from './PreflopViewer'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const SIX = ['LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']
const FILTERS = { format: 'cash', source: ALL, rake: ALL, players: 6 }

function raiseGrid(cells: Record<number, number>) {
  const g = Array<number>(169).fill(0)
  for (const [i, w] of Object.entries(cells)) g[Number(i)] = w
  return g
}

function setup(charts = [makeChart()], overrides: Partial<PreflopViewerProps> = {}) {
  const props: PreflopViewerProps = {
    charts,
    filters: FILTERS,
    onChangeFilters: vi.fn(),
    onEdit: vi.fn(),
    onCreate: vi.fn(),
    onManage: vi.fn(),
    onOpenSimulator: vi.fn(),
    onTrain: vi.fn(),
    ...overrides,
  }
  render(<PreflopViewer {...props} />)
  return props
}

describe('PreflopViewer', () => {
  it('shows the filter chip, the sequence, positions from the API and the chart stats', async () => {
    mockApi({ 'GET /api/simulator/positions/6': () => ({ json: SIX }) })
    const props = setup([
      makeChart({ position: 'BTN', actions: { raise: raiseGrid({ 0: 1, 1: 1 }) } }), // AA 6 + AKs 4 = 10 combos
      makeChart({ position: 'CO' }),
    ])
    expect(screen.getByText('Cash · Todas las fuentes · Todos los stakes · 6-max')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Cambiar' }))
    expect(props.onChangeFilters).toHaveBeenCalledOnce()

    const seq = screen.getByRole('group', { name: 'Secuencia' })
    expect(within(seq).getByRole('radio', { name: 'Open raise (RFI)' })).toBeChecked()
    expect(within(seq).getByRole('radio', { name: 'vs 3-bet' })).toBeDisabled()

    const pos = screen.getByRole('group', { name: 'Tu posición' })
    await waitFor(() => expect(within(pos).getAllByRole('radio')).toHaveLength(6))
    expect(within(pos).getByRole('radio', { name: 'BTN' })).toBeChecked()
    expect(within(pos).getByRole('radio', { name: 'LJ' })).toBeDisabled()

    expect(screen.getByText('10 combos')).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Stack efectivo' })).toHaveValue('100')
  })

  it('switches position and shows the hovered hand frequencies', async () => {
    mockApi({ 'GET /api/simulator/positions/6': () => ({ json: SIX }) })
    setup([
      makeChart({ position: 'BTN', name: 'BTN open' }),
      makeChart({ position: 'CO', name: 'CO open', actions: { raise: raiseGrid({ 1: 0.5 }) } }),
    ])
    fireEvent.click(await screen.findByRole('radio', { name: 'CO' }))
    expect(screen.getByRole('group', { name: 'Rango CO open' })).toBeInTheDocument()
    fireEvent.pointerEnter(document.querySelector('[title^="AKs:"]')!)
    const hand = screen.getByRole('region', { name: 'Mano: AKs' })
    expect(hand).toHaveTextContent('Raise 50%')
    expect(hand).toHaveTextContent('Fold 50%')
  })

  it('shows a rival row for situations with one', async () => {
    mockApi({ 'GET /api/simulator/positions/6': () => ({ json: SIX }) })
    setup([
      makeChart({ situation: 'vs_open', position: 'BB', vs_position: 'BTN' }),
      makeChart({ situation: 'vs_open', position: 'BB', vs_position: 'CO' }),
    ])
    // until the positions arrive the order comes from the charts; then it is table order
    await waitFor(() =>
      expect(
        within(screen.getByRole('group', { name: 'Rival' }))
          .getAllByRole('radio')
          .map((r) => r.getAttribute('value')),
      ).toEqual(['CO', 'BTN']),
    )
  })

  it('lets you pick among duplicate charts, newest first', async () => {
    mockApi({ 'GET /api/simulator/positions/6': () => ({ json: SIX }) })
    setup([
      makeChart({ id: 21, name: 'Viejo', source: 'pokalab', updated_at: '2026-10-01T00:00:00' }),
      makeChart({ id: 22, name: 'Nuevo', source: 'custom', updated_at: '2026-10-05T00:00:00' }),
    ])
    const pick = screen.getByRole('combobox', { name: '2 rangos' })
    expect(pick).toHaveValue('22')
    fireEvent.change(pick, { target: { value: '21' } })
    expect(screen.getByRole('group', { name: 'Rango Viejo' })).toBeInTheDocument()
  })

  it('offers to create the missing chart with the visible context', async () => {
    mockApi({ 'GET /api/simulator/positions/6': () => ({ json: SIX }) })
    const props = setup([makeChart({ situation: 'vs_open', position: 'BB', vs_position: 'BTN', stack_bb: 40 })], {
      filters: { ...FILTERS, rake: 'GG NL50' },
    })
    // the only chart has rake null, so a specific rake hides it
    expect(screen.getByText(/No hay un rango para/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Crear este rango' }))
    expect(props.onCreate).toHaveBeenCalledWith(expect.objectContaining({ source: 'custom', rake: 'GG NL50' }))
  })

  it('opens the spot in the simulator and the trainer', async () => {
    mockApi({ 'GET /api/simulator/positions/6': () => ({ json: SIX }) })
    const props = setup([makeChart({ position: 'CO', stack_bb: 40 })])
    await screen.findAllByRole('radio', { name: 'LJ' })
    fireEvent.click(screen.getByRole('button', { name: /Abrir en Simulador/ }))
    expect(props.onOpenSimulator).toHaveBeenCalledWith({
      format: 'cash',
      num_players: 6,
      hero_position: 'CO',
      effective_stack_bb: 40,
      situation: 'rfi',
    })
    fireEvent.click(screen.getByRole('button', { name: /Entrenar este spot/ }))
    expect(props.onTrain).toHaveBeenCalledWith({
      positions: ['CO'],
      situations: ['rfi'],
      formats: ['cash'],
      sources: ['chart'],
    })
  })

  it('copies the range as text, and reports when the clipboard is unavailable', async () => {
    mockApi({ 'GET /api/simulator/positions/6': () => ({ json: SIX }) })
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    setup([makeChart({ actions: { raise: raiseGrid({ 0: 1 }) } })])
    fireEvent.click(screen.getByRole('button', { name: /Copiar rango/ }))
    await waitFor(() => expect(writeText).toHaveBeenCalledWith('Raise: AA'))
    expect(await screen.findByRole('status')).toHaveTextContent('Rango copiado.')

    Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true })
    fireEvent.click(screen.getByRole('button', { name: /Copiar rango/ }))
    expect(await screen.findByText('No se pudo copiar el rango.')).toBeInTheDocument()
  })

  it('still works with the positions found in the charts when the API fails', async () => {
    mockApi({}) // every request answers 404
    setup([makeChart({ position: 'BTN' }), makeChart({ position: 'CO' })])
    const pos = screen.getByRole('group', { name: 'Tu posición' })
    expect(within(pos).getAllByRole('radio').map((r) => r.getAttribute('value'))).toEqual(['BTN', 'CO'])
    expect(within(pos).getByRole('radio', { name: 'BTN' })).toBeChecked()
  })
})
