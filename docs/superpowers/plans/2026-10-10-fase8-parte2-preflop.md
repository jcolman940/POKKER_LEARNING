# Fase 8, parte 2: Preflop (filtros → visor). Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** reemplazar la página "Rangos preflop" por la sección **Preflop** del spec. Primero se eligen los filtros (Juego, Fuente, Stake/rake, Jugadores) y después se ve el visor: secuencia, posición, rival, stack, matriz con leyenda, % del rango y accesos a Simulador y Entrenador. Se conservan el editor y el importar/exportar actuales.

**Architecture:**
- Toda la lógica de filtros, contadores y selección en cascada son funciones puras en `ranges/preflopFilters.ts` y `ranges/preflopSelection.ts`, y la conversión a texto en `ranges/notation.ts`. Así se testean sin DOM.
- Tres componentes chicos (`PreflopFiltersStep`, `PreflopViewer`, `ChartManager`) y un orquestador (`PreflopPage`), que reemplaza a `ChartsPage`.
- Los datos salen de `GET /api/charts` y `GET /api/simulator/positions/{n}`, que ya existen. **El backend no cambia.**

**Tech Stack:** React 19, TypeScript 6, Vite 8, vitest 5 + Testing Library (jsdom), oxlint. Usa los componentes de `src/ui` (parte 1) y `app/storage.ts`.

**Spec:** [`docs/superpowers/specs/2026-10-10-rediseno-ui-design.md`](../specs/2026-10-10-rediseno-ui-design.md) §4. Mockup aprobado: [`docs/superpowers/specs/2026-10-10-rediseno-ui/3-preflop.html`](../specs/2026-10-10-rediseno-ui/3-preflop.html).

## Global Constraints

- **Sin dependencias nuevas.** Solo frontend (`src/frontend/`): no se toca `src/backend`, `src/core` ni `src/launcher`.
- **Datos:** `GET /api/charts` y `GET /api/simulator/positions/{players}`, cargados una vez y recargados después de guardar, borrar o importar. **No se agregan endpoints.**
- **Filtros guardados** en `localStorage`, clave `pokker.preflop.filters`, siempre con `readStored`/`writeStored` (`app/storage.ts`). Si hay filtros guardados válidos, la sección abre en el visor; si no, en el paso de filtros.
- **Etiquetas de Juego:** Cash, Torneos (mtt), Sit & Go (sng), Spin & Go (spin). Se muestran siempre las 4.
- **Etiquetas de la secuencia, en este orden:** Open raise (RFI), vs open, vs 3-bet, vs 4-bet, Squeeze, Ciega vs ciega, vs all-in.
- **"Todas"** (fuente) y **"Todos"** (stake) son la opción `'all'`. Los rangos sin `rake` cuentan solo en "Todos".
- **Rangos repetidos:** por defecto se muestra el más reciente (`updated_at`). Un `Select` permite elegir otro.
- **Paleta y componentes:** los de la parte 1. Nada de colores sueltos: solo variables de `styles/tokens.css`.
- **Texto de la UI en español rioplatense.**
- **Comandos** (desde `src/frontend/`): `npm test`, `npm run typecheck`, `npm run lint` y `npm run build`.
- **Rama** `fase8-preflop`, creada desde `main`. Cada commit termina con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

**Desvío del spec, ya resuelto:** "Entrenar este spot" pasa `sources: ['chart']`. El spec decía `sources: [fuente]`, pero en el entrenador `sources` son sus propias fuentes (`pushfold`, `chart` y `range`), no la fuente del chart (`pokalab`, etc.). `'chart'` es "Tablas preflop", o sea entrenar con tus tablas.

## Review Focus

1. **Filtros guardados que ya no existen** (por ejemplo, un `rake` que se borró, o jugadores=9 sin rangos de 9-max). El paso de filtros muestra igual la opción guardada con contador 0, y el visor muestra el estado vacío "No hay un rango…" sin romperse. Tests en las Tasks 2 y 7.
2. **Rangos sin `rake`** con un stake específico elegido: quedan fuera; con "Todos", entran. Test en la Task 2.
3. **Falla el endpoint de posiciones** (red caída): el visor usa las posiciones que aparecen en los rangos y sigue funcionando. Tests en las Tasks 3 y 6.
4. **Acciones raras en un rango** (por ejemplo, una capa `fold` explícita o una acción desconocida): las estadísticas no cuentan el fold como jugado, y la leyenda usa el nombre crudo si no hay etiqueta. Test en la Task 1.
5. **Portapapeles no disponible** (no hay `navigator.clipboard` o la escritura falla): se muestra "No se pudo copiar el rango." sin romper. Test en la Task 6.

---

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `src/frontend/src/ranges/notation.ts` (nuevo) + test | Pasar una grilla a notación (`AA,AKs:0.5`), un chart a texto (una línea por acción) y calcular el % jugado y los combos. |
| `src/frontend/src/ranges/preflopFilters.ts` (nuevo) + test | Tipo `PreflopFilters`, coincidencias, opciones con contadores cruzados, filtros por defecto, guarda de tipo y resumen para el chip. |
| `src/frontend/src/ranges/preflopSelection.ts` (nuevo) + test | Tipo `ViewerSelection`, opciones del visor, autoselección en cascada, rangos que coinciden y borrador para "Crear este rango" o "Nuevo". |
| `src/frontend/src/test/charts.ts` (nuevo) | `makeChart()`, utilidad solo para tests. |
| `src/frontend/src/ranges/RangeMatrix.tsx` (se modifica) + test | Prop `onHover`. |
| `src/frontend/src/ranges/chartsApi.ts` (nuevo) | `importCharts`, `exportCharts` y `download`, sacados de `ChartsPage`. |
| `src/frontend/src/ranges/PreflopFiltersStep.tsx` (nuevo) + test | Paso 1: 4 tarjetas `RadioList` y Aplicar, o el estado vacío. |
| `src/frontend/src/ranges/PreflopViewer.tsx` (nuevo) + test | Paso 2: el visor. |
| `src/frontend/src/ranges/ChartManager.tsx` (nuevo) | Panel "Importar / exportar": la tabla de rangos de siempre, con Editar y Borrar. |
| `src/frontend/src/ranges/PreflopPage.tsx` (nuevo) + test | Orquesta pasos, persistencia, editor y manager. Reemplaza a `ChartsPage`. |
| `src/frontend/src/ranges/preflop.css` (nuevo) | Layout de la sección. |
| `src/frontend/src/ranges/ChartsPage.tsx` y `ChartsPage.test.tsx` (se borran) | Los reemplazan `PreflopPage` y su test. |
| `src/frontend/src/App.tsx` (se modifica) + `App.test.tsx` | Usa `PreflopPage` con `onOpenSimulator` y `onTrain`. |
| `tests/fixtures/ranges/preflop-review.json` (nuevo) | Set chico de rangos para la recorrida visual. |

---

### Task 1: Notación y estadísticas de un rango

**Files:**
- Create: `src/frontend/src/ranges/notation.ts`
- Test: `src/frontend/src/ranges/notation.test.ts`

**Interfaces:**
- Consumes: `handClassName(index: number): string` de `../simulator/cards`, y `pctOfHands(grid: number[]): number` y `ACTION_LABEL` de `./labels`.
- Produces:
  - `gridToNotation(grid: number[]): string`
  - `chartToText(actions: Record<string, number[]>): string`
  - `rangeStats(actions: Record<string, number[]>): { pct: number; combos: number }`
  - `actionLabel(action: string): string`
  - `formatPct(fraction: number): string`. Ejemplo: `0.421` da `'42,1%'`.

- [ ] **Step 1: Escribir el test que falla**

`src/frontend/src/ranges/notation.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { actionLabel, chartToText, formatPct, gridToNotation, rangeStats } from './notation'

function grid(entries: Record<number, number>): number[] {
  const g = Array<number>(169).fill(0)
  for (const [i, w] of Object.entries(entries)) g[Number(i)] = w
  return g
}

describe('gridToNotation', () => {
  it('lists hand classes in matrix order with PioViewer weights', () => {
    // 0 = AA, 1 = AKs, 13 = AKo, 14 = KK
    expect(gridToNotation(grid({ 0: 1, 1: 0.5, 13: 0.25, 14: 1 }))).toBe('AA,AKs:0.5,AKo:0.25,KK')
  })

  it('rounds weights to 3 decimals and skips zeros', () => {
    expect(gridToNotation(grid({ 0: 0.33333, 1: 0 }))).toBe('AA:0.333')
  })

  it('is empty for an empty grid', () => {
    expect(gridToNotation(grid({}))).toBe('')
  })
})

describe('chartToText', () => {
  it('writes one line per action that has hands, with its label', () => {
    expect(chartToText({ raise: grid({ 0: 1 }), call: grid({}), '3bet': grid({ 1: 0.5 }) })).toBe(
      'Raise: AA\n3-bet: AKs:0.5',
    )
  })
})

describe('rangeStats', () => {
  it('counts played combos and ignores explicit fold layers', () => {
    // AA = 6 combos; fold on KK must not count
    const s = rangeStats({ raise: grid({ 0: 1 }), fold: grid({ 14: 1 }) })
    expect(s.combos).toBe(6)
    expect(s.pct).toBeCloseTo(6 / 1326, 6)
  })

  it('caps a cell at 100% when several actions overlap', () => {
    const s = rangeStats({ raise: grid({ 0: 0.8 }), call: grid({ 0: 0.8 }) })
    expect(s.combos).toBe(6)
  })
})

describe('labels and percentages', () => {
  it('uses the Spanish label and falls back to the raw action', () => {
    expect(actionLabel('3bet')).toBe('3-bet')
    expect(actionLabel('minraise')).toBe('minraise')
  })

  it('formats with a decimal comma', () => {
    expect(formatPct(0.421)).toBe('42,1%')
    expect(formatPct(0)).toBe('0,0%')
  })
})
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd src/frontend && npx vitest run src/ranges/notation.test.ts`
Expected: FAIL porque no se puede resolver `./notation`.

- [ ] **Step 3: Escribir la implementación**

`src/frontend/src/ranges/notation.ts`:

```ts
import { handClassName } from '../simulator/cards'
import { ACTION_LABEL, pctOfHands } from './labels'

/** `AA,AKs:0.5,...` in matrix order (PioViewer / ProPokerTools weights). */
export function gridToNotation(grid: number[]): string {
  const parts: string[] = []
  grid.forEach((w, i) => {
    if (w <= 0) return
    const rounded = Math.round(w * 1000) / 1000
    parts.push(rounded >= 1 ? handClassName(i) : `${handClassName(i)}:${rounded}`)
  })
  return parts.join(',')
}

export function actionLabel(action: string): string {
  return ACTION_LABEL[action] ?? action
}

/** One line per action that has hands: `Raise: AA,AKs:0.5`. */
export function chartToText(actions: Record<string, number[]>): string {
  return Object.entries(actions)
    .map(([action, grid]) => [action, gridToNotation(grid)] as const)
    .filter(([, notation]) => notation !== '')
    .map(([action, notation]) => `${actionLabel(action)}: ${notation}`)
    .join('\n')
}

/** Share of the 1326 combos played (any action but fold), each cell capped at 100%. */
export function rangeStats(actions: Record<string, number[]>): { pct: number; combos: number } {
  const played = Array<number>(169).fill(0)
  for (const [action, grid] of Object.entries(actions)) {
    if (action === 'fold') continue
    grid.forEach((w, i) => {
      played[i] = Math.min(1, played[i] + w)
    })
  }
  const pct = pctOfHands(played)
  return { pct, combos: Math.round(pct * 1326) }
}

export function formatPct(fraction: number): string {
  return `${(fraction * 100).toFixed(1).replace('.', ',')}%`
}
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `cd src/frontend && npx vitest run src/ranges/notation.test.ts`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/ranges/notation.ts src/frontend/src/ranges/notation.test.ts
git commit -m "feat(preflop): range notation, text export and played-range stats"
```

