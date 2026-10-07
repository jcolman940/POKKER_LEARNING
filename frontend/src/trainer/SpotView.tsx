import { ACTION_LABEL, FORMAT_LABEL } from '../ranges/labels'
import { CardView } from '../simulator/CardView'
import { splitCards } from '../simulator/cards'
import { SITUATION_TEXT } from './format'
import type { Spot } from './types'

interface Props {
  spot: Spot
  onAnswer?: (action: string) => void
}

function shortcut(action: string, index: number, offered: string[]): string {
  const letter = action === 'fold' ? 'F' : ['call', 'limp', 'check'].includes(action) ? 'C' : null
  if (letter) return letter
  const firstAggressive = offered.find((a) => !['fold', 'call', 'limp', 'check'].includes(a))
  return action === firstAggressive ? 'R' : String(index + 1)
}

export function SpotView({ spot, onAnswer }: Props) {
  const sc = spot.scenario
  if (!sc) return null
  const rival = sc.villains[0]?.position
  const pushfold = spot.source === 'pushfold'
  const stacks = Object.entries(sc.stacks_bb)
  return (
    <section className="panel trainer-spot" aria-label="Spot">
      <div className="panel-header">
        <h3>{spot.title}</h3>
        <span className="badges">
          {spot.review && <span className="badge badge-warn">Repaso</span>}
        </span>
      </div>
      <p className="trainer-table">
        {FORMAT_LABEL[sc.format] ?? sc.format} · {sc.num_players} jugadores · Hero en{' '}
        <strong>{sc.hero_position}</strong> · {SITUATION_TEXT[sc.situation ?? ''] ?? sc.situation}
        {rival ? ` (rival ${rival})` : ''} · Stack {sc.effective_stack_bb} bb
        {pushfold && sc.ante_bb > 0 ? ` · Ante ${sc.ante_bb} bb` : ''}
      </p>
      {pushfold && stacks.length > 0 && (
        <p className="small muted">
          Stacks: {stacks.map(([pos, bb]) => `${pos} ${bb} bb`).join(', ')}
        </p>
      )}
      <div className="trainer-hand">
        {splitCards(sc.hero_hand).map((c) => (
          <CardView key={c} card={c} label="Hero" />
        ))}
      </div>
      {onAnswer && (
        <div className="trainer-actions" role="group" aria-label="Acciones">
          {spot.offered.map((a, i) => (
            <button key={a} type="button" className={`trainer-action action-${a}`} onClick={() => onAnswer(a)}>
              {ACTION_LABEL[a] ?? a}
              <kbd>{shortcut(a, i, spot.offered)}</kbd>
            </button>
          ))}
        </div>
      )}
    </section>
  )
}
