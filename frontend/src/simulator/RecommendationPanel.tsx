import { ACTION_LABEL } from '../ranges/labels'
import { pct } from './format'
import type { Recommendation } from './types'

const SOURCE_LABEL = {
  chart: 'Tabla preflop',
  nash: 'Nash push/fold',
  solver: 'Solver',
  heuristic: 'Heurística',
}

export function RecommendationPanel({ rec }: { rec: Recommendation }) {
  if (!rec.available) {
    return (
      <section className="panel panel-muted" aria-labelledby="rec-title">
        <h3 id="rec-title">Recomendación</h3>
        <p className="muted">{rec.message}</p>
      </section>
    )
  }
  return (
    <section className="panel panel-rec" aria-labelledby="rec-title">
      <div className="panel-header">
        <h3 id="rec-title">
          Recomendación{rec.hand_class ? ` · ${rec.hand_class}` : ''}
        </h3>
        <span className="badges">
          {rec.source && <span className="badge">{SOURCE_LABEL[rec.source]}</span>}
          {rec.confidence === 'approximate' && <span className="badge badge-warn">Aproximado</span>}
        </span>
      </div>
      <ul className="rec-actions">
        {rec.actions.map((a) => (
          <li key={a.action}>
            <span className="rec-action-name">{ACTION_LABEL[a.action] ?? a.action}</span>
            <span className="rec-bar" aria-hidden="true">
              <span
                className="rec-bar-fill"
                style={{ width: `${a.frequency * 100}%`, background: `var(--action-${a.action})` }}
              />
            </span>
            <span className="rec-freq">{pct(a.frequency, 0)}</span>
            {a.ev !== null && (
              <span className="rec-ev muted">
                EV {a.ev.toFixed(2)}
                {rec.ev_unit}
              </span>
            )}
          </li>
        ))}
      </ul>
      {rec.reference && <p className="small muted">{rec.reference}</p>}
      {rec.explanation.length > 0 && (
        <ul className="small rec-explanation">
          {rec.explanation.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      )}
      {rec.warnings.length > 0 && (
        <ul className="small rec-warnings">
          {rec.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}
    </section>
  )
}
