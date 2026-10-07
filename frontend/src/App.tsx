import { useEffect, useState } from 'react'
import { fetchVersion, type VersionInfo } from './api/client'
import { HistoryPage } from './history/HistoryPage'
import { ReplayerView } from './history/ReplayerView'
import { PushFoldPage } from './pushfold/PushFoldPage'
import { ChartsPage } from './ranges/ChartsPage'
import { type InitialScenario, SimulatorPage } from './simulator/SimulatorPage'
import { SolverPage } from './solver/SolverPage'
import { StatsPage } from './stats/StatsPage'
import { TrainerPage } from './trainer/TrainerPage'

const SECTIONS = [
  { id: 'simulator', label: 'Simulador', phase: 2 },
  { id: 'ranges', label: 'Rangos preflop', phase: 3 },
  { id: 'pushfold', label: 'Push/fold', phase: 3 },
  { id: 'history', label: 'Historiales', phase: 4 },
  { id: 'stats', label: 'Estadísticas', phase: 4 },
  { id: 'replayer', label: 'Replayer', phase: 4 },
  { id: 'solver', label: 'Solver', phase: 5 },
  { id: 'trainer', label: 'Entrenador', phase: 6 },
] as const

const AVAILABLE = new Set<string>(['simulator', 'ranges', 'pushfold', 'history', 'stats', 'replayer', 'solver', 'trainer'])

type BackendStatus =
  | { state: 'loading' }
  | { state: 'ok'; info: VersionInfo }
  | { state: 'error' }

export default function App() {
  const [backend, setBackend] = useState<BackendStatus>({ state: 'loading' })
  const [section, setSection] = useState<string>('simulator')
  const [handId, setHandId] = useState<number | null>(null)
  const [spot, setSpot] = useState<{ key: number; scenario: InitialScenario } | null>(null)

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
        {section === 'simulator' && <SimulatorPage key={spot?.key ?? 0} initial={spot?.scenario} />}
        {section === 'history' && (
          <HistoryPage
            onOpen={(id) => {
              setHandId(id)
              setSection('replayer')
            }}
          />
        )}
        {section === 'replayer' &&
          (handId === null ? (
            <p className="muted">Elegí una mano en Historiales para reproducirla.</p>
          ) : (
            <ReplayerView
              handId={handId}
              onBack={() => setSection('history')}
              onAnalyze={(scenario) => {
                setSpot({ key: Date.now(), scenario })
                setSection('simulator')
              }}
            />
          ))}
        {section === 'stats' && <StatsPage />}
        {section === 'ranges' && <ChartsPage />}
        {section === 'pushfold' && <PushFoldPage />}
        {section === 'solver' && <SolverPage />}
        {section === 'trainer' && <TrainerPage />}
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
