import { useEffect, useState } from 'react'
import { postJson } from '../api/client'
import { handClassName } from './cards'
import type { RangeParse } from './types'

interface Props {
  id: string
  value: string
  onChange: (value: string) => void
}

const CELLS = Array.from({ length: 169 }, (_, i) => i)

export function RangeEditor({ id, value, onChange }: Props) {
  const [parsed, setParsed] = useState<RangeParse | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    const timer = setTimeout(() => {
      postJson<RangeParse>('/api/ranges/parse', { text: value }, controller.signal)
        .then(setParsed)
        .catch(() => {
          if (!controller.signal.aborted) setParsed(null)
        })
    }, 250)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [value])

  return (
    <div className="range-editor">
      <textarea
        id={id}
        rows={2}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="random, 22+, A2s+, KTo+, AKs:0.5…"
        spellCheck={false}
      />
      {parsed && !parsed.valid && <p className="field-error">{parsed.error}</p>}
      {parsed?.valid && (
        <>
          <p className="range-summary">
            {parsed.combos.toFixed(0)} combos ({((parsed.combos / 1326) * 100).toFixed(1)}% de las
            manos)
          </p>
          <div className="range-grid" aria-hidden="true">
            {CELLS.map((i) => {
              const w = parsed.grid[i] ?? 0
              return (
                <span
                  key={i}
                  className={`range-cell${w >= 0.5 ? ' range-cell-on' : ''}`}
                  style={{ '--w': w } as React.CSSProperties}
                  title={`${handClassName(i)}: ${(w * 100).toFixed(0)}%`}
                >
                  {handClassName(i)}
                </span>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
