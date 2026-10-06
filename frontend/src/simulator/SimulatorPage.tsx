import { useEffect, useMemo, useState } from 'react'
import { getJson, postJson } from '../api/client'
import { CardPicker } from './CardPicker'
import { CardView } from './CardView'
import { RangeEditor } from './RangeEditor'
import { ResultsPanel } from './ResultsPanel'
import { SITUATIONS } from '../ranges/labels'
import { joinSlots, type Slot, toSlots } from './cards'
import type { Analysis, DealRequest, DealResult, GameFormat, ScenarioInput, Street } from './types'

interface VillainState {
  position: string | null
  range: string
  hand: Slot[]
  dealHand: boolean
}

type SlotGroup = 'hero' | 'board' | number // number = villain index
interface ActiveSlot {
  group: SlotGroup
  index: number
}

const MAX_PLAYERS = 10
const BOARD_LABELS = ['Flop 1', 'Flop 2', 'Flop 3', 'Turn', 'River']

function newVillain(position: string | null = null): VillainState {
  return { position, range: 'random', hand: [null, null], dealHand: false }
}

function parseAmount(value: string): number {
  const n = Number(value)
  return Number.isFinite(n) && n >= 0 ? n : 0
}

const STREET_BY_BOARD: Street[] = ['preflop', 'preflop', 'preflop', 'flop', 'turn', 'river']

/** A scenario to start from (e.g. a spot sent by the hand replayer). */
export type InitialScenario = Partial<ScenarioInput>

