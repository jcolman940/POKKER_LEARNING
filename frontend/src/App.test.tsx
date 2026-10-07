import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { mockApi } from './test/fetchMock'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const POSITIONS = ['LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']

describe('App', () => {
  it('shows backend version and opens the simulator', async () => {
    mockApi({
      'GET /api/version': () => ({ json: { app: '0.1.0', core: '0.1.0' } }),
      'GET /api/simulator/positions': () => ({ json: POSITIONS }),
      'POST /api/ranges/parse': () => ({ json: { valid: true, error: null, combos: 1326, grid: [] } }),
    })
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Poker Study' })).toBeInTheDocument()
    expect(await screen.findByText('Backend 0.1.0 · núcleo 0.1.0')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Simulador' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('button', { name: /Entrenador/ })).toBeEnabled()
  })

  it('reports when the backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('down')))
    vi.spyOn(console, 'error').mockImplementation(() => {})
    render(<App />)
    expect(await screen.findByText('Backend no disponible')).toBeInTheDocument()
  })
})
