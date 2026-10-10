import { useState } from 'react'
import { Button } from '../ui'
import { FORMAT_LABEL, SITUATION_LABEL, SOURCE_LABEL } from './labels'
import type { Chart } from './types'

interface Props {
  charts: Chart[]
  onEdit: (chart: Chart) => void
  onDelete: (chart: Chart) => void
  onImport: (file: File) => void
  onExport: (onlyOwn: boolean) => void
  onNew: () => void
  onClose: () => void
}

export function ChartManager({ charts, onEdit, onDelete, onImport, onExport, onNew, onClose }: Props) {
  const [filter, setFilter] = useState('')
  const needle = filter.trim().toLowerCase()
  const visible = charts.filter((c) =>
    [c.name, c.position, c.vs_position ?? '', SITUATION_LABEL[c.situation], FORMAT_LABEL[c.game_format]]
      .join(' ')
      .toLowerCase()
      .includes(needle),
  )

  return (
    <div className="charts-page">
      <section className="panel">
        <div className="field-row">
          <Button onClick={onClose}>Volver al visor</Button>
          <Button variant="primary" onClick={onNew}>
            Nuevo rango
          </Button>
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
          <Button onClick={() => onExport(false)}>Exportar todo</Button>
          <Button onClick={() => onExport(true)}>Exportar propios y calculados</Button>
        </div>
        <p className="muted small">
          Los rangos de fuentes externas (Pokalab, preflopranges.app) son para uso personal: se cargan a mano y no se
          comparten al exportar solo los propios.
        </p>
      </section>

      <section className="panel">
        <label>
          Filtrar
          <input type="text" value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="BTN, vs open, MTT…" />
        </label>
        <div className="table-scroll">
          <table className="charts-table">
            <thead>
              <tr>
                <th scope="col">Nombre</th>
                <th scope="col">Fuente</th>
                <th scope="col">Formato</th>
                <th scope="col">Spot</th>
                <th scope="col">Stack</th>
                <th scope="col">
                  <span className="sr-only">Acciones</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {visible.map((c) => (
                <tr key={c.id}>
                  <td>{c.name}</td>
                  <td>{SOURCE_LABEL[c.source] ?? c.source}</td>
                  <td>
                    {FORMAT_LABEL[c.game_format]} · {c.players}j
                  </td>
                  <td>
                    {c.position} {SITUATION_LABEL[c.situation]}
                    {c.vs_position ? ` (${c.vs_position})` : ''}
                  </td>
                  <td>{c.stack_bb}bb</td>
                  <td className="row-actions">
                    <Button size="sm" onClick={() => onEdit(c)}>
                      Editar
                    </Button>
                    <Button size="sm" onClick={() => onDelete(c)}>
                      Borrar
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
