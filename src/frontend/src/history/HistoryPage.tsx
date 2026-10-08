import { useEffect, useState } from 'react'
import { ApiError, getJson } from '../api/client'
import { FORMAT_LABEL } from '../ranges/labels'
import { CardView } from '../simulator/CardView'
import { splitCards } from '../simulator/cards'
import { FilterBar } from '../stats/FilterBar'
import { EMPTY_FILTERS, type Filters, filterQuery } from '../stats/filters'
import type { HandPage, ImportOut } from './types'

const PAGE = 50

async function uploadFiles(files: FileList): Promise<ImportOut> {
  const form = new FormData()
  Array.from(files).forEach((f) => form.append('files', f))
  const resp = await fetch('/api/imports', { method: 'POST', body: form })
  const body = (await resp.json().catch(() => null)) as ImportOut | { detail?: string } | null
  if (!resp.ok) {
    const detail = body && 'detail' in body ? body.detail : null
    throw new ApiError(typeof detail === 'string' ? detail : `Error del servidor (HTTP ${resp.status})`)
  }
  return body as ImportOut
}

export function HistoryPage({ onOpen }: { onOpen: (handId: number) => void }) {
  const [rooms, setRooms] = useState<{ site: string; label: string }[] | null>(null)
  const [report, setReport] = useState<ImportOut | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS)
  const [offset, setOffset] = useState(0)
  const [page, setPage] = useState<HandPage | null>(null)
  const [reload, setReload] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    getJson<{ site: string; label: string }[]>('/api/parsers', controller.signal)
      .then(setRooms)
      .catch(() => {})
    return () => controller.abort()
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    getJson<HandPage>(`/api/hands${filterQuery(filters, { limit: PAGE, offset })}`, controller.signal)
      .then(setPage)
      .catch((e: unknown) => {
        if (!controller.signal.aborted) setError(e instanceof Error ? e.message : String(e))
      })
    return () => controller.abort()
  }, [filters, offset, reload])

  async function onFiles(files: FileList | null) {
    if (!files || files.length === 0) return
    setBusy(true)
    setError(null)
    try {
      setReport(await uploadFiles(files))
      setOffset(0)
      setReload((n) => n + 1)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const totals = report?.report.totals

  return (
    <div className="history">
      <section className="panel" aria-labelledby="import-title">
        <h3 id="import-title">Importar historiales</h3>
        <p className="small muted">
          Salas soportadas:{' '}
          {rooms === null ? '…' : rooms.length ? rooms.map((r) => r.label).join(', ') : 'ninguna todavía'}
          . Se aceptan archivos .txt y .zip; las manos repetidas se ignoran.
        </p>
        <label className="file-button">
          {busy ? 'Importando…' : 'Elegir archivos'}
          <input
            type="file"
            multiple
            accept=".txt,.zip,text/plain,application/zip"
            disabled={busy}
            onChange={(e) => {
              void onFiles(e.target.files)
              e.target.value = ''
            }}
          />
        </label>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {totals && (
          <div className="import-report" aria-live="polite">
            <p>
              <strong>{totals.imported}</strong> manos importadas de {totals.hands_found} encontradas en{' '}
              {totals.files} archivo(s) · {totals.duplicates} repetidas · {totals.failed} con error
            </p>
            {report.report.errors.length > 0 && (
              <details open={totals.imported === 0}>
                <summary>Problemas ({report.report.errors.length}{report.report.errors_truncated ? '+' : ''})</summary>
                <ul className="small error-list">
                  {report.report.errors.map((e, i) => (
                    <li key={i}>
                      <strong>{e.file}</strong>
                      {e.hand !== null && ` · mano ${e.hand}`}
                      {e.line !== null && ` · línea ${e.line}`}: {e.message}
                      {e.excerpt && <code className="excerpt">{e.excerpt}</code>}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        )}
      </section>

      <section className="panel" aria-labelledby="hands-title">
        <h3 id="hands-title">Manos{page ? ` (${page.total})` : ''}</h3>
        <FilterBar
          value={filters}
          onChange={(f) => {
            setFilters(f)
            setOffset(0)
          }}
        />
        {page && page.items.length === 0 ? (
          <p className="muted">No hay manos con estos filtros.</p>
        ) : (
          <div className="table-scroll">
            <table className="hands-table">
              <thead>
                <tr>
                  <th scope="col">Fecha</th>
                  <th scope="col">Juego</th>
                  <th scope="col">Pos.</th>
                  <th scope="col">Mano</th>
                  <th scope="col" className="num">
                    Stack
                  </th>
                  <th scope="col" className="num">
                    Resultado
                  </th>
                  <th scope="col">
                    <span className="sr-only">Abrir</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {page?.items.map((h) => (
                  <tr key={h.id}>
                    <td>{new Date(h.played_at).toLocaleString('es')}</td>
                    <td>
                      {FORMAT_LABEL[h.game_type] ?? h.game_type} · {h.table_size}j
                    </td>
                    <td>{h.position ?? '—'}</td>
                    <td>
                      <span className="mini-cards">
                        {splitCards(h.hero_cards).map((c) => (
                          <CardView key={c} card={c} />
                        ))}
                      </span>
                    </td>
                    <td className="num">{h.stack_bb.toFixed(0)}bb</td>
                    <td className={`num ${h.net_bb > 0 ? 'positive' : h.net_bb < 0 ? 'negative' : ''}`}>
                      {h.net_bb > 0 ? '+' : ''}
                      {h.net_bb.toFixed(1)}bb
                    </td>
                    <td>
                      <button type="button" aria-label={`Ver mano ${h.hand_id}`} onClick={() => onOpen(h.id)}>
                        Ver
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {page && page.total > PAGE && (
          <div className="field-row">
            <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
              Anteriores
            </button>
            <span className="small muted">
              {offset + 1}–{Math.min(offset + PAGE, page.total)} de {page.total}
            </span>
            <button type="button" disabled={offset + PAGE >= page.total} onClick={() => setOffset(offset + PAGE)}>
              Siguientes
            </button>
          </div>
        )}
      </section>
    </div>
  )
}
