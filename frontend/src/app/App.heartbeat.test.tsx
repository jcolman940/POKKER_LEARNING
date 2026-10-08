import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { mockApi } from '../test/fetchMock'

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function setup(packaged: boolean, pingStatus = 204) {
  return mockApi({
    'GET /api/version': () => ({ json: { app: '0.1.0', core: '0.1.0', packaged } }),
    'POST /api/app/ping': () => ({ status: pingStatus, json: null }),
    'GET /api/simulator/positions': () => ({ json: ['BTN'] }),
    'POST /api/ranges/parse': () => ({ json: { valid: true, error: null, combos: 1, grid: [] } }),
  })
}
const pings = (fn: ReturnType<typeof setup>) =>
  fn.mock.calls.filter((c) => String(c[0]).startsWith('/api/app/ping')).length

describe('App heartbeat', () => {
  it('beats only when packaged and stops on unmount', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const fn = setup(true)
    const { unmount } = render(<App />)
    await vi.waitFor(() => expect(pings(fn)).toBeGreaterThanOrEqual(1))
    const before = pings(fn)
    await vi.advanceTimersByTimeAsync(10000)
    expect(pings(fn)).toBeGreaterThan(before)
    unmount()
    const after = pings(fn)
    await vi.advanceTimersByTimeAsync(30000)
    expect(pings(fn)).toBe(after)
  })

  it('does not beat in dev mode', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const fn = setup(false)
    render(<App />)
    await vi.waitFor(() =>
      expect(fn.mock.calls.some((c) => String(c[0]) === '/api/version')).toBe(true),
    )
    await vi.advanceTimersByTimeAsync(30000)
    expect(pings(fn)).toBe(0)
  })

  it('shows a fixed banner when the packaged server stopped answering', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const fn = setup(true, 503)
    render(<App />)
    await vi.waitFor(() => expect(pings(fn)).toBeGreaterThanOrEqual(1))
    expect(screen.queryByRole('alert')).toBeNull()
    await vi.advanceTimersByTimeAsync(10000)
    const banner = await screen.findByRole('alert')
    expect(banner.textContent).toBe(
      'POKKER se cerró. Abrilo de nuevo desde el ícono o con doble clic en POKKER.exe.',
    )
  })
})
