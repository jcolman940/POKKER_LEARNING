import { useCallback, useEffect, useState } from 'react'
import { postJson } from '../api/client'
import { CardView } from '../simulator/CardView'
import { splitCards } from '../simulator/cards'
import { pct } from '../simulator/format'
import type { Replay, ReplayStep } from './types'

interface Props {
  handId: number
  onAnalyze: (scenario: NonNullable<ReplayStep['scenario']>) => void
  onBack: () => void
}

export function ReplayerView({ handId, onAnalyze, onBack }: Props) {
  const [replay, setReplay] = useState<Replay | null>(null)
  const [ranges, setRanges] = useState<Record<string, string>>({})
  const [draft, setDraft] = useState<Record<string, string>>({})
  const [index, setIndex] = useState(0)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    postJson<Replay>(`/api/hands/${handId}/replay`, { ranges }, controller.signal)
      .then((r) => {
        setReplay(r)
        setDraft(r.ranges)
        setError(null)
      })
      .catch((e: unknown) => {
        if (!controller.signal.aborted) setError(e instanceof Error ? e.message : String(e))
      })
    return () => controller.abort()
  }, [handId, ranges])

  const steps = replay?.steps ?? []
  const step = steps[Math.min(index, steps.length - 1)]
  const last = steps.length - 1

  const onKey = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'ArrowRight') setIndex((i) => Math.min(last, i + 1))
      if (e.key === 'ArrowLeft') setIndex((i) => Math.max(0, i - 1))
    },
    [last],
  )

  if (error) {
    return (
      <p className="error" role="alert">
        {error}
      </p>
    )
  }
  if (!replay || !step) return <p className="muted">Cargando mano…</p>

  const showdown = index === last

  return (
    <div className="replayer" onKeyDown={onKey}>
      <div className="field-row">
        <button type="button" onClick={onBack}>
          ← Volver a la lista
        </button>
        <span className="small muted">
          {replay.site} · mano {replay.hand_id}
        </span>
      </div>

      <section className="panel" aria-labelledby="replay-title">
        <h3 id="replay-title">
          {step.street.toUpperCase()} · Pozo {step.pot_bb.toFixed(1)}bb
        </h3>
        <div className="replay-board" aria-label="Board">
          {splitCards(step.board).map((c) => (
            <CardView key={c} card={c} />
          ))}
          {!step.board && <span className="muted small">Sin board</span>}
        </div>
        <ul className="replay-seats">
          {replay.players.map((p) => {
            const folded = step.folded.includes(p.name)
            const reveal = p.is_hero || showdown
            return (
              <li
                key={p.name}
                className={[
                  'replay-seat',
                  p.is_hero ? 'is-hero' : '',
                  folded ? 'is-folded' : '',
                  step.actor === p.name ? 'is-actor' : '',
                ]
                  .filter(Boolean)
                  .join(' ')}
              >
                <span className="seat-pos">{p.position}</span>
                <span className="seat-name">{p.is_hero ? `${p.name} (Hero)` : p.name}</span>
                <span className="mini-cards">
                  {reveal && p.cards
                    ? splitCards(p.cards).map((c) => <CardView key={c} card={c} />)
                    : !folded && <span className="muted small">🂠🂠</span>}
                </span>
                <span className="seat-stack">{step.stacks_bb[p.name]?.toFixed(1)}bb</span>
                {step.bets_bb[p.name] > 0 && (
                  <span className="seat-bet">apuesta {step.bets_bb[p.name].toFixed(1)}</span>
                )}
                {showdown && (
                  <span
                    className={`seat-result ${replay.result[p.name] > 0 ? 'positive' : replay.result[p.name] < 0 ? 'negative' : ''}`}
                  >
                    {replay.result[p.name] > 0 ? '+' : ''}
                    {replay.result[p.name].toFixed(1)}bb
                  </span>
                )}
              </li>
            )
          })}
        </ul>
        <p className="replay-action" aria-live="polite">
          {step.description}
        </p>
        <p className="small">
          Equity de Hero contra los rangos asignados:{' '}
          <strong>{step.hero_equity ? pct(step.hero_equity.equity) : '—'}</strong>
          {step.hero_equity && !step.hero_equity.exact && (
            <span className="muted"> ± {pct(1.96 * step.hero_equity.std_error, 1)}</span>
          )}
        </p>
        <div className="field-row replay-controls">
          <button type="button" onClick={() => setIndex(0)} disabled={index === 0} aria-label="Inicio">
            ⏮
          </button>
          <button type="button" onClick={() => setIndex(index - 1)} disabled={index === 0} aria-label="Anterior">
            ◀
          </button>
          <span className="small muted">
            Paso {index + 1} de {steps.length}
          </span>
          <button type="button" onClick={() => setIndex(index + 1)} disabled={index >= last} aria-label="Siguiente">
            ▶
          </button>
          <button type="button" onClick={() => setIndex(last)} disabled={index >= last} aria-label="Final">
            ⏭
          </button>
          {step.scenario && (
            <button type="button" className="primary" onClick={() => onAnalyze(step.scenario!)}>
              Analizar este spot
            </button>
          )}
        </div>
        {!step.scenario && (
          <p className="small muted">"Analizar este spot" aparece en los pasos donde le toca decidir a Hero.</p>
        )}
      </section>

      <section className="panel" aria-labelledby="ranges-title">
        <h3 id="ranges-title">Rangos asignados a los rivales</h3>
        <p className="small muted">La equity se calcula contra estos rangos, nunca contra las cartas mostradas.</p>
        {Object.keys(draft).map((name) => (
          <label key={name}>
            {replay.players.find((p) => p.name === name)?.position} · {name}
            <input
              type="text"
              value={draft[name]}
              onChange={(e) => setDraft((d) => ({ ...d, [name]: e.target.value }))}
            />
          </label>
        ))}
        <button type="button" onClick={() => setRanges(draft)}>
          Recalcular equity
        </button>
      </section>
    </div>
  )
}
