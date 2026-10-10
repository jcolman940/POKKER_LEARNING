import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Sidebar } from './Sidebar'

function setup(collapsed = false) {
  const onSelect = vi.fn()
  const onToggle = vi.fn()
  render(
    <Sidebar current="simulator" onSelect={onSelect} collapsed={collapsed} onToggle={onToggle} status="Backend 0.7.0" />,
  )
  return { onSelect, onToggle }
}

describe('Sidebar', () => {
  it('groups sections under Estudiar and Analizar', () => {
    setup()
    const study = screen.getByRole('group', { name: 'Estudiar' })
    expect(within(study).getAllByRole('button').map((b) => b.textContent)).toEqual([
      '♦Preflop',
      '⬭Simulador',
      '⇪Push/Fold',
      '✎Entrenador',
    ])
    const analyze = screen.getByRole('group', { name: 'Analizar' })
    expect(within(analyze).getAllByRole('button')).toHaveLength(4)
    expect(within(analyze).getByRole('button', { name: 'Manos' })).toBeInTheDocument()
  })

  it('marks the current section and selects another', () => {
    const { onSelect } = setup()
    expect(screen.getByRole('button', { name: 'Simulador' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('button', { name: 'Preflop' })).not.toHaveAttribute('aria-current')
    fireEvent.click(screen.getByRole('button', { name: 'Estadísticas' }))
    expect(onSelect).toHaveBeenCalledWith('stats')
  })

  it('keeps accessible names and status when collapsed', () => {
    setup(true)
    expect(screen.getByRole('navigation', { name: 'Secciones' })).toHaveClass('sidebar-collapsed')
    expect(screen.getByRole('button', { name: 'Simulador' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('button', { name: 'Simulador' })).toHaveAttribute('title', 'Simulador')
    expect(screen.getByText('Backend 0.7.0')).toBeInTheDocument()
  })

  it('toggles with an accessible button', () => {
    const { onToggle } = setup(false)
    const toggle = screen.getByRole('button', { name: 'Plegar menú' })
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    fireEvent.click(toggle)
    expect(onToggle).toHaveBeenCalledOnce()
  })

  it('offers to expand when collapsed', () => {
    setup(true)
    expect(screen.getByRole('button', { name: 'Desplegar menú' })).toHaveAttribute('aria-expanded', 'false')
  })
})