---

### Task 2: Filtros del paso 1 (funciones puras)

**Files:**
- Create: `src/frontend/src/test/charts.ts`
- Create: `src/frontend/src/ranges/preflopFilters.ts`
- Test: `src/frontend/src/ranges/preflopFilters.test.ts`

**Interfaces:**
- Consumes: `Chart` de `./types`, `SOURCE_LABEL` de `./labels` y `Option` de `../ui`.
- Produces:
  - `ALL = 'all'`
  - `PREFLOP_FILTERS_KEY = 'pokker.preflop.filters'`
  - `interface PreflopFilters { format: string; source: string; rake: string; players: number }`
  - `FORMAT_LABELS: readonly (readonly [string, string])[]`
  - `chartMatches(c: Chart, f: PreflopFilters, ignore?: keyof PreflopFilters): boolean`
  - `applyFilters(charts: Chart[], f: PreflopFilters): Chart[]`
  - `interface FilterOptions { formats: Option<string>[]; sources: Option<string>[]; rakes: Option<string>[]; players: Option<string>[] }`
  - `filterOptions(charts: Chart[], f: PreflopFilters): FilterOptions`
  - `defaultFilters(charts: Chart[]): PreflopFilters`
  - `isPreflopFilters(v: unknown): v is PreflopFilters`
  - `filtersSummary(f: PreflopFilters): string`
  - En `src/test/charts.ts`: `makeChart(o?: Partial<Chart>): Chart`. Las Tasks 2, 3, 6 y 7 lo usan.

- [ ] **Step 1: Escribir la utilidad de tests**

`src/frontend/src/test/charts.ts`:

```ts
import type { Chart } from '../ranges/types'

let nextId = 1

/** A valid chart for tests: cash 6-max BTN RFI 100bb raising AA unless overridden. */
export function makeChart(o: Partial<Chart> = {}): Chart {
  const raise = Array<number>(169).fill(0)
  raise[0] = 1
  return {
    id: nextId++,
    name: 'BTN RFI 100bb',
    source: 'pokalab',
    game_format: 'cash',
    players: 6,
    position: 'BTN',
    vs_position: null,
    stack_bb: 100,
    situation: 'rfi',
    open_size_bb: 2.5,
    rake: null,
    ante_bb: 0,
    note: '',
    actions: { raise },
    created_at: '2026-10-01T00:00:00',
    updated_at: '2026-10-01T00:00:00',
    ...o,
  }
}
```

- [ ] **Step 2: Escribir el test que falla**

`src/frontend/src/ranges/preflopFilters.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { makeChart } from '../test/charts'
import {
  ALL,
  applyFilters,
  defaultFilters,
  filterOptions,
  filtersSummary,
  isPreflopFilters,
  type PreflopFilters,
} from './preflopFilters'

const CHARTS = [
  makeChart({ game_format: 'cash', players: 6, source: 'pokalab', rake: 'GG NL50' }),
  makeChart({ game_format: 'cash', players: 6, source: 'custom', rake: null }),
  makeChart({ game_format: 'cash', players: 9, source: 'pokalab', rake: 'GG NL50' }),
  makeChart({ game_format: 'mtt', players: 9, source: 'computed', rake: null }),
]

const CASH6: PreflopFilters = { format: 'cash', source: ALL, rake: ALL, players: 6 }
const count = (opts: { value: string; count?: number }[], value: string) => opts.find((o) => o.value === value)?.count

describe('applyFilters', () => {
  it('keeps charts matching every filter; "all" ignores source and rake', () => {
    expect(applyFilters(CHARTS, CASH6)).toHaveLength(2)
  })

  it('a specific rake drops charts without rake', () => {
    expect(applyFilters(CHARTS, { ...CASH6, rake: 'GG NL50' })).toHaveLength(1)
  })
})

describe('filterOptions', () => {
  it('always lists the 4 game formats, counted against the other filters', () => {
    const o = filterOptions(CHARTS, CASH6)
    expect(o.formats.map((x) => x.label)).toEqual(['Cash', 'Torneos', 'Sit & Go', 'Spin & Go'])
    expect(count(o.formats, 'cash')).toBe(2) // cash with 6 players
    expect(count(o.formats, 'mtt')).toBe(0) // the mtt chart is 9-max
  })

  it('counts players across formats only within the chosen format', () => {
    const o = filterOptions(CHARTS, CASH6)
    expect(o.players.map((x) => x.label)).toEqual(['6-max', '9-max'])
    expect(count(o.players, '6')).toBe(2)
    expect(count(o.players, '9')).toBe(1)
  })

  it('lists present sources and rakes after the "all" option', () => {
    const o = filterOptions(CHARTS, CASH6)
    expect(o.sources.map((x) => x.value)).toEqual([ALL, 'pokalab', 'custom', 'computed'])
    expect(o.sources[0].label).toBe('Todas')
    expect(count(o.sources, ALL)).toBe(2)
    expect(o.rakes.map((x) => x.value)).toEqual([ALL, 'GG NL50'])
    expect(o.rakes[0].label).toBe('Todos')
  })

  it('keeps a stored value that no longer exists, with count 0', () => {
    const o = filterOptions(CHARTS, { ...CASH6, rake: 'PS NL10', players: 8 })
    expect(o.rakes.find((x) => x.value === 'PS NL10')).toMatchObject({ count: 0 })
    expect(o.players.find((x) => x.value === '8')).toMatchObject({ label: '8-max', count: 0 })
  })

  it('offers 6-max and 9-max when there are no charts', () => {
    expect(filterOptions([], CASH6).players.map((x) => x.value)).toEqual(['6', '9'])
  })
})

describe('defaultFilters', () => {
  it('picks the first format with charts and its most common table size', () => {
    expect(defaultFilters(CHARTS)).toEqual({ format: 'cash', source: ALL, rake: ALL, players: 6 })
    expect(defaultFilters([makeChart({ game_format: 'mtt', players: 9 })])).toMatchObject({
      format: 'mtt',
      players: 9,
    })
  })

  it('falls back to cash 6-max with no charts', () => {
    expect(defaultFilters([])).toEqual(CASH6)
  })
})

describe('isPreflopFilters', () => {
  it('accepts a valid object and rejects anything else', () => {
    expect(isPreflopFilters(CASH6)).toBe(true)
    expect(isPreflopFilters({ ...CASH6, players: '6' })).toBe(false)
    expect(isPreflopFilters({ ...CASH6, players: 1 })).toBe(false)
    expect(isPreflopFilters({ format: 'cash' })).toBe(false)
    expect(isPreflopFilters(null)).toBe(false)
    expect(isPreflopFilters('cash')).toBe(false)
  })
})

describe('filtersSummary', () => {
  it('reads like the mockup chip', () => {
    expect(filtersSummary(CASH6)).toBe('Cash · Todas las fuentes · Todos los stakes · 6-max')
    expect(filtersSummary({ format: 'mtt', source: 'pokalab', rake: 'GG NL50', players: 9 })).toBe(
      'Torneos · Pokalab · GG NL50 · 9-max',
    )
  })
})
```

- [ ] **Step 3: Correr el test y verificar que falla**

Run: `cd src/frontend && npx vitest run src/ranges/preflopFilters.test.ts`
Expected: FAIL porque no se puede resolver `./preflopFilters`.

- [ ] **Step 4: Escribir la implementación**

`src/frontend/src/ranges/preflopFilters.ts`:

```ts
import type { Option } from '../ui'
import { SOURCE_LABEL, SOURCES } from './labels'
import type { Chart } from './types'

export const ALL = 'all'
export const PREFLOP_FILTERS_KEY = 'pokker.preflop.filters'

export interface PreflopFilters {
  format: string
  source: string
  rake: string
  players: number
}

export const FORMAT_LABELS = [
  ['cash', 'Cash'],
  ['mtt', 'Torneos'],
  ['sng', 'Sit & Go'],
  ['spin', 'Spin & Go'],
] as const

export function chartMatches(c: Chart, f: PreflopFilters, ignore?: keyof PreflopFilters): boolean {
  return (
    (ignore === 'format' || c.game_format === f.format) &&
    (ignore === 'source' || f.source === ALL || c.source === f.source) &&
    (ignore === 'rake' || f.rake === ALL || c.rake === f.rake) &&
    (ignore === 'players' || c.players === f.players)
  )
}

export function applyFilters(charts: Chart[], f: PreflopFilters): Chart[] {
  return charts.filter((c) => chartMatches(c, f))
}

export interface FilterOptions {
  formats: Option<string>[]
  sources: Option<string>[]
  rakes: Option<string>[]
  players: Option<string>[]
}

function unique<T>(values: T[]): T[] {
  return [...new Set(values)]
}

/** Each card counts the charts that match the other three filters. */
export function filterOptions(charts: Chart[], f: PreflopFilters): FilterOptions {
  const count = (ignore: keyof PreflopFilters, pred: (c: Chart) => boolean) =>
    charts.filter((c) => chartMatches(c, f, ignore) && pred(c)).length
  const withCurrent = (opts: Option<string>[], current: string, label: string) =>
    opts.some((o) => o.value === current) ? opts : [...opts, { value: current, label, count: 0 }]

  const formats = FORMAT_LABELS.map(([value, label]) => ({
    value,
    label,
    count: count('format', (c) => c.game_format === value),
  }))

  const known = SOURCES.map(([v]) => v as string)
  const present = unique(charts.map((c) => c.source))
  const sourceValues = [...known.filter((v) => present.includes(v)), ...present.filter((v) => !known.includes(v))]
  const sources = withCurrent(
    [
      { value: ALL, label: 'Todas', count: count('source', () => true) },
      ...sourceValues.map((v) => ({ value: v, label: SOURCE_LABEL[v] ?? v, count: count('source', (c) => c.source === v) })),
    ],
    f.source,
    SOURCE_LABEL[f.source] ?? f.source,
  )

  const rakeValues = unique(charts.map((c) => c.rake).filter((r): r is string => !!r)).sort()
  const rakes = withCurrent(
    [
      { value: ALL, label: 'Todos', count: count('rake', () => true) },
      ...rakeValues.map((v) => ({ value: v, label: v, count: count('rake', (c) => c.rake === v) })),
    ],
    f.rake,
    f.rake,
  )

  const presentPlayers = unique(charts.map((c) => c.players)).sort((a, b) => a - b)
  const playerValues = presentPlayers.length ? presentPlayers : [6, 9]
  const players = withCurrent(
    playerValues.map((n) => ({ value: String(n), label: `${n}-max`, count: count('players', (c) => c.players === n) })),
    String(f.players),
    `${f.players}-max`,
  )

  return { formats, sources, rakes, players }
}

export function defaultFilters(charts: Chart[]): PreflopFilters {
  const format = FORMAT_LABELS.find(([v]) => charts.some((c) => c.game_format === v))?.[0] ?? 'cash'
  const sizes = new Map<number, number>()
  for (const c of charts) if (c.game_format === format) sizes.set(c.players, (sizes.get(c.players) ?? 0) + 1)
  const players = [...sizes].sort((a, b) => b[1] - a[1] || a[0] - b[0])[0]?.[0] ?? 6
  return { format, source: ALL, rake: ALL, players }
}

export function isPreflopFilters(v: unknown): v is PreflopFilters {
  if (typeof v !== 'object' || v === null) return false
  const o = v as Record<string, unknown>
  return (
    typeof o.format === 'string' &&
    typeof o.source === 'string' &&
    typeof o.rake === 'string' &&
    typeof o.players === 'number' &&
    Number.isInteger(o.players) &&
    o.players >= 2 &&
    o.players <= 10
  )
}

export function filtersSummary(f: PreflopFilters): string {
  const format = FORMAT_LABELS.find(([v]) => v === f.format)?.[1] ?? f.format
  const source = f.source === ALL ? 'Todas las fuentes' : (SOURCE_LABEL[f.source] ?? f.source)
  const rake = f.rake === ALL ? 'Todos los stakes' : f.rake
  return `${format} · ${source} · ${rake} · ${f.players}-max`
}
```

