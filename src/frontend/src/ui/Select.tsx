import type { SelectHTMLAttributes } from 'react'
import { cx } from './cx'
import './Select.css'

interface Props extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string
}

export function Select({ label, className, children, ...rest }: Props) {
  return (
    <label className={cx('ui-select', className)}>
      <span className="ui-select-label">{label}</span>
      <select {...rest}>{children}</select>
    </label>
  )
}
