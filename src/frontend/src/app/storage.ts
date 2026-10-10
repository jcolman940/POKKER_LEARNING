/**
 * Per-viewer conveniences (collapsed menu, last filters, last table) in localStorage.
 * Storage can be missing or throw (private mode, blocked site data): every access
 * falls back silently so the app always renders.
 */

export function readStored<T>(key: string, fallback: T, isValid: (v: unknown) => v is T): T {
  try {
    const raw = window.localStorage.getItem(key)
    if (raw === null) return fallback
    const value: unknown = JSON.parse(raw)
    return isValid(value) ? value : fallback
  } catch {
    return fallback
  }
}

export function writeStored(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Not persisted this time; the in-memory state still works.
  }
}

export function isBoolean(v: unknown): v is boolean {
  return typeof v === 'boolean'
}
