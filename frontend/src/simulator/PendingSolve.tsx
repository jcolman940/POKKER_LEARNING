import { useEffect, useState } from 'react'
import { cancelJob, fetchJob } from '../solver/api'
import type { PendingJob } from '../solver/types'

interface Props {
  job: PendingJob
  onDone: () => void
  intervalMs?: number
}

export function PendingSolve({ job: initial, onDone, intervalMs = 1500 }: Props) {
  const [job, setJob] = useState(initial)
  const [error, setError] = useState<string | null>(null)
  const finished = ['done', 'failed', 'cancelled'].includes(job.status)

  useEffect(() => {
    if (finished) return
    const timer = setInterval(() => {
      fetchJob(job.id)
        .then((j) => {
          setJob(j)
          if (j.status === 'done') onDone()
          if (j.status === 'failed') setError(j.error ?? 'El solve falló')
        })
        .catch((e: unknown) => setError(String(e)))
    }, intervalMs)
    return () => clearInterval(timer)
  }, [job.id, finished, intervalMs, onDone])

  async function cancel() {
    setJob(await cancelJob(job.id))
  }

  return (
    <section className="panel panel-muted" aria-labelledby="pending-title" aria-live="polite">
      <h3 id="pending-title">Recomendación · resolviendo con el solver</h3>
      {job.status === 'queued' && job.position !== null && (
        <p>Posición en la cola: {job.position}</p>
      )}
      {job.status === 'running' && (
        <p>
          Iteración {job.iteration}
          {job.exploitability !== null && ` · explotabilidad ${job.exploitability.toFixed(2)}% del pote`}
        </p>
      )}
      {job.status === 'cancelled' && <p>Solve cancelado.</p>}
      {error && <p className="error">{error}</p>}
      {!finished && (
        <button type="button" onClick={() => void cancel()}>
          Cancelar solve
        </button>
      )}
    </section>
  )
}
