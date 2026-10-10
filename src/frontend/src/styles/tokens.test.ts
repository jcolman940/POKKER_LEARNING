import { describe, expect, it } from 'vitest'
import { contrastRatio, parseHexTokens } from './contrast'
import tokensCss from './tokens.css?raw'

const t = parseHexTokens(tokensCss)

describe('contrastRatio', () => {
  it('matches the WCAG reference values', () => {
    expect(contrastRatio('#000000', '#ffffff')).toBeCloseTo(21, 1)
    expect(contrastRatio('#ffffff', '#ffffff')).toBeCloseTo(1, 5)
    expect(contrastRatio('#777777', '#ffffff')).toBeCloseTo(4.48, 2)
  })
})

describe('parseHexTokens', () => {
  it('reads only hex custom properties', () => {
    expect(parseHexTokens(':root { --a: #0d1a14; --b: var(--a); --c:#FFF; }')).toEqual({
      '--a': '#0d1a14',
      '--c': '#ffffff',
    })
  })
})

describe('Paño y oro tokens', () => {
  // [foreground, background]: every pair renders normal-size text.
  const pairs: [string, string][] = [
    ['--text', '--bg'],
    ['--text', '--bg-deep'],
    ['--text', '--surface'],
    ['--text', '--surface-2'],
    ['--text-muted', '--bg'],
    ['--text-muted', '--bg-deep'],
    ['--text-muted', '--surface'],
    ['--text-muted', '--surface-2'],
    ['--text-muted', '--grid-empty'],
    ['--gold', '--bg'],
    ['--gold', '--bg-deep'],
    ['--gold', '--surface'],
    ['--gold', '--surface-2'],
    ['--gold-ink', '--gold'],
    ['--on-danger', '--danger'],
    ['--danger-text', '--bg'],
    ['--danger-text', '--surface'],
    ['--danger-text', '--surface-2'],
    ['--info', '--surface'],
    ['--warn', '--surface'],
    ['--positive', '--surface'],
    ['--negative', '--surface'],
    ['--suit-s', '--card-bg'],
    ['--suit-h', '--card-bg'],
    ['--suit-d', '--card-bg'],
    ['--suit-c', '--card-bg'],
    ...['raise', 'limp', 'call', '3bet', '4bet', '5bet', 'allin'].map(
      (a): [string, string] => ['--matrix-ink', `--action-${a}`],
    ),
  ]

  it.each(pairs)('%s on %s reaches 4.5:1', (fg, bg) => {
    expect(t[fg], fg).toBeDefined()
    expect(t[bg], bg).toBeDefined()
    expect(contrastRatio(t[fg], t[bg])).toBeGreaterThanOrEqual(4.5)
  })

  it('is dark-only (no light/dark media switch)', () => {
    expect(tokensCss).not.toContain('prefers-color-scheme')
  })
})
