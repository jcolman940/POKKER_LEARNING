/** Failed pings in a row after which the packaged server is considered gone. */
const DOWN_AFTER = 2

/**
 * Tells the packaged launcher the UI is still open. Pings every intervalMs and right away when
 * the tab becomes visible again (timers are throttled while hidden or after a suspend).
 * onDownChange(true) fires after DOWN_AFTER failed pings in a row, onDownChange(false) when a
 * ping succeeds again; it is only called on changes.
 */
export function startHeartbeat(
  intervalMs = 10000,
  onDownChange?: (down: boolean) => void,
): () => void {
  let failures = 0
  let down = false
  let stopped = false
  const report = (ok: boolean) => {
    if (stopped) return
    failures = ok ? 0 : failures + 1
    const nowDown = failures >= DOWN_AFTER
    if (nowDown !== down) {
      down = nowDown
      onDownChange?.(down)
    }
  }
  const beat = () => {
    fetch('/api/app/ping', { method: 'POST' }).then(
      (resp) => report(resp.ok),
      () => report(false),
    )
  }
  const onVisibility = () => {
    if (document.visibilityState === 'visible') beat()
  }
  beat()
  const id = setInterval(beat, intervalMs)
  document.addEventListener('visibilitychange', onVisibility)
  return () => {
    stopped = true
    clearInterval(id)
    document.removeEventListener('visibilitychange', onVisibility)
  }
}
