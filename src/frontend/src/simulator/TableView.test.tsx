import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { makeTable, seat } from '../test/tables'
import { sameSlot } from './slots'
import { TableView } from './TableView'

function setup(table = makeTable(), extra: Partial<Parameters<typeof TableView>[0]> = {}) {
  const props = {
    table,
    selected: null,
    onSeatClick: vi.fn(),
    activeSlot: null,
    onSlotClick: vi.fn(),
    onPotChange: vi.fn(),
    ...extra,
  }
  render(<TableView {...props} />)
  return props
}

describe('TableView', () => {
  it('draws one seat per position, the hero first, with role and stack', () => {
    setup()
    const mesa = screen.getByRole('group', { name: 'Mesa' })
    const seats = within(mesa)
      .getAllByRole('button')
      .filter((b) => / · /.test(b.getAttribute('aria-label') ?? ''))
      .map((b) => b.getAttribute('aria-label'))
    expect(seats).toEqual([
      'BTN · Vos · 100 bb',
      'SB · Fold · 100 bb',
      'BB · Rival · 100 bb',
      'LJ · Fold · 100 bb',
      'HJ · Fold · 100 bb',
      'CO · Fold · 100 bb',
    ])
  })

  it('places the hero at the bottom centre', () => {
    setup()
    const hero = screen.getByRole('button', { name: /^BTN · Vos/ }).closest('.sim-seat') as HTMLElement
    expect(hero.style.left).toBe('50%')
    expect(hero.style.top).toBe('88%')
  })

  it('opens a seat and edits the pot', () => {
    const props = setup()
    fireEvent.click(screen.getByRole('button', { name: /^BB · Rival/ }))
    expect(props.onSeatClick).toHaveBeenCalledWith('BB')
    fireEvent.change(screen.getByLabelText('Pozo (bb)'), { target: { value: '12' } })
    expect(props.onPotChange).toHaveBeenCalledWith(12)
  })

  it('shows bets as chips and the total pot', () => {
    const t = makeTable({
      seats: [seat('CO', 'villain', { bet_bb: 4 }), seat('BTN', 'hero'), seat('BB', 'villain', { bet_bb: 4 })],
    })
    setup(t)
    expect(screen.getAllByText('4 bb')).toHaveLength(2)
    expect(screen.getByText('Total con apuestas: 14,5 bb')).toBeInTheDocument()
  })

  it('offers only the board cards of the street, and your two cards', () => {
    const props = setup(makeTable({ street: 'flop', board: 'Kh7c2d' }))
    expect(screen.getByRole('button', { name: 'Flop 1: K de corazones' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Turn/ })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Hero carta 1: A de corazones' }))
    expect(props.onSlotClick).toHaveBeenCalledWith({ group: 'hero', index: 0 })
  })

  it('renders the seat panel for the selected seat only', () => {
    setup(makeTable(), { selected: 'BB', renderSeatPanel: (s) => <p>panel {s.position}</p> })
    expect(screen.getByText('panel BB')).toBeInTheDocument()
    expect(screen.queryByText('panel BTN')).toBeNull()
  })

  it('compares card slots by value', () => {
    expect(sameSlot({ group: 'seat', position: 'BB', index: 1 }, { group: 'seat', position: 'BB', index: 1 })).toBe(true)
    expect(sameSlot(null, { group: 'hero', index: 0 })).toBe(false)
  })
})