- [ ] **Step 5: Correr el test y verificar que pasa**

Run: `cd src/frontend && npx vitest run src/ranges/preflopFilters.test.ts`
Expected: PASS (11 tests).

- [ ] **Step 6: Commit**

```bash
git add src/frontend/src/test/charts.ts src/frontend/src/ranges/preflopFilters.ts src/frontend/src/ranges/preflopFilters.test.ts
git commit -m "feat(preflop): filter step logic with cross counts and safe defaults"
```

---

### Task 3: Selección del visor (funciones puras)

**Files:**
- Create: `src/frontend/src/ranges/preflopSelection.ts`
- Test: `src/frontend/src/ranges/preflopSelection.test.ts`

**Interfaces:**
- Consumes: `Chart` y `ChartData` de `./types`, `SITUATIONS` de `./labels`, `Option` de `../ui`, y `ALL` y `PreflopFilters` de `./preflopFilters`.
- Produces:
  - `interface ViewerSelection { situation: string; position: string; vsPosition: string | null; stack: number | null }`
  - `DEFAULT_SELECTION: ViewerSelection`, que es `{ situation: 'rfi', position: 'BTN', vsPosition: null, stack: 100 }`
  - `situationText(s: string): string`
  - `interface ViewerOptions { situations: Option<string>[]; positions: Option<string>[]; vsPositions: Option<string>[]; stacks: number[] }`
  - `viewerOptions(charts: Chart[], positions: string[], sel: ViewerSelection): ViewerOptions`
  - `resolveSelection(charts: Chart[], positions: string[], sel: ViewerSelection): ViewerSelection`
  - `matchingCharts(charts: Chart[], sel: ViewerSelection): Chart[]`, ordenados por `updated_at` descendente
  - `draftFor(filters: PreflopFilters, sel: ViewerSelection): ChartData`
  - `NEW_CHART: ChartData`, que es `draftFor` con los filtros y la selección por defecto

En todas estas funciones, `charts` son los **ya filtrados** por el paso 1, y `positions` es la lista del endpoint (puede venir vacía si falló). A esa lista se le suman al final las posiciones de los rangos que no estén en ella.

- [ ] **Step 1: Escribir el test que falla**

`src/frontend/src/ranges/preflopSelection.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { makeChart } from '../test/charts'
import { ALL } from './preflopFilters'
import {
  DEFAULT_SELECTION,
  draftFor,
  matchingCharts,
  resolveSelection,
  situationText,
  viewerOptions,
} from './preflopSelection'

const SIX = ['LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']
const CHARTS = [
  makeChart({ id: 1, position: 'BTN', situation: 'rfi', stack_bb: 100 }),
  makeChart({ id: 2, position: 'BTN', situation: 'rfi', stack_bb: 40 }),
  makeChart({ id: 3, position: 'CO', situation: 'rfi', stack_bb: 100 }),
  makeChart({ id: 4, position: 'BB', situation: 'vs_open', vs_position: 'BTN', stack_bb: 100 }),
  makeChart({ id: 5, position: 'BB', situation: 'vs_open', vs_position: 'CO', stack_bb: 100 }),
]

describe('viewerOptions', () => {
  it('lists situations in spec order and dims those without charts', () => {
    const o = viewerOptions(CHARTS, SIX, DEFAULT_SELECTION)
    expect(o.situations.map((s) => s.label)).toEqual([
      'Open raise (RFI)',
      'vs open',
      'vs 3-bet',
      'vs 4-bet',
      'Squeeze',
      'Ciega vs ciega',
      'vs all-in',
    ])
    expect(o.situations.filter((s) => !s.disabled).map((s) => s.value)).toEqual(['rfi', 'vs_open'])
  })

  it('dims positions without a chart for the situation; no rival row in RFI', () => {
    const o = viewerOptions(CHARTS, SIX, DEFAULT_SELECTION)
    expect(o.positions.filter((p) => !p.disabled).map((p) => p.value)).toEqual(['CO', 'BTN'])
    expect(o.vsPositions).toEqual([])
    expect(o.stacks).toEqual([40, 100])
  })

  it('offers rivals in table order for situations that have one', () => {
    const o = viewerOptions(CHARTS, SIX, { situation: 'vs_open', position: 'BB', vsPosition: 'CO', stack: 100 })
    expect(o.vsPositions.map((v) => v.value)).toEqual(['CO', 'BTN'])
  })

  it('falls back to the positions found in the charts when the endpoint list is empty', () => {
    const o = viewerOptions(CHARTS, [], DEFAULT_SELECTION)
    expect(o.positions.map((p) => p.value)).toEqual(['BTN', 'CO', 'BB'])
  })
})

describe('resolveSelection', () => {
  it('keeps a valid selection', () => {
    expect(resolveSelection(CHARTS, SIX, DEFAULT_SELECTION)).toEqual(DEFAULT_SELECTION)
  })

  it('cascades: missing position → first available, missing rival → first rival', () => {
    const s = resolveSelection(CHARTS, SIX, { situation: 'vs_open', position: 'BTN', vsPosition: null, stack: 100 })
    expect(s).toEqual({ situation: 'vs_open', position: 'BB', vsPosition: 'CO', stack: 100 })
  })

  it('moves to the first situation with charts and the closest stack', () => {
    const s = resolveSelection(CHARTS, SIX, { situation: 'squeeze', position: 'BTN', vsPosition: 'SB', stack: 50 })
    expect(s).toEqual({ situation: 'rfi', position: 'BTN', vsPosition: null, stack: 40 })
  })

  it('leaves the selection alone when nothing matches the filters', () => {
    expect(resolveSelection([], SIX, DEFAULT_SELECTION)).toEqual(DEFAULT_SELECTION)
  })
})

describe('matchingCharts', () => {
  it('returns duplicates newest first', () => {
    const older = makeChart({ id: 10, source: 'pokalab', updated_at: '2026-10-01T00:00:00' })
    const newer = makeChart({ id: 11, source: 'custom', updated_at: '2026-10-05T00:00:00' })
    expect(matchingCharts([older, newer], DEFAULT_SELECTION).map((c) => c.id)).toEqual([11, 10])
  })

  it('matches the rival exactly', () => {
    const sel = { situation: 'vs_open', position: 'BB', vsPosition: 'BTN', stack: 100 }
    expect(matchingCharts(CHARTS, sel).map((c) => c.id)).toEqual([4])
  })
})

describe('draftFor', () => {
  it('pre-fills a custom chart with the visible context', () => {
    const d = draftFor(
      { format: 'mtt', source: ALL, rake: 'GG NL50', players: 9 },
      { situation: 'vs_open', position: 'BB', vsPosition: 'BTN', stack: 40 },
    )
    expect(d).toMatchObject({
      source: 'custom',
      game_format: 'mtt',
      players: 9,
      position: 'BB',
      vs_position: 'BTN',
      situation: 'vs_open',
      stack_bb: 40,
      open_size_bb: null,
      rake: 'GG NL50',
    })
    expect(d.actions.raise).toHaveLength(169)
  })

  it('has an open size for RFI and no rake for "all"', () => {
    const d = draftFor({ format: 'cash', source: ALL, rake: ALL, players: 6 }, DEFAULT_SELECTION)
    expect(d.open_size_bb).toBe(2.5)
    expect(d.rake).toBeNull()
  })
})

describe('situationText', () => {
  it('uses the viewer labels', () => {
    expect(situationText('bvb')).toBe('Ciega vs ciega')
  })
})
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd src/frontend && npx vitest run src/ranges/preflopSelection.test.ts`
Expected: FAIL porque no se puede resolver `./preflopSelection`.

- [ ] **Step 3: Escribir la implementación**

`src/frontend/src/ranges/preflopSelection.ts`:

