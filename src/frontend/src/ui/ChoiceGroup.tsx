import { useId } from 'react'
import { cx } from './cx'
import type { Option } from './RadioList'
import './ChoiceGroup.css'

export interface ChoiceProps<T extends string> {
  legend: string
  options: Option<T>[]
  value: T | null
  onChange: (value: T) => void
  name?: string
}

/** Single choice styled as buttons: native radios, disabled options cannot be picked. */
export function ChoiceGroup<T extends string>({
  legend,
  options,
  value,
  onChange,
  name,
  vertical,
}: ChoiceProps<T> & { vertical: boolean }) {
  const autoName = useId()
  const group = name ?? autoName
  return (
    <fieldset className={cx('ui-choice', vertical ? 'ui-choice-vertical' : 'ui-choice-horizontal')}>
      <legend className="ui-choice-legend">{legend}</legend>
      <div className="ui-choice-items">
        {options.map((o) => (
          <label key={o.value} className={cx('ui-choice-item', o.disabled && 'ui-choice-disabled')}>
            <input
              type="radio"
              name={group}
              value={o.value}
              checked={o.value === value}
              disabled={o.disabled}
              onChange={() => onChange(o.value)}
            />
            <span>{o.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}
