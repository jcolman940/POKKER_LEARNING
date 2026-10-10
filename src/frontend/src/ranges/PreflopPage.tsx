import { useCallback, useEffect, useState } from 'react'
import { deleteJson, getJson, postJson, putJson } from '../api/client'
import { readStored, writeStored } from '../app/storage'
import type { InitialScenario } from '../simulator/SimulatorPage'
import type { InitialFilters } from '../trainer/types'
import { ChartEditor } from './ChartEditor'
import { ChartManager } from './ChartManager'
import { exportCharts, importCharts } from './chartsApi'
import { PreflopFiltersStep } from './PreflopFiltersStep'
import { defaultFilters, isPreflopFilters, PREFLOP_FILTERS_KEY, type PreflopFilters } from './preflopFilters'
import { DEFAULT_SELECTION, NEW_CHART, type ViewerSelection } from './preflopSelection'
import { PreflopViewer } from './PreflopViewer'
import type { Chart, ChartData } from './types'
import './preflop.css'

type Editing = { mode: 'new'; draft: ChartData } | { mode: 'edit'; chart: Chart } | null

interface Props {
  onOpenSimulator: (scenario: InitialScenario) => void
  onTrain: (filters: InitialFilters) => void
}

const message = (e: unknown) => (e instanceof Error ? e.message : String(e))
const storedOrNull = (v: unknown): v is PreflopFilters | null => v === null || isPreflopFilters(v)

export function PreflopPage({ onOpenSimulator, onTrain }: Props) {
  const [charts, setCharts] = useState<Chart[] | null>(null)
  const [filters, setFilters] = useState<PreflopFilters | null>(() =>
    readStored<PreflopFilters | null>(PREFLOP_FILTERS_KEY, null, storedOrNull),
  )
  const [step, setStep] = useState<'filters' | 'viewer'>(() => (filters ? 'viewer' : 'filters'))
  const [editing, setEditing] = useState<Editing>(null)
  const [managing, setManaging] = useState(false)
  // Lives here so the viewer comes back to the same spot after editing or managing charts.
  const [selection, setSelection] = useState<ViewerSelection>(DEFAULT_SELECTION)
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    try {
      setCharts(await getJson<Chart[]>('/api/charts'))
    } catch (e) {
      setError(message(e))
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    getJson<Chart[]>('/api/charts', controller.signal)
      .then(setCharts)
      .catch((e: unknown) => {
        if (!controller.signal.aborted) setError(message(e))
      })
    return () => controller.abort()
  }, [])

  function apply(f: PreflopFilters) {
    setFilters(f)
    writeStored(PREFLOP_FILTERS_KEY, f)
    setStep('viewer')
  }

  async function save(data: ChartData) {
    if (editing?.mode === 'edit') await putJson<Chart>(`/api/charts/${editing.chart.id}`, data)
    else await postJson<Chart>('/api/charts', data)
    setEditing(null)
    setNotice('Rango guardado.')
    await reload()
  }

  async function remove(chart: Chart) {
    if (!window.confirm(`¿Borrar "${chart.name}"?`)) return
    try {
      await deleteJson(`/api/charts/${chart.id}`)
      await reload()
    } catch (e) {
      setError(message(e))
    }
  }

  async function importFile(file: File) {
    setError(null)
    setNotice(null)
    try {
      const result = await importCharts(file)
      setNotice(`Importados: ${result.created}.`)
      if (result.errors.length) setError(result.errors.join(' · '))
      await reload()
    } catch (e) {
      setError(e instanceof SyntaxError ? 'El archivo no es JSON válido.' : message(e))
    }
  }

  async function exportFile(onlyOwn: boolean) {
    try {
      await exportCharts(onlyOwn)
    } catch (e) {
      setError(message(e))
    }
  }

  if (editing) {
    return (
      <ChartEditor
        initial={editing.mode === 'edit' ? editing.chart : editing.draft}
        onSave={save}
        onCancel={() => setEditing(null)}
      />
    )
  }

  if (charts === null) {
    return error ? (
      <p className="error" role="alert">
        {error}
      </p>
    ) : (
      <p className="muted">Cargando rangos…</p>
    )
  }

  const current = filters ?? defaultFilters(charts)
  return (
    <div className="preflop-page">
      {notice && <p className="small">{notice}</p>}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {managing ? (
        <ChartManager
          charts={charts}
          onEdit={(chart) => setEditing({ mode: 'edit', chart })}
          onDelete={(chart) => void remove(chart)}
          onImport={(file) => void importFile(file)}
          onExport={(onlyOwn) => void exportFile(onlyOwn)}
          onNew={() => setEditing({ mode: 'new', draft: NEW_CHART })}
          onClose={() => setManaging(false)}
        />
      ) : step === 'filters' || charts.length === 0 ? (
        <PreflopFiltersStep
          charts={charts}
          value={current}
          onApply={apply}
          onImport={(file) => void importFile(file)}
          onCreate={() => setEditing({ mode: 'new', draft: NEW_CHART })}
        />
      ) : (
        <PreflopViewer
          charts={charts}
          filters={current}
          onChangeFilters={() => setStep('filters')}
          onEdit={(chart) => setEditing({ mode: 'edit', chart })}
          onCreate={(draft) => setEditing({ mode: 'new', draft })}
          onManage={() => setManaging(true)}
          onOpenSimulator={onOpenSimulator}
          onTrain={onTrain}
          initialSelection={selection}
          onSelectionChange={setSelection}
        />
      )}
    </div>
  )
}
