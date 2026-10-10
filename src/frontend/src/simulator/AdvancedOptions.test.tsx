import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { makeTable } from '../test/tables'
import { AdvancedPanel } from './AdvancedOptions'
import { parsePayouts } from './table'

describe('AdvancedPanel', () => {
  it('edits situation, antes and a typed previous action', () => {
    const onChange = vi.fn()
    const table = makeTable()
    render(<AdvancedPanel table={table} onChange={onChange} autoAction="CO bet 4, BTN call 4" />)
    expect(screen.getByText('Opciones avanzadas')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Situación preflop'), { target: { value: 'vs_open' } })
    expect(onChange).toHaveBeenLastCalledWith({ ...table.advanced, situation: 'vs_open' })
    fireEvent.change(screen.getByLabelText('Ante (bb)'), { target: { value: '0.12' } })
    expect(onChange).toHaveBeenLastCalledWith({ ...table.advanced, ante_bb: 0.12 })

    const action = screen.getByLabelText('Acción previa')
    expect(action).toHaveAttribute('placeholder', 'CO bet 4, BTN call 4')
    fireEvent.change(action, { target: { value: 'CO abre 2.5bb' } })
    expect(onChange).toHaveBeenLastCalledWith({ ...table.advanced, previous_action: 'CO abre 2.5bb' })
  })

  it('shows payouts only in tournaments', () => {
    const onChange = vi.fn()
    const { rerender } = render(<AdvancedPanel table={makeTable()} onChange={onChange} autoAction="" />)
    expect(screen.queryByLabelText(/Premios/)).toBeNull()
    const mtt = makeTable({ format: 'mtt' })
    rerender(<AdvancedPanel table={mtt} onChange={onChange} autoAction="" />)
    fireEvent.change(screen.getByLabelText(/Premios/), { target: { value: '50, 30; 20' } })
    expect(onChange).toHaveBeenLastCalledWith({ ...mtt.advanced, payouts: [50, 30, 20] })
  })

  it('renders the solver fields it receives', () => {
    render(
      <AdvancedPanel table={makeTable()} onChange={() => {}} autoAction="">
        <p>campos del solver</p>
      </AdvancedPanel>,
    )
    expect(screen.getByText('campos del solver')).toBeInTheDocument()
  })
})

describe('parsePayouts', () => {
  it('splits on commas, semicolons and spaces and drops junk', () => {
    expect(parsePayouts('50, 30;20  x -5')).toEqual([50, 30, 20])
    expect(parsePayouts('')).toEqual([])
  })
})
