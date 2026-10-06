import { CardView } from './CardView'
import { num, pct } from './format'
import type { Analysis, EquityResult } from './types'

const STREET_LABEL = { preflop: 'Preflop', flop: 'Flop', turn: 'Turn', river: 'River' }

function EquityTable({ result, villainLabels }: { result: EquityResult; villainLabels: string[] }) {
  const rows = [
    { label: 'Hero', p: result.hero },
    ...result.villains.map((p, i) => ({ label: villainLabels[i] ?? `Rival ${i + 1}`, p })),
  ]
  return (
    <table className="equity-table">
      <thead>
        <tr>
          <th scope="col">Jugador</th>
          <th scope="col">Equity</th>
          <th scope="col">Gana</th>
          <th scope="col">Empata</th>
          <th scope="col">Pierde</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(({ label, p }) => (
          <tr key={label}>
            <th scope="row">{label}</th>
            <td>
              {pct(p.equity)}
              {!result.exact && (
                <span className="muted"> ± {pct(1.96 * p.std_error, 2)}</span>
              )}
            </td>
            <td>{pct(p.win)}</td>
            <td>{pct(p.tie)}</td>
            <td>{pct(p.lose)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function method(result: EquityResult): string {
  return result.exact
    ? `Cálculo exacto (${result.samples.toLocaleString('es')} runouts)`
    : `Monte Carlo (${result.samples.toLocaleString('es')} muestras, intervalo del 95%)`
}

export function ResultsPanel({
  analysis,
  villainLabels,
}: {
  analysis: Analysis
  villainLabels: string[]
}) {
  const { equity, equity_vs_hands, outs, metrics, recommendation } = analysis
  const required = metrics.required_equity
  return (
    <div className="results">
      <section className="panel" aria-labelledby="eq-title">
        <h3 id="eq-title">
          Equity contra el rango · {STREET_LABEL[analysis.street]}
        </h3>
        <p className="big-number">{pct(equity.hero.equity)}</p>
        <EquityTable result={equity} villainLabels={villainLabels} />
        <p className="muted small">{method(equity)}</p>
        <ul className="muted small range-list">
          {analysis.ranges.map((r, i) => (
            <li key={i}>
              {villainLabels[i] ?? `Rival ${i + 1}`}: {r.combos.toFixed(0)} combos vivos
            </li>
          ))}
        </ul>
      </section>

      {equity_vs_hands && (
        <section className="panel panel-info" aria-labelledby="eqh-title">
          <h3 id="eqh-title">Dato informativo</h3>
          <p>
            Contra esta mano puntual tenías <strong>{pct(equity_vs_hands.hero.equity)}</strong>.
          </p>
          <p className="muted small">
            No se usa para la recomendación: el análisis siempre es contra el rango.
          </p>
        </section>
      )}

      <section className="panel" aria-labelledby="pot-title">
        <h3 id="pot-title">Pote</h3>
        <dl className="metrics">
          <div>
            <dt>Pot odds</dt>
            <dd>{metrics.pot_odds === null ? '—' : `${num(metrics.pot_odds, 1)} : 1`}</dd>
          </div>
          <div>
            <dt>Equity requerida</dt>
            <dd>{pct(required)}</dd>
          </div>
          <div>
            <dt>MDF</dt>
            <dd>{pct(metrics.mdf)}</dd>
          </div>
          <div>
            <dt>SPR</dt>
            <dd>{num(metrics.spr, 1)}</dd>
          </div>
        </dl>
        {required !== null && (
          <p className="small">
            Tu equity contra el rango está{' '}
            <strong>{equity.hero.equity >= required ? 'por encima' : 'por debajo'}</strong> de la
            requerida para pagar (sin contar implied odds).
          </p>
        )}
      </section>

      <section className="panel" aria-labelledby="outs-title">
        <h3 id="outs-title">Outs</h3>
        {!outs.available && <p className="muted">Se calculan en flop y turn.</p>}
        {outs.available && outs.currently_ahead && (
          <p>Vas por delante del rango ({pct(outs.hero_share)} de las manos al showdown ahora).</p>
        )}
        {outs.available && !outs.currently_ahead && (
          <>
            <p>
              <strong>{outs.count}</strong> outs de {outs.unseen} cartas (
              {pct(outs.count / outs.unseen)} por carta). Hoy ganás el {pct(outs.hero_share)} de
              las manos del rango al showdown.
            </p>
            <div className="outs-cards">
              {outs.cards.map((c) => (
                <CardView key={c} card={c} />
              ))}
            </div>
            <p className="muted small">
              Out: carta que te pone por delante de al menos la mitad del rango rival.
            </p>
          </>
        )}
      </section>

      <section className="panel panel-muted" aria-labelledby="rec-title">
        <h3 id="rec-title">Recomendación</h3>
        <p className="muted">{recommendation.message}</p>
      </section>
    </div>
  )
}
