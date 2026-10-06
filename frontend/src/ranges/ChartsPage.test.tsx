import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/fetchMock'
import { ChartsPage } from './ChartsPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

const POSITIONS = ['LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']

describe('ChartsPage', () => {
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
    render(<ChartsPage />)
    expect(await screen.findByText(/Todavía no hay rangos/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Nuevo rango' }))
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
    render(<ChartsPage />)
    fireEvent.click(await screen.findByRole('button', { name: 'Nuevo rango' }))
    fireEvent.change(screen.getByLabelText('Nombre'), { target: { value: 'x' } })
    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Posición UTG no existe')
  })
})
