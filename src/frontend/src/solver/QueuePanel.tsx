import { useCallback, useEffect, useRef, useState } from 'react'
import {
  cancelJob,
  fetchJobs,
  fetchSolverStatus,
  pauseQueue,
  resumeQueue,
  retryJob,
} from './api'
import type { SolverJob } from './types'

const STATUS_LABEL: Record<SolverJob['status'], string> = {
  queued: 'En cola',
  running: 'Resolviendo',
  done: 'Resuelto',
  failed: 'Falló',
  cancelled: 'Cancelado',
}
const ORIGIN_LABEL = { simulator: 'Simulador', batch: 'Lote', library: 'Biblioteca' }

export function QueuePanel() {
  const [jobs, setJobs] = useState<SolverJob[]>([])
  const [paused, setPaused] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Request counter: only the latest request may update state, and none after unmount.
  const seq = useRef(0)

  const refresh = useCallback(() => {
    const mine = ++seq.current
    Promise.all([fetchJobs(), fetchSolverStatus()])
      .then(([j, s]) => {
        if (mine !== seq.current) return
        setJobs(j)
        setPaused(s.paused)
        setError(null)
      })
      .catch((e: unknown) => {
        if (mine === seq.current) setError(String(e))
      })
  }, [])

  useEffect(() => {
    const counter = seq
    refresh()
    const timer = setInterval(refresh, 2000)
    return () => {
      clearInterval(timer)
      counter.current++
    }
  }, [refresh])

  function run(action: () => Promise<unknown>) {
    action()
      .then(refresh)
      .catch((e: unknown) => setError(String(e)))
  }

  async function toggle() {
    try {
      const r = paused ? await resumeQueue() : await pauseQueue()
      setPaused(r.paused)
    } catch (e: unknown) {
      setError(String(e))
    }
  }

  return (
    <section className="panel" aria-labelledby="queue-title">
      <div className="panel-header">
        <h3 id="queue-title">Cola de solves</h3>
        <button type="button" onClick={() => void toggle()}>
          {paused ? 'Reanudar cola' : 'Pausar cola'}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {jobs.length === 0 && <p className="muted">No hay trabajos.</p>}
      <ul className="job-list">
        {jobs.map((j) => (
          <li key={j.id}>
            <span>{j.label}</span>
            <span className="badge">{ORIGIN_LABEL[j.origin]}</span>
            <span className="badge">{STATUS_LABEL[j.status]}</span>
            {j.status === 'queued' && j.position !== null && <span>#{j.position}</span>}
            {j.status === 'running' && (
              <span>
                Iteración {j.iteration}
                {j.exploitability !== null && ` · ${j.exploitability.toFixed(2)}%`}
              </span>
            )}
            {j.error && <span className="error small">{j.error}</span>}
            {(j.status === 'queued' || j.status === 'running') && (
              <button type="button" onClick={() => run(() => cancelJob(j.id))}>
                Cancelar
              </button>
            )}
            {(j.status === 'failed' || j.status === 'cancelled') && (
              <button type="button" onClick={() => run(() => retryJob(j.id))}>
                Reintentar
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
