import { createRef, type ReactNode, type RefObject, useRef } from 'react'
import { CardView } from './CardView'
import { toSlots } from './cards'
import { BOARD_CARDS, rotateFromHero, type Seat, type SeatRole, seatPoint, type TableState, totalPot } from './table'
import './table.css'

export type CardSlotRef =
  | { group: 'hero' | 'board'; index: number }
  | { group: 'seat'; position: string; index: number }

export function sameSlot(a: CardSlotRef | null, b: CardSlotRef): boolean {
  if (!a || a.group !== b.group || a.index !== b.index) return false
  return a.group !== 'seat' || (b.group === 'seat' && a.position === b.position)
}

const ROLE_TAG: Record<SeatRole, string> = { hero: 'Vos', villain: 'Rival', folded: 'Fold', empty: 'Vacío' }
const BOARD_LABELS = ['Flop 1', 'Flop 2', 'Flop 3', 'Turn', 'River']
const fmt = (n: number) => String(Math.round(n * 100) / 100).replace('.', ',')

interface TableViewProps {
  table: TableState
  selected: string | null
  onSeatClick: (position: string) => void
  activeSlot: CardSlotRef | null
  onSlotClick: (slot: CardSlotRef) => void
  onPotChange: (pot: number) => void
  renderSeatPanel?: (
    seat: Seat,
    anchorRef: RefObject<HTMLButtonElement | null>,
    style: { left: string; top: string },
  ) => ReactNode
}

export function TableView({ table, selected, onSeatClick, activeSlot, onSlotClick, onPotChange, renderSeatPanel }: TableViewProps) {
  const refs = useRef(new Map<string, RefObject<HTMLButtonElement | null>>())
  const refFor = (position: string) => {
    let r = refs.current.get(position)
    if (!r) {
      r = createRef<HTMLButtonElement>()
      refs.current.set(position, r)
    }
    return r
  }
  const order = rotateFromHero(table.seats)
  const n = order.length
  const used = BOARD_CARDS[table.street]
  const board = toSlots(table.board, 5)
  const hero = toSlots(table.hero_hand, 2)

  return (
    <div className="sim-stage" role="group" aria-label="Mesa">
      <div className="sim-felt" aria-hidden="true" />
      <div className="sim-center">
        <label className="sim-pot">
          Pozo (bb)
          <input
            type="number"
            min="0"
            step="0.5"
            value={table.pot_bb}
            onChange={(e) => onPotChange(Math.max(0, Number(e.target.value) || 0))}
          />
        </label>
        <p className="sim-pot-total">Total con apuestas: {fmt(totalPot(table))} bb</p>
        <div className="sim-board">
          {board.map((card, i) =>
            i < used ? (
              <CardView
                key={i}
                card={card}
                label={BOARD_LABELS[i]}
                active={sameSlot(activeSlot, { group: 'board', index: i })}
                onClick={() => onSlotClick({ group: 'board', index: i })}
              />
            ) : (
              <span key={i} className="card card-empty sim-board-off" aria-hidden="true" />
            ),
          )}
        </div>
      </div>

      {order.map((seat, k) => {
        const p = seatPoint(k, n)
        const bet = seatPoint(k, n, 0.55)
        const dealer = seatPoint(k, n, 0.72)
        const style = { left: `${p.left}%`, top: `${p.top}%` }
        return (
          <div key={seat.position}>
            <div
              className={`sim-seat sim-seat-${seat.role}${selected === seat.position ? ' sim-seat-selected' : ''}`}
              style={style}
            >
              {seat.role === 'hero' && (
                <div className="sim-hero-cards">
                  {hero.map((card, i) => (
                    <CardView
                      key={i}
                      card={card}
                      label={`Hero carta ${i + 1}`}
                      active={sameSlot(activeSlot, { group: 'hero', index: i })}
                      onClick={() => onSlotClick({ group: 'hero', index: i })}
                    />
                  ))}
                </div>
              )}
              <button
                ref={refFor(seat.position)}
                type="button"
                className="sim-plate"
                aria-label={`${seat.position} · ${ROLE_TAG[seat.role]} · ${fmt(seat.stack_bb)} bb`}
                aria-expanded={selected === seat.position}
                onClick={() => onSeatClick(seat.position)}
              >
                <span className="sim-pos">{seat.position}</span>
                <span className="sim-stack">{fmt(seat.stack_bb)} bb</span>
                <span className="sim-tag">{ROLE_TAG[seat.role]}</span>
              </button>
            </div>
            {seat.bet_bb > 0 && seat.role !== 'empty' && (
              <div className="sim-bet" style={{ left: `${bet.left}%`, top: `${bet.top}%` }}>
                <i aria-hidden="true" />
                {fmt(seat.bet_bb)} bb
              </div>
            )}
            {seat.position === 'BTN' && (
              <div
                className="sim-dealer"
                role="img"
                aria-label="Botón del dealer"
                style={{ left: `${dealer.left + 5}%`, top: `${dealer.top}%` }}
              >
                D
              </div>
            )}
            {selected === seat.position && renderSeatPanel?.(seat, refFor(seat.position), style)}
          </div>
        )
      })}
    </div>
  )
}
