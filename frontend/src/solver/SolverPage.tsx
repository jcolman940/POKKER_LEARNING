import { useState } from 'react'
import { LibraryPanel } from './LibraryPanel'
import { QueuePanel } from './QueuePanel'
import { SettingsPanel } from './SettingsPanel'
import { StrategyViewer } from './StrategyViewer'

const TABS = [
  { id: 'queue', label: 'Cola' },
  { id: 'library', label: 'Biblioteca' },
  { id: 'settings', label: 'Configuración' },
] as const

export function SolverPage() {
  const [tab, setTab] = useState<(typeof TABS)[number]['id']>('queue')
  const [libraryVersion, setLibraryVersion] = useState(0)
  const [viewing, setViewing] = useState<{ hash: string; title: string } | null>(null)
  return (
    <div className="solver-page">
      <div role="tablist" aria-label="Solver" className="tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            type="button"
            aria-selected={tab === t.id}
            className={`tab${tab === t.id ? ' tab-active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === 'queue' && <QueuePanel />}
      {tab === 'library' && (
        <LibraryPanel
          key={libraryVersion}
          onOpen={(hash, title) => setViewing({ hash, title })}
        />
      )}
      {tab === 'settings' && <SettingsPanel />}
      {viewing && (
        <StrategyViewer
          key={viewing.hash}
          hash={viewing.hash}
          title={viewing.title}
          onDeleted={() => {
            setViewing(null)
            setLibraryVersion((v) => v + 1)
          }}
        />
      )}
    </div>
  )
}
