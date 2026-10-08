import { CardView } from './CardView'
import { RANKS, SUITS } from './cards'

interface Props {
  used: Set<string>
  onPick: (card: string) => void
  onClear: () => void
  onClose: () => void
}

export function CardPicker({ used, onPick, onClear, onClose }: Props) {
  return (
    <div className="card-picker" role="dialog" aria-label="Elegir carta">
      {SUITS.map((suit) => (
        <div key={suit} className="card-picker-row">
          {RANKS.map((rank) => {
            const card = rank + suit
            return (
              <CardView
                key={card}
                card={card}
                disabled={used.has(card)}
                onClick={() => onPick(card)}
              />
            )
          })}
        </div>
      ))}
      <div className="card-picker-actions">
        <button type="button" onClick={onClear}>
          Vaciar casilla
        </button>
        <button type="button" onClick={onClose}>
          Cerrar
        </button>
      </div>
    </div>
  )
}
