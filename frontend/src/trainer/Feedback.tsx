import { ACTION_LABEL } from '../ranges/labels'
import { RangeMatrix } from '../ranges/RangeMatrix'
import { pct } from '../simulator/format'
import { lossText, VERDICT_LABEL } from './format'
import type { Feedback as FeedbackData } from './types'

interface Props {
  feedback: FeedbackData
  onNext: () => void
}

const label = (a: string | null) => (a ? (ACTION_LABEL[a] ?? a) : '—')

export function Feedback({ feedback, onNext }: Props) {
  const rec = feedback.recommendation
  const hasRec = rec?.available && rec.actions.length > 0
  return (
    <section className={`panel trainer-feedback verdict-${feedback.verdict}`} aria-live="polite">
      <div className="panel-header">
        <h3 className="verdict">{VERDICT_LABEL[feedback.verdict]}</h3>
        <span className="badges">
          {feedback.approximate && <span className="badge badge-warn">Aproximado</span>}
        </span>
      </div>
      <p>
        Tu acción: {label(feedback.chosen)} · Referencia: {label(feedback.best)}
      </p>
      <p className="muted">{lossText(feedback)}</p>
      {hasRec && rec && (
        <ul className="rec-actions">
          {rec.actions.map((a) => (
            <li key={a.label ?? a.action}>
              <span className="rec-action-name">{a.label ?? label(a.action)}</span>
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
      )}
      {rec && rec.explanation.length > 0 && (
        <ul className="small rec-explanation">
          {rec.explanation.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      )}
      {rec && rec.warnings.length > 0 && (
        <ul className="small rec-warnings">
          {rec.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}
      {feedback.reference_layers.length > 0 && (
        <RangeMatrix
          layers={feedback.reference_layers}
          caption="Referencia del rango de Hero"
          highlight={feedback.hand_index ?? undefined}
        />
      )}
      <button type="button" className="primary" onClick={onNext}>
        Siguiente <kbd>Enter</kbd>
      </button>
    </section>
  )
}
