import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../api/client'
import { FORMATS, SITUATIONS } from '../ranges/labels'
import {
  answerSpot,
  createSession,
  fetchFrequentErrors,
  fetchPayouts,
  fetchSources,
  fetchSummary,
  nextSpot,
} from './api'
import { Feedback } from './Feedback'
import { PayoutsEditor } from './PayoutsEditor'
import { RangeDrill } from './RangeDrill'
import { actionForKey } from './format'
import { SessionSidebar } from './SessionSidebar'
import { SpotView } from './SpotView'
import type {
  AnswerBody,
  Feedback as FeedbackData,
  FrequentError,
  InitialFilters,
  Mode,
  Payout,
  SessionRequest,
  Sources,
  Spot,
  Summary,
  TrainerSource,
} from './types'

const SOURCE_OPTIONS: [TrainerSource, string][] = [
  ['pushfold', 'Push/fold'],
  ['chart', 'Tablas preflop'],
  ['range', 'Pintá tu rango'],
]
const POSITIONS = ['UTG', 'UTG+1', 'UTG+2', 'UTG+3', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']
const BUCKETS = ['3-5', '6-8', '9-11', '12-15', '≤15', '16-30', '31-60', '61-120', '120+']
const MODES: [Mode, string][] = [
  ['normal', 'Normal'],
  ['review', 'Solo repaso'],
  ['frequent', 'Solo errores frecuentes'],
]

interface Filters {
  sources: string[] | null // null = every available source
  formats: string[]
  positions: string[]
  situations: string[]
  buckets: string[]
  mode: Mode
  difficulty: number
  payoutId: number | null
  preferDue: boolean
}

function initial(f?: InitialFilters): Filters {
  return {
    sources: f?.sources ?? null,
    formats: f?.formats ?? [],
    positions: f?.positions ?? [],
    situations: f?.situations ?? [],
    buckets: [],
    mode: 'normal',
    difficulty: 50,
    payoutId: null,
    preferDue: f?.preferDue ?? false,
  }
}

function toggle(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value]
}

function CheckGroup({
  legend,
  options,
  value,
  onChange,
}: {
  legend: string
  options: readonly (readonly [string, string])[]
  value: string[]
  onChange: (v: string[]) => void
}) {
  return (
    <fieldset className="trainer-group">
      <legend>{legend}</legend>
      {options.map(([id, text]) => (
        <label key={id} className="trainer-check">
          <input type="checkbox" checked={value.includes(id)} onChange={() => onChange(toggle(value, id))} />
          {text}
        </label>
      ))}
    </fieldset>
  )
}

