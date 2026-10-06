import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/fetchMock'
import { PushFoldPage } from './PushFoldPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

const grid = (v: number) => Array<number>(169).fill(v)

describe('PushFoldPage', () => {
  it('solves a spot with ICM and saves a computed chart', async () => {
    const posted: { path: string; body: unknown }[] = []
    mockApi({
      'GET /api/simulator/positions': () => ({ json: ['BTN', 'SB', 'BB'] }),
      'POST /api/pushfold/solve': (body) => {
        posted.push({ path: 'solve', body })
        return {
          json: {
            positions: ['BTN', 'SB', 'BB'],
            unit: '$',
            push: [
              { position: 'BTN', vs_position: null, share: 0.4, grid: grid(0.4), ev_diff: grid(0.1) },
              { position: 'SB', vs_position: null, share: 0.6, grid: grid(0.6), ev_diff: grid(0.1) },
            ],
            call: [{ position: 'BB', vs_position: 'SB', share: 0.3, grid: grid(0.3), ev_diff: grid(-0.1) }],
            icm_equity: [33.3, 33.3, 33.3],
            iterations: 120,
            exploitability: 0.005,
            converged: true,
          },
        }
      },
      'POST /api/charts': (body) => {
        posted.push({ path: 'charts', body })
        return { status: 201, json: body }
      },
    })
    render(<PushFoldPage />)
    fireEvent.change(screen.getByLabelText('Jugadores'), { target: { value: '3' } })
    await screen.findByLabelText('SB')
    fireEvent.change(screen.getByLabelText(/Premios/), { target: { value: '50, 30, 20' } })
    fireEvent.click(screen.getByRole('button', { name: 'Calcular Nash' }))

    expect(await screen.findByText(/ICM \(Malmuth-Harville\)/)).toBeInTheDocument()
    const solveBody = posted[0].body as { stacks_bb: number[]; payouts: number[] }
    expect(solveBody.stacks_bb).toEqual([12, 12, 12])
    expect(solveBody.payouts).toEqual([50, 30, 20])

    fireEvent.change(screen.getByLabelText('Ver'), { target: { value: 'call:SB:BB' } })
    fireEvent.click(screen.getByRole('button', { name: 'Guardar como rango (calculado)' }))
    await waitFor(() => expect(posted.some((p) => p.path === 'charts')).toBe(true))
    const chart = posted.find((p) => p.path === 'charts')!.body as Record<string, unknown>
    expect(chart).toMatchObject({ source: 'computed', situation: 'vs_allin', position: 'BB', vs_position: 'SB' })
  })

  it('rejects invalid payouts before calling the API', async () => {
    mockApi({ 'GET /api/simulator/positions': () => ({ json: ['BTN', 'BB'] }) })
    render(<PushFoldPage />)
    fireEvent.change(screen.getByLabelText(/Premios/), { target: { value: '50, abc' } })
    fireEvent.click(screen.getByRole('button', { name: 'Calcular Nash' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Premios inválidos')
  })
})
