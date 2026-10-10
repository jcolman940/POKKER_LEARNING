import { type ReactNode, useId } from 'react'
import { cx } from './cx'
import './Card.css'

interface Props {
  title?: string
  className?: string
  children: ReactNode
}

export function Card({ title, className, children }: Props) {
  const id = useId()
  return (
    <section className={cx('ui-card', className)} aria-labelledby={title ? id : undefined}>
      {title && (
        <h3 id={id} className="ui-card-title">
          {title}
        </h3>
      )}
      {children}
    </section>
  )
}
