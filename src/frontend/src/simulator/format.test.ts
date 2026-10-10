import { describe, expect, it } from 'vitest'
import { barColor } from './format'

describe('barColor', () => {
  it('uses the visible bar grey for fold and the action colour (with a fallback) otherwise', () => {
    expect(barColor('fold')).toBe('var(--action-fold-bar)')
    expect(barColor('raise')).toBe('var(--action-raise, var(--text-dim))')
  })
})
