import { useCallback, useEffect, useRef, useState } from 'react'
import { clearCache, fetchInstall, fetchSolverStatus, startInstall } from './api'
import type { InstallStatus, SolverStatus } from './types'

export function SettingsPanel() {
  const [status, setStatus] = useState<SolverStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const seq = useRef(0)
  const [install, setInstall] = useState<InstallStatus | null>(null)
  const timer = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = useCallback(() => {
    if (timer.current !== null) clearInterval(timer.current)
    timer.current = null
  }, [])

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

  // Bumped on every new download and on unmount: stale callbacks compare against it.
  const run = useRef(0)
  useEffect(() => {
    const token = run
    return () => {
      token.current++
      stopPolling()
    }
  }, [stopPolling])

  function fail(message: string) {
    stopPolling()
    setInstall({ state: 'error', bytes: 0, total: null, error: message })
  }

  function download() {
    stopPolling()
    const mine = ++run.current
    let failures = 0
    let requested = 0
    let applied = 0
    const alive = () => mine === run.current
    const poll = () => {
      const id = ++requested
      fetchInstall()
        .then((st) => {
          if (!alive() || id < applied) return
          applied = id
          failures = 0
          setInstall(st)
          if (st.state === 'done' || st.state === 'error') {
            stopPolling()
            if (st.state === 'done') refresh()
          }
        })
        .catch((e: unknown) => {
          if (!alive()) return
          if (++failures >= 3) fail(String(e))
        })
    }
    setInstall({ state: 'downloading', bytes: 0, total: null, error: null })
    startInstall()
      .then((st) => {
        if (!alive()) return
        setInstall(st)
        timer.current = setInterval(poll, 1000)
      })
      .catch((e: unknown) => {
        if (alive()) fail(String(e))
      })
  }

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
      {!status.configured && (
        <div>
          <button
            type="button"
            disabled={install !== null && install.state !== 'error' && install.state !== 'done'}
            onClick={download}
          >
            Descargar TexasSolver (39 MB)
          </button>
          <p className="muted">Programa de otro autor (licencia AGPL); se baja de su página oficial.</p>
        </div>
      )}
      {install && install.state !== 'idle' && install.state !== 'error' && (
        <p>
          {install.state === 'done' ? (
            'Solver listo'
          ) : (
            <>
              {install.state === 'downloading'
                ? 'Descargando… '
                : install.state === 'verifying'
                  ? 'Verificando… '
                  : 'Descomprimiendo… '}
              <progress
                aria-label="Progreso de la descarga"
                value={install.state === 'downloading' && install.total ? install.bytes : undefined}
                max={install.state === 'downloading' && install.total ? install.total : undefined}
              />
            </>
          )}
        </p>
      )}
      {install?.state === 'error' && <p className="error">{install.error}</p>}
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
