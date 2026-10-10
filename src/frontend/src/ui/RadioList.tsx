import { useId } from 'react'
import { cx } from './cx'
import './RadioList.css'

export interface Option<T extends string> {
  value: T
  label: string
  count?: number
  disabled?: boolean
}

interface Props<T extends string> {
  legend: string
  options: Option<T>[]
  value: T
  onChange: (value: T) => void
  name?: string
}

/** Filter card: native radios (arrow keys for free), count in grey, count 0 dimmed but selectable. */
export function RadioList<T extends string>({ legend, options, value, onChange, name }: Props<T>) {
  const autoName = useId()
  const group = name ?? autoName
  return (
    <fieldset className="ui-radio-list">
      <legend className="ui-radio-legend">{legend}</legend>
      <div className="ui-radio-card">
        {options.map((o) => (
          <label key={o.value} className={cx('ui-radio-row', o.count === 0 && 'ui-radio-dim')}>
            <span className="ui-radio-text">
              {o.label}
              {o.count !== undefined && <span className="ui-radio-count">{o.count}</span>}
            </span>
            <input
              type="radio"
              name={group}
              value={o.value}
              checked={o.value === value}
              disabled={o.disabled}
              onChange={() => onChange(o.value)}
            />
          </label>
        ))}
      </div>
    </fieldset>
  )
}
