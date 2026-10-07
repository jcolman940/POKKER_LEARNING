import { useEffect, useState } from 'react'
import { RangeMatrix } from '../ranges/RangeMatrix'
import { fetchNode } from './api'
import type { SolverNode } from './types'

export function StrategyViewer({ hash, title }: { hash: string; title: string }) {
  const [path, setPath] = useState<{ index: number; label: string }[]>([])
  const [loaded, setLoaded] = useState<{ key: string; node: SolverNode } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const key = path.map((p) => p.index).join('.')
  const node = loaded?.node ?? null
  const loading = loaded?.key !== key

  useEffect(() => {
    let stale = false
    fetchNode(hash, key)
      .then((n) => {
        if (stale) return
        setLoaded({ key, node: n })
        setError(null)
      })
      .catch((e: unknown) => {
        if (stale) return
        setError(String(e))
      })
    return () => {
      stale = true
    }
  }, [hash, key])

  return (
    <section className="panel" aria-labelledby="viewer-title">
      <h3 id="viewer-title">{title}</h3>
      <nav aria-label="Camino en el árbol" className="small">
        <button type="button" onClick={() => setPath([])}>
          Raíz
        </button>
        {path.map((p, i) => (
          <button key={i} type="button" onClick={() => setPath(path.slice(0, i + 1))}>
            {' › '}
            {p.label}
          </button>
        ))}
      </nav>
      {error && <p className="error">{error}</p>}
      {node && (
        <>
          <p>{node.player === 'oop' ? 'OOP actúa' : 'IP actúa'}</p>
          <ul className="rec-actions">
            {node.actions.map((a) => (
              <li key={a.index}>
                <span className="rec-action-name">{a.label}</span>
                <span className="rec-freq">{Math.round(a.frequency * 100)}%</span>
                {a.has_child && (
                  <button
                    type="button"
                    disabled={loading}
                    onClick={() => setPath([...path, { index: a.index, label: a.label }])}
                  >
                    Ver respuesta
                  </button>
                )}
              </li>
            ))}
          </ul>
          <RangeMatrix
            layers={node.layers.map((l) => ({ action: l.action, grid: l.grid }))}
            caption="Estrategia del rango en este nodo"
          />
          <p className="small muted">
            Mezcla sobre el rango inicial del jugador (sin ponderar por la línea jugada).
          </p>
        </>
      )}
    </section>
  )
}
