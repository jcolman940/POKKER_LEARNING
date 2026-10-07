import { useCallback, useEffect, useRef, useState } from 'react'
import { enqueueLibrary, fetchLibrary } from './api'
import type { LibraryEntry, LibraryFamily } from './types'

const ENTRY_LABEL: Record<LibraryEntry['status'], string> = {
  solved: 'resuelto',
  queued: 'en cola',
  running: 'resolviendo',
  missing_chart: 'falta tabla',
  outdated: 'desactualizado',
  pending: 'sin resolver',
}

export function LibraryPanel({ onOpen }: { onOpen: (hash: string, title: string) => void }) {
  const [families, setFamilies] = useState<LibraryFamily[]>([])
  const [message, setMessage] = useState<string | null>(null)
  const seq = useRef(0)
  const alive = useRef(true)
  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
    }
  }, [])
  const refresh = useCallback(() => {
    const mine = ++seq.current
    fetchLibrary()
      .then((f) => {
        if (mine === seq.current) setFamilies(f)
      })
      .catch((e: unknown) => {
        if (mine === seq.current) setMessage(String(e))
      })
  }, [])
  useEffect(() => {
    const counter = seq
    refresh()
    return () => {
      counter.current++
    }
  }, [refresh])

  async function enqueue(family: string, line: string | null) {
    try {
      const r = await enqueueLibrary(family, line)
      if (!alive.current) return
      setMessage(
        r.missing.length > 0
          ? `Encolados: ${r.enqueued}. ${r.missing.join(' · ')}`
          : `Encolados: ${r.enqueued}.`,
      )
      refresh()
    } catch (e: unknown) {
      if (alive.current) setMessage(String(e))
    }
  }

  return (
    <section className="panel" aria-labelledby="library-title">
      <h3 id="library-title">Biblioteca de spots</h3>
      {message && <p className="small">{message}</p>}
      {families.map((f) => (
        <details key={f.id} open>
          <summary>
            {f.label} · preset {f.preset}{' '}
            <button type="button" onClick={() => void enqueue(f.id, null)}>
              Encolar familia
            </button>
          </summary>
          {f.lines.map((line) => (
            <div key={line.id} className="library-line">
              <h4>
                {line.label}
                {line.approximate && <span className="badge badge-warn">Aproximado</span>}{' '}
                <button type="button" onClick={() => void enqueue(f.id, line.id)}>
                  Encolar línea
                </button>
              </h4>
              {line.missing.map((m) => (
                <p key={m} className="small muted">
                  {m}
                </p>
              ))}
              <ul className="flop-list">
                {line.entries.map((e) => (
                  <li key={e.flop}>
                    {e.status === 'solved' && e.spot_hash ? (
                      <button
                        type="button"
                        onClick={() => onOpen(e.spot_hash as string, `${line.label} · ${e.flop}`)}
                      >
                        {e.flop}
                      </button>
                    ) : (
                      <span>{e.flop}</span>
                    )}{' '}
                    <span className="small muted">{ENTRY_LABEL[e.status]}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </details>
      ))}
    </section>
  )
}
