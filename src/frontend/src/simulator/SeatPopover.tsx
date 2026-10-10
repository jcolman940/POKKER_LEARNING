import type { RefObject } from 'react'
import { Button, PillGroup, Popover } from '../ui'
import { CardView } from './CardView'
import { toSlots } from './cards'
import { RangeEditor } from './RangeEditor'
import { type BetPreset, presetBet, type Seat, type SeatRole, type TableState } from './table'
import { type CardSlotRef, sameSlot } from './slots'

const ROLES: { value: SeatRole; label: string }[] = [
  { value: 'hero', label: 'Vos' },
  { value: 'villain', label: 'Rival' },
  { value: 'folded', label: 'Fold' },
  { value: 'empty', label: 'Vacío' },
]
const PRESETS: [BetPreset, string][] = [
  ['third', '⅓'],
  ['half', '½'],
  ['twothirds', '⅔'],
  ['pot', 'Pot'],
  ['allin', 'All-in'],
]

interface SeatPopoverProps {
  seat: Seat
  table: TableState
  anchorRef: RefObject<HTMLButtonElement | null>
  onClose: () => void
  onRole: (role: SeatRole) => void
  onChange: (patch: Partial<Seat>) => void
  activeSlot: CardSlotRef | null
  onSlotClick: (slot: CardSlotRef) => void
}

const amount = (value: string) => Math.max(0, Number(value) || 0)

export function SeatPopover({ seat, table, anchorRef, onClose, onRole, onChange, activeSlot, onSlotClick }: SeatPopoverProps) {
  const playing = seat.role === 'hero' || seat.role === 'villain'
  const rangeId = `seat-${seat.position}-range`
  return (
    <Popover open onClose={onClose} anchorRef={anchorRef} label={`Asiento ${seat.position}`} className="sim-popover">
      <div className="sim-popover-title">{seat.position}</div>
      <PillGroup legend="Asiento" options={ROLES} value={seat.role} onChange={onRole} />
      {playing && (
        <>
          <fieldset className="sim-field">
            <legend>Apuesta en esta calle</legend>
            <div className="sim-presets">
              {PRESETS.map(([preset, label]) => (
                <Button
                  key={preset}
                  size="sm"
                  onClick={() => onChange({ bet_bb: presetBet(table, seat.position, preset) })}
                >
                  {label}
                </Button>
              ))}
            </div>
            <label>
              Apuesta (bb)
              <input
                type="number"
                min="0"
                step="0.5"
                value={seat.bet_bb}
                onChange={(e) => onChange({ bet_bb: amount(e.target.value) })}
              />
            </label>
          </fieldset>
          <label>
            Stack (bb)
            <input
              type="number"
              min="0"
              step="1"
              value={seat.stack_bb}
              onChange={(e) => onChange({ stack_bb: amount(e.target.value) })}
            />
          </label>
        </>
      )}
      {seat.role === 'villain' && (
        <>
          <label htmlFor={rangeId}>Rango</label>
          <RangeEditor id={rangeId} value={seat.range} onChange={(range) => onChange({ range })} />
          <p className="field-label">Cartas (opcional)</p>
          <div className="card-slots">
            {toSlots(seat.hand, 2).map((card, i) => (
              <CardView
                key={i}
                card={card}
                label={`${seat.position} carta ${i + 1}`}
                active={sameSlot(activeSlot, { group: 'seat', position: seat.position, index: i })}
                onClick={() => onSlotClick({ group: 'seat', position: seat.position, index: i })}
              />
            ))}
          </div>
        </>
      )}
      <Button size="sm" onClick={onClose}>
        Listo
      </Button>
    </Popover>
  )
}
