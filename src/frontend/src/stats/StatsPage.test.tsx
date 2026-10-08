import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/fetchMock'
import { StatsPage } from './StatsPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

const metric = (key: string, label: string, value: number, insufficient: boolean, unit = '%') => ({
  key,
  label,
  value,
  n: 40,
  ci_low: value - 10,
  ci_high: value + 10,
  unit,
  insufficient,
})

const GRAPH = [
  { hand: 0, net: 0, showdown: 0, non_showdown: 0, allin_adj: 0 },
  { hand: 20, net: 10, showdown: 4, non_showdown: 6, allin_adj: 8 },
  { hand: 40, net: 35, showdown: 10, non_showdown: 25, allin_adj: 30 },
]

describe('StatsPage', () => {
  it('shows metrics with CI, sample flags, chart and tournaments', async () => {
    const fetchMock = mockApi({
      'GET /api/leaks': () => ({
        json: { total_hands: 0, min_sample: 30, leaks: [], insufficient: [], other: [], warnings: [] },
      }),
      'GET /api/stats/graph': () => ({ json: GRAPH }),
      'GET /api/stats/tournaments': () => ({
        json: {
          tournaments: 3,
          cost: 30,
          prizes: 50,
          profit: 20,
          roi: metric('roi', 'ROI', 66.7, true),
          itm: metric('itm', 'ITM', 33.3, true),
          chips_per_tournament: metric('chip_ev', 'Chip EV por torneo', 120, true, 'fichas'),
        },
      }),
      'GET /api/stats': () => ({
        json: {
          min_sample: 100,
          groups: [
            {
              group: 'Total',
              hands: 40,
              metrics: [metric('vpip', 'VPIP', 75, true), metric('winrate', 'Winrate', 87.5, true, 'bb/100')],
            },
          ],
        },
      }),
    })
    render(<StatsPage />)
    expect(await screen.findByText('VPIP')).toBeInTheDocument()
    expect(screen.getByText('65.0% – 85.0%')).toBeInTheDocument()
    expect(screen.getAllByTitle('Muestra insuficiente').length).toBeGreaterThan(0)
    expect(screen.getByText(/Ganancias acumuladas/)).toBeInTheDocument()
    const legend = document.querySelector('.chart-legend') as HTMLElement
    expect(within(legend).getByText('+35.0')).toBeInTheDocument() // end value of the total line
    expect(screen.getByRole('heading', { name: 'Torneos' })).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Agrupar por'), { target: { value: 'position' } })
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([u]) => String(u).includes('group_by=position'))).toBe(true),
    )
  })
})
