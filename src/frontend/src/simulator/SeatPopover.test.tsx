import { fireEvent, render, screen } from '@testing-library/react'
import { useRef } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { makeTable, seat } from '../test/tables'
import { mockApi } from '../test/fetchMock'
import { SeatPopover } from './SeatPopover'
import type { Seat } from './table'

afterEach(() => vi.unstubAllGlobals())

function Harness(props: { seat: Seat; onRole?: () => void; onChange?: () => void; onSlotClick?: () => void }) {
  const anchor = useRef<HTMLButtonElement>(null)
  const table = makeTable({ seats: [seat('BTN', 'hero'), props.seat] }) // total pot 6.5 + bets
  return (
    <div>
      <button ref={anchor} type="button">
        ancla
      </button>
      <SeatPopover
        seat={props.seat}
        table={table}
        anchorRef={anchor}
        onClose={() => {}}
        onRole={props.onRole ?? (() => {})}
        onChange={props.onChange ?? (() => {})}
        activeSlot={null}
        onSlotClick={props.onSlotClick ?? (() => {})}
      />
    </div>
  )
}

describe('SeatPopover', () => {
  it('changes the role of the seat', () => {
    const onRole = vi.fn()
    render(<Harness seat={seat('BB', 'villain')} onRole={onRole} />)
    expect(screen.getByRole('dialog', { name: 'Asiento BB' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Rival' })).toBeChecked()
    fireEvent.click(screen.getByRole('radio', { name: 'Vos' }))
    expect(onRole).toHaveBeenCalledWith('hero')
  })

  it('sizes bets on the total pot and accepts a free amount and the stack', () => {
    mockApi({ 'POST /api/ranges/parse': () => ({ json: { valid: true, error: null, combos: 1326, grid: [] } }) })
    const onChange = vi.fn()
    render(<Harness seat={seat('BB', 'villain', { stack_bb: 50 })} onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: 'Pot' }))
    expect(onChange).toHaveBeenLastCalledWith({ bet_bb: 6.5 })
    fireEvent.click(screen.getByRole('button', { name: 'All-in' }))
    expect(onChange).toHaveBeenLastCalledWith({ bet_bb: 50 })
    fireEvent.change(screen.getByLabelText('Apuesta (bb)'), { target: { value: '4' } })
    expect(onChange).toHaveBeenLastCalledWith({ bet_bb: 4 })
    fireEvent.change(screen.getByLabelText('Stack (bb)'), { target: { value: '93' } })
    expect(onChange).toHaveBeenLastCalledWith({ stack_bb: 93 })
  })

  it('edits the range and optional cards of a rival', () => {
    mockApi({ 'POST /api/ranges/parse': () => ({ json: { valid: true, error: null, combos: 1326, grid: [] } }) })
    const onChange = vi.fn()
    const onSlotClick = vi.fn()
    render(<Harness seat={seat('BB', 'villain')} onChange={onChange} onSlotClick={onSlotClick} />)
    fireEvent.change(screen.getByLabelText('Rango'), { target: { value: 'QQ+' } })
    expect(onChange).toHaveBeenLastCalledWith({ range: 'QQ+' })
    fireEvent.click(screen.getByRole('button', { name: 'BB carta 1: vacía' }))
    expect(onSlotClick).toHaveBeenCalledWith({ group: 'seat', position: 'BB', index: 0 })
  })

  it('a folded seat only offers the role', () => {
    render(<Harness seat={seat('CO', 'folded')} />)
    expect(screen.queryByLabelText('Apuesta (bb)')).toBeNull()
    expect(screen.queryByLabelText('Rango')).toBeNull()
  })
})
