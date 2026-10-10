import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getJson, postJson } from '../api/client'
import { readStored, writeStored } from '../app/storage'
import { isPreflopFilters, PREFLOP_FILTERS_KEY, type PreflopFilters } from '../ranges/preflopFilters'
import { fetchSolverStatus, prefillRanges } from '../solver/api'
import { Button, Chip, PillGroup, Popover } from '../ui'
import { AdvancedPanel } from './AdvancedOptions'
import { CardPicker } from './CardPicker'
import { joinSlots, type Slot, toSlots } from './cards'
import { PostflopSolverFields } from './PostflopSolverFields'
import { ResultsPanel } from './ResultsPanel'
import { SeatPopover } from './SeatPopover'
import {
  BOARD_CARDS,
  boardForStreet,
  defaultTable,
  heroSeat,
  isTableState,
  previousActionFrom,
  seatsFor,
  setRole,
  SIM_TABLE_KEY,
  STREET_LABEL,
  streetFromBoard,
  tableFromInitial,
  type TableState,
  tableToScenario,
  updateSeat,
  validateTable,
  villainSeats,
} from './table'
import { type CardSlotRef, sameSlot } from './slots'
import { TableView } from './TableView'
import type { Analysis, DealRequest, DealResult, GameFormat, ScenarioInput, Street } from './types'

/** A scenario to start from (e.g. a spot sent by the hand replayer or Preflop). */
export type InitialScenario = Partial<ScenarioInput>

const FORMAT_LABEL: Record<GameFormat, string> = { cash: 'Cash', mtt: 'Torneo (MTT)', sng: 'Sit & Go', spin: 'Spin & Go' }
const STREETS: Street[] = ['preflop', 'flop', 'turn', 'river']
const MAX_PLAYERS = 10
const message = (e: unknown) => (e instanceof Error ? e.message : String(e))
const storedFilters = (v: unknown): v is PreflopFilters | null => v === null || isPreflopFilters(v)

/** Seats near the left or right edge open their popover towards the centre of the table. */
function popoverSide(left: string): string {
  const x = parseFloat(left)
  return x > 62 ? ' sim-popover-anchor-right' : x < 38 ? ' sim-popover-anchor-left' : ''
}

function initialTable(initial?: InitialScenario): TableState {
  const base = defaultTable(readStored<PreflopFilters | null>(PREFLOP_FILTERS_KEY, null, storedFilters))
  if (initial) return tableFromInitial(initial, base)
  return readStored(SIM_TABLE_KEY, base, isTableState)
}