```ts
import type { Option } from '../ui'
import { SITUATIONS } from './labels'
import { ALL, type PreflopFilters } from './preflopFilters'
import type { Chart, ChartData } from './types'

export interface ViewerSelection {
  situation: string
  position: string
  vsPosition: string | null
  stack: number | null
}

export const DEFAULT_SELECTION: ViewerSelection = { situation: 'rfi', position: 'BTN', vsPosition: null, stack: 100 }

const SITUATION_TEXT: Record<string, string> = {
  rfi: 'Open raise (RFI)',
  vs_open: 'vs open',
  vs_3bet: 'vs 3-bet',
  vs_4bet: 'vs 4-bet',
  squeeze: 'Squeeze',
  bvb: 'Ciega vs ciega',
  vs_allin: 'vs all-in',
}

export function situationText(s: string): string {
  return SITUATION_TEXT[s] ?? s
}

export interface ViewerOptions {
  situations: Option<string>[]
  positions: Option<string>[]
  vsPositions: Option<string>[]
  stacks: number[]
}

function unique<T>(values: T[]): T[] {
  return [...new Set(values)]
}

function tableOrder(positions: string[], charts: Chart[]): string[] {
  return unique([...positions, ...charts.map((c) => c.position)])
}

export function viewerOptions(charts: Chart[], positions: string[], sel: ViewerSelection): ViewerOptions {
  const order = tableOrder(positions, charts)
  const inSituation = charts.filter((c) => c.situation === sel.situation)
  const atPosition = inSituation.filter((c) => c.position === sel.position)

  const situations = SITUATIONS.map(([value]) => ({
    value,
    label: situationText(value),
    disabled: !charts.some((c) => c.situation === value),
  }))
  const positionOpts = order.map((p) => ({ value: p, label: p, disabled: !inSituation.some((c) => c.position === p) }))

  const rivals =
    sel.situation === 'rfi'
      ? []
      : unique(atPosition.map((c) => c.vs_position).filter((v): v is string => !!v)).sort(
          (a, b) => order.indexOf(a) - order.indexOf(b),
        )
  const vsPositions = rivals.map((v) => ({ value: v, label: v }))

  const forStack = rivals.length === 0 ? atPosition : atPosition.filter((c) => c.vs_position === sel.vsPosition)
  const stacks = unique(forStack.map((c) => c.stack_bb)).sort((a, b) => a - b)

  return { situations, positions: positionOpts, vsPositions, stacks }
}

function closest(values: number[], target: number | null): number {
  if (target === null) return values[values.length - 1]
  return values.reduce((best, v) => {
    const d = Math.abs(v - target)
    const bd = Math.abs(best - target)
    return d < bd || (d === bd && v > best) ? v : best
  })
}

/** Each control falls back to the first available value when the current one has no charts. */
export function resolveSelection(charts: Chart[], positions: string[], sel: ViewerSelection): ViewerSelection {
  const s = { ...sel }
  const firstEnabled = (opts: Option<string>[]) => opts.find((o) => !o.disabled)?.value

  let o = viewerOptions(charts, positions, s)
  if (o.situations.find((x) => x.value === s.situation)?.disabled !== false) {
    s.situation = firstEnabled(o.situations) ?? s.situation
    o = viewerOptions(charts, positions, s)
  }
  if (o.positions.find((x) => x.value === s.position)?.disabled !== false) {
    s.position = firstEnabled(o.positions) ?? s.position
    o = viewerOptions(charts, positions, s)
  }
  if (o.vsPositions.length === 0) s.vsPosition = null
  else if (!o.vsPositions.some((x) => x.value === s.vsPosition)) s.vsPosition = o.vsPositions[0].value
  o = viewerOptions(charts, positions, s)
  if (o.stacks.length > 0 && (s.stack === null || !o.stacks.includes(s.stack))) s.stack = closest(o.stacks, s.stack)
  return s
}

export function matchingCharts(charts: Chart[], sel: ViewerSelection): Chart[] {
  return charts
    .filter(
      (c) =>
        c.situation === sel.situation &&
        c.position === sel.position &&
        (c.vs_position ?? null) === sel.vsPosition &&
        c.stack_bb === sel.stack,
    )
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
}

/** Editor draft for "Nuevo" / "Crear este rango": the visible context as a custom chart. */
export function draftFor(filters: PreflopFilters, sel: ViewerSelection): ChartData {
  return {
    name: '',
    source: 'custom',
    game_format: filters.format,
    players: filters.players,
    position: sel.position,
    vs_position: sel.vsPosition,
    stack_bb: sel.stack ?? 100,
    situation: sel.situation,
    open_size_bb: sel.situation === 'rfi' ? 2.5 : null,
    rake: filters.rake === ALL ? null : filters.rake,
    ante_bb: 0,
    note: '',
    actions: { raise: Array<number>(169).fill(0) },
  }
}

export const NEW_CHART: ChartData = draftFor({ format: 'cash', source: ALL, rake: ALL, players: 6 }, DEFAULT_SELECTION)
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `cd src/frontend && npx vitest run src/ranges/preflopSelection.test.ts`
Expected: PASS (13 tests).

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/ranges/preflopSelection.ts src/frontend/src/ranges/preflopSelection.test.ts
git commit -m "feat(preflop): viewer options, cascading selection and chart drafts"
```

---

### Task 4: `RangeMatrix` avisa la celda bajo el mouse

**Files:**
- Modify: `src/frontend/src/ranges/RangeMatrix.tsx` (interfaz `Props`, el `<div className="matrix">` y los dos tipos de celda)
- Test: `src/frontend/src/ranges/RangeMatrix.test.tsx` (ya existe desde la parte 1; se agrega un `describe`)

**Interfaces:**
- Produces: prop opcional `onHover?: (index: number | null) => void`. Recibe el índice 0–168 al entrar en una celda y `null` al salir de la matriz.

- [ ] **Step 1: Escribir el test que falla**

Agregar al final de `src/frontend/src/ranges/RangeMatrix.test.tsx`. Sumá `fireEvent` y `vi` a los imports existentes: `import { fireEvent, render } from '@testing-library/react'` y `import { describe, expect, it, vi } from 'vitest'`.

```tsx
describe('RangeMatrix hover', () => {
  it('reports the hovered cell and null when leaving the matrix', () => {
    const onHover = vi.fn()
    const { container } = render(<RangeMatrix layers={[{ action: 'raise', grid: grid(1) }]} onHover={onHover} />)
    fireEvent.pointerEnter(container.querySelector('[title^="AKs:"]')!)
    expect(onHover).toHaveBeenLastCalledWith(1)
    fireEvent.pointerLeave(container.querySelector('.matrix')!)
    expect(onHover).toHaveBeenLastCalledWith(null)
  })

  it('also reports while painting cells in the editor', () => {
    const onHover = vi.fn()
    const { container } = render(
      <RangeMatrix layers={[{ action: 'raise', grid: grid(0) }]} onPaint={() => {}} onHover={onHover} />,
    )
    fireEvent.pointerEnter(container.querySelector('button[title^="KK:"]')!)
    expect(onHover).toHaveBeenLastCalledWith(14)
  })
})
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd src/frontend && npx vitest run src/ranges/RangeMatrix.test.tsx`
Expected: FAIL en los 2 tests nuevos (`onHover` nunca se llama). Los 2 tests de la parte 1 siguen en PASS.

- [ ] **Step 3: Implementar**

En `src/frontend/src/ranges/RangeMatrix.tsx`:

1. En `interface Props`, agregar:

```ts
  /** Index (0-168) of the cell under the pointer; null when the pointer leaves the matrix. */
  onHover?: (index: number | null) => void
```

2. En la firma de la función, agregar `onHover` a la desestructuración: `export function RangeMatrix({ layers, onPaint, detail, caption, implicitFold = true, highlight, onHover }: Props)`.
3. En el `<div className="matrix" …>`, agregar `onPointerLeave={() => onHover?.(null)}`.
4. En el `<span …>` de solo lectura, agregar `onPointerEnter={onHover ? () => onHover(i) : undefined}`.
5. En el `<button …>`, reemplazar el `onPointerEnter` existente por:

```tsx
            onPointerEnter={() => {
              onHover?.(i)
              if (painting.current) onPaint(i)
            }}
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `cd src/frontend && npx vitest run src/ranges/RangeMatrix.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/ranges/RangeMatrix.tsx src/frontend/src/ranges/RangeMatrix.test.tsx
git commit -m "feat(preflop): RangeMatrix reports the hovered cell"
```

---

### Task 5: Paso 1, filtros (`PreflopFiltersStep`)

**Files:**
- Create: `src/frontend/src/ranges/PreflopFiltersStep.tsx`
- Create: `src/frontend/src/ranges/preflop.css`
- Test: `src/frontend/src/ranges/PreflopFiltersStep.test.tsx`

**Interfaces:**
- Consumes: `filterOptions` y `PreflopFilters` (Task 2), y `Button` y `RadioList` de `../ui`.
- Produces: `PreflopFiltersStep(props: { charts: Chart[]; value: PreflopFilters; onApply: (f: PreflopFilters) => void; onImport: (file: File) => void; onCreate: () => void })`. Su estado interno arranca en `value` y solo avisa al tocar "Aplicar".

- [ ] **Step 1: Escribir el test que falla**

`src/frontend/src/ranges/PreflopFiltersStep.test.tsx`:

```tsx
import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { makeChart } from '../test/charts'
import { PreflopFiltersStep } from './PreflopFiltersStep'
import { ALL } from './preflopFilters'

const VALUE = { format: 'cash', source: ALL, rake: ALL, players: 6 }

describe('PreflopFiltersStep', () => {
  it('shows the four filter cards with counts and applies the chosen filters', () => {
    const onApply = vi.fn()
    const charts = [
      makeChart({ game_format: 'cash', players: 6 }),
      makeChart({ game_format: 'mtt', players: 9, rake: 'GG NL50' }),
    ]
    render(<PreflopFiltersStep charts={charts} value={VALUE} onApply={onApply} onImport={() => {}} onCreate={() => {}} />)
    for (const name of ['Juego', 'Fuente', 'Stake / rake', 'Jugadores']) {
      expect(screen.getByRole('group', { name })).toBeInTheDocument()
    }
    const juego = screen.getByRole('group', { name: 'Juego' })
    expect(within(juego).getByRole('radio', { name: /Cash/ })).toBeChecked()

    fireEvent.click(within(juego).getByRole('radio', { name: /Torneos/ }))
    fireEvent.click(within(screen.getByRole('group', { name: 'Jugadores' })).getByRole('radio', { name: /9-max/ }))
    expect(onApply).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar' }))
    expect(onApply).toHaveBeenCalledWith({ format: 'mtt', source: ALL, rake: ALL, players: 9 })
  })

  it('without charts offers to import or create instead of filters', () => {
    const onCreate = vi.fn()
    const onImport = vi.fn()
    render(<PreflopFiltersStep charts={[]} value={VALUE} onApply={() => {}} onImport={onImport} onCreate={onCreate} />)
    expect(screen.getByRole('heading', { name: 'Todavía no hay rangos' })).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: 'Juego' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Crear rango' }))
    expect(onCreate).toHaveBeenCalledOnce()
    const file = new File(['{}'], 'set.json', { type: 'application/json' })
    fireEvent.change(screen.getByLabelText('Importar set (.json)'), { target: { files: [file] } })
    expect(onImport).toHaveBeenCalledWith(file)
  })
})
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd src/frontend && npx vitest run src/ranges/PreflopFiltersStep.test.tsx`
Expected: FAIL porque no se puede resolver `./PreflopFiltersStep`.

- [ ] **Step 3: Escribir el componente y el CSS**

`src/frontend/src/ranges/PreflopFiltersStep.tsx`:

```tsx
import { useState } from 'react'
import { Button, RadioList } from '../ui'
import { filterOptions, type PreflopFilters } from './preflopFilters'
import type { Chart } from './types'

interface Props {
  charts: Chart[]
  value: PreflopFilters
  onApply: (filters: PreflopFilters) => void
  onImport: (file: File) => void
  onCreate: () => void
}

export function PreflopFiltersStep({ charts, value, onApply, onImport, onCreate }: Props) {
  const [f, setF] = useState(value)

  if (charts.length === 0) {
    return (
      <section className="panel preflop-empty" aria-labelledby="preflop-empty-title">
        <h2 id="preflop-empty-title" className="preflop-title">
          Todavía no hay rangos
        </h2>
        <p className="muted">Importá un set de rangos (.json) o creá uno propio para empezar.</p>
        <div className="field-row">
          <label className="file-button">
            Importar set (.json)
            <input
              type="file"
              accept=".json,application/json"
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) onImport(file)
                e.target.value = ''
              }}
            />
          </label>
          <Button variant="primary" onClick={onCreate}>
            Crear rango
          </Button>
        </div>
      </section>
    )
  }

  const o = filterOptions(charts, f)
  return (
    <section className="preflop-filters" aria-labelledby="preflop-filters-title">
      <h2 id="preflop-filters-title" className="preflop-title">
        Elegí tus filtros
      </h2>
      <div className="preflop-filter-cards">
        <RadioList legend="Juego" options={o.formats} value={f.format} onChange={(format) => setF({ ...f, format })} />
        <RadioList legend="Fuente" options={o.sources} value={f.source} onChange={(source) => setF({ ...f, source })} />
        <RadioList legend="Stake / rake" options={o.rakes} value={f.rake} onChange={(rake) => setF({ ...f, rake })} />
        <RadioList
          legend="Jugadores"
          options={o.players}
          value={String(f.players)}
          onChange={(p) => setF({ ...f, players: Number(p) })}
        />
      </div>
      <div>
        <Button variant="primary" onClick={() => onApply(f)}>
          Aplicar
        </Button>
      </div>
      <p className="muted small">
        Las opciones salen de los rangos que tenés cargados; el número es cuántos hay con el resto de los filtros.
      </p>
    </section>
  )
}
```

`src/frontend/src/ranges/preflop.css`:

```css
.preflop-page,
.preflop-filters,
.preflop-viewer {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.preflop-title {
  margin: 0;
  font-size: 22px;
  font-weight: 800;
}

.preflop-filter-cards {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-3);
}