export function TrainerPage({ initialFilters }: { initialFilters?: InitialFilters }) {
  const [filters, setFilters] = useState<Filters>(() => initial(initialFilters))
  const [sources, setSources] = useState<Sources | null>(null)
  const [payouts, setPayouts] = useState<Payout[]>([])
  const [errors, setErrors] = useState<FrequentError[]>([])
  const [configOpen, setConfigOpen] = useState(true)
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [spot, setSpot] = useState<Spot | null>(null)
  const [feedback, setFeedback] = useState<FeedbackData | null>(null)
  const [summary, setSummary] = useState<Summary | null>(null)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [noSpots, setNoSpots] = useState(false)
  const [starting, setStarting] = useState(false)
  const [sourcesError, setSourcesError] = useState(false)
  const [payoutsError, setPayoutsError] = useState(false)
  const [summaryError, setSummaryError] = useState(false)
  const busy = useRef(false)
  const startingRef = useRef(false)
  // Monotonic request id: any response from a superseded begin/next/answer is discarded.
  const gen = useRef(0)
  const mounted = useRef(true)

  const refreshErrors = useCallback(() => {
    fetchFrequentErrors()
      .then(setErrors)
      .catch(() => setErrors([]))
  }, [])

  useEffect(() => {
    const c = new AbortController()
    mounted.current = true
    fetchSources(c.signal)
      .then(setSources)
      .catch(() => {
        if (!c.signal.aborted) setSourcesError(true)
      })
    fetchPayouts(c.signal)
      .then(setPayouts)
      .catch(() => {
        if (!c.signal.aborted) setPayoutsError(true)
      })
    refreshErrors()
    return () => {
      mounted.current = false
      c.abort()
    }
  }, [refreshErrors])

  // Unknown sources (request failed) are never enabled; while loading they stay selectable.
  const available = (id: TrainerSource) => !sourcesError && (sources === null || sources[id].available)
  const reasonFor = (id: TrainerSource) =>
    sourcesError ? 'No se pudo consultar la disponibilidad' : sources?.[id].reason
  const chosen = filters.sources ?? SOURCE_OPTIONS.map(([id]) => id)
  const selectedSources = (): TrainerSource[] =>
    SOURCE_OPTIONS.map(([id]) => id).filter((id) => chosen.includes(id) && available(id))

  const loadNext = useCallback(async (id: number) => {
    const my = ++gen.current
    busy.current = false
    setSpot(null)
    setFeedback(null)
    setMessage(null)
    setNoSpots(false)
    setLoading(true)
    try {
      const next = await nextSpot(id)
      if (my !== gen.current || !mounted.current) return
      setSpot(next)
    } catch (err) {
      if (my !== gen.current || !mounted.current) return
      if (err instanceof ApiError && err.status === 409) {
        setNoSpots(true)
        setConfigOpen(true)
      } else {
        setMessage(err instanceof Error ? err.message : 'No se pudo preparar el spot')
      }
    } finally {
      if (my === gen.current && mounted.current) setLoading(false)
    }
  }, [])

  const begin = async (override?: Partial<SessionRequest>) => {
    if (startingRef.current) return
    startingRef.current = true
    setStarting(true)
    const my = ++gen.current
    busy.current = false
    setMessage(null)
    setSummary(null)
    setSummaryError(false)
    const body: SessionRequest = {
      sources: selectedSources(),
      formats: filters.formats,
      positions: filters.positions,
      situations: filters.situations,
      stack_buckets: filters.buckets,
      mode: filters.mode,
      difficulty: filters.difficulty,
      payout_id: filters.payoutId,
      ...(filters.preferDue ? { prefer_due: true } : {}),
      ...override,
    }
    try {
      const { id } = await createSession(body)
      if (my !== gen.current || !mounted.current) return
      setSessionId(id)
      setConfigOpen(false)
      startingRef.current = false
      setStarting(false)
      await loadNext(id)
    } catch (err) {
      if (my !== gen.current || !mounted.current) return
      setSessionId(null)
      setSpot(null)
      setFeedback(null)
      setNoSpots(false)
      setMessage(err instanceof Error ? err.message : 'No se pudo crear la sesión')
    } finally {
      startingRef.current = false
      if (mounted.current) setStarting(false)
    }
  }

  const answer = useCallback(
    async (body: AnswerBody) => {
      if (!spot || feedback || busy.current || sessionId === null) return
      busy.current = true
      const my = gen.current
      const live = () => my === gen.current && mounted.current
      try {
        const fb = await answerSpot(spot.spot_id, body)
        if (!live()) return
        setFeedback(fb)
        setSummaryError(false)
        fetchSummary(sessionId)
          .then((s) => live() && setSummary(s))
          .catch(() => live() && setSummaryError(true))
        refreshErrors()
      } catch (err) {
        if (!live()) return
        setMessage(err instanceof Error ? err.message : 'No se pudo registrar la respuesta')
      } finally {
        if (live()) busy.current = false
      }
    },
    [spot, feedback, sessionId, refreshErrors],
  )

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return
      const t = e.target as HTMLElement | null
      if (t && ['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName)) return
      if (e.key === 'Enter') {
        // A focused button handles Enter natively through its click.
        if (feedback && sessionId !== null && !(t && t.tagName === 'BUTTON')) {
          e.preventDefault()
          void loadNext(sessionId)
        }
        return
      }
      if (!spot || spot.kind !== 'hand' || feedback) return
      const action = actionForKey(e.key, spot.offered)
      if (action) {
        e.preventDefault()
        void answer({ action })
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [spot, feedback, sessionId, answer, loadNext])

  const set = (patch: Partial<Filters>) => setFilters((f) => ({ ...f, ...patch }))
  const clear = () => {
    setFilters(initial())
    setNoSpots(false)
  }

  const trainErrors = () =>
    begin({
      mode: 'frequent',
      card_ids: errors.map((e) => e.card_id),
      sources: [...new Set(errors.map((e) => e.source))] as TrainerSource[],
      formats: [],
      positions: [],
      situations: [],
      stack_buckets: [],
    })

  return (
    <div className="trainer">
      <div className="trainer-main">
        <section className="panel trainer-config">
          <div className="panel-header">
            <h3>Configuración</h3>
            <button type="button" aria-expanded={configOpen} onClick={() => setConfigOpen((o) => !o)}>
              {configOpen ? 'Plegar' : 'Mostrar'}
            </button>
          </div>
          {configOpen && (
            <>
              <fieldset className="trainer-group">
                <legend>Fuentes</legend>
                {SOURCE_OPTIONS.map(([id, text]) => {
                  const disabled = !available(id)
                  return (
                    <label key={id} className="trainer-check">
                      <input
                        type="checkbox"
                        disabled={disabled}
                        checked={!disabled && chosen.includes(id)}
                        onChange={() => set({ sources: toggle(chosen, id) })}
                      />
                      {text}
                      {disabled && reasonFor(id) && <span className="muted small"> {reasonFor(id)}</span>}
                    </label>
                  )
                })}
              </fieldset>
              <PayoutsEditor
                payouts={payouts}
                onChange={(list) => {
                  setPayouts(list)
                  setFilters((f) =>
                    f.payoutId !== null && !list.some((p) => p.id === f.payoutId) ? { ...f, payoutId: null } : f,
                  )
                }}
              />
              <CheckGroup
                legend="Formatos"
                options={FORMATS}
                value={filters.formats}
                onChange={(formats) => set({ formats })}
              />
              <CheckGroup
                legend="Posiciones"
                options={POSITIONS.map((p) => [p, p] as const)}
                value={filters.positions}
                onChange={(positions) => set({ positions })}
              />
              <CheckGroup
                legend="Situaciones"
                options={SITUATIONS}
                value={filters.situations}
                onChange={(situations) => set({ situations })}
              />
              <CheckGroup
                legend="Stack (bb)"
                options={BUCKETS.map((b) => [b, b] as const)}
                value={filters.buckets}
                onChange={(buckets) => set({ buckets })}
              />
              <div className="trainer-row">
                <label>
                  Modo{' '}
                  <select value={filters.mode} onChange={(e) => set({ mode: e.target.value as Mode })}>
                    {MODES.map(([id, text]) => (
                      <option key={id} value={id}>
                        {text}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Dificultad {filters.difficulty}{' '}
                  <input
                    type="range"
                    min={0}
                    max={100}
                    value={filters.difficulty}
                    onChange={(e) => set({ difficulty: Number(e.target.value) })}
                  />
                </label>
                <label>
                  Premios{' '}
                  <select
                    value={filters.payoutId ?? ''}
                    onChange={(e) => set({ payoutId: e.target.value === '' ? null : Number(e.target.value) })}
                  >
                    <option value="">Chip EV</option>
                    {payouts.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              {sourcesError && (
                <p className="error small" role="alert">
                  No se pudieron cargar las fuentes disponibles.
                </p>
              )}
              {payoutsError && (
                <p className="error small" role="alert">
                  No se pudieron cargar las estructuras de premios.
                </p>
              )}
            </>
          )}
          <button
            type="button"
            className="primary"
            disabled={starting || loading}
            onClick={() => void begin()}
          >
            Empezar
          </button>
          {message && sessionId === null && (
            <p className="error" role="alert">
              {message}
            </p>
          )}
        </section>

        {loading && <p className="muted">Preparando spot…</p>}
        {noSpots && (
          <div className="panel" role="alert">
            <p>No hay spots para estos filtros</p>
            <button type="button" onClick={clear}>
              Limpiar filtros
            </button>
          </div>
        )}
        {message && sessionId !== null && (
          <p className="error" role="alert">
            {message}
          </p>
        )}
        {spot && spot.kind === 'range' && (
          <RangeDrill
            key={spot.spot_id}
            spot={spot}
            feedback={feedback}
            onSubmit={(painted) => void answer({ painted })}
            onNext={sessionId !== null ? () => void loadNext(sessionId) : undefined}
          />
        )}
        {spot && spot.kind === 'hand' && (
          <>
            <SpotView spot={spot} onAnswer={feedback ? undefined : (a) => void answer({ action: a })} />
            {feedback && sessionId !== null && (
              <Feedback feedback={feedback} onNext={() => void loadNext(sessionId)} />
            )}
          </>
        )}
      </div>
      <SessionSidebar
        summary={summary}
        summaryError={summaryError}
        errors={errors}
        busy={starting || loading}
        onTrainErrors={() => void trainErrors()}
      />
    </div>
  )
}
