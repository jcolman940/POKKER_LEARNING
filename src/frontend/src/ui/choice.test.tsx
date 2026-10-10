import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Chip, PillGroup, RadioList, SegmentList } from '.'

const GAMES = [
  { value: 'cash', label: 'Cash', count: 12 },
  { value: 'mtt', label: 'Torneos', count: 40 },
  { value: 'sng', label: 'Sit & Go', count: 0 },
] as const

describe('RadioList', () => {
  it('renders a named group with counts and the current value checked', () => {
    render(<RadioList legend="Juego" options={[...GAMES]} value="cash" onChange={() => {}} />)
    const group = screen.getByRole('group', { name: 'Juego' })
    expect(within(group).getByRole('radio', { name: /Cash/ })).toBeChecked()
    expect(within(group).getByText('12')).toBeInTheDocument()
  })

  it('dims options with count 0 but still lets you pick them', () => {
    const onChange = vi.fn()
    render(<RadioList legend="Juego" options={[...GAMES]} value="cash" onChange={onChange} />)
    const sng = screen.getByRole('radio', { name: /Sit & Go/ })
    expect(sng).toBeEnabled()
    expect(sng.closest('label')).toHaveClass('ui-radio-dim')
    fireEvent.click(sng)
    expect(onChange).toHaveBeenCalledWith('sng')
  })

  it('uses one radio group per list so arrow keys stay inside it', () => {
    render(
      <>
        <RadioList legend="Juego" options={[...GAMES]} value="cash" onChange={() => {}} />
        <RadioList legend="Otro" options={[...GAMES]} value="mtt" onChange={() => {}} />
      </>,
    )
    const names = screen.getAllByRole('radio').map((r) => r.getAttribute('name'))
    expect(new Set(names).size).toBe(2)
  })
})

describe('PillGroup / SegmentList', () => {
  const POS = [
    { value: 'CO', label: 'CO' },
    { value: 'BTN', label: 'BTN' },
    { value: 'BB', label: 'BB', disabled: true },
  ]

  it('selects a pill and blocks disabled ones', () => {
    const onChange = vi.fn()
    render(<PillGroup legend="Tu posición" options={POS} value="BTN" onChange={onChange} />)
    expect(screen.getByRole('radio', { name: 'BTN' })).toBeChecked()
    expect(screen.getByRole('radio', { name: 'BB' })).toBeDisabled()
    fireEvent.click(screen.getByRole('radio', { name: 'CO' }))
    expect(onChange).toHaveBeenCalledWith('CO')
  })

  it('allows no selection', () => {
    render(<PillGroup legend="Rival" options={POS} value={null} onChange={() => {}} />)
    expect(screen.getAllByRole('radio').filter((r) => (r as HTMLInputElement).checked)).toHaveLength(0)
  })

  it('SegmentList renders vertically with the same behaviour', () => {
    const onChange = vi.fn()
    render(<SegmentList legend="Secuencia" options={POS} value="CO" onChange={onChange} />)
    expect(screen.getByRole('group', { name: 'Secuencia' })).toHaveClass('ui-choice-vertical')
    fireEvent.click(screen.getByRole('radio', { name: 'BTN' }))
    expect(onChange).toHaveBeenCalledWith('BTN')
  })
})

describe('Chip', () => {
  it('shows content and an optional action', () => {
    const onAction = vi.fn()
    render(
      <Chip actionLabel="Cambiar" onAction={onAction}>
        Cash · 6-max
      </Chip>,
    )
    expect(screen.getByText('Cash · 6-max')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Cambiar' }))
    expect(onAction).toHaveBeenCalledOnce()
  })

  it('has no button without an action', () => {
    render(<Chip>Solo texto</Chip>)
    expect(screen.queryByRole('button')).toBeNull()
  })
})
