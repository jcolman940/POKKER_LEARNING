import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/fetchMock'
import { SolverPage } from './SolverPage'

afterEach(() => vi.unstubAllGlobals())

const status = {
  configured: true, path: 'C:/ts/console_solver.exe', threads: 6, paused: false,
  cache_entries: 3, cache_bytes: 120000, presets: [{ name: 'simple', label: 'Simple' }],
}
const job = {
  id: 1, label: 'River Qs Jh 2h 7c 3d · pote 20bb', origin: 'batch', priority: 10,
  status: 'running', iteration: 40, exploitability: 2.5, error: null, position: null,
  spot_hash: 'h', created_at: '2026-10-06T00:00:00Z', started_at: null, finished_at: null,
}
const library = [{
  id: 'cash', label: 'Cash 6-max 100bb', preset: 'simple',
  lines: [{
    id: 'btn_bb', label: 'BTN vs BB · SRP', missing: [], approximate: false,
    entries: [{ flop: 'AsKh2d', status: 'solved', spot_hash: 'abc', job_id: null }],
  }],
}]
const node = {
  player: 'oop', path: '',
  actions: [
    { index: 0, kind: 'check', label: 'Check', amount_bb: null, frequency: 0.7, has_child: true },
    { index: 1, kind: 'bet', label: 'Bet 33% (1.8bb)', amount_bb: 1.8, frequency: 0.3, has_child: true },
  ],
  layers: [
    { action: 'check', label: 'Check', grid: Array(169).fill(0.7) },
    { action: 'bet', label: 'Bet 33% (1.8bb)', grid: Array(169).fill(0.3) },
  ],
}

function routes(extra = {}) {
  return mockApi({
    'GET /api/solver/status': () => ({ json: status }),
    'GET /api/solver/jobs': () => ({ json: [job] }),
    'GET /api/solver/library': () => ({ json: library }),
    'GET /api/solver/results/abc/node': () => ({ json: node }),
    'POST /api/solver/queue/pause': () => ({ json: { paused: true } }),
    ...extra,
  })
}

describe('SolverPage', () => {
  it('lists the queue and pauses it', async () => {
    const api = routes()
    render(<SolverPage />)
    expect(await screen.findByText(/River Qs Jh/)).toBeInTheDocument()
    expect(screen.getByText(/Iteración 40/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Pausar cola' }))
    await waitFor(() =>
      expect(api).toHaveBeenCalledWith('/api/solver/queue/pause', expect.anything()),
    )
  })

  it('opens a solved library flop in the viewer and navigates', async () => {
    routes()
    render(<SolverPage />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Biblioteca' }))
    fireEvent.click(await screen.findByRole('button', { name: /AsKh2d/ }))
    expect(await screen.findByText('Bet 33% (1.8bb)')).toBeInTheDocument()
    expect(screen.getByText(/OOP actúa/)).toBeInTheDocument()
  })

  it('shows configuration', async () => {
    routes()
    render(<SolverPage />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Configuración' }))
    expect(await screen.findByText(/console_solver.exe/)).toBeInTheDocument()
    expect(screen.getByText(/3 resultados/)).toBeInTheDocument()
  })
})
