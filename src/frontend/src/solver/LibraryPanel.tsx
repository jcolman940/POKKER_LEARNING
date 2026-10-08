import { type FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import { enqueueBatch, enqueueLibrary, fetchLibrary, fetchSolverStatus } from './api'
import type { LibraryEntry, LibraryFamily } from './types'

const ENTRY_LABEL: Record<LibraryEntry['status'], string> = {
  solved: 'resuelto',
  queued: 'en cola',
  running: 'resolviendo',
  missing_chart: 'falta tabla',
  outdated: 'desactualizado',
  pending: 'sin resolver',
}

const FALLBACK_PRESETS = [
  { name: 'simple', label: 'Simple' },
  { name: 'chico', label: 'Chico' },
  { name: 'amplio', label: 'Amplio' },
]

function BatchForm({ onResult }: { onResult: (text: string) => void }) {
  const [format, setFormat] = useState('cash')
  const [players, setPlayers] = useState('6')
  const [aggressor, setAggressor] = useState('')
  const [caller, setCaller] = useState('')
  const [potType, setPotType] = useState<'srp' | '3bet'>('srp')
  const [stack, setStack] = useState('100')
  const [open, setOpen] = useState('2.5')
  const [threebet, setThreebet] = useState('')
  const [ante, setAnte] = useState('0')
  const [preset, setPreset] = useState('chico')
  const [presets, setPresets] = useState(FALLBACK_PRESETS)
  const [flops, setFlops] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    fetchSolverStatus()
      .then((s) => s.presets.length > 0 && setPresets(s.presets))
      .catch(() => undefined)
  }, [])

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    try {
      const list = flops.split(/[\s,;]+/).filter(Boolean)
      const r = await enqueueBatch({
        game_format: format,
        players: Number(players),
        ante_total_bb: Number(ante),
        preset,
        line: {
          aggressor: aggressor.trim().toUpperCase(),
          caller: caller.trim().toUpperCase(),
          pot_type: potType,
          stack_bb: Number(stack),
          open_size_bb: Number(open),
          ...(potType === '3bet' ? { threebet_size_bb: Number(threebet) } : {}),
        },
        flops: list.length > 0 ? list : null,
      })
      onResult(
        r.missing.length > 0
          ? `Encolados: ${r.enqueued}. ${r.missing.join(' · ')}`
          : `Encolados: ${r.enqueued}.`,
      )
    } catch (err: unknown) {
      onResult(String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={(e) => void submit(e)} aria-labelledby="batch-title" className="batch-form">
      <h4 id="batch-title">Lote propio</h4>
      <label>
        Formato{' '}
        <select value={format} onChange={(e) => setFormat(e.target.value)}>
          <option value="cash">Cash</option>
          <option value="mtt">MTT</option>
        </select>
      </label>{' '}
      <label>
        Jugadores{' '}
        <input
          type="number"
          min={2}
          max={10}
          value={players}
          onChange={(e) => setPlayers(e.target.value)}
        />
      </label>{' '}
      <label>
        Agresor <input value={aggressor} onChange={(e) => setAggressor(e.target.value)} />
      </label>{' '}
      <label>
        Caller <input value={caller} onChange={(e) => setCaller(e.target.value)} />
      </label>{' '}
      <label>
        Tipo de pote{' '}
        <select value={potType} onChange={(e) => setPotType(e.target.value as 'srp' | '3bet')}>
          <option value="srp">SRP</option>
          <option value="3bet">3-bet</option>
        </select>
      </label>{' '}
      <label>
        Stack (bb){' '}
        <input type="number" min={1} value={stack} onChange={(e) => setStack(e.target.value)} />
      </label>{' '}
      <label>
        Open (bb){' '}
        <input
          type="number"
          min={0}
          step="any"
          value={open}
          onChange={(e) => setOpen(e.target.value)}
        />
      </label>{' '}
      {potType === '3bet' && (
        <label>
          3-bet (bb){' '}
          <input
            type="number"
            min={0}
            step="any"
            value={threebet}
            onChange={(e) => setThreebet(e.target.value)}
          />
        </label>
      )}{' '}
      <label>
        Ante total (bb){' '}
        <input
          type="number"
          min={0}
          step="any"
          value={ante}
          onChange={(e) => setAnte(e.target.value)}
        />
      </label>{' '}
      <label>
        Preset{' '}
        <select value={preset} onChange={(e) => setPreset(e.target.value)}>
          {presets.map((p) => (
            <option key={p.name} value={p.name}>
              {p.label}
            </option>
          ))}
        </select>
      </label>
      <div>
        <label>
          Flops (opcional){' '}
          <textarea
            rows={2}
            value={flops}
            placeholder="vacío = los 25 flops representativos; ej. AhKd2c 7s7h2d"
            onChange={(e) => setFlops(e.target.value)}
          />
        </label>
      </div>
      <button type="submit" disabled={busy || !aggressor || !caller}>
        Encolar lote
      </button>
    </form>
  )
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
      <BatchForm
        onResult={(text) => {
          if (!alive.current) return
          setMessage(text)
          refresh()
        }}
      />
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
