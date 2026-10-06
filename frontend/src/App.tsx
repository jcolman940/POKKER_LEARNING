import { useEffect, useState } from 'react'
import { fetchVersion, type VersionInfo } from './api/client'

const SECTIONS = [
  { id: 'simulator', label: 'Simulador', phase: 2 },
  { id: 'ranges', label: 'Rangos preflop', phase: 3 },
  { id: 'history', label: 'Historiales', phase: 4 },
  { id: 'stats', label: 'Estadísticas', phase: 4 },
  { id: 'replayer', label: 'Replayer', phase: 4 },
  { id: 'trainer', label: 'Entrenador', phase: 6 },
] as const

type BackendStatus =
  | { state: 'loading' }
  | { state: 'ok'; info: VersionInfo }
  | { state: 'error' }

export default function App() {
  const [backend, setBackend] = useState<BackendStatus>({ state: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    fetchVersion(controller.signal)
      .then((info) => setBackend({ state: 'ok', info }))
      .catch((err: unknown) => {
        if (!controller.signal.aborted) {
          console.error(err)
          setBackend({ state: 'error' })
        }
      })
    return () => controller.abort()
  }, [])

  return (
    <div className="app">
      <header className="app-header">
        <h1>Poker Study</h1>
        <p className="subtitle">Herramienta de estudio post-sesión. Sin asistencia en tiempo real.</p>
      </header>

      <nav className="sections" aria-label="Secciones">
        {SECTIONS.map((s) => (
          <div key={s.id} className="section-card" aria-disabled="true">
            <span className="section-label">{s.label}</span>
            <span className="section-phase">Próximamente (fase {s.phase})</span>
          </div>
        ))}
      </nav>

      <footer className="app-footer">
        <span>Versión {__APP_VERSION__}</span>
        <span aria-live="polite">
          {backend.state === 'loading' && 'Conectando con el backend…'}
          {backend.state === 'ok' &&
            `Backend ${backend.info.app} · núcleo ${backend.info.core}`}
          {backend.state === 'error' && 'Backend no disponible'}
        </span>
      </footer>
    </div>
  )
}
