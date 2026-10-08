import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/fetchMock'
import { RangeMatrix } from '../ranges/RangeMatrix'
import { PendingSolve } from './PendingSolve'
import { PostflopSolverFields } from './PostflopSolverFields'
import { RecommendationPanel } from './RecommendationPanel'
import type { Recommendation } from './types'

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

const baseRec: Recommendation = {
  available: true,
  message: null,
  source: 'solver',
  confidence: 'exact',
  hand_class: null,
  actions: [
    { action: 'check', frequency: 0.4, ev: null, label: 'Check', amount_bb: null },
    { action: 'bet', frequency: 0.6, ev: null, label: 'Bet 75% (15bb)', amount_bb: 15 },
  ],
  ev_unit: null,
  reference: 'TexasSolver · preset Simple · explotabilidad 0.42% del pote',
  explanation: [],
  warnings: ['Solo primera decisión de la calle: raises y re-raises previos no se modelan.'],
  pending_job: null,
  strategy_grid: [
    { action: 'check', label: 'Check', grid: Array(169).fill(0.4) },
    { action: 'bet', label: 'Bet 75% (15bb)', grid: Array(169).fill(0.6) },
  ],
}

describe('solver recommendation', () => {
  it('shows sized actions and the strategy grid', () => {
    render(<RecommendationPanel rec={baseRec} />)
    expect(screen.getByText('Bet 75% (15bb)')).toBeInTheDocument()
    expect(screen.getByText(/explotabilidad 0.42%/)).toBeInTheDocument()
    expect(screen.getByRole('group', { name: /Estrategia del rango de Hero/ })).toBeInTheDocument()
  })

  it('polls a pending job and reports when it is done', async () => {
    let calls = 0
    mockApi({
      'GET /api/solver/jobs/7': () => {
        calls += 1
        return {
          json: {
            id: 7, status: calls < 2 ? 'running' : 'done', iteration: calls * 50,
            exploitability: 1.2, position: null,
          },
        }
      },
    })
    const onDone = vi.fn()
    render(
      <PendingSolve
        job={{ id: 7, status: 'queued', iteration: 0, exploitability: null, position: 2 }}
        onDone={onDone}
        intervalMs={10}
      />,
    )
    expect(screen.getByText(/Posición en la cola: 2/)).toBeInTheDocument()
    await waitFor(() => expect(onDone).toHaveBeenCalled())
  })

  it('cancels a pending job', async () => {
    const api = mockApi({
      'GET /api/solver/jobs/7': () => ({
        json: { id: 7, status: 'running', iteration: 10, exploitability: 3, position: null },
      }),
      'POST /api/solver/jobs/7/cancel': () => ({
        json: { id: 7, status: 'cancelled', iteration: 10, exploitability: 3, position: null },
      }),
    })
    render(
      <PendingSolve
        job={{ id: 7, status: 'running', iteration: 10, exploitability: 3, position: null }}
        onDone={() => {}}
        intervalMs={1000}
      />,
    )
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Cancelar solve' })))
    expect(api).toHaveBeenCalledWith('/api/solver/jobs/7/cancel', expect.anything())
    expect(await screen.findByText(/cancelado/i)).toBeInTheDocument()
  })

  it('prefill button calls back and shows notes', async () => {
    const prefill = vi.fn(async () => {})
    render(
      <PostflopSolverFields
        heroRange=""
        onHeroRange={() => {}}
        preset="simple"
        onPreset={() => {}}
        presets={[{ name: 'simple', label: 'Simple' }]}
        prefill={prefill}
        prefillNotes={['Stack del rango: 40bb (escenario: 100bb)']}
        potType="srp"
        onPotType={() => {}}
        aggressor="hero"
        onAggressor={() => {}}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Prellenar desde tablas' }))
    expect(prefill).toHaveBeenCalled()
    expect(screen.getByText(/Stack del rango/)).toBeInTheDocument()
    expect(screen.getByText('Aproximado')).toBeInTheDocument()
  })
})

describe('pending solve details', () => {
  const pending = { id: 7, status: 'queued', iteration: 0, exploitability: null, position: 1 }

  it('tells the user the queue is paused and keeps polling', async () => {
    const api = mockApi({
      'GET /api/solver/jobs/7': () => ({
        json: { ...pending, paused: true, started_at: null },
      }),
    })
    render(<PendingSolve job={{ ...pending, paused: true }} onDone={() => {}} intervalMs={10} />)
    expect(screen.getByText('La cola está pausada: reanudala en Solver → Cola.')).toBeInTheDocument()
    await waitFor(() => expect(api.mock.calls.length).toBeGreaterThan(2))
  })

  it('hides the paused message when the queue is not paused', () => {
    render(<PendingSolve job={{ ...pending, paused: false }} onDone={() => {}} intervalMs={10000} />)
    expect(screen.queryByText(/La cola está pausada/)).not.toBeInTheDocument()
  })

  it('shows elapsed seconds for a running job', () => {
    const started = new Date(Date.now() - 42_000).toISOString()
    render(
      <PendingSolve
        job={{ ...pending, status: 'running', iteration: 5, started_at: started }}
        onDone={() => {}}
        intervalMs={10000}
      />,
    )
    expect(screen.getByText(/· 4[2-5] s/)).toBeInTheDocument()
  })
})

describe('RangeMatrix implicit fold', () => {
  const layers = [{ action: 'check', grid: Array(169).fill(0.4) }]

  it('adds a phantom Fold share by default', () => {
    render(<RangeMatrix layers={layers} />)
    expect(screen.getAllByTitle(/Fold 60%/).length).toBeGreaterThan(0)
  })

  it('omits it when implicitFold is false', () => {
    render(<RangeMatrix layers={layers} implicitFold={false} />)
    expect(screen.queryAllByTitle(/Fold/)).toHaveLength(0)
  })

  it('is disabled in the solver strategy grid', () => {
    render(
      <RecommendationPanel
        rec={{ ...baseRec, strategy_grid: [{ action: 'check', label: 'Check', grid: Array(169).fill(0.4) }] }}
      />,
    )
    expect(screen.queryAllByTitle(/Fold/)).toHaveLength(0)
  })
})
