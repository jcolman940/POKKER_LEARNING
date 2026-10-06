import { useEffect, useState } from 'react'
import { getJson, postJson } from '../api/client'
import type { RangeParse } from '../simulator/types'
import { RangeMatrix } from './RangeMatrix'
import { paintCell } from './paint'
import {
  ACTION_LABEL,
  ACTIONS,
  FORMATS,
  SITUATIONS,
  SOURCES,
  pctOfHands,
} from './labels'
import type { ChartData } from './types'

interface Props {
  initial: ChartData
  onSave: (data: ChartData) => Promise<void>
  onCancel: () => void
}

const EMPTY_GRID = () => Array<number>(169).fill(0)

export function ChartEditor({ initial, onSave, onCancel }: Props) {
  const [data, setData] = useState<ChartData>(initial)
  const [positions, setPositions] = useState<string[]>([])
  const [brushAction, setBrushAction] = useState<string>(Object.keys(initial.actions)[0] ?? 'raise')
  const [brushValue, setBrushValue] = useState(100)
  const [eraser, setEraser] = useState(false)
  const [notation, setNotation] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    getJson<string[]>(`/api/simulator/positions/${data.players}`, controller.signal)
      .then(setPositions)
      .catch(() => {})
    return () => controller.abort()
  }, [data.players])

  const set = <K extends keyof ChartData>(key: K, value: ChartData[K]) =>
    setData((d) => ({ ...d, [key]: value }))

  const actionNames = Object.keys(data.actions)
  const available = ACTIONS.filter((a) => !actionNames.includes(a))

  function addAction(action: string) {
    setData((d) => ({ ...d, actions: { ...d.actions, [action]: EMPTY_GRID() } }))
    setBrushAction(action)
    setEraser(false)
  }

  function removeAction(action: string) {
    setData((d) => {
      const actions = { ...d.actions }
      delete actions[action]
      return { ...d, actions }
    })
    if (brushAction === action) setBrushAction(actionNames.find((a) => a !== action) ?? 'raise')
  }

  function paint(i: number) {
    setData((d) => {
      if (eraser) {
        const actions = Object.fromEntries(
          Object.entries(d.actions).map(([a, g]) => [a, g.map((w, j) => (j === i ? 0 : w))]),
        )
        return { ...d, actions }
      }
      if (!d.actions[brushAction]) return d
      return { ...d, actions: paintCell(d.actions, brushAction, i, brushValue / 100) }
    })
  }

  async function applyNotation(text: string) {
    setError(null)
    try {
      const parsed = await postJson<RangeParse>('/api/ranges/parse', { text })
      if (!parsed.valid) {
        setError(parsed.error)
        return
      }
      setData((d) => {
        // The pasted range replaces this action; others shrink where they overflow.
        let actions = { ...d.actions, [brushAction]: EMPTY_GRID() }
        parsed.grid.forEach((w, i) => {
          if (w > 0) actions = paintCell(actions, brushAction, i, w)
        })
        return { ...d, actions }
      })
      setNotation('')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  async function importTxt(file: File) {
    await applyNotation(await file.text())
  }

  async function save() {
    setError(null)
    if (!data.name.trim()) {
      setError('Poné un nombre al rango.')
      return
    }
    if (actionNames.length === 0) {
      setError('Agregá al menos una acción.')
      return
    }
    setSaving(true)
    try {
      await onSave(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSaving(false)
    }
  }

  const layers = actionNames.map((action) => ({ action, grid: data.actions[action] }))

  return (
    <div className="chart-editor">
      <section className="panel" aria-labelledby="chart-meta-title">
        <h3 id="chart-meta-title">Datos del rango</h3>
        <label>
          Nombre
          <input type="text" value={data.name} onChange={(e) => set('name', e.target.value)} />
        </label>
        <div className="field-row">
          <label>
            Fuente
            <select value={data.source} onChange={(e) => set('source', e.target.value)}>
              {SOURCES.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </label>
          <label>
            Formato
            <select value={data.game_format} onChange={(e) => set('game_format', e.target.value)}>
              {FORMATS.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </label>
          <label>
            Jugadores
            <select value={data.players} onChange={(e) => set('players', Number(e.target.value))}>
              {Array.from({ length: 9 }, (_, i) => i + 2).map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <label>
            Situación
            <select value={data.situation} onChange={(e) => set('situation', e.target.value)}>
              {SITUATIONS.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="field-row">
          <label>
            Posición
            <select value={data.position} onChange={(e) => set('position', e.target.value)}>
              {!positions.includes(data.position) && <option value={data.position}>{data.position}</option>}
              {positions.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>
          <label>
            Rival
            <select
              value={data.vs_position ?? ''}
              onChange={(e) => set('vs_position', e.target.value || null)}
            >
              <option value="">—</option>
              {positions.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>
          <label>
            Stack (bb)
            <input
              type="number"
              min="1"
              value={data.stack_bb}
              onChange={(e) => set('stack_bb', Number(e.target.value))}
            />
          </label>
          <label>
            Apertura (bb)
            <input
              type="number"
              min="0"
              step="0.1"
              value={data.open_size_bb ?? ''}
              onChange={(e) => set('open_size_bb', e.target.value ? Number(e.target.value) : null)}
            />
          </label>
          <label>
            Ante (bb)
            <input
              type="number"
              min="0"
              step="0.01"
              value={data.ante_bb}
              onChange={(e) => set('ante_bb', Number(e.target.value))}
            />
          </label>
        </div>
        <label>
          Rake
          <input
            type="text"
            value={data.rake ?? ''}
            placeholder="Ej.: GG NL50 5% cap 3bb"
            onChange={(e) => set('rake', e.target.value || null)}
          />
        </label>
        <label>
          Nota
          <textarea rows={2} value={data.note} onChange={(e) => set('note', e.target.value)} />
        </label>
      </section>

      <section className="panel" aria-labelledby="chart-actions-title">
        <h3 id="chart-actions-title">Acciones</h3>
        <div className="action-chips">
          {actionNames.map((a) => (
            <span key={a} className="action-chip">
              <span className="swatch" style={{ background: `var(--action-${a})` }} />
              {ACTION_LABEL[a]} · {(pctOfHands(data.actions[a]) * 100).toFixed(1)}%
              <button
                type="button"
                className="link-button"
                aria-label={`Quitar ${ACTION_LABEL[a]}`}
                onClick={() => removeAction(a)}
              >
                ×
              </button>
            </span>
          ))}
          {available.length > 0 && (
            <select
              aria-label="Agregar acción"
              value=""
              onChange={(e) => e.target.value && addAction(e.target.value)}
            >
              <option value="">+ Acción</option>
              {available.map((a) => (
                <option key={a} value={a}>
                  {ACTION_LABEL[a]}
                </option>
              ))}
            </select>
          )}
        </div>
        <p className="muted small">El resto de cada mano es fold.</p>

        <div className="field-row brush">
          <label>
            Pincel
            <select
              value={eraser ? '__erase' : brushAction}
              onChange={(e) => {
                if (e.target.value === '__erase') setEraser(true)
                else {
                  setEraser(false)
                  setBrushAction(e.target.value)
                }
              }}
            >
              {actionNames.map((a) => (
                <option key={a} value={a}>
                  {ACTION_LABEL[a]}
                </option>
              ))}
              <option value="__erase">Borrar (fold)</option>
            </select>
          </label>
          <label>
            Frecuencia: {brushValue}%
            <input
              type="range"
              min="0"
              max="100"
              step="5"
              value={brushValue}
              disabled={eraser}
              onChange={(e) => setBrushValue(Number(e.target.value))}
            />
          </label>
        </div>

        <RangeMatrix layers={layers} onPaint={paint} caption="Editor de rango: tocá o arrastrá" />

        <label>
          Pegar notación para {ACTION_LABEL[brushAction] ?? brushAction}
          <textarea
            rows={2}
            value={notation}
            placeholder="22+, A2s+, KTo+ · o formato PioViewer: AA:1.0,AKs:0.5,…"
            onChange={(e) => setNotation(e.target.value)}
          />
        </label>
        <div className="field-row">
          <button
            type="button"
            onClick={() => void applyNotation(notation)}
            disabled={!notation.trim() || eraser || !data.actions[brushAction]}
          >
            Aplicar notación
          </button>
          <label className="file-button">
            Importar .txt (PioViewer)
            <input
              type="file"
              accept=".txt,text/plain"
              disabled={eraser || !data.actions[brushAction]}
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) void importTxt(file)
                e.target.value = ''
              }}
            />
          </label>
        </div>
      </section>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="field-row">
        <button type="button" className="primary" onClick={() => void save()} disabled={saving}>
          {saving ? 'Guardando…' : 'Guardar'}
        </button>
        <button type="button" onClick={onCancel}>
          Cancelar
        </button>
      </div>
    </div>
  )
}
