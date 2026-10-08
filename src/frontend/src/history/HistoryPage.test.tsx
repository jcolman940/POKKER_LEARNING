import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/fetchMock'
import { HistoryPage } from './HistoryPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

const HAND = {
  id: 7,
  site: 'fake',
  hand_id: '1',
  played_at: '2026-01-01T12:00:00Z',
  game_type: 'cash',
  table_size: 6,
  position: 'BTN',
  hero_cards: 'AhKh',
  stack_bb: 100,
  net_bb: 3,
  allin_adj_bb: 3,
  showdown: false,
}

describe('HistoryPage', () => {
  it('imports files and shows the report with failures', async () => {
    let imported = false
    mockApi({
      'GET /api/parsers': () => ({ json: [] }),
      'GET /api/hands': () => ({ json: imported ? { total: 1, items: [HAND] } : { total: 0, items: [] } }),
      'POST /api/imports': () => {
        imported = true
        return {
          json: {
            id: 1,
            created_at: '2026-01-01T00:00:00Z',
            report: {
              totals: { files: 1, hands_found: 3, imported: 1, duplicates: 1, failed: 1 },
              files: [],
              errors: [{ file: 'a.txt', message: 'Línea rara', hand: 3, line: 40, excerpt: 'xx' }],
              errors_truncated: false,
            },
          },
        }
      },
    })
    const onOpen = vi.fn()
    render(<HistoryPage onOpen={onOpen} />)
    expect(await screen.findByText(/ninguna todavía/)).toBeInTheDocument()
    expect(await screen.findByText('No hay manos con estos filtros.')).toBeInTheDocument()

    const input = screen.getByLabelText('Elegir archivos') as HTMLInputElement
    const file = new File(['hh'], 'a.txt', { type: 'text/plain' })
    fireEvent.change(input, { target: { files: [file] } })

    expect(
      await screen.findByText((_, el) => el?.tagName === 'P' && /^1 manos importadas de 3/.test(el.textContent ?? '')),
    ).toBeInTheDocument()
    expect(screen.getByText(/mano 3 · línea 40/)).toBeInTheDocument()
    fireEvent.click(await screen.findByRole('button', { name: 'Ver mano 1' }))
    expect(onOpen).toHaveBeenCalledWith(7)
    expect(screen.getByText('+3.0bb')).toBeInTheDocument()
  })

  it('sends filters to the API', async () => {
    const fetchMock = mockApi({
      'GET /api/parsers': () => ({ json: [{ site: 'pokerstars', label: 'PokerStars' }] }),
      'GET /api/hands': () => ({ json: { total: 0, items: [] } }),
    })
    render(<HistoryPage onOpen={() => {}} />)
    await screen.findByText(/PokerStars/)
    fireEvent.click(screen.getByRole('checkbox', { name: 'BTN' }))
    fireEvent.change(screen.getByLabelText('Hasta'), { target: { value: '2026-01-31' } })
    await waitFor(() => {
      const urls = fetchMock.mock.calls.map(([u]) => String(u))
      expect(urls.some((u) => u.includes('positions=BTN') && u.includes('date_to=2026-02-01'))).toBe(true)
    })
  })
})
