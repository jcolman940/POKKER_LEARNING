import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/fetchMock'
import { SettingsPanel } from './SettingsPanel'

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const base = {
  version: 'texassolver-0.2.0',
  threads: 6,
  paused: false,
  cache_entries: 0,
  cache_bytes: 0,
  presets: [],
}
const idle = { state: 'idle', bytes: 0, total: null, error: null }
const installGets = (fn: ReturnType<typeof mockApi>) =>
  fn.mock.calls.filter(
    (c) => String(c[0]) === '/api/solver/install' && (c[1]?.method ?? 'GET') === 'GET',
  ).length

describe('SettingsPanel solver download', () => {
  it('offers the download only when the solver is not configured', async () => {
    mockApi({
      'GET /api/solver/status': () => ({ json: { ...base, configured: true, path: 'C:/x.exe' } }),
    })
    render(<SettingsPanel />)
    await screen.findByText(/C:\/x.exe/)
    expect(screen.queryByRole('button', { name: /Descargar TexasSolver/ })).toBeNull()
  })

  it('shows progress, then refreshes the status on done', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let configured = false
    let polls = 0
    const fn = mockApi({
      'GET /api/solver/status': () => ({
        json: { ...base, configured, path: configured ? 'C:/t/console_solver.exe' : null },
      }),
      'POST /api/solver/install': () => ({
        status: 202,
        json: { state: 'downloading', bytes: 0, total: 1000, error: null },
      }),
      'GET /api/solver/install': () => {
        polls++
        if (polls === 1) return { json: { state: 'downloading', bytes: 500, total: 1000, error: null } }
        configured = true
        return { json: { state: 'done', bytes: 1000, total: 1000, error: null } }
      },
    })
    render(<SettingsPanel />)
    expect(await screen.findByText(/licencia AGPL/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Descargar TexasSolver (39 MB)' }))
    await act(() => vi.advanceTimersByTimeAsync(1000))
    const bar = await screen.findByRole('progressbar')
    expect(bar).toHaveAttribute('value', '500')
    expect(bar).toHaveAttribute('max', '1000')
    await act(() => vi.advanceTimersByTimeAsync(1000))
    expect(await screen.findByText('Solver listo')).toBeInTheDocument()
    expect(await screen.findByText(/console_solver.exe/)).toBeInTheDocument()
    const n = installGets(fn)
    await act(() => vi.advanceTimersByTimeAsync(5000))
    expect(installGets(fn)).toBe(n)
  })

  it('shows an indeterminate bar when the total is unknown', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    mockApi({
      'GET /api/solver/status': () => ({ json: { ...base, configured: false, path: null } }),
      'POST /api/solver/install': () => ({ status: 202, json: { ...idle, state: 'downloading' } }),
      'GET /api/solver/install': () => ({
        json: { state: 'downloading', bytes: 10, total: null, error: null },
      }),
    })
    render(<SettingsPanel />)
    fireEvent.click(await screen.findByRole('button', { name: /Descargar TexasSolver/ }))
    await act(() => vi.advanceTimersByTimeAsync(1000))
    const bar = await screen.findByRole('progressbar')
    expect(bar).not.toHaveAttribute('value')
  })

  it('shows the error and lets the user retry', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    mockApi({
      'GET /api/solver/status': () => ({ json: { ...base, configured: false, path: null } }),
      'POST /api/solver/install': () => ({ status: 202, json: { ...idle, state: 'downloading' } }),
      'GET /api/solver/install': () => ({
        json: {
          state: 'error',
          bytes: 0,
          total: null,
          error: 'No se pudo descargar TexasSolver (sin conexión o GitHub no respondió).',
        },
      }),
    })
    render(<SettingsPanel />)
    fireEvent.click(await screen.findByRole('button', { name: /Descargar TexasSolver/ }))
    await act(() => vi.advanceTimersByTimeAsync(1000))
    expect(await screen.findByText(/No se pudo descargar TexasSolver/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Descargar TexasSolver/ })).toBeEnabled()
  })
})
