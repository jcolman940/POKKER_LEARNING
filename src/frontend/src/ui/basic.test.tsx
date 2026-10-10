import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Button, Card, Select, Stat } from '.'
import { cx } from './cx'

describe('cx', () => {
  it('joins truthy class names', () => {
    expect(cx('a', false, null, undefined, 'b')).toBe('a b')
  })
})

describe('Button', () => {
  it('defaults to a secondary md button of type "button"', () => {
    render(<Button>Copiar</Button>)
    const b = screen.getByRole('button', { name: 'Copiar' })
    expect(b).toHaveAttribute('type', 'button')
    expect(b).toHaveClass('btn', 'btn-secondary', 'btn-md')
  })

  it('applies variant, size and native props', () => {
    const onClick = vi.fn()
    render(
      <Button variant="primary" size="sm" className="extra" onClick={onClick}>
        Aplicar
      </Button>,
    )
    const b = screen.getByRole('button', { name: 'Aplicar' })
    expect(b).toHaveClass('btn-primary', 'btn-sm', 'extra')
    fireEvent.click(b)
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('does not fire when disabled', () => {
    const onClick = vi.fn()
    render(
      <Button disabled onClick={onClick}>
        Analizar
      </Button>,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Analizar' }))
    expect(onClick).not.toHaveBeenCalled()
  })
})

describe('Card', () => {
  it('is a region named by its title', () => {
    render(<Card title="Juego">contenido</Card>)
    expect(screen.getByRole('region', { name: 'Juego' })).toHaveTextContent('contenido')
  })

  it('renders without a title', () => {
    const { container } = render(<Card>solo</Card>)
    expect(container.querySelector('section.ui-card')).toHaveTextContent('solo')
  })
})

describe('Select', () => {
  it('is labelled and reports changes', () => {
    const onChange = vi.fn()
    render(
      <Select label="Stack efectivo" value="100" onChange={onChange}>
        <option value="40">40 BB</option>
        <option value="100">100 BB</option>
      </Select>,
    )
    const s = screen.getByRole('combobox', { name: 'Stack efectivo' })
    fireEvent.change(s, { target: { value: '40' } })
    expect(onChange).toHaveBeenCalledOnce()
  })
})

describe('Stat', () => {
  it('shows label, value and detail', () => {
    render(<Stat label="Rango" value="48,4%" detail="642 combos" />)
    expect(screen.getByText('Rango')).toBeInTheDocument()
    expect(screen.getByText('48,4%')).toHaveClass('ui-stat-value')
    expect(screen.getByText('642 combos')).toBeInTheDocument()
  })
})
