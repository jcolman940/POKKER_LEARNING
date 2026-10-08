import { FORMATS } from '../ranges/labels'
import type { Filters } from './filters'

const POSITIONS = ['UTG', 'UTG+1', 'UTG+2', 'UTG+3', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']

function toggle<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value]
}

export function FilterBar({ value, onChange }: { value: Filters; onChange: (f: Filters) => void }) {
  const set = (patch: Partial<Filters>) => onChange({ ...value, ...patch })
  return (
    <div className="filter-bar" role="group" aria-label="Filtros">
      <label>
        Formato
        <select
          value={value.game_types[0] ?? ''}
          onChange={(e) => set({ game_types: e.target.value ? [e.target.value] : [] })}
        >
          <option value="">Todos</option>
          {FORMATS.map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
      </label>
      <label>
        Jugadores
        <select
          value={value.table_sizes[0] ?? ''}
          onChange={(e) => set({ table_sizes: e.target.value ? [Number(e.target.value)] : [] })}
        >
          <option value="">Todos</option>
          {Array.from({ length: 9 }, (_, i) => i + 2).map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
      </label>
      <label>
        Stack mín. (bb)
        <input type="number" min="0" value={value.stack_min} onChange={(e) => set({ stack_min: e.target.value })} />
      </label>
      <label>
        Stack máx. (bb)
        <input type="number" min="0" value={value.stack_max} onChange={(e) => set({ stack_max: e.target.value })} />
      </label>
      <label>
        Desde
        <input type="date" value={value.date_from} onChange={(e) => set({ date_from: e.target.value })} />
      </label>
      <label>
        Hasta
        <input type="date" value={value.date_to} onChange={(e) => set({ date_to: e.target.value })} />
      </label>
      <fieldset className="position-filter">
        <legend>Posiciones</legend>
        {POSITIONS.map((p) => (
          <label key={p} className="checkbox">
            <input
              type="checkbox"
              checked={value.positions.includes(p)}
              onChange={() => set({ positions: toggle(value.positions, p) })}
            />
            {p}
          </label>
        ))}
      </fieldset>
    </div>
  )
}
