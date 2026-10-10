import { type ReactNode, type RefObject, useEffect, useRef } from 'react'
import { cx } from './cx'
import './Popover.css'

interface Props {
  open: boolean
  onClose: () => void
  anchorRef: RefObject<HTMLElement | null>
  label: string
  className?: string
  children: ReactNode
}

const FOCUSABLE =
  'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea, [tabindex]:not([tabindex="-1"])'

/** Floating panel next to its anchor. The caller positions it through className. */
export function Popover({ open, onClose, anchorRef, label, className, children }: Props) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const anchor = anchorRef.current
    ref.current?.querySelector<HTMLElement>(FOCUSABLE)?.focus()

    function onMouseDown(e: MouseEvent) {
      const target = e.target as Node
      if (ref.current?.contains(target) || anchorRef.current?.contains(target)) return
      onClose()
    }
    document.addEventListener('mousedown', onMouseDown)
    return () => {
      document.removeEventListener('mousedown', onMouseDown)
      anchor?.focus()
    }
  }, [open, onClose, anchorRef])

  if (!open) return null
  return (
    <div
      ref={ref}
      role="dialog"
      aria-label={label}
      className={cx('ui-popover', className)}
      onKeyDown={(e) => {
        if (e.key === 'Escape') {
          e.stopPropagation()
          onClose()
        }
      }}
    >
      {children}
    </div>
  )
}
