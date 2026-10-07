/** Tells the packaged launcher the UI is still open; errors are ignored on purpose. */
export function startHeartbeat(intervalMs = 10000): () => void {
  const beat = () => {
    fetch('/api/app/ping', { method: 'POST' }).catch(() => {})
  }
  beat()
  const id = setInterval(beat, intervalMs)
  return () => clearInterval(id)
}
