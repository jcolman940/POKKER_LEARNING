import { pct } from '../simulator/format'
import type { FrequentError, Summary } from './types'

interface Props {
  summary: Summary | null
  errors: FrequentError[]
  onTrainErrors: () => void
}

export function SessionSidebar({ summary, errors, onTrainErrors }: Props) {
  return (
    <aside className="trainer-sidebar" aria-label="Sesión">
      <section className="panel">
        <h3>Sesión</h3>
        {summary ? (
          <ul className="trainer-summary">
            <li>Spots: {summary.spots}</li>
            <li>Correctos: {summary.correct}</li>
            <li>Aceptables: {summary.acceptable}</li>
            <li>Errores: {summary.error}</li>
            <li>Pérdida EV: {summary.ev_loss_bb.toFixed(2).replace('.', ',')} bb</li>
            {summary.avg_freq_error !== null && (
              <li>Error de frecuencia medio: {pct(summary.avg_freq_error, 0)}</li>
            )}
            {summary.avg_precision !== null && <li>Precisión media: {pct(summary.avg_precision, 0)}</li>}
          </ul>
        ) : (
          <p className="muted small">Todavía no respondiste ningún spot.</p>
        )}
      </section>
      <section className="panel">
        <h3>Tus errores frecuentes</h3>
        {errors.length === 0 ? (
          <p className="muted small">Todavía no hay errores repetidos.</p>
        ) : (
          <>
            <ul className="trainer-errors">
              {errors.map((e) => (
                <li key={e.card_id}>
                  {e.label} <span className="muted small">({e.lapses} fallos / {e.reps})</span>
                </li>
              ))}
            </ul>
            <button type="button" onClick={onTrainErrors}>
              Entrenar solo estas
            </button>
          </>
        )}
      </section>
    </aside>
  )
}
