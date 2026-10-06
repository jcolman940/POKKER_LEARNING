import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/fetchMock'
import { ReplayerView } from './ReplayerView'
import type { Replay } from './types'

afterEach(() => {
  vi.unstubAllGlobals()
})

const step = (index: number, description: string, extra: object = {}) => ({
  index,
  street: 'preflop',
  description,
  actor: null,
  board: '',
  pot_bb: 1.5,
  stacks_bb: { Hero: 99, V: 99.5 },
  bets_bb: { Hero: 1, V: 0.5 },
  folded: [],
  hero_equity: { equity: 0.6, std_error: 0.001, exact: false },
  scenario: null,
  ...extra,
})

const REPLAY: Replay = {
  site: 'fake',
  hand_id: '1',
  game_type: 'cash',
  bb: 1,
  players: [
    { name: 'V', seat: 1, position: 'BTN', stack_bb: 100, is_hero: false, cards: 'KcKs' },
    { name: 'Hero', seat: 2, position: 'BB', stack_bb: 100, is_hero: true, cards: 'AhAd' },
  ],
  ranges: { V: 'random' },
  steps: [
    step(0, 'Ciegas', { scenario: { hero_hand: 'AhAd', board: '', villains: [] } }),
    step(1, 'BTN (V) sube a 2.5bb'),
    step(2, 'BTN (V) gana 3bb'),
  ] as Replay['steps'],
  result: { Hero: -1, V: 1 },
}

describe('ReplayerView', () => {
  it('steps through the hand and sends the spot to the simulator', async () => {
    const calls: unknown[] = []
    mockApi({
      'POST /api/hands/5/replay': (body) => {
        calls.push(body)
        return { json: REPLAY }
      },
    })
    const onAnalyze = vi.fn()
    render(<ReplayerView handId={5} onAnalyze={onAnalyze} onBack={() => {}} />)
    expect(await screen.findByText('Ciegas')).toBeInTheDocument()
    expect(screen.getByText('60.0%')).toBeInTheDocument()
    // Villain cards stay hidden until the end.
    expect(screen.queryByRole('img', { name: 'K de tréboles' })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Analizar este spot' }))
    expect(onAnalyze).toHaveBeenCalledWith({ hero_hand: 'AhAd', board: '', villains: [] })

    fireEvent.click(screen.getByRole('button', { name: 'Final' }))
    expect(screen.getByText('BTN (V) gana 3bb')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'K de tréboles' })).toBeInTheDocument()
    expect(screen.getByText('-1.0bb')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText(/BTN · V/), { target: { value: 'QQ+' } })
    fireEvent.click(screen.getByRole('button', { name: 'Recalcular equity' }))
    await waitFor(() => expect(calls).toHaveLength(2))
    expect(calls.at(-1)).toEqual({ ranges: { V: 'QQ+' } })
    expect(screen.getByText('BTN (V) gana 3bb')).toBeInTheDocument() // stays on the same step
  })
})
