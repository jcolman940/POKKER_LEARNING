import { SUIT_NAME, SUIT_SYMBOL, type Suit } from './cards'

interface Props {
  card: string | null
  onClick?: () => void
  active?: boolean
  disabled?: boolean
  label?: string
}

export function CardView({ card, onClick, active = false, disabled = false, label }: Props) {
  const suit = card ? (card[1] as Suit) : null
  const className = [
    'card',
    suit ? `suit-${suit}` : 'card-empty',
    active ? 'card-active' : '',
    disabled ? 'card-disabled' : '',
  ]
    .filter(Boolean)
    .join(' ')
  const ariaLabel = card
    ? `${label ? label + ': ' : ''}${card[0]} de ${SUIT_NAME[suit as Suit]}`
    : `${label ? label + ': ' : ''}vacía`

  const face = card ? (
    <>
      <span className="card-rank">{card[0]}</span>
      <span className="card-suit">{SUIT_SYMBOL[suit as Suit]}</span>
    </>
  ) : (
    <span className="card-placeholder">+</span>
  )

  if (!onClick) {
    return (
      <span className={className} role="img" aria-label={ariaLabel}>
        {face}
      </span>
    )
  }

  return (
    <button
      type="button"
      className={className}
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel}
      aria-pressed={active}
    >
      {face}
    </button>
  )
}
