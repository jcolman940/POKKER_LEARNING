import { useEffect, useMemo, useState } from 'react'
import { getJson, postJson } from '../api/client'
import { RangeMatrix } from '../ranges/RangeMatrix'
import type { ChartData } from '../ranges/types'

interface RangeOut {
  position: string
  vs_position: string | null
  share: number
  grid: number[]
  ev_diff: number[]
}

interface PushFoldOut {
  positions: string[]
  unit: string
  push: RangeOut[]
  call: RangeOut[]
  icm_equity: number[] | null
  iterations: number
  exploitability: number
  converged: boolean
}

function parsePayouts(text: string): number[] | null {
  const parts = text
    .split(/[,;\s]+/)
    .map((p) => p.trim())
    .filter(Boolean)
  const values = parts.map(Number)
  return values.every((v) => Number.isFinite(v) && v >= 0) ? values : null
}

export function PushFoldPage() {
  const [players, setPlayers] = useState(9)
  const [positions, setPositions] = useState<string[]>([])
  const [stacks, setStacks] = useState<Record<string, string>>({})
  const [defaultStack, setDefaultStack] = useState('12')
  const [ante, setAnte] = useState('0')
  const [bbAnte, setBbAnte] = useState('1')
  const [payouts, setPayouts] = useState('')
  const [result, setResult] = useState<PushFoldOut | null>(null)
  const [view, setView] = useState<string>('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    getJson<string[]>(`/api/simulator/positions/${players}`, controller.signal)
      .then(setPositions)
      .catch(() => {})
    return () => controller.abort()
  }, [players])

  const stackOf = (p: string) => Number(stacks[p] ?? defaultStack)

  async function solve() {
    setError(null)
    setMessage(null)
    const prizes = parsePayouts(payouts)
    if (prizes === null) {
      setError('Premios inválidos: escribilos separados por comas (ej.: 50, 30, 20).')
      return
    }
    const stackList = positions.map(stackOf)
    if (stackList.some((s) => !(s > 0))) {
      setError('Todos los stacks deben ser mayores que 0.')
      return
    }
    setBusy(true)
    try {
      const data = await postJson<PushFoldOut>('/api/pushfold/solve', {
        stacks_bb: stackList,
        ante_bb: Number(ante) || 0,
        bb_ante_bb: Number(bbAnte) || 0,
        payouts: prizes,
      })
      setResult(data)
      setView(`push:${data.push[0].position}`)
    } catch (e) {
      setResult(null)
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const current = useMemo(() => {
    if (!result) return null
    const [kind, a, b] = view.split(':')
    if (kind === 'push') return result.push.find((r) => r.position === a) ?? null
    return result.call.find((r) => r.vs_position === a && r.position === b) ?? null
  }, [result, view])

  async function saveAsChart() {
    if (!result || !current) return
    const isPush = current.vs_position === null
    const chart: ChartData = {
      name: isPush
        ? `Push ${current.position} ${stackOf(current.position)}bb (${players}j)`
        : `Call ${current.position} vs push ${current.vs_position} (${players}j)`,
      source: 'computed',
      game_format: 'mtt',
      players,
      position: current.position,
      vs_position: current.vs_position,
      stack_bb: stackOf(current.position),
      situation: isPush ? 'rfi' : 'vs_allin',
      open_size_bb: null,
      rake: null,
      ante_bb: Number(ante) || 0,
      note:
        `Push/fold Nash${result.unit === '$' ? ' + ICM (premios: ' + payouts + ')' : ' chip EV'}. ` +
        `Stacks: ${positions.map((p) => `${p} ${stackOf(p)}`).join(', ')}.`,
      actions: { [isPush ? 'allin' : 'call']: current.grid },
    }
    try {
      await postJson('/api/charts', chart)
      setMessage(`Guardado en Preflop: "${chart.name}".`)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const unit = result?.unit ?? 'bb'

  return (
    <div className="pushfold">
      <section className="panel" aria-labelledby="pf-title">
        <h3 id="pf-title">Mesa (stacks en bb)</h3>
        <div className="field-row">
          <label>
            Jugadores
            <select value={players} onChange={(e) => setPlayers(Number(e.target.value))}>
              {Array.from({ length: 9 }, (_, i) => i + 2).map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <label>
            Stack por defecto
            <input type="number" min="1" value={defaultStack} onChange={(e) => setDefaultStack(e.target.value)} />
          </label>
          <label>
            Ante por jugador
            <input type="number" min="0" step="0.01" value={ante} onChange={(e) => setAnte(e.target.value)} />
          </label>
          <label>
            BB ante
            <input type="number" min="0" step="0.1" value={bbAnte} onChange={(e) => setBbAnte(e.target.value)} />
          </label>
        </div>
        <div className="stack-grid">
          {positions.map((p) => (
            <label key={p}>
              {p}
              <input
                type="number"
                min="0.5"
                step="0.5"
                value={stacks[p] ?? defaultStack}
                onChange={(e) => setStacks((s) => ({ ...s, [p]: e.target.value }))}
              />
            </label>
          ))}
        </div>
        <label>
          Premios que quedan (vacío = chip EV)
          <input
            type="text"
            value={payouts}
            onChange={(e) => setPayouts(e.target.value)}
            placeholder="Ej.: 50, 30, 20"
          />
        </label>
        <p className="muted small">
          Modelo: cada jugador hace push o fold si le llega foldeado; detrás se paga o se foldea, con
          un solo caller (sin overcalls).
        </p>
        <button type="button" className="primary" onClick={() => void solve()} disabled={busy}>
          {busy ? 'Calculando…' : 'Calcular Nash'}
        </button>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </section>

      {result && current && (
        <section className="panel" aria-labelledby="pf-result-title">
          <h3 id="pf-result-title">Resultado</h3>
          <p className="small">
            {result.unit === '$' ? 'ICM (Malmuth-Harville)' : 'Chip EV'} · {result.iterations}{' '}
            iteraciones · explotabilidad {result.exploitability.toFixed(4)}
            {unit}
            {!result.converged && <strong> · no convergió del todo: aproximado</strong>}
          </p>
          {result.icm_equity && (
            <p className="small">
              Equity ICM inicial:{' '}
              {result.positions.map((p, i) => `${p} ${result.icm_equity![i].toFixed(2)}`).join(' · ')}
            </p>
          )}
          <label>
            Ver
            <select value={view} onChange={(e) => setView(e.target.value)}>
              <optgroup label="Push (foldean hasta el jugador)">
                {result.push.map((r) => (
                  <option key={r.position} value={`push:${r.position}`}>
                    Push {r.position} · {(r.share * 100).toFixed(1)}%
                  </option>
                ))}
              </optgroup>
              <optgroup label="Call vs push">
                {result.call.map((r) => (
                  <option key={`${r.vs_position}-${r.position}`} value={`call:${r.vs_position}:${r.position}`}>
                    {r.position} paga push de {r.vs_position} · {(r.share * 100).toFixed(1)}%
                  </option>
                ))}
              </optgroup>
            </select>
          </label>
          <RangeMatrix
            layers={[{ action: current.vs_position ? 'call' : 'allin', grid: current.grid }]}
            detail={(i) => `ΔEV ${current.ev_diff[i] >= 0 ? '+' : ''}${current.ev_diff[i].toFixed(3)}${unit}`}
            caption="Rango Nash"
          />
          <div className="field-row">
            <button type="button" onClick={() => void saveAsChart()}>
              Guardar como rango (calculado)
            </button>
          </div>
          {message && <p className="small">{message}</p>}
        </section>
      )}
    </div>
  )
}
