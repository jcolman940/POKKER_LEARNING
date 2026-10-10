import type { ReactNode } from 'react'
import './Chip.css'

interface Props {
  children: ReactNode
  actionLabel?: string
  onAction?: () => void
}

export function Chip({ children, actionLabel, onAction }: Props) {
  return (
    <span className="ui-chip">
      <span>{children}</span>
      {actionLabel && onAction && (
        <button type="button" className="ui-chip-action" onClick={onAction}>
          {actionLabel}
        </button>
      )}
    </span>
  )
}
