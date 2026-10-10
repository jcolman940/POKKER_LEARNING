import { useEffect, useState } from 'react'
import { fetchVersion, type VersionInfo } from './api/client'
import { startHeartbeat } from './app/heartbeat'
import { HistoryPage } from './history/HistoryPage'
import { ReplayerView } from './history/ReplayerView'
import { PushFoldPage } from './pushfold/PushFoldPage'
import { PreflopPage } from './ranges/PreflopPage'
import { type InitialScenario, SimulatorPage } from './simulator/SimulatorPage'
import { SolverPage } from './solver/SolverPage'
import { StatsPage } from './stats/StatsPage'
import type { InitialFilters } from './trainer/types'
import { TrainerPage } from './trainer/TrainerPage'
import { Sidebar } from './app/Sidebar'
import { SIDEBAR_KEY, type SectionId } from './app/sections'
import { isBoolean, readStored, writeStored } from './app/storage'
import './app/shell.css'

type BackendStatus =
  | { state: 'loading' }
  | { state: 'ok'; info: VersionInfo }
  | { state: 'error' }

export default function App() {
  const [backend, setBackend] = useState<BackendStatus>({ state: 'loading' })
  const [section, setSection] = useState<SectionId>('simulator')
  const [collapsed, setCollapsed] = useState(() => readStored(SIDEBAR_KEY, false, isBoolean))

  function toggleSidebar() {
    setCollapsed((c) => {
      writeStored(SIDEBAR_KEY, !c)
      return !c
    })
  }
  const [handId, setHandId] = useState<number | null>(null)
  const [spot, setSpot] = useState<{ key: number; scenario: InitialScenario } | null>(null)

  const [trainer, setTrainer] = useState<{ key: number; filters?: InitialFilters }>({ key: 0 })

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

  const packaged = backend.state === 'ok' && backend.info.packaged === true
  const [serverDown, setServerDown] = useState(false)
  useEffect(() => (packaged ? startHeartbeat(10000, setServerDown) : undefined), [packaged])

  const status =
    backend.state === 'loading'
      ? 'Conectando con el backend…'
      : backend.state === 'ok'
        ? `Backend ${backend.info.app} · núcleo ${backend.info.core}`
        : 'Backend no disponible'

  return (
    <div className="app-shell">
      {serverDown && (
        <div className="server-down-banner" role="alert">
          POKKER se cerró. Abrilo de nuevo desde el ícono o con doble clic en POKKER.exe.
        </div>
      )}
      <Sidebar
        current={section}
        onSelect={(id) => {
          // A spot from the replayer or Preflop applies once; the menu reopens the saved table.
          if (id === 'simulator') setSpot(null)
          setSection(id)
        }}
        collapsed={collapsed}
        onToggle={toggleSidebar}
        status={
          <>
            <span className="sidebar-status-line">{status}</span>
            <span className="sidebar-status-line">Versión {__APP_VERSION__}</span>
          </>
        }
      />
      <main className="app-main">
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
            <p className="muted">Elegí una mano en Manos para reproducirla.</p>
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
        {section === 'stats' && (
          <StatsPage
            onTrain={(filters) => {
              setTrainer({ key: Date.now(), filters: { ...filters, preferDue: true } })
              setSection('trainer')
            }}
          />
        )}
        {section === 'ranges' && (
          <PreflopPage
            onOpenSimulator={(scenario) => {
              setSpot({ key: Date.now(), scenario })
              setSection('simulator')
            }}
            onTrain={(filters) => {
              setTrainer({ key: Date.now(), filters })
              setSection('trainer')
            }}
          />
        )}
        {section === 'pushfold' && <PushFoldPage />}
        {section === 'solver' && <SolverPage />}
        {section === 'trainer' && <TrainerPage key={trainer.key} initialFilters={trainer.filters} />}
      </main>
    </div>
  )
}