export function SimulatorPage({ initial }: { initial?: InitialScenario } = {}) {
  const [table, setTable] = useState<TableState>(() => initialTable(initial))
  const [selected, setSelected] = useState<string | null>(null)
  const [active, setActive] = useState<CardSlotRef | null>(null)
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [presets, setPresets] = useState<{ name: string; label: string }[]>([])
  const [prefillNotes, setPrefillNotes] = useState<string[]>([])
  const [potType, setPotType] = useState<'srp' | '3bet'>('srp')
  const [aggressor, setAggressor] = useState<'hero' | 'villain'>('villain')
  const [configOpen, setConfigOpen] = useState(false)
  const configAnchor = useRef<HTMLButtonElement>(null)
  const closeConfig = useCallback(() => setConfigOpen(false), [])
  const closeSeat = useCallback(() => setSelected(null), [])

  useEffect(() => writeStored(SIM_TABLE_KEY, table), [table])

  useEffect(() => {
    fetchSolverStatus()
      .then((s) => setPresets(s.presets))
      .catch(() => setPresets([{ name: 'chico', label: 'Chico' }]))
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    getJson<string[]>(`/api/simulator/positions/${table.num_players}`, controller.signal)
      .then((names) =>
        setTable((t) => ({
          ...t,
          seats: seatsFor(
            names,
            t.seats.filter((s) => names.includes(s.position)),
            heroSeat(t.seats)?.stack_bb ?? 100,
          ),
        })),
      )
      .catch(() => {
        // Without the position list the table keeps the seats it has.
      })
    return () => controller.abort()
  }, [table.num_players])

  const used = useMemo(
    () => new Set([table.hero_hand, table.board, ...table.seats.map((s) => s.hand ?? '')].join('').match(/.{2}/g) ?? []),
    [table],
  )

  function setSlot(slot: CardSlotRef, card: Slot) {
    const { index } = slot
    if (slot.group === 'seat') {
      const { position } = slot
      setTable((t) => {
        const s = toSlots(t.seats.find((x) => x.position === position)?.hand, 2)
        s[index] = card
        return { ...t, seats: updateSeat(t.seats, position, { hand: joinSlots(s) || null }) }
      })
    } else if (slot.group === 'hero') {
      setTable((t) => {
        const s = toSlots(t.hero_hand, 2)
        s[index] = card
        return { ...t, hero_hand: joinSlots(s) }
      })
    } else {
      setTable((t) => {
        const s = toSlots(t.board, 5)
        s[index] = card
        return { ...t, board: joinSlots(s) }
      })
    }
  }

  async function deal(clearFirst: boolean) {
    setError(null)
    const villains = villainSeats(table.seats)
    const request: DealRequest = {
      street: table.street,
      hero_hand: clearFirst ? '' : table.hero_hand,
      board: clearFirst ? '' : boardForStreet(table.board, table.street),
      villain_hands: villains.map((v) => (clearFirst ? null : v.hand)),
      deal_villains: [],
    }
    try {
      const r = await postJson<DealResult>('/api/simulator/deal', request)
      setTable((t) => {
        let seats = t.seats
        villainSeats(t.seats).forEach((v, i) => {
          seats = updateSeat(seats, v.position, { hand: r.villain_hands[i] ?? null })
        })
        return { ...t, hero_hand: r.hero_hand, board: r.board, street: r.board ? streetFromBoard(r.board) : t.street, seats }
      })
      setActive(null)
      setAnalysis(null)
    } catch (e) {
      setError(message(e))
    }
  }

  const problem = validateTable(table)

  async function analyze() {
    if (validateTable(table)) return
    setError(null)
    setBusy(true)
    try {
      setAnalysis(await postJson<Analysis>('/api/simulator/analyze', tableToScenario(table)))
    } catch (e) {
      setAnalysis(null)
      setError(message(e))
    } finally {
      setBusy(false)
    }
  }

  async function prefill() {
    const hero = heroSeat(table.seats)
    const villain = villainSeats(table.seats)[0]
    if (!hero || !villain) {
      setError('Marcá tu asiento y un rival para prellenar.')
      return
    }
    setError(null)
    const [aggr, caller] = aggressor === 'hero' ? [hero.position, villain.position] : [villain.position, hero.position]
    try {
      const r = await prefillRanges({
        game_format: table.format,
        players: table.num_players,
        aggressor: aggr,
        caller,
        pot_type: potType,
        stack_bb: tableToScenario(table).effective_stack_bb,
        ante_bb: table.advanced.ante_bb,
      })
      const heroPart = aggressor === 'hero' ? r.aggressor : r.caller
      const villPart = aggressor === 'hero' ? r.caller : r.aggressor
      const missing = [heroPart.missing, villPart.missing].filter(Boolean) as string[]
      setTable((t) => ({
        ...t,
        seats: villPart.text ? updateSeat(t.seats, villain.position, { range: villPart.text }) : t.seats,
        advanced: {
          ...t.advanced,
          hero_range: heroPart.text || t.advanced.hero_range,
          ranges_approximate: heroPart.approximate || villPart.approximate || missing.length > 0,
        },
      }))
      setPrefillNotes([...heroPart.notes, ...villPart.notes, ...missing.map((m) => `Falta tabla: ${m}`)])
    } catch (e) {
      setError(message(e))
    }
  }

  // Keep the latest analyze() reachable from the polling callback without re-arming its timer.
  const analyzeRef = useRef(analyze)
  useEffect(() => {
    analyzeRef.current = analyze
  })
  const refreshAnalysis = useCallback(() => void analyzeRef.current(), [])

  const hero = heroSeat(table.seats)
  const villains = villainSeats(table.seats)
  const showSolverFields =
    BOARD_CARDS[table.street] >= 3 && table.board.length / 2 >= 3 && villains.length === 1

  return (
    <div className="simulator">
      <div className="sim-main">
        <div className="sim-top">
          <span className="sim-config">
            <Chip>
              {FORMAT_LABEL[table.format]} · {table.num_players}-max · {hero?.stack_bb ?? 100} bb
            </Chip>
            <button
              ref={configAnchor}
              type="button"
              className="btn btn-ghost btn-sm"
              aria-expanded={configOpen}
              onClick={() => setConfigOpen((o) => !o)}
            >
              Cambiar
            </button>
            <Popover open={configOpen} onClose={closeConfig} anchorRef={configAnchor} label="Mesa" className="sim-config-pop">
              <label>
                Formato
                <select
                  value={table.format}
                  onChange={(e) => setTable((t) => ({ ...t, format: e.target.value as GameFormat }))}
                >
                  {(Object.keys(FORMAT_LABEL) as GameFormat[]).map((f) => (
                    <option key={f} value={f}>
                      {FORMAT_LABEL[f]}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Jugadores
                <select
                  value={table.num_players}
                  onChange={(e) => setTable((t) => ({ ...t, num_players: Number(e.target.value) }))}
                >
                  {Array.from({ length: MAX_PLAYERS - 1 }, (_, i) => i + 2).map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Stack efectivo por defecto (bb)
                <input
                  type="number"
                  min="0"
                  step="1"
                  value={hero?.stack_bb ?? 100}
                  onChange={(e) => {
                    const stack = Math.max(0, Number(e.target.value) || 0)
                    setTable((t) => ({ ...t, seats: t.seats.map((s) => ({ ...s, stack_bb: stack })) }))
                  }}
                />
              </label>
              <Button size="sm" onClick={closeConfig}>
                Listo
              </Button>
            </Popover>
          </span>
          <PillGroup
            legend="Calle"
            options={STREETS.map((s) => ({ value: s, label: STREET_LABEL[s] }))}
            value={table.street}
            onChange={(street) => setTable((t) => ({ ...t, street }))}
          />
        </div>

        <TableView
          table={table}
          selected={selected}
          onSeatClick={(p) => setSelected((s) => (s === p ? null : p))}
          activeSlot={active}
          onSlotClick={(slot) => setActive((a) => (sameSlot(a, slot) ? null : slot))}
          onPotChange={(pot_bb) => setTable((t) => ({ ...t, pot_bb }))}
          renderSeatPanel={(seat, anchorRef, style) => (
            <div
              className={`sim-popover-anchor${popoverSide(style.left)}`}
              style={style}
            >
              <SeatPopover
                seat={seat}
                table={table}
                anchorRef={anchorRef}
                onClose={closeSeat}
                onRole={(role) => setTable((t) => ({ ...t, seats: setRole(t.seats, seat.position, role) }))}
                onChange={(patch) => setTable((t) => ({ ...t, seats: updateSeat(t.seats, seat.position, patch) }))}
                activeSlot={active}
                onSlotClick={(slot) => setActive((a) => (sameSlot(a, slot) ? null : slot))}
              />
            </div>
          )}
        />

        {active && (
          <CardPicker
            used={used}
            onPick={(card) => {
              setSlot(active, card)
              setActive(null)
            }}
            onClear={() => {
              setSlot(active, null)
              setActive(null)
            }}
            onClose={() => setActive(null)}
          />
        )}

        <div className="sim-actions">
          <Button onClick={() => void deal(false)}>Completar al azar</Button>
          <Button onClick={() => void deal(true)}>Todo al azar</Button>
        </div>

        <AdvancedPanel
          table={table}
          onChange={(advanced) => setTable((t) => ({ ...t, advanced }))}
          autoAction={previousActionFrom({ ...table, advanced: { ...table.advanced, previous_action: '' } })}
        >
          {showSolverFields && (
            <PostflopSolverFields
              heroRange={table.advanced.hero_range}
              onHeroRange={(v) => {
                setTable((t) => ({ ...t, advanced: { ...t.advanced, hero_range: v, ranges_approximate: false } }))
                setPrefillNotes([])
              }}
              preset={table.advanced.solver_preset}
              onPreset={(v) => setTable((t) => ({ ...t, advanced: { ...t.advanced, solver_preset: v } }))}
              presets={presets}
              prefill={prefill}
              prefillNotes={prefillNotes}
              potType={potType}
              onPotType={setPotType}
              aggressor={aggressor}
              onAggressor={setAggressor}
            />
          )}
        </AdvancedPanel>
      </div>

      <aside className="sim-side" aria-live="polite">
        <Button variant="primary" onClick={() => void analyze()} disabled={busy || problem !== null}>
          {busy ? 'Calculando…' : 'Analizar'}
        </Button>
        {problem && <p className="muted small">{problem}</p>}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {analysis ? (
          <ResultsPanel
            analysis={analysis}
            villainLabels={villains.map((v) => `Rival (${v.position})`)}
            onSolveDone={refreshAnalysis}
          />
        ) : (
          <section className="panel panel-muted">
            <p className="muted">
              Armá la mesa: tocá un asiento para marcar rivales y apuestas, elegí tus cartas y el board, y tocá{' '}
              <strong>Analizar</strong>. La equity se calcula siempre contra el rango del rival.
            </p>
          </section>
        )}
      </aside>
    </div>
  )
}
