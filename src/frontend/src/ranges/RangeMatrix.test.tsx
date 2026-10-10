import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { RangeMatrix } from './RangeMatrix'

const grid = (w: number) => Array<number>(169).fill(w)

function cellClasses(layers: { action: string; grid: number[] }[], implicitFold = true) {
  const { container } = render(<RangeMatrix layers={layers} implicitFold={implicitFold} />)
  return container.querySelectorAll('.matrix-cell')[0].className
}

describe('RangeMatrix label colour', () => {
  it('uses the dark ink on cells mostly filled by a played action', () => {
    expect(cellClasses([{ action: 'raise', grid: grid(0.8) }])).toContain('matrix-cell-on')
  })

  it('keeps the light label on cells that are explicit fold (solver layers)', () => {
    // fold paints with --action-fold, the same dark green as an empty cell
    expect(cellClasses([{ action: 'fold', grid: grid(1) }], false)).not.toContain('matrix-cell-on')
    expect(
      cellClasses(
        [
          { action: 'call', grid: grid(0.3) },
          { action: 'fold', grid: grid(0.7) },
        ],
        false,
      ),
    ).not.toContain('matrix-cell-on')
  })
})