.preflop-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.preflop-tools {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.preflop-body {
  display: grid;
  grid-template-columns: 170px minmax(0, 1fr) 200px;
  gap: var(--space-5);
  align-items: start;
}

.preflop-left,
.preflop-center,
.preflop-right {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-width: 0;
}

.preflop-legend {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
  margin: 0;
  padding: 0;
  list-style: none;
  font-size: 12px;
  font-weight: 700;
}

.preflop-legend li {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.preflop-legend .preflop-legend-pct {
  color: var(--text-muted);
  font-weight: 500;
}

.preflop-missing {
  align-items: flex-start;
}

.preflop-right .ui-card p {
  margin: 0;
}

.preflop-links {
  align-items: flex-start;
}

@media (max-width: 1100px) {
  .preflop-body {
    grid-template-columns: 150px minmax(0, 1fr);
  }

  .preflop-right {
    grid-column: 1 / -1;
    flex-direction: row;
    flex-wrap: wrap;
  }

  .preflop-filter-cards {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `cd src/frontend && npx vitest run src/ranges/PreflopFiltersStep.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/ranges/PreflopFiltersStep.tsx src/frontend/src/ranges/PreflopFiltersStep.test.tsx src/frontend/src/ranges/preflop.css
git commit -m "feat(preflop): filter step with counted radio cards and empty state"
```

---

### Task 6: Paso 2, visor (`PreflopViewer`)

**Files:**
- Create: `src/frontend/src/ranges/PreflopViewer.tsx`
- Test: `src/frontend/src/ranges/PreflopViewer.test.tsx`

**Interfaces:**
- Consumes:
  - Task 1: `chartToText`, `rangeStats`, `actionLabel` y `formatPct`.
  - Task 2: `applyFilters`, `filtersSummary` y `PreflopFilters`.
  - Task 3: `DEFAULT_SELECTION`, `resolveSelection`, `viewerOptions`, `matchingCharts`, `draftFor`, `situationText` y `ViewerSelection`.
  - Task 4: `RangeMatrix` con `onHover`.
  - De `../ui`: `Button`, `Card`, `Chip`, `PillGroup`, `SegmentList`, `Select` y `Stat`.
  - `getJson` de `../api/client`, `handClassName` de `../simulator/cards`, `SOURCE_LABEL` de `./labels`, `InitialScenario` de `../simulator/SimulatorPage` (tipo `Partial<ScenarioInput>`), `GameFormat` de `../simulator/types` e `InitialFilters` de `../trainer/types`.
- Produces: `PreflopViewer(props: PreflopViewerProps)` con:

```ts
export interface PreflopViewerProps {
  charts: Chart[]
  filters: PreflopFilters
  onChangeFilters: () => void
  onEdit: (chart: Chart) => void
  onCreate: (draft: ChartData) => void
  onManage: () => void
  onOpenSimulator: (scenario: InitialScenario) => void
  onTrain: (filters: InitialFilters) => void
}
```

- [ ] **Step 1: Escribir el test que falla**

`src/frontend/src/ranges/PreflopViewer.test.tsx`:

```tsx
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { makeChart } from '../test/charts'
import { mockApi } from '../test/fetchMock'
import { ALL } from './preflopFilters'
import { PreflopViewer, type PreflopViewerProps } from './PreflopViewer'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const SIX = ['LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']
const FILTERS = { format: 'cash', source: ALL, rake: ALL, players: 6 }

function raiseGrid(cells: Record<number, number>) {
  const g = Array<number>(169).fill(0)
  for (const [i, w] of Object.entries(cells)) g[Number(i)] = w
  return g
}

function setup(charts = [makeChart()], overrides: Partial<PreflopViewerProps> = {}) {
  const props: PreflopViewerProps = {
    charts,
    filters: FILTERS,
    onChangeFilters: vi.fn(),
    onEdit: vi.fn(),
    onCreate: vi.fn(),
    onManage: vi.fn(),
    onOpenSimulator: vi.fn(),
    onTrain: vi.fn(),
    ...overrides,
  }
  render(<PreflopViewer {...props} />)
  return props
}

describe('PreflopViewer', () => {
  it('shows the filter chip, the sequence, positions from the API and the chart stats', async () => {
    mockApi({ 'GET /api/simulator/positions/6': () => ({ json: SIX }) })
    const props = setup([
      makeChart({ position: 'BTN', actions: { raise: raiseGrid({ 0: 1, 1: 1 }) } }), // AA 6 + AKs 4 = 10 combos
      makeChart({ position: 'CO' }),
    ])
    expect(screen.getByText('Cash · Todas las fuentes · Todos los stakes · 6-max')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Cambiar' }))
    expect(props.onChangeFilters).toHaveBeenCalledOnce()

    const seq = screen.getByRole('group', { name: 'Secuencia' })
    expect(within(seq).getByRole('radio', { name: 'Open raise (RFI)' })).toBeChecked()
    expect(within(seq).getByRole('radio', { name: 'vs 3-bet' })).toBeDisabled()

    const pos = screen.getByRole('group', { name: 'Tu posición' })
    await waitFor(() => expect(within(pos).getAllByRole('radio')).toHaveLength(6))
    expect(within(pos).getByRole('radio', { name: 'BTN' })).toBeChecked()
    expect(within(pos).getByRole('radio', { name: 'LJ' })).toBeDisabled()

    expect(screen.getByText('10 combos')).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Stack efectivo' })).toHaveValue('100')
  })

  it('switches position and shows the hovered hand frequencies', async () => {
    mockApi({ 'GET /api/simulator/positions/6': () => ({ json: SIX }) })
    setup([
      makeChart({ position: 'BTN', name: 'BTN open' }),
      makeChart({ position: 'CO', name: 'CO open', actions: { raise: raiseGrid({ 1: 0.5 }) } }),
    ])
    fireEvent.click(await screen.findByRole('radio', { name: 'CO' }))
    expect(screen.getByRole('group', { name: 'Rango CO open' })).toBeInTheDocument()
    fireEvent.pointerEnter(document.querySelector('[title^="AKs:"]')!)
    const hand = screen.getByRole('region', { name: 'Mano: AKs' })
    expect(hand).toHaveTextContent('Raise 50%')
    expect(hand).toHaveTextContent('Fold 50%')
  })

  it('shows a rival row for situations with one', async () => {
    mockApi({ 'GET /api/simulator/positions/6': () => ({ json: SIX }) })
    setup([
      makeChart({ situation: 'vs_open', position: 'BB', vs_position: 'BTN' }),
      makeChart({ situation: 'vs_open', position: 'BB', vs_position: 'CO' }),
    ])
    // until the positions arrive the order comes from the charts; then it is table order
    await waitFor(() =>
      expect(
        within(screen.getByRole('group', { name: 'Rival' }))
          .getAllByRole('radio')
          .map((r) => r.getAttribute('value')),
      ).toEqual(['CO', 'BTN']),
    )
  })

  it('lets you pick among duplicate charts, newest first', async () => {
    mockApi({ 'GET /api/simulator/positions/6': () => ({ json: SIX }) })
    setup([
      makeChart({ id: 21, name: 'Viejo', source: 'pokalab', updated_at: '2026-10-01T00:00:00' }),
      makeChart({ id: 22, name: 'Nuevo', source: 'custom', updated_at: '2026-10-05T00:00:00' }),
    ])
    const pick = screen.getByRole('combobox', { name: '2 rangos' })
    expect(pick).toHaveValue('22')
    fireEvent.change(pick, { target: { value: '21' } })
    expect(screen.getByRole('group', { name: 'Rango Viejo' })).toBeInTheDocument()
  })

  it('offers to create the missing chart with the visible context', async () => {
    mockApi({ 'GET /api/simulator/positions/6': () => ({ json: SIX }) })
    const props = setup([makeChart({ situation: 'vs_open', position: 'BB', vs_position: 'BTN', stack_bb: 40 })], {
      filters: { ...FILTERS, rake: 'GG NL50' },
    })
    // the only chart has rake null, so a specific rake hides it
    expect(screen.getByText(/No hay un rango para/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Crear este rango' }))
    expect(props.onCreate).toHaveBeenCalledWith(expect.objectContaining({ source: 'custom', rake: 'GG NL50' }))
  })

  it('opens the spot in the simulator and the trainer', async () => {
    mockApi({ 'GET /api/simulator/positions/6': () => ({ json: SIX }) })
    const props = setup([makeChart({ position: 'CO', stack_bb: 40 })])
    await screen.findAllByRole('radio', { name: 'LJ' })
    fireEvent.click(screen.getByRole('button', { name: /Abrir en Simulador/ }))
    expect(props.onOpenSimulator).toHaveBeenCalledWith({
      format: 'cash',
      num_players: 6,
      hero_position: 'CO',
      effective_stack_bb: 40,
      situation: 'rfi',
    })
    fireEvent.click(screen.getByRole('button', { name: /Entrenar este spot/ }))
    expect(props.onTrain).toHaveBeenCalledWith({
      positions: ['CO'],
      situations: ['rfi'],
      formats: ['cash'],
      sources: ['chart'],
    })
  })

  it('copies the range as text, and reports when the clipboard is unavailable', async () => {
    mockApi({ 'GET /api/simulator/positions/6': () => ({ json: SIX }) })
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    setup([makeChart({ actions: { raise: raiseGrid({ 0: 1 }) } })])
    fireEvent.click(screen.getByRole('button', { name: /Copiar rango/ }))
    await waitFor(() => expect(writeText).toHaveBeenCalledWith('Raise: AA'))
    expect(await screen.findByRole('status')).toHaveTextContent('Rango copiado.')

    Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true })
    fireEvent.click(screen.getByRole('button', { name: /Copiar rango/ }))
    expect(await screen.findByText('No se pudo copiar el rango.')).toBeInTheDocument()
  })

  it('still works with the positions found in the charts when the API fails', async () => {
    mockApi({}) // every request answers 404
    setup([makeChart({ position: 'BTN' }), makeChart({ position: 'CO' })])
    const pos = screen.getByRole('group', { name: 'Tu posición' })
    expect(within(pos).getAllByRole('radio').map((r) => r.getAttribute('value'))).toEqual(['BTN', 'CO'])
    expect(within(pos).getByRole('radio', { name: 'BTN' })).toBeChecked()
  })
})
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd src/frontend && npx vitest run src/ranges/PreflopViewer.test.tsx`
Expected: FAIL porque no se puede resolver `./PreflopViewer`.

- [ ] **Step 3: Escribir el componente**

`src/frontend/src/ranges/PreflopViewer.tsx`:

```tsx
import { useEffect, useMemo, useState } from 'react'
import { getJson } from '../api/client'
import { handClassName } from '../simulator/cards'
import type { InitialScenario } from '../simulator/SimulatorPage'
import type { GameFormat } from '../simulator/types'
import type { InitialFilters } from '../trainer/types'
import { Button, Card, Chip, PillGroup, SegmentList, Select, Stat } from '../ui'
import { SOURCE_LABEL } from './labels'
import { actionLabel, chartToText, formatPct, rangeStats } from './notation'
import { applyFilters, filtersSummary, type PreflopFilters } from './preflopFilters'
import {
  DEFAULT_SELECTION,
  draftFor,
  matchingCharts,
  resolveSelection,
  situationText,
  type ViewerSelection,
  viewerOptions,
} from './preflopSelection'
import { RangeMatrix } from './RangeMatrix'
import type { Chart, ChartData } from './types'

export interface PreflopViewerProps {
  charts: Chart[]
  filters: PreflopFilters
  onChangeFilters: () => void
  onEdit: (chart: Chart) => void
  onCreate: (draft: ChartData) => void
  onManage: () => void
  onOpenSimulator: (scenario: InitialScenario) => void
  onTrain: (filters: InitialFilters) => void
}

function cellText(chart: Chart, index: number): string[] {
  const parts = Object.entries(chart.actions)
    .filter(([action, grid]) => action !== 'fold' && (grid[index] ?? 0) > 0)
    .map(([action, grid]) => `${actionLabel(action)} ${Math.round(grid[index] * 100)}%`)
  const played = Object.entries(chart.actions)
    .filter(([action]) => action !== 'fold')
    .reduce((s, [, grid]) => s + (grid[index] ?? 0), 0)
  if (played < 0.999) parts.push(`Fold ${Math.round((1 - Math.min(1, played)) * 100)}%`)
  return parts
}

export function PreflopViewer(props: PreflopViewerProps) {
  const { charts, filters, onChangeFilters, onEdit, onCreate, onManage, onOpenSimulator, onTrain } = props
  const visible = useMemo(() => applyFilters(charts, filters), [charts, filters])

  const [positions, setPositions] = useState<string[]>([])
  useEffect(() => {
    const controller = new AbortController()
    getJson<string[]>(`/api/simulator/positions/${filters.players}`, controller.signal)
      .then(setPositions)
      .catch(() => {
        // Without the table order the viewer falls back to the positions found in the charts.
        if (!controller.signal.aborted) setPositions([])
      })
    return () => controller.abort()
  }, [filters.players])

  const [wanted, setWanted] = useState<ViewerSelection>(DEFAULT_SELECTION)
  const [pickedId, setPickedId] = useState<number | null>(null)
  const [hover, setHover] = useState<number | null>(null)
  const [note, setNote] = useState<string | null>(null)

  const sel = resolveSelection(visible, positions, wanted)
  const options = viewerOptions(visible, positions, sel)
  const matches = matchingCharts(visible, sel)
  const chart = matches.find((c) => c.id === pickedId) ?? matches[0] ?? null

  function change(patch: Partial<ViewerSelection>) {
    setWanted({ ...sel, ...patch })
    setPickedId(null)
    setNote(null)
  }

  async function copy() {
    if (!chart) return
    try {
      if (!navigator.clipboard) throw new Error('clipboard unavailable')
      await navigator.clipboard.writeText(chartToText(chart.actions))
      setNote('Rango copiado.')
    } catch {
      setNote('No se pudo copiar el rango.')
    }
  }

  const layers = chart ? Object.entries(chart.actions).map(([action, grid]) => ({ action, grid })) : []
  const stats = chart ? rangeStats(chart.actions) : null
  const spot = `${sel.position}${sel.vsPosition ? ` vs ${sel.vsPosition}` : ''} · ${situationText(sel.situation)} · ${sel.stack ?? '?'}bb`

  return (
    <div className="preflop-viewer">
      <div className="preflop-top">
        <Chip actionLabel="Cambiar" onAction={onChangeFilters}>
          {filtersSummary(filters)}
        </Chip>
        <div className="preflop-tools">
          <Button size="sm" disabled={!chart} onClick={() => void copy()}>
            ⧉ Copiar rango
          </Button>
          <Button size="sm" disabled={!chart} onClick={() => chart && onEdit(chart)}>
            ✎ Editar
          </Button>
          <Button size="sm" onClick={() => onCreate(draftFor(filters, sel))}>
            ＋ Nuevo
          </Button>
          <Button size="sm" onClick={onManage}>
            ⇅ Importar / exportar
          </Button>
        </div>
      </div>
      {note && (
        <p className="small" role="status">
          {note}
        </p>
      )}

      <div className="preflop-body">
        <aside className="preflop-left">
          <SegmentList
            legend="Secuencia"
            options={options.situations}
            value={sel.situation}
            onChange={(situation) => change({ situation })}
          />
          {options.stacks.length > 0 && (
            <Select
              label="Stack efectivo"
              value={String(sel.stack)}
              onChange={(e) => change({ stack: Number(e.target.value) })}
            >
              {options.stacks.map((s) => (
                <option key={s} value={s}>
                  {s} BB
                </option>
              ))}
            </Select>
          )}
        </aside>

        <div className="preflop-center">
          <PillGroup
            legend="Tu posición"
            options={options.positions}
            value={sel.position}
            onChange={(position) => change({ position })}
          />
          {options.vsPositions.length > 0 && (
            <PillGroup
              legend="Rival"
              options={options.vsPositions}
              value={sel.vsPosition}
              onChange={(vsPosition) => change({ vsPosition })}
            />
          )}
          {matches.length > 1 && chart && (
            <Select
              label={`${matches.length} rangos`}
              value={String(chart.id)}
              onChange={(e) => setPickedId(Number(e.target.value))}
            >
              {matches.map((c) => (
                <option key={c.id} value={c.id}>
                  {SOURCE_LABEL[c.source] ?? c.source} · {c.name}
                </option>
              ))}
            </Select>
          )}
          {chart && stats ? (
            <>
              <ul className="preflop-legend" aria-label="Leyenda">
                {layers
                  .filter(({ action }) => action !== 'fold')
                  .map(({ action, grid }) => (
                    <li key={action}>
                      <span className="swatch" style={{ background: `var(--action-${action})` }} />
                      {actionLabel(action)}
                      <span className="preflop-legend-pct">{formatPct(rangeStats({ [action]: grid }).pct)}</span>
                    </li>
                  ))}
                <li>
                  <span className="swatch" style={{ background: 'var(--grid-empty)' }} />
                  Fold
                  <span className="preflop-legend-pct">{formatPct(1 - stats.pct)}</span>
                </li>
              </ul>
              <RangeMatrix layers={layers} caption={`Rango ${chart.name}`} onHover={setHover} />
            </>
          ) : (
            <div className="panel preflop-missing">
              <p>No hay un rango para {spot}.</p>
              <Button variant="primary" onClick={() => onCreate(draftFor(filters, sel))}>
                Crear este rango
              </Button>
            </div>
          )}
        </div>

        <aside className="preflop-right">
          {chart && stats && (
            <Card>
              <Stat label="Rango" value={formatPct(stats.pct)} detail={`${stats.combos} combos`} />
            </Card>
          )}
          {chart && hover !== null && (
            <Card title={`Mano: ${handClassName(hover)}`}>
              {cellText(chart, hover).map((line) => (
                <p key={line}>{line}</p>
              ))}
            </Card>
          )}
          <Card title="Abrir en" className="preflop-links">
            <Button
              variant="ghost"
              onClick={() =>
                onOpenSimulator({
                  format: filters.format as GameFormat,
                  num_players: filters.players,
                  hero_position: sel.position,
                  effective_stack_bb: sel.stack ?? 100,
                  situation: sel.situation,
                })
              }
            >
              ⬭ Abrir en Simulador →
            </Button>
            <Button
              variant="ghost"
              onClick={() =>
                onTrain({
                  positions: [sel.position],
                  situations: [sel.situation],
                  formats: [filters.format],
                  sources: ['chart'],
                })
              }
            >
              ✎ Entrenar este spot →
            </Button>
          </Card>
        </aside>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `cd src/frontend && npx vitest run src/ranges/PreflopViewer.test.tsx`
Expected: PASS (8 tests). Si falla el test de la API caída porque la petición rechazada deja `positions` vacío, eso es lo esperado: el fallback viene de `viewerOptions`.

- [ ] **Step 5: Typecheck, lint y commit**

Run: `cd src/frontend && npm run typecheck && npm run lint`
Expected: sin errores.

```bash
git add src/frontend/src/ranges/PreflopViewer.tsx src/frontend/src/ranges/PreflopViewer.test.tsx
git commit -m "feat(preflop): chart viewer with sequence, positions, legend and spot links"
```

---

### Task 7: `PreflopPage` reemplaza a `ChartsPage`, y se conecta en `App`

**Files:**
- Create: `src/frontend/src/ranges/chartsApi.ts`
- Create: `src/frontend/src/ranges/ChartManager.tsx`
- Create: `src/frontend/src/ranges/PreflopPage.tsx`
- Test: `src/frontend/src/ranges/PreflopPage.test.tsx`
- Delete: `src/frontend/src/ranges/ChartsPage.tsx`, `src/frontend/src/ranges/ChartsPage.test.tsx`
- Modify: `src/frontend/src/App.tsx` (import y línea `{section === 'ranges' && <ChartsPage />}`)
- Modify test: `src/frontend/src/App.test.tsx` (se agrega un test)

**Interfaces:**
- Consumes:
  - `readStored`/`writeStored` de `../app/storage`.
  - Task 2: `defaultFilters`, `isPreflopFilters`, `PREFLOP_FILTERS_KEY` y `PreflopFilters`.
  - Task 3: `NEW_CHART`.
  - `PreflopFiltersStep` (Task 5), `PreflopViewer` (Task 6) y el `ChartEditor` actual (`{ initial: ChartData; onSave: (data: ChartData) => Promise<void>; onCancel: () => void }`).
- Produces:
  - `PreflopPage(props: { onOpenSimulator: (scenario: InitialScenario) => void; onTrain: (filters: InitialFilters) => void })`
  - `importCharts(file: File): Promise<{ created: number; errors: string[] }>`
  - `exportCharts(onlyOwn: boolean): Promise<void>`
  - `ChartManager(props: { charts: Chart[]; onEdit: (chart: Chart) => void; onDelete: (chart: Chart) => void; onImport: (file: File) => void; onExport: (onlyOwn: boolean) => void; onNew: () => void; onClose: () => void })`

- [ ] **Step 1: Escribir el test que falla**

`src/frontend/src/ranges/PreflopPage.test.tsx` (los dos tests del viejo `ChartsPage.test.tsx` se adaptan, entrando por el estado vacío):

```tsx
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { makeChart } from '../test/charts'
import { mockApi } from '../test/fetchMock'
import { PreflopPage } from './PreflopPage'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  window.localStorage.clear()
})

const POSITIONS = ['LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']
const KEY = 'pokker.preflop.filters'
const noop = () => {}

describe('PreflopPage', () => {
  it('creates a chart by painting cells and pasting notation', async () => {
    const created: unknown[] = []
    const aaGrid = Array<number>(169).fill(0)
    aaGrid[0] = 1
    aaGrid[1] = 0.5
    mockApi({
      'GET /api/charts': () => ({ json: [] }),
      'GET /api/simulator/positions': () => ({ json: POSITIONS }),
      'POST /api/ranges/parse': () => ({ json: { valid: true, error: null, combos: 8, grid: aaGrid } }),
      'POST /api/charts': (body) => {
        created.push(body)
        return { status: 201, json: { ...(body as object), id: 1 } }
      },
    })
    render(<PreflopPage onOpenSimulator={noop} onTrain={noop} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Crear rango' }))
    fireEvent.change(screen.getByLabelText('Nombre'), { target: { value: 'BTN open' } })

    // Paint KK (grid index 14) at 100% raise.
    fireEvent.pointerDown(screen.getByRole('button', { name: /^KK:/ }))
    expect(screen.getByRole('button', { name: /^KK: Raise 100%/ })).toBeInTheDocument()

    // Paste notation for the brush action.
    fireEvent.change(screen.getByLabelText(/Pegar notación/), { target: { value: 'AA, AKs:0.5' } })
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar notación' }))
    expect(await screen.findByRole('button', { name: /^AKs: Raise 50%, Fold 50%/ })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(created).toHaveLength(1))
    const body = created[0] as { name: string; actions: { raise: number[] } }
    expect(body.name).toBe('BTN open')
    expect(body.actions.raise[0]).toBe(1)
    expect(body.actions.raise[1]).toBe(0.5)
    expect(body.actions.raise[14]).toBe(0) // pasted notation replaced the action
  })

  it('shows API validation errors when saving', async () => {
    mockApi({
      'GET /api/charts': () => ({ json: [] }),
      'GET /api/simulator/positions': () => ({ json: POSITIONS }),
      'POST /api/charts': () => ({
        status: 422,
        json: { detail: [{ msg: 'Value error, Posición UTG no existe en una mesa de 6' }] },
      }),
    })
    render(<PreflopPage onOpenSimulator={noop} onTrain={noop} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Crear rango' }))
    fireEvent.change(screen.getByLabelText('Nombre'), { target: { value: 'x' } })
    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Posición UTG no existe')
  })

  it('starts on the filter step, remembers the applied filters and reopens on the viewer', async () => {
    mockApi({
      'GET /api/charts': () => ({ json: [makeChart({ name: 'BTN open' })] }),
      'GET /api/simulator/positions': () => ({ json: POSITIONS }),
    })
    const { unmount } = render(<PreflopPage onOpenSimulator={noop} onTrain={noop} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Aplicar' }))
    expect(screen.getByRole('group', { name: 'Rango BTN open' })).toBeInTheDocument()
    expect(JSON.parse(window.localStorage.getItem(KEY) ?? 'null')).toEqual({
      format: 'cash',
      source: 'all',
      rake: 'all',
      players: 6,
    })
    unmount()

    render(<PreflopPage onOpenSimulator={noop} onTrain={noop} />)
    expect(await screen.findByRole('group', { name: 'Rango BTN open' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Cambiar' }))
    expect(screen.getByRole('button', { name: 'Aplicar' })).toBeInTheDocument()
  })

  it('ignores corrupt stored filters and survives stale ones', async () => {
    mockApi({
      'GET /api/charts': () => ({ json: [makeChart()] }),
      'GET /api/simulator/positions': () => ({ json: POSITIONS }),
    })
    window.localStorage.setItem(KEY, '{"format":"cash"}')
    const first = render(<PreflopPage onOpenSimulator={noop} onTrain={noop} />)
    expect(await screen.findByRole('button', { name: 'Aplicar' })).toBeInTheDocument()
    first.unmount()

    window.localStorage.setItem(KEY, JSON.stringify({ format: 'cash', source: 'all', rake: 'PS NL10', players: 9 }))
    render(<PreflopPage onOpenSimulator={noop} onTrain={noop} />)
    expect(await screen.findByText(/No hay un rango para/)).toBeInTheDocument()
  })

  it('manages charts: table with edit, import and back to the viewer', async () => {
    const imported: unknown[] = []
    mockApi({
      'GET /api/charts': () => ({ json: [makeChart({ name: 'BTN open' })] }),
      'GET /api/simulator/positions': () => ({ json: POSITIONS }),
      'POST /api/charts/import': (body) => {
        imported.push(body)
        return { json: { created: 2, errors: [] } }
      },
    })
    window.localStorage.setItem(KEY, JSON.stringify({ format: 'cash', source: 'all', rake: 'all', players: 6 }))
    render(<PreflopPage onOpenSimulator={noop} onTrain={noop} />)
    fireEvent.click(await screen.findByRole('button', { name: /Importar \/ exportar/ }))
    expect(screen.getByRole('table')).toHaveTextContent('BTN open')

    const file = new File(['{"format":"poker-study-ranges","version":1,"charts":[]}'], 'set.json')
    fireEvent.change(screen.getByLabelText('Importar set (.json)'), { target: { files: [file] } })
    expect(await screen.findByText('Importados: 2.')).toBeInTheDocument()
    expect(imported).toHaveLength(1)

    fireEvent.click(screen.getByRole('button', { name: 'Volver al visor' }))
    expect(screen.getByRole('group', { name: 'Rango BTN open' })).toBeInTheDocument()
  })
})
```

En `src/frontend/src/App.test.tsx`, agregar al final del `describe('App', …)`:

```tsx
  it('opens a preflop spot in the simulator with the position preset', async () => {
    const raise = Array<number>(169).fill(0)
    raise[0] = 1
    mockApi({
      'GET /api/version': () => ({ json: { app: '0.1.0', core: '0.1.0' } }),
      'GET /api/charts': () => ({
        json: [
          {
            id: 1, name: 'CO open', source: 'pokalab', game_format: 'cash', players: 6, position: 'CO',
            vs_position: null, stack_bb: 100, situation: 'rfi', open_size_bb: 2.5, rake: null, ante_bb: 0,
            note: '', actions: { raise }, created_at: '2026-10-01T00:00:00', updated_at: '2026-10-01T00:00:00',
          },
        ],
      }),
      'GET /api/simulator/positions': () => ({ json: POSITIONS }),
      'POST /api/ranges/parse': () => ({ json: { valid: true, error: null, combos: 1326, grid: [] } }),
    })
    window.localStorage.setItem(
      'pokker.preflop.filters',
      JSON.stringify({ format: 'cash', source: 'all', rake: 'all', players: 6 }),
    )
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Preflop' }))
    fireEvent.click(await screen.findByRole('button', { name: /Abrir en Simulador/ }))
    expect(screen.getByRole('button', { name: 'Simulador' })).toHaveAttribute('aria-current', 'page')
    // Hero and each rival have a "Posición" select; the hero one is #hero-pos.
    await waitFor(() => expect(document.getElementById('hero-pos')).toHaveValue('CO'))
    window.localStorage.clear()
  })
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd src/frontend && npx vitest run src/ranges/PreflopPage.test.tsx src/App.test.tsx`
Expected: FAIL. `./PreflopPage` no existe, y en App no hay botón "Abrir en Simulador".

- [ ] **Step 3: Escribir `chartsApi.ts`**

`src/frontend/src/ranges/chartsApi.ts`:

```ts
import { getJson, postJson } from '../api/client'

export async function importCharts(file: File): Promise<{ created: number; errors: string[] }> {
  const body: unknown = JSON.parse(await file.text())
  return postJson<{ created: number; errors: string[] }>('/api/charts/import', body)
}

export function download(name: string, data: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

export async function exportCharts(onlyOwn: boolean): Promise<void> {
  const query = onlyOwn ? '?source=custom&source=computed' : ''
  const data = await getJson<unknown>(`/api/charts/export${query}`)
  download(onlyOwn ? 'rangos-propios.json' : 'rangos.json', data)
}
```

- [ ] **Step 4: Escribir `ChartManager.tsx`**

Es el panel de gestión: el mismo contenido que tenía `ChartsPage` (botones de importar y exportar, aviso de uso personal, filtro de texto y tabla con Editar y Borrar), más "Nuevo rango" y "Volver al visor".

`src/frontend/src/ranges/ChartManager.tsx`:

```tsx
import { useState } from 'react'
import { Button } from '../ui'
import { FORMAT_LABEL, SITUATION_LABEL, SOURCE_LABEL } from './labels'
import type { Chart } from './types'

interface Props {
  charts: Chart[]
  onEdit: (chart: Chart) => void
  onDelete: (chart: Chart) => void
  onImport: (file: File) => void
  onExport: (onlyOwn: boolean) => void
  onNew: () => void
  onClose: () => void
}

export function ChartManager({ charts, onEdit, onDelete, onImport, onExport, onNew, onClose }: Props) {
  const [filter, setFilter] = useState('')
  const needle = filter.trim().toLowerCase()
  const visible = charts.filter((c) =>
    [c.name, c.position, c.vs_position ?? '', SITUATION_LABEL[c.situation], FORMAT_LABEL[c.game_format]]
      .join(' ')
      .toLowerCase()
      .includes(needle),
  )

  return (
    <div className="charts-page">
      <section className="panel">
        <div className="field-row">
          <Button onClick={onClose}>Volver al visor</Button>
          <Button variant="primary" onClick={onNew}>
            Nuevo rango
          </Button>
          <label className="file-button">
            Importar set (.json)
            <input
              type="file"
              accept=".json,application/json"
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) onImport(file)
                e.target.value = ''
              }}
            />
          </label>
          <Button onClick={() => onExport(false)}>Exportar todo</Button>
          <Button onClick={() => onExport(true)}>Exportar propios y calculados</Button>
        </div>
        <p className="muted small">
          Los rangos de fuentes externas (Pokalab, preflopranges.app) son para uso personal: se cargan a mano y no se
          comparten al exportar solo los propios.
        </p>
      </section>

      <section className="panel">
        <label>
          Filtrar
          <input type="text" value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="BTN, vs open, MTT…" />
        </label>
        <div className="table-scroll">
          <table className="charts-table">
            <thead>
              <tr>
                <th scope="col">Nombre</th>
                <th scope="col">Fuente</th>
                <th scope="col">Formato</th>
                <th scope="col">Spot</th>
                <th scope="col">Stack</th>
                <th scope="col">
                  <span className="sr-only">Acciones</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {visible.map((c) => (
                <tr key={c.id}>
                  <td>{c.name}</td>
                  <td>{SOURCE_LABEL[c.source] ?? c.source}</td>
                  <td>
                    {FORMAT_LABEL[c.game_format]} · {c.players}j
                  </td>
                  <td>
                    {c.position} {SITUATION_LABEL[c.situation]}
                    {c.vs_position ? ` (${c.vs_position})` : ''}
                  </td>
                  <td>{c.stack_bb}bb</td>
                  <td className="row-actions">
                    <Button size="sm" onClick={() => onEdit(c)}>
                      Editar
                    </Button>
                    <Button size="sm" onClick={() => onDelete(c)}>
                      Borrar
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
```

- [ ] **Step 5: Escribir `PreflopPage.tsx`**

`src/frontend/src/ranges/PreflopPage.tsx`:

```tsx
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
import { NEW_CHART } from './preflopSelection'
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
        />
      )}
    </div>
  )
}
```

- [ ] **Step 6: Conectar en `App.tsx` y borrar `ChartsPage`**

En `src/frontend/src/App.tsx`:
- reemplazar `import { ChartsPage } from './ranges/ChartsPage'` por `import { PreflopPage } from './ranges/PreflopPage'`;
- reemplazar `{section === 'ranges' && <ChartsPage />}` por:

```tsx
        {section === 'ranges' && (
          <PreflopPage
            onOpenSimulator={(scenario) => {
              setSpot({ key: Date.now(), scenario })
              setSection('simulator')
            }}
            onTrain={(filters) => {
              setTrainer({ key: Date.now(), filters })
              setSection('trainer')
            }}
          />
        )}
```

Después borrar los archivos viejos:

```bash
git rm src/frontend/src/ranges/ChartsPage.tsx src/frontend/src/ranges/ChartsPage.test.tsx
```

- [ ] **Step 7: Correr los tests y verificar que pasan**

Run: `cd src/frontend && npx vitest run src/ranges/PreflopPage.test.tsx src/App.test.tsx`
Expected: PASS. `PreflopPage` tiene 5 tests y `App` tiene 5 (4 previos más el nuevo).

- [ ] **Step 8: Suite completa, typecheck, lint y build**

Run: `cd src/frontend && npm test && npm run typecheck && npm run lint && npm run build`
Expected: todo en PASS, sin errores. `.charts-page`, `.charts-table` y `.row-actions` (en `ranges/ranges.css`) siguen en uso desde `ChartManager`. `.row-selected` queda sin uso: borrala de `ranges/ranges.css`.

- [ ] **Step 9: Commit**

```bash
git add -A src/frontend/src
git commit -m "feat(preflop): Preflop section (filters → viewer) replaces the charts page"
```

---

### Task 8: Datos de muestra, recorrida visual y verificación completa

**Files:**
- Create: `tests/fixtures/ranges/preflop-review.json`
- Modify: CSS de `ranges/preflop.css`, solo si la recorrida encuentra defectos

- [ ] **Step 1: Crear el set de muestra**

`tests/fixtures/ranges/preflop-review.json`:

```json
{
  "format": "poker-study-ranges",
  "version": 1,
  "charts": [
    {
      "name": "BTN RFI 100bb (Pokalab)", "source": "pokalab", "game_format": "cash", "players": 6,
      "position": "BTN", "vs_position": null, "stack_bb": 100, "situation": "rfi", "open_size_bb": 2.5,
      "rake": "GG NL50", "ante_bb": 0, "note": "",
      "actions": { "raise": "22+,A2s+,K5s+,Q8s+,J8s+,T8s+,97s+,86s+,75s+,65s,54s,A8o+,KTo+,QTo+,JTo,A5o-A2o:0.5" }
    },
    {
      "name": "CO RFI 100bb", "source": "pokalab", "game_format": "cash", "players": 6,
      "position": "CO", "vs_position": null, "stack_bb": 100, "situation": "rfi", "open_size_bb": 2.5,
      "rake": "GG NL50", "ante_bb": 0, "note": "",
      "actions": { "raise": "33+,A2s+,K8s+,Q9s+,J9s+,T9s,98s,87s,76s,A9o+,KJo+,QJo" }
    },
    {
      "name": "BTN RFI 100bb (propio)", "source": "custom", "game_format": "cash", "players": 6,
      "position": "BTN", "vs_position": null, "stack_bb": 100, "situation": "rfi", "open_size_bb": 2.5,
      "rake": null, "ante_bb": 0, "note": "",
      "actions": { "raise": "22+,A2s+,K2s+,Q6s+,J7s+,T7s+,96s+,85s+,75s+,64s+,54s,A2o+,K9o+,Q9o+,J9o+,T9o" }
    },
    {
      "name": "BB vs BTN open 100bb", "source": "pokalab", "game_format": "cash", "players": 6,
      "position": "BB", "vs_position": "BTN", "stack_bb": 100, "situation": "vs_open", "open_size_bb": null,
      "rake": "GG NL50", "ante_bb": 0, "note": "",
      "actions": {
        "call": "22-99,A2s-AJs,K2s+,Q5s+,J7s+,T7s+,96s+,85s+,75s+,64s+,54s,A2o-AJo,K9o+,Q9o+,J9o+,T9o",
        "3bet": "TT+,AQs+,AQo+,A5s-A4s:0.5"
      }
    },
    {
      "name": "BTN RFI 40bb", "source": "pokalab", "game_format": "cash", "players": 6,
      "position": "BTN", "vs_position": null, "stack_bb": 40, "situation": "rfi", "open_size_bb": 2.0,
      "rake": null, "ante_bb": 0, "note": "",
      "actions": { "raise": "22+,A2s+,K7s+,Q9s+,J9s+,T9s,98s,A7o+,KTo+,QJo" }
    },
    {
      "name": "UTG RFI 25bb MTT", "source": "computed", "game_format": "mtt", "players": 9,
      "position": "UTG", "vs_position": null, "stack_bb": 25, "situation": "rfi", "open_size_bb": 2.0,
      "rake": null, "ante_bb": 0, "note": "",
      "actions": { "raise": "77+,ATs+,KQs,AJo+" }
    }
  ]
}
```

- [ ] **Step 2: Levantar la app con una carpeta de datos aparte e importar el set**

La base de desarrollo del usuario (`var/`) **no se toca**: la recorrida usa una carpeta temporal. En una PowerShell, desde la raíz del repo:

```powershell
$env:POKER_DATA_DIR = "$env:TEMP\pokker-review"
scripts\dev.ps1
```

En el navegador, abrí `http://localhost:5173`, andá a **Preflop** e importá `tests/fixtures/ranges/preflop-review.json` desde el estado vacío.
Expected: "Importados: 6." y ningún error.

- [ ] **Step 3: Recorrida contra el mockup `3-preflop.html`, a 1280 px y a 1024 px**

Compará con el mockup y verificá cada punto:

- **Paso 1:** se ven las 4 tarjetas. Cash tiene 5 rangos y Torneos 1. Al elegir Torneos, Jugadores cuenta 9-max: 1. Aplicar lleva al visor.
- **Visor con Cash, todas las fuentes, todos los stakes, 6-max:**
  - BTN y RFI muestran el selector "2 rangos" y por defecto el más reciente.
  - El stack ofrece 40 y 100 BB.
  - CO y BB están habilitadas; LJ, HJ y SB, apagadas.
  - vs open con BB muestra la fila Rival con BTN, y la leyenda muestra Call, 3-bet y Fold con sus porcentajes.
- **Leyenda y matriz:** las celdas mixtas (`A5s-A4s:0.5` de 3-bet) se ven partidas y la etiqueta se lee.
- **Mano bajo el mouse:** el panel derecho muestra la mano y sus frecuencias.
- **Copiar rango:** pegarlo en un editor de texto da una línea por acción.
- **Cambiar → Stake GG NL50:** desaparece el rango "propio" y deja de aparecer el selector de repetidos.
- **Abrir en Simulador:** lleva al Simulador con la posición elegida. **Entrenar este spot** abre el Entrenador filtrado.
- **Importar / exportar:** se ve la tabla, Editar abre el editor y "Volver al visor" vuelve.
- **A 1024 px con el menú plegado:** no hay desborde horizontal y el panel derecho baja debajo de la matriz.

Cada defecto se corrige en `ranges/preflop.css` (o con un test que falle primero si es de lógica) y se anota en el commit.

- [ ] **Step 4: Suite completa del repo, paquete y e2e del launcher**

Desde la raíz del repo, en el dev shell de MSVC, con POKKER cerrado (si está abierto desde `dist\POKKER`, `package.ps1` no puede reemplazarlo):

```powershell
scripts\test.ps1
scripts\package.ps1 -SkipTests
scripts\test.ps1 launcher
```

Expected:
- core 31, backend 362 (más 1 skipped), integración 2;
- frontend con todos los tests en PASS (161 previos, menos los 2 de `ChartsPage` que se mudaron, más los nuevos);
- el paquete se arma con la prueba de humo en OK;
- el e2e del launcher pasa sus 9 tests.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/ranges/preflop-review.json src/frontend/src/ranges/preflop.css
git commit -m "test(preflop): sample chart set for the visual review; layout polish"
```

---

## Self-review (hecho al escribir el plan)

- **Cobertura del spec §4:**
  - §4.1, paso de filtros: Task 2 (lógica) y Task 5 (componente). Cubre los contadores cruzados, los 4 formatos siempre visibles, "Todas" y "Todos", los rangos sin rake, los jugadores con 6 y 9 por defecto, Aplicar, la persistencia (Task 7) y el estado vacío con Importar y Crear (Task 5).
  - §4.2, visor: Task 6. Cubre el chip con Cambiar, Copiar (Task 1), Editar, Nuevo con contexto (Task 3, `draftFor`), Importar/exportar con la tabla y Editar/Borrar (Task 7, `ChartManager`), la secuencia con apagados, el stack, las posiciones del endpoint con fallback, la fila Rival, la leyenda con % y Fold, la matriz, el % y los combos, el detalle de la mano bajo el mouse (Task 4), Abrir en Simulador, Entrenar, la autoselección en cascada (Task 3), el estado vacío con "Crear este rango" y los repetidos con `Select` y el más reciente primero.
  - §4.3, datos: carga única y recarga después de guardar, borrar o importar (Task 7). Funciones puras en `preflopFilters.ts`; además `preflopSelection.ts` y `notation.ts`, para que cada archivo tenga una sola responsabilidad. Filtros en `localStorage` (Task 7). El contrato con el Simulador pasa por `onOpenSimulator` con los 5 campos del spec.
  - El nombre de la sección ya era "Preflop" desde la parte 1.
- **Desvíos:** `sources: ['chart']` en Entrenar, explicado en Global Constraints. El spec dice "un CSS por sección junto a su página": se cumple con `ranges/preflop.css`, importado desde `PreflopPage.tsx`.
- **Consistencia de nombres:**
  - `PreflopFilters`, `ViewerSelection`, `ALL`, `PREFLOP_FILTERS_KEY`, `NEW_CHART` y `draftFor` se usan igual en las Tasks 2, 3, 5, 6 y 7.
  - `onHover` está definido en la Task 4 y se usa en la 6.
  - `makeChart` está en `src/test/charts.ts` y se usa en las Tasks 2, 3, 5, 6 y 7.
  - Los nombres accesibles que buscan los tests coinciden con el markup: "Secuencia", "Tu posición", "Rival", "Stack efectivo", "N rangos", "Rango {name}", "Mano: X", "Cambiar", "Crear este rango", "Volver al visor" e "Importar set (.json)".
- **Review Focus:**
  1. Los filtros guardados que ya no existen tienen tests en la Task 2 (`withCurrent`) y en la Task 7 ("survives stale ones").
  2. Los rangos sin rake, en la Task 2.
  3. La API de posiciones caída, en las Tasks 3 y 6.
  4. Las acciones raras y el fold explícito, en la Task 1.
  5. El portapapeles no disponible, en la Task 6.
