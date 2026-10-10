import { useState } from 'react'
import { Button, RadioList } from '../ui'
import { filterOptions, type PreflopFilters } from './preflopFilters'
import type { Chart } from './types'

interface Props {
  charts: Chart[]
  value: PreflopFilters
  onApply: (filters: PreflopFilters) => void
  onImport: (file: File) => void
  onCreate: () => void
}

export function PreflopFiltersStep({ charts, value, onApply, onImport, onCreate }: Props) {
  const [f, setF] = useState(value)

  if (charts.length === 0) {
    return (
      <section className="panel preflop-empty" aria-labelledby="preflop-empty-title">
        <h2 id="preflop-empty-title" className="preflop-title">
          Todavía no hay rangos
        </h2>
        <p className="muted">Importá un set de rangos (.json) o creá uno propio para empezar.</p>
        <div className="field-row">
          <label className="file-button">
            Importar set (.json)
            <input
              type="file"
              accept=".json,application/json"
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) onImport(file)
                e.target.value = ''
              }}
            />
          </label>
          <Button variant="primary" onClick={onCreate}>
            Crear rango
          </Button>
        </div>
      </section>
    )
  }

  const o = filterOptions(charts, f)
  return (
    <section className="preflop-filters" aria-labelledby="preflop-filters-title">
      <h2 id="preflop-filters-title" className="preflop-title">
        Elegí tus filtros
      </h2>
      <div className="preflop-filter-cards">
        <RadioList legend="Juego" options={o.formats} value={f.format} onChange={(format) => setF({ ...f, format })} />
        <RadioList legend="Fuente" options={o.sources} value={f.source} onChange={(source) => setF({ ...f, source })} />
        <RadioList legend="Stake / rake" options={o.rakes} value={f.rake} onChange={(rake) => setF({ ...f, rake })} />
        <RadioList
          legend="Jugadores"
          options={o.players}
          value={String(f.players)}
          onChange={(p) => setF({ ...f, players: Number(p) })}
        />
      </div>
      <div>
        <Button variant="primary" onClick={() => onApply(f)}>
          Aplicar
        </Button>
      </div>
      <p className="muted small">
        Las opciones salen de los rangos que tenés cargados; el número es cuántos hay con el resto de los filtros.
      </p>
    </section>
  )
}
