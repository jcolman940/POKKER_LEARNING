import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { QueuePanel } from './QueuePanel'
import { mockApi } from '../test/fetchMock'
import { SolverPage } from './SolverPage'

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

const status = {
  configured: true, path: 'C:/ts/console_solver.exe', threads: 6, paused: false, version: 'texassolver-0.2.0',
  cache_entries: 3, cache_bytes: 120000, presets: [{ name: 'simple', label: 'Simple' }],
}
const job = {
  id: 1, label: 'River Qs Jh 2h 7c 3d · pote 20bb', origin: 'batch', priority: 10,
  status: 'running', iteration: 40, exploitability: 2.5, error: null, position: null,
  spot_hash: 'h', created_at: '2026-10-06T00:00:00Z', started_at: null, paused: false, finished_at: null,
}
const library = [{
  id: 'cash', label: 'Cash 6-max 100bb', preset: 'simple',
  lines: [{
    id: 'btn_bb', label: 'BTN vs BB · SRP', missing: [], approximate: false,
    entries: [{ flop: 'AsKh2d', status: 'solved', spot_hash: 'abc', job_id: null }],
  }],
}]
const childNode = {
  player: 'ip', path: '0',
  actions: [{ index: 0, kind: 'check', label: 'Check back', amount_bb: null, frequency: 1, has_child: false }],
  layers: [{ action: 'check', label: 'Check back', grid: Array(169).fill(1) }],
}
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
    'GET /api/solver/results/abc/node?path=0': () => ({ json: childNode }),
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

  it('navigates into a child node and back to the root', async () => {
    routes()
    render(<SolverPage />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Biblioteca' }))
    fireEvent.click(await screen.findByRole('button', { name: /AsKh2d/ }))
    await screen.findByText('Bet 33% (1.8bb)')
    fireEvent.click(screen.getAllByRole('button', { name: 'Ver respuesta' })[0])
    expect(await screen.findByText('Check back')).toBeInTheDocument()
    expect(screen.getByText(/IP actúa/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Raíz' }))
    expect(await screen.findByText(/OOP actúa/)).toBeInTheDocument()
  })

  it('clears the cache only when confirmed', async () => {
    const api = routes({ 'DELETE /api/solver/cache': () => ({ json: {} }) })
    const confirm = vi.spyOn(window, 'confirm')
    render(<SolverPage />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Configuración' }))
    const button = await screen.findByRole('button', { name: 'Vaciar caché' })
    confirm.mockReturnValue(false)
    fireEvent.click(button)
    expect(api).not.toHaveBeenCalledWith('/api/solver/cache', expect.anything())
    confirm.mockReturnValue(true)
    fireEvent.click(button)
    await waitFor(() =>
      expect(api).toHaveBeenCalledWith('/api/solver/cache', expect.objectContaining({ method: 'DELETE' })),
    )
  })

  it('shows an error when the cache clear fails', async () => {
    routes({ 'DELETE /api/solver/cache': () => ({ status: 500, json: { detail: 'boom' } }) })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(<SolverPage />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Configuración' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Vaciar caché' }))
    expect(await screen.findByText(/Error/)).toBeInTheDocument()
  })

  it('shows an error when the status cannot be loaded', async () => {
    routes({ 'GET /api/solver/status': () => ({ status: 500, json: { detail: 'down' } }) })
    render(<SolverPage />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Configuración' }))
    expect(await screen.findByText(/Error/)).toBeInTheDocument()
    expect(screen.queryByText('Cargando…')).not.toBeInTheDocument()
  })

  it('shows an error when cancelling a job fails', async () => {
    routes({ 'POST /api/solver/jobs/1/cancel': () => ({ status: 500, json: { detail: 'nope' } }) })
    render(<SolverPage />)
    fireEvent.click(await screen.findByRole('button', { name: 'Cancelar' }))
    expect(await screen.findByText(/Error/)).toBeInTheDocument()
  })

  it('stops polling after the queue unmounts', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const api = routes()
    const { unmount } = render(<QueuePanel />)
    await vi.advanceTimersByTimeAsync(2100)
    expect(api.mock.calls.length).toBeGreaterThan(2)
    unmount()
    const before = api.mock.calls.length
    await vi.advanceTimersByTimeAsync(10000)
    expect(api.mock.calls.length).toBe(before)
  })

  it('shows the solver version in settings', async () => {
    routes()
    render(<SolverPage />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Configuración' }))
    expect(await screen.findByText(/texassolver-0.2.0/)).toBeInTheDocument()
  })

  it('enqueues a custom batch and reports missing charts', async () => {
    const api = routes({
      'POST /api/solver/batch': () => ({ json: { enqueued: 3, missing: ['falta tabla: BTN RFI'] } }),
    })
    render(<SolverPage />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Biblioteca' }))
    fireEvent.change(await screen.findByLabelText('Agresor'), { target: { value: 'BTN' } })
    fireEvent.change(screen.getByLabelText('Caller'), { target: { value: 'BB' } })
    fireEvent.change(screen.getByLabelText('Stack (bb)'), { target: { value: '100' } })
    fireEvent.change(screen.getByLabelText('Open (bb)'), { target: { value: '2.5' } })
    fireEvent.change(screen.getByLabelText('Flops (opcional)'), { target: { value: 'AhKd2c\n7s7h2d' } })
    fireEvent.click(screen.getByRole('button', { name: 'Encolar lote' }))
    expect(await screen.findByText(/Encolados: 3/)).toBeInTheDocument()
    expect(screen.getByText(/falta tabla: BTN RFI/)).toBeInTheDocument()
    const call = api.mock.calls.find(([u]) => String(u) === '/api/solver/batch')
    const init = call?.[1] as RequestInit
    const body = JSON.parse(init.body as string)
    expect(body).toMatchObject({
      game_format: 'cash',
      preset: 'chico',
      line: { aggressor: 'BTN', caller: 'BB', pot_type: 'srp', stack_bb: 100, open_size_bb: 2.5 },
      flops: ['AhKd2c', '7s7h2d'],
    })
  })

  it('deletes a cached result only when confirmed and closes the viewer', async () => {
    const api = routes({ 'DELETE /api/solver/cache/abc': () => ({ json: null }) })
    const confirm = vi.spyOn(window, 'confirm')
    render(<SolverPage />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Biblioteca' }))
    fireEvent.click(await screen.findByRole('button', { name: /AsKh2d/ }))
    const del = await screen.findByRole('button', { name: 'Borrar de la caché' })
    confirm.mockReturnValue(false)
    fireEvent.click(del)
    expect(api).not.toHaveBeenCalledWith('/api/solver/cache/abc', expect.anything())
    confirm.mockReturnValue(true)
    fireEvent.click(del)
    await waitFor(() =>
      expect(api).toHaveBeenCalledWith('/api/solver/cache/abc', expect.objectContaining({ method: 'DELETE' })),
    )
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: 'Borrar de la caché' })).not.toBeInTheDocument(),
    )
  })
})
