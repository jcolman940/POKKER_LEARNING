import { useEffect, useState } from 'react'
import { fetchVersion, type VersionInfo } from './api/client'
import { PushFoldPage } from './pushfold/PushFoldPage'
import { ChartsPage } from './ranges/ChartsPage'
import { SimulatorPage } from './simulator/SimulatorPage'

const SECTIONS = [
  { id: 'simulator', label: 'Simulador', phase: 2 },
  { id: 'ranges', label: 'Rangos preflop', phase: 3 },
  { id: 'pushfold', label: 'Push/fold', phase: 3 },
  { id: 'history', label: 'Historiales', phase: 4 },
  { id: 'stats', label: 'Estadísticas', phase: 4 },
  { id: 'replayer', label: 'Replayer', phase: 4 },
  { id: 'trainer', label: 'Entrenador', phase: 6 },
] as const

const AVAILABLE = new Set<string>(['simulator', 'ranges', 'pushfold'])

type BackendStatus =
  | { state: 'loading' }
  | { state: 'ok'; info: VersionInfo }
  | { state: 'error' }

export default function App() {
  const [backend, setBackend] = useState<BackendStatus>({ state: 'loading' })
  const [section, setSection] = useState<string>('simulator')

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

      <nav className="tabs" aria-label="Secciones">
        {SECTIONS.map((s) => {
          const available = AVAILABLE.has(s.id)
          return (
            <button
              key={s.id}
              type="button"
              className={`tab${section === s.id ? ' tab-active' : ''}`}
              aria-current={section === s.id ? 'page' : undefined}
              disabled={!available}
              title={available ? undefined : `Próximamente (fase ${s.phase})`}
              onClick={() => setSection(s.id)}
            >
              {s.label}
              {!available && <span className="tab-phase">fase {s.phase}</span>}
            </button>
          )
        })}
      </nav>

      <main>
        {section === 'simulator' && <SimulatorPage />}
        {section === 'ranges' && <ChartsPage />}
        {section === 'pushfold' && <PushFoldPage />}
      </main>

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
