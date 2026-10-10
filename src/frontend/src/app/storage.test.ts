import { afterEach, describe, expect, it, vi } from 'vitest'
import { isBoolean, readStored, writeStored } from './storage'

afterEach(() => {
  vi.restoreAllMocks()
  window.localStorage.clear()
})

describe('readStored / writeStored', () => {
  it('round-trips a valid value', () => {
    writeStored('k', true)
    expect(readStored('k', false, isBoolean)).toBe(true)
  })

  it('returns the fallback when the key is missing', () => {
    expect(readStored('missing', false, isBoolean)).toBe(false)
  })

  it('returns the fallback for corrupt JSON or a value of the wrong type', () => {
    window.localStorage.setItem('k', '{not json')
    expect(readStored('k', false, isBoolean)).toBe(false)
    window.localStorage.setItem('k', '"yes"')
    expect(readStored('k', false, isBoolean)).toBe(false)
    window.localStorage.setItem('k', '{}')
    expect(readStored('k', false, isBoolean)).toBe(false)
  })

  it('returns the fallback when localStorage throws on read', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(readStored('k', false, isBoolean)).toBe(false)
  })

  it('ignores errors when localStorage throws on write', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('quota')
    })
    expect(() => writeStored('k', true)).not.toThrow()
  })
})
