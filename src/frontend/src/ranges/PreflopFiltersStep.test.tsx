import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { makeChart } from '../test/charts'
import { PreflopFiltersStep } from './PreflopFiltersStep'
import { ALL } from './preflopFilters'

const VALUE = { format: 'cash', source: ALL, rake: ALL, players: 6 }

describe('PreflopFiltersStep', () => {
  it('shows the four filter cards with counts and applies the chosen filters', () => {
    const onApply = vi.fn()
    const charts = [
      makeChart({ game_format: 'cash', players: 6 }),
      makeChart({ game_format: 'mtt', players: 9, rake: 'GG NL50' }),
    ]
    render(<PreflopFiltersStep charts={charts} value={VALUE} onApply={onApply} onImport={() => {}} onCreate={() => {}} />)
    for (const name of ['Juego', 'Fuente', 'Stake / rake', 'Jugadores']) {
      expect(screen.getByRole('group', { name })).toBeInTheDocument()
    }
    const juego = screen.getByRole('group', { name: 'Juego' })
    expect(within(juego).getByRole('radio', { name: /Cash/ })).toBeChecked()

    fireEvent.click(within(juego).getByRole('radio', { name: /Torneos/ }))
    fireEvent.click(within(screen.getByRole('group', { name: 'Jugadores' })).getByRole('radio', { name: /9-max/ }))
    expect(onApply).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar' }))
    expect(onApply).toHaveBeenCalledWith({ format: 'mtt', source: ALL, rake: ALL, players: 9 })
  })

  it('without charts offers to import or create instead of filters', () => {
    const onCreate = vi.fn()
    const onImport = vi.fn()
    render(<PreflopFiltersStep charts={[]} value={VALUE} onApply={() => {}} onImport={onImport} onCreate={onCreate} />)
    expect(screen.getByRole('heading', { name: 'Todavía no hay rangos' })).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: 'Juego' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Crear rango' }))
    expect(onCreate).toHaveBeenCalledOnce()
    const file = new File(['{}'], 'set.json', { type: 'application/json' })
    fireEvent.change(screen.getByLabelText('Importar set (.json)'), { target: { files: [file] } })
    expect(onImport).toHaveBeenCalledWith(file)
  })
})
