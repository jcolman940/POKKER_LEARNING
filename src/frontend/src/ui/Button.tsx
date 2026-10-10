import type { ButtonHTMLAttributes } from 'react'
import { cx } from './cx'
import './Button.css'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost'
  size?: 'sm' | 'md'
}

export function Button({ variant = 'secondary', size = 'md', type = 'button', className, ...rest }: ButtonProps) {
  return <button type={type} className={cx('btn', `btn-${variant}`, `btn-${size}`, className)} {...rest} />
}
