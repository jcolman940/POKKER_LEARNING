import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { makeChart } from '../test/charts'
import { mockApi } from '../test/fetchMock'
import { PreflopPage } from './PreflopPage'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  window.localStorage.clear()
})

const POSITIONS = ['LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']
const KEY = 'pokker.preflop.filters'
const noop = () => {}

describe('PreflopPage', () => {
  it('creates a chart by painting cells and pasting notation', async () => {
    const created: unknown[] = []
    const aaGrid = Array<number>(169).fill(0)
    aaGrid[0] = 1
    aaGrid[1] = 0.5
    mockApi({
      'GET /api/charts': () => ({ json: [] }),
      'GET /api/simulator/positions': () => ({ json: POSITIONS }),
      'POST /api/ranges/parse': () => ({ json: { valid: true, error: null, combos: 8, grid: aaGrid } }),
      'POST /api/charts': (body) => {
        created.push(body)
        return { status: 201, json: { ...(body as object), id: 1 } }
      },
    })
    render(<PreflopPage onOpenSimulator={noop} onTrain={noop} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Crear rango' }))
    fireEvent.change(screen.getByLabelText('Nombre'), { target: { value: 'BTN open' } })

    // Paint KK (grid index 14) at 100% raise.
    fireEvent.pointerDown(screen.getByRole('button', { name: /^KK:/ }))
    expect(screen.getByRole('button', { name: /^KK: Raise 100%/ })).toBeInTheDocument()

    // Paste notation for the brush action.
    fireEvent.change(screen.getByLabelText(/Pegar notación/), { target: { value: 'AA, AKs:0.5' } })
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar notación' }))
    expect(await screen.findByRole('button', { name: /^AKs: Raise 50%, Fold 50%/ })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(created).toHaveLength(1))
    const body = created[0] as { name: string; actions: { raise: number[] } }
    expect(body.name).toBe('BTN open')
    expect(body.actions.raise[0]).toBe(1)
    expect(body.actions.raise[1]).toBe(0.5)
    expect(body.actions.raise[14]).toBe(0) // pasted notation replaced the action
  })

  it('shows API validation errors when saving', async () => {
    mockApi({
      'GET /api/charts': () => ({ json: [] }),
      'GET /api/simulator/positions': () => ({ json: POSITIONS }),
      'POST /api/charts': () => ({
        status: 422,
        json: { detail: [{ msg: 'Value error, Posición UTG no existe en una mesa de 6' }] },
      }),
    })
    render(<PreflopPage onOpenSimulator={noop} onTrain={noop} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Crear rango' }))
    fireEvent.change(screen.getByLabelText('Nombre'), { target: { value: 'x' } })
    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Posición UTG no existe')
  })

  it('starts on the filter step, remembers the applied filters and reopens on the viewer', async () => {
    mockApi({
      'GET /api/charts': () => ({ json: [makeChart({ name: 'BTN open' })] }),
      'GET /api/simulator/positions': () => ({ json: POSITIONS }),
    })
    const { unmount } = render(<PreflopPage onOpenSimulator={noop} onTrain={noop} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Aplicar' }))
    expect(screen.getByRole('group', { name: 'Rango BTN open' })).toBeInTheDocument()
    expect(JSON.parse(window.localStorage.getItem(KEY) ?? 'null')).toEqual({
      format: 'cash',
      source: 'all',
      rake: 'all',
      players: 6,
    })
    unmount()

    render(<PreflopPage onOpenSimulator={noop} onTrain={noop} />)
    expect(await screen.findByRole('group', { name: 'Rango BTN open' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Cambiar' }))
    expect(screen.getByRole('button', { name: 'Aplicar' })).toBeInTheDocument()
  })

  it('ignores corrupt stored filters and survives stale ones', async () => {
    mockApi({
      'GET /api/charts': () => ({ json: [makeChart()] }),
      'GET /api/simulator/positions': () => ({ json: POSITIONS }),
    })
    window.localStorage.setItem(KEY, '{"format":"cash"}')
    const first = render(<PreflopPage onOpenSimulator={noop} onTrain={noop} />)
    expect(await screen.findByRole('button', { name: 'Aplicar' })).toBeInTheDocument()
    first.unmount()

    window.localStorage.setItem(KEY, JSON.stringify({ format: 'cash', source: 'all', rake: 'PS NL10', players: 9 }))
    render(<PreflopPage onOpenSimulator={noop} onTrain={noop} />)
    expect(await screen.findByText(/No hay un rango para/)).toBeInTheDocument()
  })

  it('keeps the viewer selection after managing or editing charts', async () => {
    mockApi({
      'GET /api/charts': () => ({
        json: [makeChart({ name: 'BTN open', position: 'BTN' }), makeChart({ name: 'CO open', position: 'CO' })],
      }),
      'GET /api/simulator/positions': () => ({ json: POSITIONS }),
    })
    window.localStorage.setItem(KEY, JSON.stringify({ format: 'cash', source: 'all', rake: 'all', players: 6 }))
    render(<PreflopPage onOpenSimulator={noop} onTrain={noop} />)
    fireEvent.click(await screen.findByRole('radio', { name: 'CO' }))
    expect(screen.getByRole('group', { name: 'Rango CO open' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Importar \/ exportar/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Volver al visor' }))
    expect(screen.getByRole('group', { name: 'Rango CO open' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Editar/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }))
    expect(screen.getByRole('group', { name: 'Rango CO open' })).toBeInTheDocument()
  })

  it('manages charts: table with edit, import and back to the viewer', async () => {
    const imported: unknown[] = []
    mockApi({
      'GET /api/charts': () => ({ json: [makeChart({ name: 'BTN open' })] }),
      'GET /api/simulator/positions': () => ({ json: POSITIONS }),
      'POST /api/charts/import': (body) => {
        imported.push(body)
        return { json: { created: 2, errors: [] } }
      },
    })
    window.localStorage.setItem(KEY, JSON.stringify({ format: 'cash', source: 'all', rake: 'all', players: 6 }))
    render(<PreflopPage onOpenSimulator={noop} onTrain={noop} />)
    fireEvent.click(await screen.findByRole('button', { name: /Importar \/ exportar/ }))
    expect(screen.getByRole('table')).toHaveTextContent('BTN open')

    const file = new File(['{"format":"poker-study-ranges","version":1,"charts":[]}'], 'set.json')
    fireEvent.change(screen.getByLabelText('Importar set (.json)'), { target: { files: [file] } })
    expect(await screen.findByText('Importados: 2.')).toBeInTheDocument()
    expect(imported).toHaveLength(1)

    fireEvent.click(screen.getByRole('button', { name: 'Volver al visor' }))
    expect(screen.getByRole('group', { name: 'Rango BTN open' })).toBeInTheDocument()
  })
})
