import { fireEvent, render } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
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

describe('RangeMatrix hover', () => {
  it('reports the hovered cell and null when leaving the matrix', () => {
    const onHover = vi.fn()
    const { container } = render(<RangeMatrix layers={[{ action: 'raise', grid: grid(1) }]} onHover={onHover} />)
    fireEvent.pointerEnter(container.querySelector('[title^="AKs:"]')!)
    expect(onHover).toHaveBeenLastCalledWith(1)
    fireEvent.pointerLeave(container.querySelector('.matrix')!)
    expect(onHover).toHaveBeenLastCalledWith(null)
  })

  it('also reports while painting cells in the editor', () => {
    const onHover = vi.fn()
    const { container } = render(
      <RangeMatrix layers={[{ action: 'raise', grid: grid(0) }]} onPaint={() => {}} onHover={onHover} />,
    )
    fireEvent.pointerEnter(container.querySelector('button[title^="KK:"]')!)
    expect(onHover).toHaveBeenLastCalledWith(14)
  })
})
