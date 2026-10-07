import { useEffect, useState } from 'react'
import { clearCache, fetchSolverStatus } from './api'
import type { SolverStatus } from './types'

export function SettingsPanel() {
  const [status, setStatus] = useState<SolverStatus | null>(null)
  const refresh = () => {
    fetchSolverStatus()
      .then(setStatus)
      .catch(() => setStatus(null))
  }
  useEffect(refresh, [])
  if (!status) return <p className="muted">Cargando…</p>
  return (
    <section className="panel" aria-labelledby="settings-title">
      <h3 id="settings-title">Configuración del solver</h3>
      <p>
        {status.configured
          ? `Solver: ${status.path}`
          : 'Solver no configurado: definí POKER_SOLVER_PATH con la ruta de console_solver.exe.'}
      </p>
      <p>Hilos: {status.threads}</p>
      <p>
        Caché: {status.cache_entries} resultados · {(status.cache_bytes / 1024 / 1024).toFixed(1)} MB{' '}
        <button
          type="button"
          onClick={() => {
            if (window.confirm('¿Vaciar toda la caché del solver?')) void clearCache().then(refresh)
          }}
        >
          Vaciar caché
        </button>
      </p>
    </section>
  )
}
