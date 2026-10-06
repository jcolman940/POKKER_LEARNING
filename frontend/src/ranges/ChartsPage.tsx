import { useCallback, useEffect, useState } from 'react'
import { deleteJson, getJson, postJson, putJson } from '../api/client'
import { ChartEditor } from './ChartEditor'
import { RangeMatrix } from './RangeMatrix'
import { FORMAT_LABEL, SITUATION_LABEL, SOURCE_LABEL } from './labels'
import type { Chart, ChartData } from './types'

const NEW_CHART: ChartData = {
  name: '',
  source: 'custom',
  game_format: 'cash',
  players: 6,
  position: 'BTN',
  vs_position: null,
  stack_bb: 100,
  situation: 'rfi',
  open_size_bb: 2.5,
  rake: null,
  ante_bb: 0,
  note: '',
  actions: { raise: Array<number>(169).fill(0) },
}

function download(name: string, data: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

type Editing = { mode: 'new' } | { mode: 'edit'; chart: Chart } | null

export function ChartsPage() {
  const [charts, setCharts] = useState<Chart[]>([])
  const [editing, setEditing] = useState<Editing>(null)
  const [selected, setSelected] = useState<number | null>(null)
  const [filter, setFilter] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    try {
      setCharts(await getJson<Chart[]>('/api/charts'))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    getJson<Chart[]>('/api/charts', controller.signal)
      .then(setCharts)
      .catch((e: unknown) => {
        if (!controller.signal.aborted) setError(e instanceof Error ? e.message : String(e))
      })
    return () => controller.abort()
  }, [])

  async function save(data: ChartData) {
    if (editing?.mode === 'edit') await putJson<Chart>(`/api/charts/${editing.chart.id}`, data)
    else await postJson<Chart>('/api/charts', data)
    setEditing(null)
    setMessage('Rango guardado.')
    await reload()
  }

  async function remove(chart: Chart) {
    if (!window.confirm(`¿Borrar "${chart.name}"?`)) return
    try {
      await deleteJson(`/api/charts/${chart.id}`)
      if (selected === chart.id) setSelected(null)
      await reload()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  async function importFile(file: File) {
    setError(null)
    setMessage(null)
    try {
      const body: unknown = JSON.parse(await file.text())
      const result = await postJson<{ created: number; errors: string[] }>('/api/charts/import', body)
      setMessage(`Importados: ${result.created}.`)
      if (result.errors.length) setError(result.errors.join(' · '))
      await reload()
    } catch (e) {
      setError(e instanceof SyntaxError ? 'El archivo no es JSON válido.' : e instanceof Error ? e.message : String(e))
    }
  }

  async function exportCharts(onlyOwn: boolean) {
    const query = onlyOwn ? '?source=custom&source=computed' : ''
    try {
      const data = await getJson<unknown>(`/api/charts/export${query}`)
      download(onlyOwn ? 'rangos-propios.json' : 'rangos.json', data)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  if (editing) {
    return (
      <ChartEditor
        initial={editing.mode === 'edit' ? editing.chart : NEW_CHART}
        onSave={save}
        onCancel={() => setEditing(null)}
      />
    )
  }

  const needle = filter.trim().toLowerCase()
  const visible = charts.filter((c) =>
    [c.name, c.position, c.vs_position ?? '', SITUATION_LABEL[c.situation], FORMAT_LABEL[c.game_format]]
      .join(' ')
      .toLowerCase()
      .includes(needle),
  )
  const preview = charts.find((c) => c.id === selected)

  return (
    <div className="charts-page">
      <section className="panel">
        <div className="field-row">
          <button type="button" className="primary" onClick={() => setEditing({ mode: 'new' })}>
            Nuevo rango
          </button>
          <label className="file-button">
            Importar set (.json)
            <input
              type="file"
              accept=".json,application/json"
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) void importFile(file)
                e.target.value = ''
              }}
            />
          </label>
          <button type="button" onClick={() => void exportCharts(false)}>
            Exportar todo
          </button>
          <button type="button" onClick={() => void exportCharts(true)}>
            Exportar propios y calculados
          </button>
        </div>
        <p className="muted small">
          Los rangos de fuentes externas (Pokalab, preflopranges.app) son para uso personal: se cargan
          a mano y no se comparten al exportar solo los propios.
        </p>
        {message && <p className="small">{message}</p>}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </section>

      <section className="panel">
        <label>
          Filtrar
          <input type="text" value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="BTN, vs open, MTT…" />
        </label>
        {charts.length === 0 ? (
          <p className="muted">
            Todavía no hay rangos. Creá uno o importá un set; también podés guardar rangos de
            push/fold calculados.
          </p>
        ) : (
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
                  <tr key={c.id} className={selected === c.id ? 'row-selected' : undefined}>
                    <td>
                      <button type="button" className="link-button" onClick={() => setSelected(c.id)}>
                        {c.name}
                      </button>
                    </td>
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
                      <button type="button" onClick={() => setEditing({ mode: 'edit', chart: c })}>
                        Editar
                      </button>
                      <button type="button" onClick={() => void remove(c)}>
                        Borrar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {preview && (
        <section className="panel" aria-labelledby="preview-title">
          <h3 id="preview-title">{preview.name}</h3>
          <RangeMatrix
            layers={Object.entries(preview.actions).map(([action, grid]) => ({ action, grid }))}
            caption={`Rango ${preview.name}`}
          />
          {preview.note && <p className="small">{preview.note}</p>}
        </section>
      )}
    </div>
  )
}
