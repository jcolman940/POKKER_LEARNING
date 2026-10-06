import { useEffect, useRef } from 'react'
import { handClassName } from '../simulator/cards'
import { ACTION_LABEL } from './labels'

export interface Layer {
  action: string
  grid: number[]
}

interface Props {
  layers: Layer[]
  onPaint?: (index: number) => void
  /** Extra text for each cell's tooltip (e.g. EV). */
  detail?: (index: number) => string | null
  caption?: string
}

const CELLS = Array.from({ length: 169 }, (_, i) => i)

function background(layers: Layer[], i: number): string {
  let start = 0
  const stops: string[] = []
  for (const { action, grid } of layers) {
    const w = grid[i] ?? 0
    if (w <= 0) continue
    const end = Math.min(1, start + w)
    const color = `var(--action-${action})`
    stops.push(`${color} ${start * 100}% ${end * 100}%`)
    start = end
  }
  if (start < 1) stops.push(`var(--grid-empty) ${start * 100}% 100%`)
  return `linear-gradient(to right, ${stops.join(', ')})`
}

function describe(layers: Layer[], i: number): string {
  const parts = layers
    .filter(({ grid }) => (grid[i] ?? 0) > 0)
    .map(({ action, grid }) => `${ACTION_LABEL[action] ?? action} ${Math.round(grid[i] * 100)}%`)
  const total = layers.reduce((s, { grid }) => s + (grid[i] ?? 0), 0)
  if (total < 0.999) parts.push(`Fold ${Math.round((1 - total) * 100)}%`)
  return `${handClassName(i)}: ${parts.join(', ')}`
}

export function RangeMatrix({ layers, onPaint, detail, caption }: Props) {
  const painting = useRef(false)

  useEffect(() => {
    const stop = () => {
      painting.current = false
    }
    window.addEventListener('pointerup', stop)
    return () => window.removeEventListener('pointerup', stop)
  }, [])

  return (
    <div className="matrix" role="group" aria-label={caption ?? 'Matriz de rango 13×13'}>
      {CELLS.map((i) => {
        const extra = detail?.(i)
        const label = describe(layers, i) + (extra ? ` · ${extra}` : '')
        const style = { background: background(layers, i) }
        const filled = layers.reduce((sum, { grid }) => sum + (grid[i] ?? 0), 0) >= 0.5
        const className = filled ? 'matrix-cell matrix-cell-on' : 'matrix-cell'
        if (!onPaint) {
          return (
            <span key={i} className={className} style={style} title={label}>
              {handClassName(i)}
            </span>
          )
        }
        return (
          <button
            key={i}
            type="button"
            className={className}
            style={style}
            title={label}
            aria-label={label}
            onPointerDown={(e) => {
              e.preventDefault()
              painting.current = true
              onPaint(i)
            }}
            onPointerEnter={() => {
              if (painting.current) onPaint(i)
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                onPaint(i)
              }
            }}
          >
            {handClassName(i)}
          </button>
        )
      })}
    </div>
  )
}
