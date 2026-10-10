import { type ReactNode, useState } from 'react'
import { SITUATIONS } from '../ranges/labels'
import { type AdvancedOptions, parsePayouts, type TableState } from './table'

const amount = (value: string) => Math.max(0, Number(value) || 0)

interface Props {
  table: TableState
  onChange: (advanced: AdvancedOptions) => void
  /** Previous action built from the bets, shown as the placeholder. */
  autoAction: string
  children?: ReactNode
}

export function AdvancedPanel({ table, onChange, autoAction, children }: Props) {
  const a = table.advanced
  const [payoutText, setPayoutText] = useState(a.payouts.join(', '))
  const set = (patch: Partial<AdvancedOptions>) => onChange({ ...a, ...patch })
  return (
    <details className="panel sim-advanced">
      <summary>Opciones avanzadas</summary>
      <div className="field-row">
        <label>
          Situación preflop
          <select value={a.situation ?? ''} onChange={(e) => set({ situation: e.target.value || null })}>
            <option value="">Sin definir</option>
            {SITUATIONS.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </label>
        <label>
          Ante (bb)
          <input type="number" min="0" step="0.01" value={a.ante_bb} onChange={(e) => set({ ante_bb: amount(e.target.value) })} />
        </label>
        <label>
          BB ante (bb)
          <input
            type="number"
            min="0"
            step="0.1"
            value={a.bb_ante_bb}
            onChange={(e) => set({ bb_ante_bb: amount(e.target.value) })}
          />
        </label>
      </div>
      <label>
        Acción previa
        <input
          type="text"
          value={a.previous_action}
          placeholder={autoAction || 'Se arma con las apuestas de la mesa'}
          onChange={(e) => set({ previous_action: e.target.value })}
        />
      </label>
      {table.format !== 'cash' && (
        <label>
          Premios que quedan (vacío = chip EV)
          <input
            type="text"
            value={payoutText}
            placeholder="Ej.: 50, 30, 20"
            onChange={(e) => {
              setPayoutText(e.target.value)
              set({ payouts: parsePayouts(e.target.value) })
            }}
          />
        </label>
      )}
      {children}
    </details>
  )
}
