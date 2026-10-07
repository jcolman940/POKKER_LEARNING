import { useState } from 'react'
import { RangeMatrix } from '../ranges/RangeMatrix'
import { VERDICT_LABEL } from './format'
import type { Feedback, Spot } from './types'

interface Props {
  spot: Spot
  onSubmit: (painted: number[]) => void
  feedback?: Feedback | null
  onNext?: () => void
}

const EMPTY = () => Array<number>(169).fill(0)
const BRUSHES = [0, 50, 100]

function combos(n: number): string {
  const text = Number.isInteger(n) ? String(n) : n.toFixed(1).replace('.', ',')
  return `${text} combos`
}

export function RangeDrill({ spot, onSubmit, feedback, onNext }: Props) {
  const [painted, setPainted] = useState<number[]>(EMPTY)
  const [brush, setBrush] = useState(100)
  const action = spot.offered[0] ?? 'raise'
  const done = Boolean(feedback)

  const paint = (i: number) => {
    if (done) return
    setPainted((g) => (g[i] === brush / 100 ? g : g.map((w, j) => (j === i ? brush / 100 : w))))
  }

  const range = feedback?.range
  const missing = range?.top_classes.filter((c) => c.target > c.painted) ?? []
  const extra = range?.top_classes.filter((c) => c.painted > c.target) ?? []
  const list = (rows: typeof missing) =>
    rows.map((c) => `${c.hand_class} (${combos(c.weight)})`).join(', ')

  return (
    <section className="panel trainer-spot range-drill" aria-label="Ejercicio de rango">
      <div className="panel-header">
        <h3>{spot.title}</h3>
        <span className="badges">{spot.review && <span className="badge badge-warn">Repaso</span>}</span>
      </div>
      {!done && (
        <>
          <div className="field-row brush" role="group" aria-label="Pincel">
            {BRUSHES.map((b) => (
              <button
                key={b}
                type="button"
                aria-pressed={brush === b}
                className={brush === b ? 'primary' : undefined}
                onClick={() => setBrush(b)}
              >
                {b}%
              </button>
            ))}
          </div>
          <RangeMatrix
            layers={[{ action, grid: painted }]}
            onPaint={paint}
            caption="Tu rango: tocá o arrastrá"
            implicitFold={false}
          />
          <div className="field-row">
            <button type="button" onClick={() => setPainted(EMPTY())}>
              Limpiar
            </button>
            <button type="button" className="primary" onClick={() => onSubmit(painted)}>
              Enviar
            </button>
          </div>
        </>
      )}
      {feedback && range && (
        <div className={`trainer-feedback verdict-${feedback.verdict}`} aria-live="polite">
          <h3 className="verdict">{VERDICT_LABEL[feedback.verdict]}</h3>
          <p>Precisión: {Math.round(range.precision * 100)}%</p>
          <RangeMatrix
            layers={[
              { action: 'call', grid: range.diff_grid.map((d) => Math.max(0, -d)) },
              { action: 'raise', grid: range.diff_grid.map((d) => Math.max(0, d)) },
            ]}
            caption="Diferencias: verde faltante, rojo sobrante"
            implicitFold={false}
          />
          {missing.length > 0 && <p>Faltan: {list(missing)}</p>}
          {extra.length > 0 && <p>Sobran: {list(extra)}</p>}
          {missing.length === 0 && extra.length === 0 && <p>Sin diferencias.</p>}
          {onNext && (
            <button type="button" className="primary" onClick={onNext}>
              Siguiente <kbd>Enter</kbd>
            </button>
          )}
        </div>
      )}
    </section>
  )
}
