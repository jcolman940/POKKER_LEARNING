import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('App', () => {
  it('shows backend version when the API responds', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ app: '0.1.0', core: '0.1.0' }), { status: 200 }),
      ),
    )
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Poker Study' })).toBeInTheDocument()
    expect(await screen.findByText('Backend 0.1.0 · núcleo 0.1.0')).toBeInTheDocument()
  })

  it('reports when the backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('down')))
    vi.spyOn(console, 'error').mockImplementation(() => {})
    render(<App />)
    expect(await screen.findByText('Backend no disponible')).toBeInTheDocument()
  })
})