export function SimulatorPage({ initial }: { initial?: InitialScenario } = {}) {
  const [format, setFormat] = useState<GameFormat>(initial?.format ?? 'cash')
  const [numPlayers, setNumPlayers] = useState(initial?.num_players ?? 6)
  const [positions, setPositions] = useState<string[]>([])
  const [heroPosition, setHeroPosition] = useState<string | null>(
    initial ? (initial.hero_position ?? null) : 'BTN',
  )
  const [villains, setVillains] = useState<VillainState[]>(() =>
    initial?.villains?.length
      ? initial.villains.map((v) => ({
          position: v.position,
          range: v.range,
          hand: toSlots(v.hand, 2),
          dealHand: false,
        }))
      : [newVillain('BB')],
  )
  const [heroSlots, setHeroSlots] = useState<Slot[]>(() => toSlots(initial?.hero_hand, 2))
  const [boardSlots, setBoardSlots] = useState<Slot[]>(() => toSlots(initial?.board, 5))
  const [street, setStreet] = useState<Street>(
    initial ? STREET_BY_BOARD[(initial.board ?? '').length / 2] ?? 'flop' : 'flop',
  )
  const [pot, setPot] = useState(String(initial?.pot_bb ?? 6.5))
  const [toCall, setToCall] = useState(String(initial?.to_call_bb ?? 0))
  const [stack, setStack] = useState(String(initial?.effective_stack_bb ?? 100))
  const [previousAction, setPreviousAction] = useState(initial?.previous_action ?? '')
  const [situation, setSituation] = useState<string>(initial?.situation ?? '')
  const [ante, setAnte] = useState(String(initial?.ante_bb ?? 0))
  const [bbAnte, setBbAnte] = useState(String(initial?.bb_ante_bb ?? 0))
  const [stacksByPos, setStacksByPos] = useState<Record<string, string>>(() =>
    Object.fromEntries(Object.entries(initial?.stacks_bb ?? {}).map(([k, v]) => [k, String(v)])),
  )
  const [payouts, setPayouts] = useState((initial?.payouts ?? []).join(', '))
  const [active, setActive] = useState<ActiveSlot | null>(null)
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    getJson<string[]>(`/api/simulator/positions/${numPlayers}`, controller.signal)
      .then((names) => {
        setPositions(names)
        setHeroPosition((p) => (p && names.includes(p) ? p : null))
        setVillains((vs) =>
          vs
            .slice(0, numPlayers - 1)
            .map((v) => ({ ...v, position: v.position && names.includes(v.position) ? v.position : null })),
        )
      })
      .catch(() => {
        if (!controller.signal.aborted) setPositions([])
      })
    return () => controller.abort()
  }, [numPlayers])

  const used = useMemo(() => {
    const all = [...heroSlots, ...boardSlots, ...villains.flatMap((v) => v.hand)]
    return new Set(all.filter((c): c is string => c !== null))
  }, [heroSlots, boardSlots, villains])

  const villainLabels = villains.map((v, i) => `Rival ${i + 1}${v.position ? ` (${v.position})` : ''}`)

  function slotsOf(group: SlotGroup): Slot[] {
    if (group === 'hero') return heroSlots
    if (group === 'board') return boardSlots
    return villains[group].hand
  }

  function setSlot(group: SlotGroup, index: number, card: Slot) {
    const next = [...slotsOf(group)]
    next[index] = card
    if (group === 'hero') setHeroSlots(next)
    else if (group === 'board') setBoardSlots(next)
    else setVillains((vs) => vs.map((v, i) => (i === group ? { ...v, hand: next } : v)))
  }

  function updateVillain(index: number, patch: Partial<VillainState>) {
    setVillains((vs) => vs.map((v, i) => (i === index ? { ...v, ...patch } : v)))
  }

  function renderSlots(group: SlotGroup, labels: string[]) {
    return (
      <div className="card-slots">
        {slotsOf(group).map((card, index) => (
          <CardView
            key={index}
            card={card}
            label={labels[index]}
            active={active?.group === group && active.index === index}
            onClick={() =>
              setActive((a) => (a?.group === group && a.index === index ? null : { group, index }))
            }
          />
        ))}
      </div>
    )
  }

  async function deal(clearFirst: boolean) {
    setError(null)
    const hero = clearFirst ? [] : heroSlots
    const board = clearFirst ? [] : boardSlots
    const request: DealRequest = {
      street,
      hero_hand: joinSlots(hero),
      board: joinSlots(board),
      villain_hands: villains.map((v) => (clearFirst ? null : joinSlots(v.hand) || null)),
      deal_villains: villains.flatMap((v, i) => (v.dealHand ? [i] : [])),
    }
    try {
      const result = await postJson<DealResult>('/api/simulator/deal', request)
      setHeroSlots(toSlots(result.hero_hand, 2))
      setBoardSlots(toSlots(result.board, 5))
      setVillains((vs) => vs.map((v, i) => ({ ...v, hand: toSlots(result.villain_hands[i], 2) })))
      setActive(null)
      setAnalysis(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const isTournament = format !== 'cash'
  const payoutList = payouts
    .split(/[,;\s]+/)
    .filter(Boolean)
    .map(Number)
    .filter((n) => Number.isFinite(n) && n >= 0)

  async function analyze() {
    setError(null)
    const heroHand = joinSlots(heroSlots)
    if (heroHand.length !== 4) {
      setError('Elegí las dos cartas de Hero (o generalas al azar).')
      return
    }
    const scenario: ScenarioInput = {
      format,
      num_players: numPlayers,
      hero_position: heroPosition,
      hero_hand: heroHand,
      villains: villains.map((v) => ({
        position: v.position,
        range: v.range,
        hand: joinSlots(v.hand) || null,
      })),
      board: joinSlots(boardSlots),
      pot_bb: parseAmount(pot),
      to_call_bb: parseAmount(toCall),
      effective_stack_bb: parseAmount(stack),
      previous_action: previousAction,
      situation: situation || null,
      ante_bb: parseAmount(ante),
      bb_ante_bb: parseAmount(bbAnte),
      stacks_bb: isTournament
        ? Object.fromEntries(
            Object.entries(stacksByPos)
              .filter(([p, v]) => positions.includes(p) && v.trim() !== '')
              .map(([p, v]) => [p, parseAmount(v)]),
          )
        : {},
      payouts: isTournament ? payoutList : [],
    }
    setBusy(true)
    try {
      setAnalysis(await postJson<Analysis>('/api/simulator/analyze', scenario))
    } catch (e) {
      setAnalysis(null)
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  function positionSelect(id: string, value: string | null, onChange: (v: string | null) => void) {
    return (
      <select id={id} value={value ?? ''} onChange={(e) => onChange(e.target.value || null)}>
        <option value="">Sin definir</option>
        {positions.map((p) => (
          <option key={p} value={p}>
            {p}
          </option>
        ))}
      </select>
    )
  }

  return (
    <div className="simulator">
      <div className="sim-config">
        <section className="panel" aria-labelledby="table-title">
          <h3 id="table-title">Mesa</h3>
          <div className="field-row">
            <label>
              Formato
              <select value={format} onChange={(e) => setFormat(e.target.value as GameFormat)}>
                <option value="cash">Cash</option>
                <option value="mtt">Torneo (MTT)</option>
                <option value="sng">Sit &amp; Go</option>
                <option value="spin">Spin &amp; Go</option>
              </select>
            </label>
            <label>
              Jugadores
              <select value={numPlayers} onChange={(e) => setNumPlayers(Number(e.target.value))}>
                {Array.from({ length: MAX_PLAYERS - 1 }, (_, i) => i + 2).map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="field-row">
            <label>
              Pote (bb)
              <input type="number" min="0" step="0.5" value={pot} onChange={(e) => setPot(e.target.value)} />
            </label>
            <label>
              A pagar (bb)
              <input type="number" min="0" step="0.5" value={toCall} onChange={(e) => setToCall(e.target.value)} />
            </label>
            <label>
              Stack efectivo (bb)
              <input type="number" min="0" step="1" value={stack} onChange={(e) => setStack(e.target.value)} />
            </label>
          </div>
          <p className="muted small">El pote incluye la apuesta que estás enfrentando.</p>
          <div className="field-row">
            <label>
              Situación preflop
              <select value={situation} onChange={(e) => setSituation(e.target.value)}>
                <option value="">Sin definir</option>
                {SITUATIONS.map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Ante (bb)
              <input type="number" min="0" step="0.01" value={ante} onChange={(e) => setAnte(e.target.value)} />
            </label>
            <label>
              BB ante (bb)
              <input type="number" min="0" step="0.1" value={bbAnte} onChange={(e) => setBbAnte(e.target.value)} />
            </label>
          </div>
          <p className="muted small">Rival 1 es quien abrió, subió o fue all-in antes que vos.</p>
          {isTournament && (
            <details className="tournament">
              <summary>Torneo: stacks por posición y premios (ICM)</summary>
              <div className="stack-grid">
                {positions.map((p) => (
                  <label key={p}>
                    {p}
                    <input
                      type="number"
                      min="0"
                      step="0.5"
                      placeholder={stack}
                      value={stacksByPos[p] ?? ''}
                      onChange={(e) => setStacksByPos((s) => ({ ...s, [p]: e.target.value }))}
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
            </details>
          )}
          <label>
            Acción previa
            <input
              type="text"
              value={previousAction}
              onChange={(e) => setPreviousAction(e.target.value)}
              placeholder="Ej.: CO abre 2.5bb, BTN paga"
            />
          </label>
        </section>

        <section className="panel" aria-labelledby="hero-title">
          <h3 id="hero-title">Hero</h3>
          <div className="field-row">
            <label htmlFor="hero-pos">Posición</label>
            {positionSelect('hero-pos', heroPosition, setHeroPosition)}
          </div>
          {renderSlots('hero', ['Hero carta 1', 'Hero carta 2'])}
        </section>

        <section className="panel" aria-labelledby="board-title">
          <h3 id="board-title">Board</h3>
          {renderSlots('board', BOARD_LABELS)}
        </section>

        {active && (
          <CardPicker
            used={used}
            onPick={(card) => {
              setSlot(active.group, active.index, card)
              setActive(null)
            }}
            onClear={() => {
              setSlot(active.group, active.index, null)
              setActive(null)
            }}
            onClose={() => setActive(null)}
          />
        )}

        {villains.map((v, i) => (
          <section key={i} className="panel" aria-labelledby={`villain-${i}-title`}>
            <div className="panel-header">
              <h3 id={`villain-${i}-title`}>Rival {i + 1}</h3>
              {villains.length > 1 && (
                <button
                  type="button"
                  className="link-button"
                  onClick={() => setVillains((vs) => vs.filter((_, j) => j !== i))}
                >
                  Quitar
                </button>
              )}
            </div>
            <div className="field-row">
              <label htmlFor={`villain-${i}-pos`}>Posición</label>
              {positionSelect(`villain-${i}-pos`, v.position, (p) => updateVillain(i, { position: p }))}
            </div>
            <label htmlFor={`villain-${i}-range`}>Rango</label>
            <RangeEditor
              id={`villain-${i}-range`}
              value={v.range}
              onChange={(range) => updateVillain(i, { range })}
            />
            <p className="field-label">Mano puntual (opcional, solo informativa)</p>
            {renderSlots(i, [`Rival ${i + 1} carta 1`, `Rival ${i + 1} carta 2`])}
            <label className="checkbox">
              <input
                type="checkbox"
                checked={v.dealHand}
                onChange={(e) => updateVillain(i, { dealHand: e.target.checked })}
              />
              Repartirle mano al azar
            </label>
          </section>
        ))}
        {villains.length < numPlayers - 1 && (
          <button type="button" onClick={() => setVillains((vs) => [...vs, newVillain()])}>
            Agregar rival
          </button>
        )}

        <section className="panel actions" aria-label="Acciones">
          <label>
            Calle
            <select value={street} onChange={(e) => setStreet(e.target.value as Street)}>
              <option value="preflop">Preflop</option>
              <option value="flop">Flop</option>
              <option value="turn">Turn</option>
              <option value="river">River</option>
            </select>
          </label>
          <button type="button" onClick={() => void deal(false)}>
            Completar al azar
          </button>
          <button type="button" onClick={() => void deal(true)}>
            Todo al azar
          </button>
          <button type="button" className="primary" onClick={() => void analyze()} disabled={busy}>
            {busy ? 'Calculando…' : 'Analizar'}
          </button>
        </section>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </div>

      <div className="sim-results" aria-live="polite">
        {analysis ? (
          <ResultsPanel analysis={analysis} villainLabels={villainLabels} />
        ) : (
          <section className="panel panel-muted">
            <p className="muted">
              Armá el escenario (o generalo al azar) y tocá <strong>Analizar</strong>. La equity se
              calcula siempre contra el rango del rival.
            </p>
          </section>
        )}
      </div>
    </div>
  )
}
