import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/fetchMock'
import { EMPTY_FILTERS } from './filters'
import { LeaksPanel } from './LeaksPanel'

afterEach(() => {
  vi.unstubAllGlobals()
})

const group = (over: Record<string, unknown> = {}) => ({
  key: 'cash|6|BTN|rfi|-|61-120|chart',
  label: 'CASH 6-max · BTN RFI · 61-120 bb',
  game_format: 'cash',
  table_size: 6,
  position: 'BTN',
  situation: 'rfi',
  vs_position: null,
  stack_bucket: '61-120',
  source: 'chart',
  approximate: false,
  notes: [],
  n: 80,
  insufficient: false,
  actions: [
    { action: 'raise', observed: 0.18, expected: 0.45, ci_low: 0.15, ci_high: 0.23, diff: -0.27, significant: true },
    { action: 'fold', observed: 0.82, expected: 0.55, ci_low: 0.7, ci_high: 0.9, diff: 0.27, significant: false },
  ],
  impact: 2.4,
  impact_unit: 'bb/100',
  ev_loss_bb: 1.2,
  ...over,
})

const nashGroup = group({
  key: 'mtt|9|SB|rfi|-|6-8|nash',
  position: 'SB',
  game_format: 'mtt',
  table_size: 9,
  stack_bucket: '6-8',
  source: 'nash',
  approximate: true,
  n: 50,
  impact: 3.1,
  impact_unit: 'pts/100',
})

const REPORT = {
  total_hands: 500,
  min_sample: 30,
  leaks: [group(), nashGroup],
  insufficient: [group({ key: 'k2', position: 'CO', n: 5, insufficient: true, impact: 0.5 })],
  other: [group({ key: 'k3', position: 'HJ', n: 60, actions: [], impact: 0 })],
  warnings: [],
}

const DETAIL = {
  group: group(),
  action: 'raise',
  top_classes: [{ hand_class: 'AKo', n: 6, observed: 0.1, expected: 1, diff: -0.9 }],
  grid: [...Array(169).fill(null)].map((_, i) => (i === 0 ? -0.5 : null)),
}

describe('LeaksPanel', () => {
  it('lists leaks with texts and sections, expands for detail and bridges to the trainer', async () => {
    const fetchMock = mockApi({
      'GET /api/leaks/detail': () => ({ json: DETAIL }),
      'GET /api/leaks': () => ({ json: REPORT }),
    })
    const onTrain = vi.fn()
    render(<LeaksPanel filters={EMPTY_FILTERS} onTrain={onTrain} />)

    expect(await screen.findByText('BTN · RFI · cash 6 · 61-120bb')).toBeInTheDocument()
    expect(screen.getAllByText(/Observado 18% \(IC 15–23%\) · Esperado 45%/).length).toBeGreaterThan(0)
    expect(screen.getByText('2,4 bb/100')).toBeInTheDocument()
    expect(screen.getByText('3,1 pts/100')).toBeInTheDocument()
    expect(screen.getByText('Aproximado')).toBeInTheDocument()
    expect(screen.getByText('Nash (chip EV)')).toBeInTheDocument()
    expect(screen.getByText('Muestra insuficiente')).toBeInTheDocument()
    expect(screen.getByText('Sin desvíos')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /BTN · RFI · cash 6/ }))
    expect((await screen.findAllByText('AKo')).length).toBeGreaterThan(0)
    const detailUrl = fetchMock.mock.calls.map((c) => String(c[0])).find((u) => u.includes('/detail'))!
    expect(detailUrl).toContain(`key=${encodeURIComponent('cash|6|BTN|rfi|-|61-120|chart')}`)

    expect(screen.getByText('Abrís 18% desde BTN; tu tabla abre 45% (n=80, IC 15–23%)')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Entrenar este spot' }))
    expect(onTrain).toHaveBeenCalledWith({
      positions: ['BTN'],
      situations: ['rfi'],
      formats: ['cash'],
      sources: ['chart'],
    })
  })

  it('clears report and open detail when filters change', async () => {
    const fetchMock = mockApi({
      'GET /api/leaks/detail': () => ({ json: DETAIL }),
      'GET /api/leaks': () => ({ json: REPORT }),
    })
    const { rerender } = render(<LeaksPanel filters={EMPTY_FILTERS} onTrain={vi.fn()} />)
    fireEvent.click(await screen.findByRole('button', { name: /BTN · RFI · cash 6/ }))
    await screen.findAllByText('AKo')
    const detailCalls = () =>
      fetchMock.mock.calls.filter((c) => String(c[0]).includes('/detail')).length
    expect(detailCalls()).toBe(1)

    rerender(<LeaksPanel filters={{ ...EMPTY_FILTERS, positions: ['CO'] }} onTrain={vi.fn()} />)
    expect(screen.queryByText('BTN · RFI · cash 6 · 61-120bb')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Entrenar este spot' })).not.toBeInTheDocument()
    await screen.findByText('BTN · RFI · cash 6 · 61-120bb')
    expect(detailCalls()).toBe(1)
  })

  it('uses pushfold source for nash leaks', async () => {
    mockApi({
      'GET /api/leaks/detail': () => ({ json: { ...DETAIL, group: nashGroup } }),
      'GET /api/leaks': () => ({ json: { ...REPORT, leaks: [nashGroup] } }),
    })
    const onTrain = vi.fn()
    render(<LeaksPanel filters={EMPTY_FILTERS} onTrain={onTrain} />)
    fireEvent.click(await screen.findByRole('button', { name: /SB · RFI · mtt 9/ }))
    fireEvent.click(await screen.findByRole('button', { name: 'Entrenar este spot' }))
    expect(onTrain).toHaveBeenCalledWith({
      positions: ['SB'],
      situations: ['rfi'],
      formats: ['mtt'],
      sources: ['pushfold'],
    })
  })

  it('shows the import notice on empty state and backend warnings', async () => {
    mockApi({
      'GET /api/leaks': () => ({
        json: { ...REPORT, total_hands: 0, leaks: [], insufficient: [], other: [], warnings: ['Importá historiales'] },
      }),
    })
    render(<LeaksPanel filters={EMPTY_FILTERS} onTrain={vi.fn()} />)
    expect(await screen.findByText('Importá historiales')).toBeInTheDocument()
    expect(screen.getByText(/Importá tus historiales en Manos/)).toBeInTheDocument()
  })

  it('shows errors', async () => {
    mockApi({ 'GET /api/leaks': () => ({ status: 500, json: { detail: 'boom' } }) })
    render(<LeaksPanel filters={EMPTY_FILTERS} onTrain={vi.fn()} />)
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('boom'))
  })
})
