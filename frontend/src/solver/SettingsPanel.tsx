import { useCallback, useEffect, useRef, useState } from 'react'
import { clearCache, fetchSolverStatus } from './api'
import type { SolverStatus } from './types'

export function SettingsPanel() {
  const [status, setStatus] = useState<SolverStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const seq = useRef(0)

  const refresh = useCallback(() => {
    const mine = ++seq.current
    fetchSolverStatus()
      .then((s) => {
        if (mine !== seq.current) return
        setStatus(s)
        setError(null)
      })
      .catch((e: unknown) => {
        if (mine === seq.current) setError(String(e))
      })
  }, [])

  useEffect(() => {
    const counter = seq
    refresh()
    return () => {
      counter.current++
    }
  }, [refresh])

  function clear() {
    clearCache()
      .then(refresh)
      .catch((e: unknown) => setError(String(e)))
  }

  if (!status) {
    return error ? <p className="error">{error}</p> : <p className="muted">Cargando…</p>
  }
  return (
    <section className="panel" aria-labelledby="settings-title">
      <h3 id="settings-title">Configuración del solver</h3>
      {error && <p className="error">{error}</p>}
      <p>
        {status.configured
          ? `Solver: ${status.path}`
          : 'Solver no configurado: definí POKER_SOLVER_PATH con la ruta de console_solver.exe.'}
      </p>
      <p>Versión del solver: {status.version}</p>
      <p>Hilos: {status.threads}</p>
      <p>
        Caché: {status.cache_entries} resultados · {(status.cache_bytes / 1024 / 1024).toFixed(1)} MB{' '}
        <button
          type="button"
          onClick={() => {
            if (window.confirm('¿Vaciar toda la caché del solver?')) clear()
          }}
        >
          Vaciar caché
        </button>
      </p>
    </section>
  )
}
