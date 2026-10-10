# Fase 8, parte 1: base visual (plan de implementación)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** que las 8 secciones de POKKER se vean con la paleta "Paño y oro" y un menú lateral agrupado y plegable, sin cambiar su comportamiento. Además, dejar listos los componentes base que usan las partes 2 y 3.

**Architecture:**
- Tokens CSS en `styles/tokens.css`, con alias para los nombres viejos, así que todas las secciones toman la paleta sin tocar su markup.
- El `index.css` de 1135 líneas se reparte en archivos por área que importa `styles/index.css`.
- `App.tsx` pasa a un layout con `Sidebar`.
- Los componentes nuevos van en `src/ui/`, con un CSS cada uno.
- Sin dependencias nuevas.

**Tech Stack:** React 19, TypeScript 6, Vite 8, vitest 5 + Testing Library (jsdom), oxlint. Todo vive en `src/frontend/`.

**Spec:** [`docs/superpowers/specs/2026-10-10-rediseno-ui-design.md`](../specs/2026-10-10-rediseno-ui-design.md) §1, §2 y §3. Mockups en [`docs/superpowers/specs/2026-10-10-rediseno-ui/`](../specs/2026-10-10-rediseno-ui/): `1-paleta.html` (opción A) y `2-navegacion.html` (opción B).

## Global Constraints

- **Sin dependencias nuevas** en `package.json`: ni Tailwind ni librerías de componentes.
- **Solo frontend:** no se toca `src/backend`, `src/core` ni `src/launcher`.
- **Paleta:** "Paño y oro", solo oscura (sin `prefers-color-scheme`). Los valores salen de la tabla de §2.1 del spec, con dos ajustes ya resueltos en este plan (ver Task 1):
  - `--action-allin` pasa de `#c2524a` a `#d4625a`;
  - `--action-5bet` pasa de `#b8543d` a `#c96a4f`.
  
  Con los valores del spec, el texto oscuro de la matriz no llegaba a 4,5:1.
- **Contraste mínimo de 4,5:1** en todo par de texto y fondo.
- **Tipografía:** `'Segoe UI', system-ui, sans-serif`. Sin fuentes externas (la app funciona offline).
- **Espaciado** de 4, 8, 12, 16, 24 y 32 px. **Radios** de 6 px (controles), 10 px (tarjetas) y 12 px (contenedores).
- **Menú:** grupo **Estudiar** (Preflop, Simulador, Push/Fold, Entrenador) y grupo **Analizar** (Manos, Replayer, Estadísticas, Solver). Desplegado mide unos 170 px y plegado unos 48 px. Guarda su estado en `localStorage` con la clave `pokker.sidebar.collapsed`, siempre dentro de try/catch; si falla, arranca desplegado.
- **Texto de la UI en español** (rioplatense, como el resto de la app).
- **Comandos** (desde `src/frontend/`): `npm test` (vitest run), `npm run typecheck`, `npm run lint` y `npm run build`.
- **Commits:** en la rama `fase8-ui`, terminando cada mensaje con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **`localStorage` que tira error** (modo privado, datos bloqueados). La app tiene que abrir igual, con el menú desplegado. Lo cubre la Task 2, con un `getItem` y un `setItem` que tiran error.
2. **Valor guardado corrupto** (por ejemplo, `"yes"` o `{}` en la clave del menú). Se ignora y se usa el valor por defecto. Lo cubre la Task 2.
3. **Menú plegado sin perder accesibilidad.** Cada botón conserva su nombre accesible ("Simulador", etc.) y el `aria-current`, porque los tests de App y el lector de pantalla dependen de eso. Lo cubre la Task 3.
4. **Reglas CSS perdidas al repartir `index.css`.** Si se pierde un selector, alguna sección queda rota sin que falle ningún test. La Task 5 lo controla con el script de comparación de selectores, y la Task 8 con la recorrida visual.
5. **Texto ilegible sobre colores de acción** (celdas de la matriz con texto blanco sobre verde claro, por ejemplo). Lo cubre la Task 1 con el test de contraste, y la Task 6 con el color `--matrix-ink` en las celdas llenas.

---

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `src/styles/tokens.css` (nuevo) | Variables de paleta, acciones, espaciado, radios, tipografía y alias de nombres viejos. |
| `src/styles/contrast.ts` (nuevo) | Funciones puras de luminancia y contraste WCAG, más el parser de tokens hex. |
| `src/styles/tokens.test.ts` (nuevo) | Verifica los pares de contraste sobre `tokens.css`. |
| `src/styles/index.css` (nuevo) | Solo `@import`, en orden. |
| `src/styles/base.css` (nuevo) | Reset, tipografía, controles, panel, utilidades. |
| `src/styles/cards.css` (nuevo) | Cartas de juego, card picker, mini-cartas. |
| `src/styles/matrix.css` (nuevo) | Matriz 13×13, vista previa de rangos, chips de acción. |
| `src/simulator/simulator.css` (nuevo) | Layout del simulador, resultados, recomendación. |
| `src/ranges/ranges.css` (nuevo) | Charts page, editor, tabla de rangos. |
| `src/pushfold/pushfold.css` (nuevo) | Grilla de stacks y torneo. |
| `src/solver/solver.css` (nuevo) | Página del solver. |
| `src/history/history.css` (nuevo) | Historiales, replayer, filtros y tablas de stats. |
| `src/stats/stats.css` (nuevo) | Gráfico de ganancias y leaks. |
| `src/trainer/trainer.css` (nuevo) | Entrenador. |
| `src/index.css` (se borra) | Su contenido se reparte entre los archivos de arriba. |
| `src/app/storage.ts` (nuevo) + test | `readStored` y `writeStored`, a prueba de errores. |
| `src/app/sections.ts` (nuevo) | Ids, etiquetas, íconos y grupos del menú. |
| `src/app/Sidebar.tsx` (nuevo) + `Sidebar.css` + test | Menú lateral agrupado y plegable. |
| `src/app/shell.css` (nuevo) | Layout de la app: sidebar más contenido, banner. |
| `src/App.tsx` (se modifica) | Usa `Sidebar` y saca las pestañas, el header y el footer. |
| `src/ui/cx.ts` (nuevo) | Une nombres de clase. |
| `src/ui/Button.tsx`, `Card.tsx`, `Select.tsx`, `Stat.tsx` (nuevos) + CSS + tests | Componentes simples. |
| `src/ui/ChoiceGroup.tsx` (nuevo) | Base de `PillGroup` y `SegmentList` (radios nativos estilizados). |
| `src/ui/RadioList.tsx`, `PillGroup.tsx`, `SegmentList.tsx` (nuevos) + CSS + tests | Selección única. |
| `src/ui/Chip.tsx`, `Popover.tsx` (nuevos) + CSS + tests | Resumen con acción y panel flotante. |
| `src/ui/index.ts` (nuevo) | Exporta los componentes. |

---

### Task 1: Tokens "Paño y oro" con test de contraste

**Files:**
- Create: `src/frontend/src/styles/tokens.css`
- Create: `src/frontend/src/styles/contrast.ts`
- Test: `src/frontend/src/styles/tokens.test.ts`

**Interfaces:**
- Produces:
  - Las variables CSS de la tabla de abajo, que usan todas las tareas.
  - `parseHexTokens(css: string): Record<string, string>`
  - `contrastRatio(a: string, b: string): number`

- [ ] **Step 1: Escribir el test que falla**

`src/frontend/src/styles/tokens.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { contrastRatio, parseHexTokens } from './contrast'
import tokensCss from './tokens.css?raw'

const t = parseHexTokens(tokensCss)

describe('contrastRatio', () => {
  it('matches the WCAG reference values', () => {
    expect(contrastRatio('#000000', '#ffffff')).toBeCloseTo(21, 1)
    expect(contrastRatio('#ffffff', '#ffffff')).toBeCloseTo(1, 5)
    expect(contrastRatio('#777777', '#ffffff')).toBeCloseTo(4.48, 2)
  })
})

describe('parseHexTokens', () => {
  it('reads only hex custom properties', () => {
    expect(parseHexTokens(':root { --a: #0d1a14; --b: var(--a); --c:#FFF; }')).toEqual({
      '--a': '#0d1a14',
      '--c': '#ffffff',
    })
  })
})

describe('Paño y oro tokens', () => {
  // [foreground, background]: every pair renders normal-size text.
  const pairs: [string, string][] = [
    ['--text', '--bg'],
    ['--text', '--bg-deep'],
    ['--text', '--surface'],
    ['--text', '--surface-2'],
    ['--text-muted', '--bg'],
    ['--text-muted', '--bg-deep'],
    ['--text-muted', '--surface'],
    ['--text-muted', '--surface-2'],
    ['--text-muted', '--grid-empty'],
    ['--gold', '--bg'],
    ['--gold', '--bg-deep'],
    ['--gold', '--surface'],
    ['--gold', '--surface-2'],
    ['--gold-ink', '--gold'],
    ['--on-danger', '--danger'],
    ['--info', '--surface'],
    ['--warn', '--surface'],
    ['--positive', '--surface'],
    ['--negative', '--surface'],
    ['--suit-s', '--card-bg'],
    ['--suit-h', '--card-bg'],
    ['--suit-d', '--card-bg'],
    ['--suit-c', '--card-bg'],
    ...['raise', 'limp', 'call', '3bet', '4bet', '5bet', 'allin'].map(
      (a): [string, string] => ['--matrix-ink', `--action-${a}`],
    ),
  ]

  it.each(pairs)('%s on %s reaches 4.5:1', (fg, bg) => {
    expect(t[fg], fg).toBeDefined()
    expect(t[bg], bg).toBeDefined()
    expect(contrastRatio(t[fg], t[bg])).toBeGreaterThanOrEqual(4.5)
  })

  it('is dark-only (no light/dark media switch)', () => {
    expect(tokensCss).not.toContain('prefers-color-scheme')
  })
})
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd src/frontend && npx vitest run src/styles/tokens.test.ts`
Expected: FAIL porque no se puede resolver `./contrast` ni `./tokens.css?raw`.

- [ ] **Step 3: Escribir `contrast.ts`**

`src/frontend/src/styles/contrast.ts`:

```ts
/** WCAG 2.x relative luminance and contrast ratio, plus a reader for hex tokens in a CSS string. */

function channel(v: number): number {
  const c = v / 255
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
}

function luminance(hex: string): number {
  const h = hex.replace('#', '')
  const full = h.length === 3 ? [...h].map((c) => c + c).join('') : h
  const [r, g, b] = [0, 2, 4].map((i) => channel(parseInt(full.slice(i, i + 2), 16)))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

export function contrastRatio(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

/** `--name: #abc;` / `--name: #aabbcc;` declarations, lower-cased and expanded to 6 digits. */
export function parseHexTokens(css: string): Record<string, string> {
  const out: Record<string, string> = {}
  for (const m of css.matchAll(/(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3})\s*;/g)) {
    const h = m[2].toLowerCase().slice(1)
    out[m[1]] = '#' + (h.length === 3 ? [...h].map((c) => c + c).join('') : h)
  }
  return out
}
```

- [ ] **Step 4: Escribir `tokens.css`**

`src/frontend/src/styles/tokens.css`:

```css
/* POKKER design tokens: "Paño y oro" (dark only). Spec: docs/superpowers/specs/2026-10-10-rediseno-ui-design.md §2.1 */
:root {
  color-scheme: dark;

  /* Surfaces and text */
  --bg: #0d1a14;
  --bg-deep: #0a140f;
  --surface: #13261c;
  --surface-2: #1c3527;
  --line: #1f3a2b;
  --line-strong: #2c4a39;
  --text: #e8efe9;
  --text-muted: #8fa898;
  --text-dim: #4d6b58;

  /* Accent and states */
  --gold: #d9b45a;
  --gold-ink: #1a1406;
  --danger: #c2524a;
  --on-danger: #ffffff;
  --ok: #2f9e63;
  --info: #4a8fd1;
  --warn: #e0a84a;
  --positive: #4cc38a;
  --negative: #e0736b;

  /* Poker table (simulator, part 3) */
  --felt: #1f6b45;
  --felt-edge: #0f3d28;
  --rail: #3a2a16;

  /* Range matrix: text on filled cells and colour per action */
  --matrix-ink: #0b1510;
  --grid-empty: #1a2e23;
  --action-raise: #2f9e63;
  --action-limp: #7fb69a;
  --action-call: #4a8fd1;
  --action-3bet: #9b6bd6;
  --action-4bet: #d07a3a;
  --action-5bet: #c96a4f;
  --action-allin: #d4625a;
  --action-fold: #1a2e23;
  --action-check: var(--action-call);
  --action-bet: var(--action-raise);

  /* Playing cards: light face, four-colour deck */
  --card-bg: #f7f3ea;
  --suit-s: #1b1f1d;
  --suit-h: #c62828;
  --suit-d: #1565c0;
  --suit-c: #2e7d32;

  /* Winnings chart series */
  --series-total: #4cc38a;
  --series-showdown: #4a8fd1;
  --series-nonshowdown: #e0736b;
  --series-ev: #c3c2b7;

  /* Legacy names still used by older sections */
  --muted: var(--text-muted);
  --border: var(--line-strong);
  --accent: var(--gold);
  --on-accent: var(--gold-ink);

  /* Spacing, radii, type */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 24px;
  --space-6: 32px;
  --radius-control: 6px;
  --radius-card: 10px;
  --radius-box: 12px;
  --font: 'Segoe UI', system-ui, sans-serif;
  --sidebar-width: 170px;
  --sidebar-width-collapsed: 48px;

  font-family: var(--font);
  line-height: 1.5;
  color: var(--text);
  background: var(--bg);
}
```

- [ ] **Step 5: Correr el test y verificar que pasa**

Run: `cd src/frontend && npx vitest run src/styles/tokens.test.ts`
Expected: PASS, con 33 tests en verde.

- [ ] **Step 6: Commit**

```bash
git add src/frontend/src/styles/tokens.css src/frontend/src/styles/contrast.ts src/frontend/src/styles/tokens.test.ts
git commit -m "feat(ui): Paño y oro design tokens with WCAG contrast test"
```

---

### Task 2: `localStorage` a prueba de errores

**Files:**
- Create: `src/frontend/src/app/storage.ts`
- Test: `src/frontend/src/app/storage.test.ts`

**Interfaces:**
- Produces:
  - `readStored<T>(key: string, fallback: T, isValid: (v: unknown) => v is T): T`
  - `writeStored(key: string, value: unknown): void`
  - `isBoolean(v: unknown): v is boolean`
- Consumers: `App.tsx` (Task 3) y, más adelante, las partes 2 y 3 (`pokker.preflop.filters`, `pokker.simulator.table`).

- [ ] **Step 1: Escribir el test que falla**

`src/frontend/src/app/storage.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from 'vitest'
import { isBoolean, readStored, writeStored } from './storage'

afterEach(() => {
  vi.restoreAllMocks()
  window.localStorage.clear()
})

describe('readStored / writeStored', () => {
  it('round-trips a valid value', () => {
    writeStored('k', true)
    expect(readStored('k', false, isBoolean)).toBe(true)
  })

  it('returns the fallback when the key is missing', () => {
    expect(readStored('missing', false, isBoolean)).toBe(false)
  })

  it('returns the fallback for corrupt JSON or a value of the wrong type', () => {
    window.localStorage.setItem('k', '{not json')
    expect(readStored('k', false, isBoolean)).toBe(false)
    window.localStorage.setItem('k', '"yes"')
    expect(readStored('k', false, isBoolean)).toBe(false)
    window.localStorage.setItem('k', '{}')
    expect(readStored('k', false, isBoolean)).toBe(false)
  })

  it('returns the fallback when localStorage throws on read', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(readStored('k', false, isBoolean)).toBe(false)
  })

  it('ignores errors when localStorage throws on write', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('quota')
    })
    expect(() => writeStored('k', true)).not.toThrow()
  })
})
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd src/frontend && npx vitest run src/app/storage.test.ts`
Expected: FAIL porque no se puede resolver `./storage`.

- [ ] **Step 3: Escribir la implementación**

`src/frontend/src/app/storage.ts`:

```ts
/**
 * Per-viewer conveniences (collapsed menu, last filters, last table) in localStorage.
 * Storage can be missing or throw (private mode, blocked site data): every access
 * falls back silently so the app always renders.
 */

export function readStored<T>(key: string, fallback: T, isValid: (v: unknown) => v is T): T {
  try {
    const raw = window.localStorage.getItem(key)
    if (raw === null) return fallback
    const value: unknown = JSON.parse(raw)
    return isValid(value) ? value : fallback
  } catch {
    return fallback
  }
}

export function writeStored(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Not persisted this time; the in-memory state still works.
  }
}

export function isBoolean(v: unknown): v is boolean {
  return typeof v === 'boolean'
}
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `cd src/frontend && npx vitest run src/app/storage.test.ts`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/app/storage.ts src/frontend/src/app/storage.test.ts
git commit -m "feat(ui): failure-safe localStorage helpers"
```

---

### Task 3: Menú lateral agrupado y plegable

**Files:**
- Create: `src/frontend/src/app/sections.ts`
- Create: `src/frontend/src/app/Sidebar.tsx`
- Create: `src/frontend/src/app/Sidebar.css`
- Create: `src/frontend/src/app/shell.css`
- Modify: `src/frontend/src/App.tsx` (todo el bloque de `return`, más las constantes `SECTIONS` y `AVAILABLE`)
- Modify: `src/frontend/src/stats/LeaksPanel.tsx:312`, `src/frontend/src/stats/StatsPage.tsx:131` y `src/frontend/src/pushfold/PushFoldPage.tsx:120` (los textos que nombran secciones)
- Test: `src/frontend/src/app/Sidebar.test.tsx`
- Modify test: `src/frontend/src/App.test.tsx:21` y `src/frontend/src/stats/LeaksPanel.test.tsx:142`

**Interfaces:**
- Consumes: `readStored`, `writeStored` e `isBoolean` (Task 2).
- Produces:
  - `type SectionId = 'ranges' | 'simulator' | 'pushfold' | 'trainer' | 'history' | 'replayer' | 'stats' | 'solver'`
  - `NAV_GROUPS: readonly { title: string; items: readonly { id: SectionId; label: string; icon: string }[] }[]`
  - `Sidebar` props: `{ current: SectionId; onSelect: (id: SectionId) => void; collapsed: boolean; onToggle: () => void; status: ReactNode }`
  - `SIDEBAR_KEY = 'pokker.sidebar.collapsed'`

Estos cambios de etiqueta van en esta task, porque son textos del menú (spec §1 y mockup `2-navegacion.html`):
- "Rangos preflop" pasa a **"Preflop"**.
- "Historiales" pasa a **"Manos"**.
- "Push/fold" pasa a **"Push/Fold"**.

Hoy todas las secciones están habilitadas (las 8 están en `AVAILABLE`), así que se borran `phase`, `AVAILABLE` y `.tab-phase`. La regla de §2.3 sobre secciones deshabilitadas no aplica a ninguna.

Los títulos de grupo ("Estudiar" y "Analizar") usan `--text-muted` y no `--text-dim`. Con `--text-dim`, el contraste daría 2,9:1, y el requisito global de 4,5:1 tiene prioridad sobre la tabla del spec.

- [ ] **Step 1: Escribir el test del Sidebar que falla**

`src/frontend/src/app/Sidebar.test.tsx`:

```tsx
import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Sidebar } from './Sidebar'

function setup(collapsed = false) {
  const onSelect = vi.fn()
  const onToggle = vi.fn()
  render(
    <Sidebar current="simulator" onSelect={onSelect} collapsed={collapsed} onToggle={onToggle} status="Backend 0.7.0" />,
  )
  return { onSelect, onToggle }
}

describe('Sidebar', () => {
  it('groups sections under Estudiar and Analizar', () => {
    setup()
    const study = screen.getByRole('group', { name: 'Estudiar' })
    expect(within(study).getAllByRole('button').map((b) => b.textContent)).toEqual([
      '♦Preflop',
      '⬭Simulador',
      '⇪Push/Fold',
      '✎Entrenador',
    ])
    const analyze = screen.getByRole('group', { name: 'Analizar' })
    expect(within(analyze).getAllByRole('button')).toHaveLength(4)
    expect(within(analyze).getByRole('button', { name: 'Manos' })).toBeInTheDocument()
  })

  it('marks the current section and selects another', () => {
    const { onSelect } = setup()
    expect(screen.getByRole('button', { name: 'Simulador' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('button', { name: 'Preflop' })).not.toHaveAttribute('aria-current')
    fireEvent.click(screen.getByRole('button', { name: 'Estadísticas' }))
    expect(onSelect).toHaveBeenCalledWith('stats')
  })

  it('keeps accessible names and status when collapsed', () => {
    setup(true)
    expect(screen.getByRole('navigation', { name: 'Secciones' })).toHaveClass('sidebar-collapsed')
    expect(screen.getByRole('button', { name: 'Simulador' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('button', { name: 'Simulador' })).toHaveAttribute('title', 'Simulador')
    expect(screen.getByText('Backend 0.7.0')).toBeInTheDocument()
  })

  it('toggles with an accessible button', () => {
    const { onToggle } = setup(false)
    const toggle = screen.getByRole('button', { name: 'Plegar menú' })
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    fireEvent.click(toggle)
    expect(onToggle).toHaveBeenCalledOnce()
  })

  it('offers to expand when collapsed', () => {
    setup(true)
    expect(screen.getByRole('button', { name: 'Desplegar menú' })).toHaveAttribute('aria-expanded', 'false')
  })
})
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd src/frontend && npx vitest run src/app/Sidebar.test.tsx`
Expected: FAIL porque no se puede resolver `./Sidebar`.

- [ ] **Step 3: Escribir `sections.ts`**

`src/frontend/src/app/sections.ts`:

```ts
export type SectionId = 'ranges' | 'simulator' | 'pushfold' | 'trainer' | 'history' | 'replayer' | 'stats' | 'solver'

export interface SectionDef {
  id: SectionId
  label: string
  icon: string
}

export const NAV_GROUPS: readonly { title: string; items: readonly SectionDef[] }[] = [
  {
    title: 'Estudiar',
    items: [
      { id: 'ranges', label: 'Preflop', icon: '♦' },
      { id: 'simulator', label: 'Simulador', icon: '⬭' },
      { id: 'pushfold', label: 'Push/Fold', icon: '⇪' },
      { id: 'trainer', label: 'Entrenador', icon: '✎' },
    ],
  },
  {
    title: 'Analizar',
    items: [
      { id: 'history', label: 'Manos', icon: '☰' },
      { id: 'replayer', label: 'Replayer', icon: '▶' },
      { id: 'stats', label: 'Estadísticas', icon: '▤' },
      { id: 'solver', label: 'Solver', icon: '⚙' },
    ],
  },
]

export const SIDEBAR_KEY = 'pokker.sidebar.collapsed'
```

- [ ] **Step 4: Escribir `Sidebar.tsx`**

`src/frontend/src/app/Sidebar.tsx`:

```tsx
import type { ReactNode } from 'react'
import { NAV_GROUPS, type SectionId } from './sections'
import './Sidebar.css'

interface Props {
  current: SectionId
  onSelect: (id: SectionId) => void
  collapsed: boolean
  onToggle: () => void
  status: ReactNode
}

export function Sidebar({ current, onSelect, collapsed, onToggle, status }: Props) {
  return (
    <nav className={`sidebar${collapsed ? ' sidebar-collapsed' : ''}`} aria-label="Secciones">
      <div className="sidebar-top">
        <h1 className="sidebar-logo">
          <span aria-hidden="true">♠</span>
          <span className="sidebar-text">POKKER</span>
        </h1>
        <button
          type="button"
          className="sidebar-toggle"
          aria-label={collapsed ? 'Desplegar menú' : 'Plegar menú'}
          aria-expanded={!collapsed}
          title={collapsed ? 'Desplegar menú' : 'Plegar menú'}
          onClick={onToggle}
        >
          <span aria-hidden="true">{collapsed ? '»' : '«'}</span>
        </button>
      </div>

      {NAV_GROUPS.map((group) => (
        <div key={group.title} role="group" aria-label={group.title} className="sidebar-group">
          <div className="sidebar-group-title" aria-hidden="true">
            {group.title}
          </div>
          {group.items.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`sidebar-item${current === item.id ? ' sidebar-item-active' : ''}`}
              aria-current={current === item.id ? 'page' : undefined}
              title={item.label}
              onClick={() => onSelect(item.id)}
            >
              <span className="sidebar-icon" aria-hidden="true">
                {item.icon}
              </span>
              <span className="sidebar-text">{item.label}</span>
            </button>
          ))}
        </div>
      ))}

      <div className="sidebar-status" aria-live="polite">
        <span className="sidebar-text">{status}</span>
      </div>
    </nav>
  )
}
```

Cuando el menú está plegado, `.sidebar-text` se oculta con el patrón `sr-only`, así que el nombre accesible del botón sigue siendo "Simulador". El ícono es `aria-hidden`. Ese es el punto 3 del Review Focus.

- [ ] **Step 5: Escribir `Sidebar.css`**

`src/frontend/src/app/Sidebar.css`:

```css
.sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  width: var(--sidebar-width);
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--space-3) var(--space-2);
  background: var(--bg-deep);
  border-right: 1px solid var(--line);
  overflow-y: auto;
  transition: width 0.15s ease;
}

.sidebar-collapsed {
  width: var(--sidebar-width-collapsed);
  padding-inline: var(--space-1);
}

.sidebar-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 0 var(--space-2) var(--space-2);
  gap: var(--space-1);
}

.sidebar-collapsed .sidebar-top {
  flex-direction: column;
  margin-inline: 0;
}

.sidebar-logo {
  margin: 0;
  display: flex;
  gap: 6px;
  font-size: 15px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: var(--gold);
}

.sidebar-toggle {
  border: none;
  background: none;
  color: var(--text-muted);
  padding: 2px 6px;
  font-size: 14px;
}

.sidebar-toggle:hover {
  color: var(--gold);
}

.sidebar-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sidebar-group-title {
  margin: var(--space-3) var(--space-2) var(--space-1);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.sidebar-collapsed .sidebar-group-title {
  visibility: hidden;
  height: 1px;
  margin-block: var(--space-2);
}

.sidebar-item {
  display: flex;
  align-items: center;
  gap: 9px;
  width: 100%;
  padding: 7px 10px;
  border: none;
  border-radius: var(--radius-control);
  background: none;
  color: var(--text-muted);
  text-align: left;
  font-size: 13px;
}

.sidebar-item:hover {
  background: var(--surface);
  color: var(--text);
}

.sidebar-item-active,
.sidebar-item-active:hover {
  background: var(--surface-2);
  color: var(--gold);
  font-weight: 700;
}

.sidebar-collapsed .sidebar-item {
  justify-content: center;
  padding-inline: 0;
}

.sidebar-icon {
  width: 16px;
  text-align: center;
  flex-shrink: 0;
}

.sidebar-status {
  margin-top: auto;
  padding: var(--space-2);
  font-size: 11px;
  color: var(--text-muted);
}

.sidebar-status-line {
  display: block;
}

/* Collapsed: labels stay in the accessibility tree, hidden visually (same as .sr-only). */
.sidebar-collapsed .sidebar-text {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}
```

- [ ] **Step 6: Correr el test del Sidebar y verificar que pasa**

Run: `cd src/frontend && npx vitest run src/app/Sidebar.test.tsx`
Expected: PASS (5 tests).

- [ ] **Step 7: Actualizar los tests de App que fallan con el cambio**

En `src/frontend/src/App.test.tsx`, reemplazar la línea 21:

```tsx
    expect(screen.getByRole('heading', { name: 'Poker Study' })).toBeInTheDocument()
```

por:

```tsx
    expect(screen.getByRole('heading', { name: 'POKKER' })).toBeInTheDocument()
```

Agregar al final del `describe('App', ...)` un test que fija la persistencia del menú:

```tsx
  it('remembers the collapsed menu and survives a broken localStorage', () => {
    mockApi({
      'GET /api/version': () => ({ json: { app: '0.1.0', core: '0.1.0' } }),
      'GET /api/simulator/positions': () => ({ json: POSITIONS }),
      'POST /api/ranges/parse': () => ({ json: { valid: true, error: null, combos: 1326, grid: [] } }),
    })
    window.localStorage.setItem('pokker.sidebar.collapsed', 'true')
    const { unmount } = render(<App />)
    expect(screen.getByRole('navigation', { name: 'Secciones' })).toHaveClass('sidebar-collapsed')
    fireEvent.click(screen.getByRole('button', { name: 'Desplegar menú' }))
    expect(window.localStorage.getItem('pokker.sidebar.collapsed')).toBe('false')
    unmount()

    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    render(<App />)
    expect(screen.getByRole('navigation', { name: 'Secciones' })).not.toHaveClass('sidebar-collapsed')
    window.localStorage.clear()
  })
```

En `src/frontend/src/stats/LeaksPanel.test.tsx:142`, reemplazar `/Importá tus historiales en Historiales/` por `/Importá tus historiales en Manos/`.

- [ ] **Step 8: Correr los tests de App y verificar que fallan**

Run: `cd src/frontend && npx vitest run src/App.test.tsx src/stats/LeaksPanel.test.tsx`
Expected: FAIL. No hay heading "POKKER", no existe `sidebar-collapsed` y el texto del leak todavía dice "Historiales".

- [ ] **Step 9: Reescribir `App.tsx` con el Sidebar**

En `src/frontend/src/App.tsx`:

1. Borrar las constantes `SECTIONS` y `AVAILABLE` (líneas 14 a 25).
2. Agregar estos imports:

```tsx
import { Sidebar } from './app/Sidebar'
import { SIDEBAR_KEY, type SectionId } from './app/sections'
import { isBoolean, readStored, writeStored } from './app/storage'
import './app/shell.css'
```

3. Cambiar el estado de la sección y agregar el del menú:

```tsx
  const [section, setSection] = useState<SectionId>('simulator')
  const [collapsed, setCollapsed] = useState(() => readStored(SIDEBAR_KEY, false, isBoolean))

  function toggleSidebar() {
    setCollapsed((c) => {
      writeStored(SIDEBAR_KEY, !c)
      return !c
    })
  }
```

4. Reemplazar el `return (...)` completo por esto (el contenido de `<main>` queda igual, salvo el texto "Historiales" → "Manos"):

```tsx
  const status =
    backend.state === 'loading'
      ? 'Conectando con el backend…'
      : backend.state === 'ok'
        ? `Backend ${backend.info.app} · núcleo ${backend.info.core}`
        : 'Backend no disponible'

  return (
    <div className="app-shell">
      {serverDown && (
        <div className="server-down-banner" role="alert">
          POKKER se cerró. Abrilo de nuevo desde el ícono o con doble clic en POKKER.exe.
        </div>
      )}
      <Sidebar
        current={section}
        onSelect={setSection}
        collapsed={collapsed}
        onToggle={toggleSidebar}
        status={
          <>
            <span className="sidebar-status-line">{status}</span>
            <span className="sidebar-status-line">Versión {__APP_VERSION__}</span>
          </>
        }
      />
      <main className="app-main">
        {section === 'simulator' && <SimulatorPage key={spot?.key ?? 0} initial={spot?.scenario} />}
        {section === 'history' && (
          <HistoryPage
            onOpen={(id) => {
              setHandId(id)
              setSection('replayer')
            }}
          />
        )}
        {section === 'replayer' &&
          (handId === null ? (
            <p className="muted">Elegí una mano en Manos para reproducirla.</p>
          ) : (
            <ReplayerView
              handId={handId}
              onBack={() => setSection('history')}
              onAnalyze={(scenario) => {
                setSpot({ key: Date.now(), scenario })
                setSection('simulator')
              }}
            />
          ))}
        {section === 'stats' && (
          <StatsPage
            onTrain={(filters) => {
              setTrainer({ key: Date.now(), filters: { ...filters, preferDue: true } })
              setSection('trainer')
            }}
          />
        )}
        {section === 'ranges' && <ChartsPage />}
        {section === 'pushfold' && <PushFoldPage />}
        {section === 'solver' && <SolverPage />}
        {section === 'trainer' && <TrainerPage key={trainer.key} initialFilters={trainer.filters} />}
      </main>
    </div>
  )
```

Cada línea va en su propio `<span>`. Así el test existente `findByText('Backend 0.1.0 · núcleo 0.1.0')` encuentra un elemento cuyo texto completo es exactamente esa cadena. Con un `<br />` dentro de un solo span no la encontraría.

5. Cambiar los textos que nombran secciones:
   - `src/frontend/src/stats/LeaksPanel.tsx:312`: "Importá tus historiales en Historiales para ver tus leaks." pasa a "Importá tus historiales en Manos para ver tus leaks."
   - `src/frontend/src/stats/StatsPage.tsx:131`: "Importalas en Historiales." pasa a "Importalas en Manos."
   - `src/frontend/src/pushfold/PushFoldPage.tsx:120`: `Guardado en Rangos preflop: "${chart.name}".` pasa a `Guardado en Preflop: "${chart.name}".`

- [ ] **Step 10: Escribir `shell.css`**

`src/frontend/src/app/shell.css`:

```css
.app-shell {
  display: flex;
  min-height: 100vh;
  background: var(--bg);
}

.app-main {
  flex: 1;
  min-width: 0;
  padding: var(--space-5) var(--space-5) var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.server-down-banner {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 1000;
  padding: 10px 16px;
  background: var(--danger);
  color: var(--on-danger);
  font-weight: 600;
  text-align: center;
}
```

- [ ] **Step 11: Correr toda la suite del frontend**

Run: `cd src/frontend && npm test`
Expected: PASS en todos los archivos, incluidos `App.test.tsx`, `App.heartbeat.test.tsx` y `LeaksPanel.test.tsx`. Si algún test buscaba "Historiales" o "Rangos preflop", actualizalo al nombre nuevo.

- [ ] **Step 12: Typecheck y lint**

Run: `cd src/frontend && npm run typecheck && npm run lint`
Expected: sin errores.

- [ ] **Step 13: Commit**

```bash
git add src/frontend/src/app src/frontend/src/App.tsx src/frontend/src/App.test.tsx src/frontend/src/stats src/frontend/src/pushfold/PushFoldPage.tsx
git commit -m "feat(ui): grouped collapsible sidebar replaces the top tabs"
```

---

### Task 4: Componentes simples (`Button`, `Card`, `Select`, `Stat`)

**Files:**
- Create: `src/frontend/src/ui/cx.ts`
- Create: `src/frontend/src/ui/Button.tsx`, `src/frontend/src/ui/Button.css`
- Create: `src/frontend/src/ui/Card.tsx`, `src/frontend/src/ui/Card.css`
- Create: `src/frontend/src/ui/Select.tsx`, `src/frontend/src/ui/Select.css`
- Create: `src/frontend/src/ui/Stat.tsx`, `src/frontend/src/ui/Stat.css`
- Create: `src/frontend/src/ui/index.ts`
- Test: `src/frontend/src/ui/basic.test.tsx`

**Interfaces:**
- Produces:
  - `cx(...parts: (string | false | null | undefined)[]): string`
  - `Button`: props de `<button>` más `variant?: 'primary' | 'secondary' | 'ghost'` (default `'secondary'`) y `size?: 'sm' | 'md'` (default `'md'`). El `type` por defecto es `'button'`.
  - `Card`: `{ title?: string; className?: string; children: ReactNode }`. Renderiza `<section>` y, si hay título, `aria-labelledby` apunta a él.
  - `Select`: props de `<select>` más `label: string`. Renderiza `<label>` con el select adentro.
  - `Stat`: `{ label: string; value: string; detail?: string }`.

La clase de `Card` es `.ui-card` y no `.card`, porque `.card` ya se usa para las cartas de juego.

- [ ] **Step 1: Escribir el test que falla**

`src/frontend/src/ui/basic.test.tsx`:

```tsx
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Button, Card, Select, Stat } from '.'
import { cx } from './cx'

describe('cx', () => {
  it('joins truthy class names', () => {
    expect(cx('a', false, null, undefined, 'b')).toBe('a b')
  })
})

describe('Button', () => {
  it('defaults to a secondary md button of type "button"', () => {
    render(<Button>Copiar</Button>)
    const b = screen.getByRole('button', { name: 'Copiar' })
    expect(b).toHaveAttribute('type', 'button')
    expect(b).toHaveClass('btn', 'btn-secondary', 'btn-md')
  })

  it('applies variant, size and native props', () => {
    const onClick = vi.fn()
    render(
      <Button variant="primary" size="sm" className="extra" onClick={onClick}>
        Aplicar
      </Button>,
    )
    const b = screen.getByRole('button', { name: 'Aplicar' })
    expect(b).toHaveClass('btn-primary', 'btn-sm', 'extra')
    fireEvent.click(b)
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('does not fire when disabled', () => {
    const onClick = vi.fn()
    render(
      <Button disabled onClick={onClick}>
        Analizar
      </Button>,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Analizar' }))
    expect(onClick).not.toHaveBeenCalled()
  })
})

describe('Card', () => {
  it('is a region named by its title', () => {
    render(<Card title="Juego">contenido</Card>)
    expect(screen.getByRole('region', { name: 'Juego' })).toHaveTextContent('contenido')
  })

  it('renders without a title', () => {
    const { container } = render(<Card>solo</Card>)
    expect(container.querySelector('section.ui-card')).toHaveTextContent('solo')
  })
})

describe('Select', () => {
  it('is labelled and reports changes', () => {
    const onChange = vi.fn()
    render(
      <Select label="Stack efectivo" value="100" onChange={onChange}>
        <option value="40">40 BB</option>
        <option value="100">100 BB</option>
      </Select>,
    )
    const s = screen.getByRole('combobox', { name: 'Stack efectivo' })
    fireEvent.change(s, { target: { value: '40' } })
    expect(onChange).toHaveBeenCalledOnce()
  })
})

describe('Stat', () => {
  it('shows label, value and detail', () => {
    render(<Stat label="Rango" value="48,4%" detail="642 combos" />)
    expect(screen.getByText('Rango')).toBeInTheDocument()
    expect(screen.getByText('48,4%')).toHaveClass('ui-stat-value')
    expect(screen.getByText('642 combos')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd src/frontend && npx vitest run src/ui/basic.test.tsx`
Expected: FAIL porque no se pueden resolver `.` ni `./cx`.

- [ ] **Step 3: Escribir `cx.ts` y los componentes**

`src/frontend/src/ui/cx.ts`:

```ts
export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(' ')
}
```

`src/frontend/src/ui/Button.tsx`:

```tsx
import type { ButtonHTMLAttributes } from 'react'
import { cx } from './cx'
import './Button.css'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost'
  size?: 'sm' | 'md'
}

export function Button({ variant = 'secondary', size = 'md', type = 'button', className, ...rest }: ButtonProps) {
  return <button type={type} className={cx('btn', `btn-${variant}`, `btn-${size}`, className)} {...rest} />
}
```

`src/frontend/src/ui/Button.css`:

```css
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border-radius: var(--radius-control);
  border: 1px solid transparent;
  font-weight: 600;
  cursor: pointer;
}

.btn-md {
  padding: 8px 16px;
  font-size: 13px;
}

.btn-sm {
  padding: 5px 11px;
  font-size: 12px;
}

.btn-primary {
  background: var(--gold);
  color: var(--gold-ink);
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.btn-primary:hover:not(:disabled) {
  filter: brightness(1.08);
}

.btn-secondary {
  background: var(--surface);
  border-color: var(--line);
  color: var(--text);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--surface-2);
}

.btn-ghost {
  background: none;
  color: var(--gold);
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}
```

`src/frontend/src/ui/Card.tsx`:

```tsx
import { type ReactNode, useId } from 'react'
import { cx } from './cx'
import './Card.css'

interface Props {
  title?: string
  className?: string
  children: ReactNode
}

export function Card({ title, className, children }: Props) {
  const id = useId()
  return (
    <section className={cx('ui-card', className)} aria-labelledby={title ? id : undefined}>
      {title && (
        <h3 id={id} className="ui-card-title">
          {title}
        </h3>
      )}
      {children}
    </section>
  )
}
```

`src/frontend/src/ui/Card.css`:

```css
.ui-card {
  background: var(--surface);
  border-radius: var(--radius-card);
  padding: var(--space-3) var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.ui-card-title {
  margin: 0 0 var(--space-1);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--text-muted);
}
```

`src/frontend/src/ui/Select.tsx`:

```tsx
import type { SelectHTMLAttributes } from 'react'
import { cx } from './cx'
import './Select.css'

interface Props extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string
}

export function Select({ label, className, children, ...rest }: Props) {
  return (
    <label className={cx('ui-select', className)}>
      <span className="ui-select-label">{label}</span>
      <select {...rest}>{children}</select>
    </label>
  )
}
```

`src/frontend/src/ui/Select.css`:

```css
.ui-select {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.ui-select-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.ui-select select {
  background: var(--gold);
  color: var(--gold-ink);
  border: none;
  border-radius: var(--radius-control);
  padding: 7px 12px;
  font-weight: 800;
}
```

`src/frontend/src/ui/Stat.tsx`:

```tsx
import './Stat.css'

interface Props {
  label: string
  value: string
  detail?: string
}

export function Stat({ label, value, detail }: Props) {
  return (
    <div className="ui-stat">
      <div className="ui-stat-label">{label}</div>
      <div className="ui-stat-value">{value}</div>
      {detail && <div className="ui-stat-detail">{detail}</div>}
    </div>
  )
}
```

`src/frontend/src/ui/Stat.css`:

```css
.ui-stat-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.ui-stat-value {
  font-size: 24px;
  font-weight: 800;
  color: var(--gold);
  line-height: 1.2;
}

.ui-stat-detail {
  color: var(--text-muted);
  font-size: 12px;
}
```

`src/frontend/src/ui/index.ts`:

```ts
export { Button } from './Button'
export { Card } from './Card'
export { Select } from './Select'
export { Stat } from './Stat'
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `cd src/frontend && npx vitest run src/ui/basic.test.tsx`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/ui
git commit -m "feat(ui): Button, Card, Select and Stat base components"
```

---

### Task 5: Repartir `index.css` en archivos por área

Es una mudanza mecánica: **no cambia ninguna regla**, solo dónde vive cada una. El estilo nuevo se aplica en la Task 6.

**Files:**
- Create: `src/frontend/src/styles/index.css`, `base.css`, `cards.css`, `matrix.css`
- Create: `src/frontend/src/simulator/simulator.css`, `src/frontend/src/ranges/ranges.css`, `src/frontend/src/pushfold/pushfold.css`, `src/frontend/src/solver/solver.css`, `src/frontend/src/history/history.css`, `src/frontend/src/stats/stats.css`, `src/frontend/src/trainer/trainer.css`
- Modify: `src/frontend/src/main.tsx:4` (`./index.css` pasa a `./styles/index.css`)
- Delete: `src/frontend/src/index.css`

**Interfaces:**
- Consumes: `tokens.css` (Task 1) y `shell.css` (Task 3).
- Produces: el orden de importación de abajo. Las tareas que siguen agregan reglas a estos archivos.

- [ ] **Step 1: Sacar la lista de selectores de antes**

Run (desde la raíz del repo):

```bash
node -e "const s=require('fs').readFileSync('src/frontend/src/index.css','utf8').replace(/\/\*[\s\S]*?\*\//g,'');const m=[...s.matchAll(/([^{}]+)\{/g)].map(x=>x[1].trim().replace(/\s+/g,' '));require('fs').writeFileSync(process.env.TEMP+'/sel-before.txt',m.sort().join('\n'))"
```

Expected: crea `%TEMP%\sel-before.txt`, con un selector (o `@media`) por línea.

- [ ] **Step 2: Crear los archivos y mover cada bloque según la tabla**

Mové cada regla de `src/frontend/src/index.css` **tal cual** al archivo que indica la tabla. Respetá el orden relativo dentro de cada archivo. Las reglas duplicadas (por ejemplo, `.flop-list` y `.rec-warnings`, que aparecen dos veces) quedan las dos, en el mismo orden. Cada `@media` va al archivo de las clases que contiene.

| Selectores (tal cual aparecen en `index.css`) | Destino |
|---|---|
| `:root { … }` y el `@media (prefers-color-scheme: dark)` de las líneas 1 a 76 | **Se borran** (los reemplaza `tokens.css`) |
| `.app`, `.app-header h1`, `.subtitle`, `.server-down-banner`, `.app-footer`, `.tabs`, `.tab`, `.tab-active`, `.tab-phase` (líneas 87 a 152) | **Se borran** (los reemplaza `app/shell.css`) |
| `*`, `body` | `styles/base.css` |
| Todo lo de `/* ---- Controls ---- */`: `button, select, input, textarea` hasta `.small` | `styles/base.css` |
| `.panel`, `.panel h3`, `.panel-header`, `.panel-info`, `.panel-muted`, `.actions`, `.panel > button, .panel > .file-button` | `styles/base.css` |
| `.file-button`, `.file-button input`, `.file-button:focus-within`, `.table-scroll`, `.sr-only`, `kbd` | `styles/base.css` |
| `.card-slots, .outs-cards` hasta `.card-picker-actions` (bloque `/* ---- Cards ---- */`), `.mini-cards`, `.mini-cards .card`, `.mini-cards .card-suit` | `styles/cards.css` |
| `.range-summary`, `.range-grid`, `.range-cell`, `.range-cell-on`, `.range-list` | `styles/matrix.css` |
| `.matrix`, `.matrix-cell`, `.matrix-cell-on`, `button.matrix-cell`, `.matrix-cell-highlight`, `.action-chips`, `.action-chip`, `.swatch` | `styles/matrix.css` |
| `.simulator` (con su `@media (max-width: 860px)`), `.sim-config, .results`, `.sim-results` | `simulator/simulator.css` |
| `.big-number`, `.equity-table*`, `.metrics*` (bloque `/* ---- Results ---- */`) | `simulator/simulator.css` |
| Todo el bloque `/* ---- Recommendation ---- */`: `.panel-rec` hasta `.badge-warn`, `.rec-actions`, `.rec-actions li` | `simulator/simulator.css` |
| `.chart-editor, .charts-page, .pushfold`, `.charts-table*`, `.row-selected`, `.row-actions` | `ranges/ranges.css` |
| `.stack-grid`, `.tournament summary`, `.tournament[open]` | `pushfold/pushfold.css` |
| Todo el bloque `/* ---- Solver tab ---- */`: `.solver-page` hasta el último `.rec-warnings` | `solver/solver.css` |
| Bloque `/* ---- History, replayer, stats ---- */` hasta antes de `/* Chart */`, salvo `.mini-cards*`: `.replayer`, `.filter-bar*`, `.position-filter*`, `.chart-table*`, `.num`, `.positive`, `.negative`, `.error-list`, `.excerpt`, `.metric-low`, `.metric-flag`, `.ci-line`, y `/* Replayer */` (`.replay-*`, `.seat-*`, `.is-hero`, `.is-actor`, `.is-folded`) | `history/history.css` |
| Bloque `/* Chart */`: `.chart` hasta `.chart-tooltip-row`, más `.leak-list`, `.leak-row`, `.leak-head` | `stats/stats.css` |
| Bloque `/* ---- Trainer ---- */` salvo `.matrix-cell-highlight` y `kbd` (`.trainer` hasta `.trainer-errors`), con sus dos `@media` (860 px y 640 px) | `trainer/trainer.css` |

`src/frontend/src/styles/index.css`:

```css
/* Global stylesheet: imported once from main.tsx. Order = cascade order. */
@import './tokens.css';
@import './base.css';
@import './cards.css';
@import './matrix.css';
@import '../simulator/simulator.css';
@import '../ranges/ranges.css';
@import '../pushfold/pushfold.css';
@import '../solver/solver.css';
@import '../history/history.css';
@import '../stats/stats.css';
@import '../trainer/trainer.css';
```

En `src/frontend/src/main.tsx`, reemplazar `import './index.css'` por `import './styles/index.css'`. Después borrar `src/frontend/src/index.css`.

- [ ] **Step 3: Comparar los selectores de antes y de después**

Run (desde la raíz del repo):

```bash
node -e "const fs=require('fs'),p=require('path');const files=['styles/base.css','styles/cards.css','styles/matrix.css','simulator/simulator.css','ranges/ranges.css','pushfold/pushfold.css','solver/solver.css','history/history.css','stats/stats.css','trainer/trainer.css'].map(f=>p.join('src/frontend/src',f));const s=files.map(f=>fs.readFileSync(f,'utf8')).join('\n').replace(/\/\*[\s\S]*?\*\//g,'');const after=[...s.matchAll(/([^{}]+)\{/g)].map(x=>x[1].trim().replace(/\s+/g,' ')).sort();const before=fs.readFileSync(process.env.TEMP+'/sel-before.txt','utf8').split('\n');const removed=[':root','@media (prefers-color-scheme: dark)','.app','.app-header h1','.subtitle','.server-down-banner','.app-footer','.tabs','.tab','.tab-active','.tab-phase'];const count=a=>a.reduce((m,x)=>(m[x]=(m[x]||0)+1,m),{});const b=count(before.filter(x=>!removed.includes(x))),a=count(after);const diff=[...new Set([...Object.keys(a),...Object.keys(b)])].filter(k=>a[k]!==b[k]);console.log(diff.length?diff.map(k=>k+': antes '+(b[k]||0)+', despues '+(a[k]||0)).join('\n'):'OK: mismos selectores')"
```

Expected: `OK: mismos selectores`. El script ya descuenta lo que se borra a propósito: los dos `:root`, el `@media` oscuro y las reglas del layout viejo. Cualquier otra diferencia es una regla perdida o duplicada: hay que corregirla antes de seguir.

- [ ] **Step 4: Verificar que build y tests siguen bien**

Run: `cd src/frontend && npm test && npm run build`
Expected: todos los tests en PASS y el build sin errores. Vite resuelve los `@import`.

- [ ] **Step 5: Commit**

```bash
git add -A src/frontend/src
git commit -m "refactor(ui): split index.css into per-area stylesheets"
```

---

### Task 6: Estilo "Paño y oro" en la base y en las áreas

Ajusta las reglas movidas en la Task 5 para que se vean como el mockup `1-paleta.html` (opción A). Esta task no cambia markup.

**Files:**
- Modify: `src/frontend/src/styles/base.css`
- Modify: `src/frontend/src/styles/matrix.css`
- Modify: `src/frontend/src/styles/cards.css`
- Modify: `src/frontend/src/simulator/simulator.css`

**Interfaces:**
- Consumes: los tokens de la Task 1 y las clases `btn-*` de la Task 4. `button.primary` se ve igual que `.btn-primary`.

- [ ] **Step 1: Controles y panel en `base.css`**

En `styles/base.css`, reemplazar estas reglas completas por las versiones de abajo. El resto queda como está.

```css
body {
  margin: 0;
  background: var(--bg);
  font-size: 14px;
}

h2,
h3 {
  color: var(--text);
}

button,
select,
input,
textarea {
  font: inherit;
  color: var(--text);
  background: var(--bg-deep);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-control);
  padding: 6px 10px;
}

button {
  cursor: pointer;
  background: var(--surface);
  border-color: var(--line);
}

button:hover:not(:disabled) {
  background: var(--surface-2);
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

/* Legacy primary buttons look like <Button variant="primary"> */
button.primary {
  background: var(--gold);
  border-color: var(--gold);
  color: var(--gold-ink);
  font-weight: 800;
  letter-spacing: 0.06em;
}

button.primary:hover:not(:disabled) {
  background: var(--gold);
  filter: brightness(1.08);
}

.link-button {
  border: none;
  background: none;
  color: var(--gold);
  padding: 0;
}

.link-button:hover:not(:disabled) {
  background: none;
  text-decoration: underline;
}

:focus-visible {
  outline: 2px solid var(--gold);
  outline-offset: 2px;
}

label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.panel {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-card);
  padding: var(--space-3) var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.panel h3 {
  margin: 0;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.panel-info {
  border-color: var(--info);
}

.file-button {
  position: relative;
  display: inline-flex;
  flex-direction: row;
  align-items: center;
  border: 1px solid var(--line);
  border-radius: var(--radius-control);
  padding: 6px 10px;
  cursor: pointer;
  background: var(--surface);
  color: var(--text);
}

.file-button:focus-within {
  outline: 2px solid var(--gold);
  outline-offset: 2px;
}
```

En `label.checkbox`, agregar `color: var(--text);`. Así las casillas del entrenador se leen con texto principal.

- [ ] **Step 2: Matriz con texto oscuro en las celdas llenas (`matrix.css`)**

Reemplazar `.matrix-cell` y `.matrix-cell-on`:

```css
.matrix-cell {
  aspect-ratio: 1.25;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: none;
  border-radius: 3px;
  font-size: clamp(0.5rem, 1.5vw, 0.7rem);
  font-weight: 700;
  color: var(--text-muted);
  overflow: hidden;
}

.matrix-cell-on {
  color: var(--matrix-ink);
}
```

En `.matrix`, cambiar `gap: 1px` por `gap: 2px`. En `.range-cell`, cambiar `color: var(--text)` por `color: var(--text-muted)`.

- [ ] **Step 3: Cartas (`cards.css`)**

En `.card`, cambiar `border: 1px solid var(--border)` por `border: 1px solid #d8d0bd` y agregar `color: #111;` y `box-shadow: 0 2px 4px #0006;`.

En `.card-empty`, reemplazar la regla por:

```css
.card-empty {
  border: 2px dashed var(--line-strong);
  background: transparent;
  color: var(--text-muted);
  box-shadow: none;
}
```

En `.card-picker`, cambiar `border: 1px solid var(--accent)` por `border: 1px solid var(--gold)` y `border-radius: 8px` por `border-radius: var(--radius-card)`.

- [ ] **Step 4: Resultados (`simulator.css`)**

En `.big-number`, cambiar `color: var(--accent)` por `color: var(--gold)` y `font-weight: 700` por `font-weight: 800`. En `.panel-rec`, cambiar `border-color: var(--accent)` por `border-color: var(--gold)`.

- [ ] **Step 5: Verificar tests y build**

Run: `cd src/frontend && npm test && npm run build`
Expected: todo en PASS y el build sin errores.

- [ ] **Step 6: Commit**

```bash
git add src/frontend/src/styles src/frontend/src/simulator/simulator.css
git commit -m "feat(ui): Paño y oro look for controls, panels, matrix and cards"
```

---

### Task 7: Componentes de selección (`RadioList`, `PillGroup`, `SegmentList`), `Chip` y `Popover`

**Files:**
- Create: `src/frontend/src/ui/RadioList.tsx`, `src/frontend/src/ui/RadioList.css`
- Create: `src/frontend/src/ui/ChoiceGroup.tsx`, `src/frontend/src/ui/ChoiceGroup.css`
- Create: `src/frontend/src/ui/PillGroup.tsx`, `src/frontend/src/ui/SegmentList.tsx`
- Create: `src/frontend/src/ui/Chip.tsx`, `src/frontend/src/ui/Chip.css`
- Create: `src/frontend/src/ui/Popover.tsx`, `src/frontend/src/ui/Popover.css`
- Modify: `src/frontend/src/ui/index.ts`
- Test: `src/frontend/src/ui/choice.test.tsx`, `src/frontend/src/ui/Popover.test.tsx`

**Interfaces:**
- Consumes: `cx` (Task 4).
- Produces (los usan las partes 2 y 3):
  - `interface Option<T extends string> { value: T; label: string; count?: number; disabled?: boolean }`
  - `RadioList<T>({ legend, options, value, onChange, name? })`. Muestra `count` entre paréntesis en gris. Con `count === 0` la opción se ve apagada (clase `ui-radio-dim`), pero **se puede elegir**.
  - `PillGroup<T>({ legend, options, value, onChange, name? })` en fila. Las opciones con `disabled: true` **no se pueden elegir**. `value` puede ser `null`.
  - `SegmentList<T>`: mismas props que `PillGroup`, en columna.
  - `Chip({ children, actionLabel?, onAction? })`
  - `Popover({ open, onClose, anchorRef, label, className?, children })`. Es `role="dialog"`. Al abrirse enfoca el primer elemento enfocable. Se cierra con Esc o con un clic fuera del popover y del ancla. Al cerrarse devuelve el foco al ancla. **No se posiciona solo**: quien lo usa le pasa `className` con la posición.

Las tres listas usan `<input type="radio">` nativos dentro de un `<fieldset>`. Así las flechas del teclado y el lector de pantalla funcionan sin código extra (spec §2.2).

- [ ] **Step 1: Escribir los tests que fallan**

`src/frontend/src/ui/choice.test.tsx`:

```tsx
import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Chip, PillGroup, RadioList, SegmentList } from '.'

const GAMES = [
  { value: 'cash', label: 'Cash', count: 12 },
  { value: 'mtt', label: 'Torneos', count: 40 },
  { value: 'sng', label: 'Sit & Go', count: 0 },
] as const

describe('RadioList', () => {
  it('renders a named group with counts and the current value checked', () => {
    render(<RadioList legend="Juego" options={[...GAMES]} value="cash" onChange={() => {}} />)
    const group = screen.getByRole('group', { name: 'Juego' })
    expect(within(group).getByRole('radio', { name: /Cash/ })).toBeChecked()
    expect(within(group).getByText('12')).toBeInTheDocument()
  })

  it('dims options with count 0 but still lets you pick them', () => {
    const onChange = vi.fn()
    render(<RadioList legend="Juego" options={[...GAMES]} value="cash" onChange={onChange} />)
    const sng = screen.getByRole('radio', { name: /Sit & Go/ })
    expect(sng).toBeEnabled()
    expect(sng.closest('label')).toHaveClass('ui-radio-dim')
    fireEvent.click(sng)
    expect(onChange).toHaveBeenCalledWith('sng')
  })

  it('uses one radio group per list so arrow keys stay inside it', () => {
    render(
      <>
        <RadioList legend="Juego" options={[...GAMES]} value="cash" onChange={() => {}} />
        <RadioList legend="Otro" options={[...GAMES]} value="mtt" onChange={() => {}} />
      </>,
    )
    const names = screen.getAllByRole('radio').map((r) => r.getAttribute('name'))
    expect(new Set(names).size).toBe(2)
  })
})

describe('PillGroup / SegmentList', () => {
  const POS = [
    { value: 'CO', label: 'CO' },
    { value: 'BTN', label: 'BTN' },
    { value: 'BB', label: 'BB', disabled: true },
  ]

  it('selects a pill and blocks disabled ones', () => {
    const onChange = vi.fn()
    render(<PillGroup legend="Tu posición" options={POS} value="BTN" onChange={onChange} />)
    expect(screen.getByRole('radio', { name: 'BTN' })).toBeChecked()
    expect(screen.getByRole('radio', { name: 'BB' })).toBeDisabled()
    fireEvent.click(screen.getByRole('radio', { name: 'CO' }))
    expect(onChange).toHaveBeenCalledWith('CO')
  })

  it('allows no selection', () => {
    render(<PillGroup legend="Rival" options={POS} value={null} onChange={() => {}} />)
    expect(screen.getAllByRole('radio').filter((r) => (r as HTMLInputElement).checked)).toHaveLength(0)
  })

  it('SegmentList renders vertically with the same behaviour', () => {
    const onChange = vi.fn()
    render(<SegmentList legend="Secuencia" options={POS} value="CO" onChange={onChange} />)
    expect(screen.getByRole('group', { name: 'Secuencia' })).toHaveClass('ui-choice-vertical')
    fireEvent.click(screen.getByRole('radio', { name: 'BTN' }))
    expect(onChange).toHaveBeenCalledWith('BTN')
  })
})

describe('Chip', () => {
  it('shows content and an optional action', () => {
    const onAction = vi.fn()
    render(
      <Chip actionLabel="Cambiar" onAction={onAction}>
        Cash · 6-max
      </Chip>,
    )
    expect(screen.getByText('Cash · 6-max')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Cambiar' }))
    expect(onAction).toHaveBeenCalledOnce()
  })

  it('has no button without an action', () => {
    render(<Chip>Solo texto</Chip>)
    expect(screen.queryByRole('button')).toBeNull()
  })
})
```

`src/frontend/src/ui/Popover.test.tsx`:

```tsx
import { fireEvent, render, screen } from '@testing-library/react'
import { useRef, useState } from 'react'
import { describe, expect, it } from 'vitest'
import { Popover } from '.'

function Harness() {
  const [open, setOpen] = useState(false)
  const anchor = useRef<HTMLButtonElement>(null)
  return (
    <div>
      <button ref={anchor} type="button" onClick={() => setOpen(true)}>
        BTN
      </button>
      <button type="button">afuera</button>
      <Popover open={open} onClose={() => setOpen(false)} anchorRef={anchor} label="Asiento BTN">
        <button type="button">Rival</button>
        <button type="button">Fold</button>
      </Popover>
    </div>
  )
}

describe('Popover', () => {
  it('opens as a labelled dialog and focuses its first control', () => {
    render(<Harness />)
    expect(screen.queryByRole('dialog')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'BTN' }))
    expect(screen.getByRole('dialog', { name: 'Asiento BTN' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Rival' })).toHaveFocus()
  })

  it('closes on Escape and returns focus to the anchor', () => {
    render(<Harness />)
    fireEvent.click(screen.getByRole('button', { name: 'BTN' }))
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(screen.getByRole('button', { name: 'BTN' })).toHaveFocus()
  })

  it('closes on a click outside, but not inside or on the anchor', () => {
    render(<Harness />)
    fireEvent.click(screen.getByRole('button', { name: 'BTN' }))
    fireEvent.mouseDown(screen.getByRole('button', { name: 'Fold' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    fireEvent.mouseDown(screen.getByRole('button', { name: 'BTN' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    fireEvent.mouseDown(screen.getByRole('button', { name: 'afuera' }))
    expect(screen.queryByRole('dialog')).toBeNull()
  })
})
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd src/frontend && npx vitest run src/ui/choice.test.tsx src/ui/Popover.test.tsx`
Expected: FAIL porque `RadioList`, `PillGroup`, `SegmentList`, `Chip` y `Popover` no se exportan desde `.`.

- [ ] **Step 3: Escribir `RadioList`**

`src/frontend/src/ui/RadioList.tsx`:

```tsx
import { useId } from 'react'
import { cx } from './cx'
import './RadioList.css'

export interface Option<T extends string> {
  value: T
  label: string
  count?: number
  disabled?: boolean
}

interface Props<T extends string> {
  legend: string
  options: Option<T>[]
  value: T
  onChange: (value: T) => void
  name?: string
}

/** Filter card: native radios (arrow keys for free), count in grey, count 0 dimmed but selectable. */
export function RadioList<T extends string>({ legend, options, value, onChange, name }: Props<T>) {
  const autoName = useId()
  const group = name ?? autoName
  return (
    <fieldset className="ui-radio-list">
      <legend className="ui-radio-legend">{legend}</legend>
      <div className="ui-radio-card">
        {options.map((o) => (
          <label key={o.value} className={cx('ui-radio-row', o.count === 0 && 'ui-radio-dim')}>
            <span className="ui-radio-text">
              {o.label}
              {o.count !== undefined && <span className="ui-radio-count">{o.count}</span>}
            </span>
            <input
              type="radio"
              name={group}
              value={o.value}
              checked={o.value === value}
              disabled={o.disabled}
              onChange={() => onChange(o.value)}
            />
          </label>
        ))}
      </div>
    </fieldset>
  )
}
```

`src/frontend/src/ui/RadioList.css`:

```css
.ui-radio-list {
  border: none;
  margin: 0;
  padding: 0;
  min-width: 0;
}

.ui-radio-legend {
  padding: 0;
  margin-bottom: var(--space-2);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.ui-radio-card {
  background: var(--surface);
  border-radius: var(--radius-card);
  padding: var(--space-1) var(--space-3);
  min-height: 150px;
}

.ui-radio-row {
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-2);
  padding: 9px 0;
  border-bottom: 1px solid var(--line);
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--text);
  cursor: pointer;
}

.ui-radio-row:last-child {
  border-bottom: none;
}

.ui-radio-count {
  margin-left: 6px;
  font-weight: 500;
  color: var(--text-muted);
  text-transform: none;
}

.ui-radio-dim {
  color: var(--text-muted);
}

.ui-radio-row input {
  appearance: none;
  width: 16px;
  height: 16px;
  margin: 0;
  padding: 0;
  border-radius: 50%;
  border: 2px solid var(--line-strong);
  background: transparent;
  flex-shrink: 0;
  cursor: pointer;
}

.ui-radio-row input:checked {
  border-color: var(--gold);
  background: radial-gradient(var(--gold) 42%, transparent 48%);
}
```

- [ ] **Step 4: Escribir `ChoiceGroup`, `PillGroup` y `SegmentList`**

`src/frontend/src/ui/ChoiceGroup.tsx`:

```tsx
import { useId } from 'react'
import { cx } from './cx'
import type { Option } from './RadioList'
import './ChoiceGroup.css'

export interface ChoiceProps<T extends string> {
  legend: string
  options: Option<T>[]
  value: T | null
  onChange: (value: T) => void
  name?: string
}

/** Single choice styled as buttons: native radios, disabled options cannot be picked. */
export function ChoiceGroup<T extends string>({
  legend,
  options,
  value,
  onChange,
  name,
  vertical,
}: ChoiceProps<T> & { vertical: boolean }) {
  const autoName = useId()
  const group = name ?? autoName
  return (
    <fieldset className={cx('ui-choice', vertical ? 'ui-choice-vertical' : 'ui-choice-horizontal')}>
      <legend className="ui-choice-legend">{legend}</legend>
      <div className="ui-choice-items">
        {options.map((o) => (
          <label key={o.value} className={cx('ui-choice-item', o.disabled && 'ui-choice-disabled')}>
            <input
              type="radio"
              name={group}
              value={o.value}
              checked={o.value === value}
              disabled={o.disabled}
              onChange={() => onChange(o.value)}
            />
            <span>{o.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}
```

`src/frontend/src/ui/PillGroup.tsx`:

```tsx
import { ChoiceGroup, type ChoiceProps } from './ChoiceGroup'

export function PillGroup<T extends string>(props: ChoiceProps<T>) {
  return <ChoiceGroup {...props} vertical={false} />
}
```

`src/frontend/src/ui/SegmentList.tsx`:

```tsx
import { ChoiceGroup, type ChoiceProps } from './ChoiceGroup'

export function SegmentList<T extends string>(props: ChoiceProps<T>) {
  return <ChoiceGroup {...props} vertical />
}
```

`src/frontend/src/ui/ChoiceGroup.css`:

```css
.ui-choice {
  border: none;
  margin: 0;
  padding: 0;
  min-width: 0;
}

.ui-choice-legend {
  padding: 0;
  margin-bottom: 7px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.ui-choice-items {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.ui-choice-vertical .ui-choice-items {
  flex-direction: column;
  flex-wrap: nowrap;
  gap: 1px;
}

.ui-choice-item {
  position: relative;
  display: block;
  cursor: pointer;
  color: var(--text);
}

/* The radio stays focusable and announced; the label text is what you see. */
.ui-choice-item input {
  position: absolute;
  opacity: 0;
  inset: 0;
  margin: 0;
  cursor: pointer;
}

.ui-choice-item span {
  display: block;
  padding: 6px 12px;
  border-radius: var(--radius-control);
  background: var(--surface);
  font-size: 12px;
  font-weight: 700;
}

.ui-choice-vertical .ui-choice-item span {
  border-radius: 0;
  padding: 9px 12px;
  text-transform: uppercase;
  font-size: 11px;
}

.ui-choice-item:hover span {
  background: var(--surface-2);
}

.ui-choice-item input:checked + span {
  background: var(--gold);
  color: var(--gold-ink);
}

.ui-choice-item input:focus-visible + span {
  outline: 2px solid var(--gold);
  outline-offset: 2px;
}

.ui-choice-disabled,
.ui-choice-disabled input {
  cursor: not-allowed;
}

.ui-choice-disabled span,
.ui-choice-disabled:hover span {
  background: var(--surface);
  color: var(--text-dim);
}
```

`--text-dim` sobre `--surface` solo se usa en opciones deshabilitadas. WCAG exime al texto de controles deshabilitados del requisito de contraste.

- [ ] **Step 5: Escribir `Chip`**

`src/frontend/src/ui/Chip.tsx`:

```tsx
import type { ReactNode } from 'react'
import './Chip.css'

interface Props {
  children: ReactNode
  actionLabel?: string
  onAction?: () => void
}

export function Chip({ children, actionLabel, onAction }: Props) {
  return (
    <span className="ui-chip">
      <span>{children}</span>
      {actionLabel && onAction && (
        <button type="button" className="ui-chip-action" onClick={onAction}>
          {actionLabel}
        </button>
      )}
    </span>
  )
}
```

`src/frontend/src/ui/Chip.css`:

```css
.ui-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 5px 12px;
  color: var(--text-muted);
  font-size: 12px;
}

.ui-chip-action,
.ui-chip-action:hover:not(:disabled) {
  border: none;
  background: none;
  padding: 0;
  color: var(--gold);
  font-weight: 700;
}
```

- [ ] **Step 6: Escribir `Popover`**

`src/frontend/src/ui/Popover.tsx`:

```tsx
import { type ReactNode, type RefObject, useEffect, useRef } from 'react'
import { cx } from './cx'
import './Popover.css'

interface Props {
  open: boolean
  onClose: () => void
  anchorRef: RefObject<HTMLElement | null>
  label: string
  className?: string
  children: ReactNode
}

const FOCUSABLE = 'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea, [tabindex]:not([tabindex="-1"])'

/** Floating panel next to its anchor. The caller positions it through className. */
export function Popover({ open, onClose, anchorRef, label, className, children }: Props) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const anchor = anchorRef.current
    ref.current?.querySelector<HTMLElement>(FOCUSABLE)?.focus()

    function onMouseDown(e: MouseEvent) {
      const target = e.target as Node
      if (ref.current?.contains(target) || anchorRef.current?.contains(target)) return
      onClose()
    }
    document.addEventListener('mousedown', onMouseDown)
    return () => {
      document.removeEventListener('mousedown', onMouseDown)
      anchor?.focus()
    }
  }, [open, onClose, anchorRef])

  if (!open) return null
  return (
    <div
      ref={ref}
      role="dialog"
      aria-label={label}
      className={cx('ui-popover', className)}
      onKeyDown={(e) => {
        if (e.key === 'Escape') {
          e.stopPropagation()
          onClose()
        }
      }}
    >
      {children}
    </div>
  )
}
```

El efecto devuelve el foco al ancla en su limpieza, que corre cuando `open` pasa a `false`. Para que la limpieza no corra en cada render, quien lo usa tiene que pasar un `onClose` estable (por ejemplo, con `useCallback` o un setter de estado). En el test, `() => setOpen(false)` se recrea en cada render del harness, pero el harness solo se re-renderiza al cambiar `open`, así que alcanza.

`src/frontend/src/ui/Popover.css`:

```css
.ui-popover {
  position: absolute;
  z-index: 50;
  min-width: 190px;
  background: var(--surface);
  border: 1px solid var(--gold);
  border-radius: var(--radius-card);
  padding: 10px 12px;
  box-shadow: 0 8px 24px #000a;
}
```

- [ ] **Step 7: Exportar desde `ui/index.ts`**

Reemplazar `src/frontend/src/ui/index.ts` completo por:

```ts
export { Button } from './Button'
export { Card } from './Card'
export { Chip } from './Chip'
export { PillGroup } from './PillGroup'
export { Popover } from './Popover'
export { RadioList, type Option } from './RadioList'
export { SegmentList } from './SegmentList'
export { Select } from './Select'
export { Stat } from './Stat'
```

- [ ] **Step 8: Correr los tests y verificar que pasan**

Run: `cd src/frontend && npx vitest run src/ui`
Expected: PASS en `basic.test.tsx` (8), `choice.test.tsx` (8) y `Popover.test.tsx` (3).

- [ ] **Step 9: Typecheck y lint**

Run: `cd src/frontend && npm run typecheck && npm run lint`
Expected: sin errores.

- [ ] **Step 10: Commit**

```bash
git add src/frontend/src/ui
git commit -m "feat(ui): RadioList, PillGroup, SegmentList, Chip and Popover"
```

---

### Task 8: Limpieza, recorrida visual y verificación completa

**Files:**
- Modify: los CSS de la Task 5 (se borran reglas sin uso)
- Modify: los CSS de cada área, si la recorrida encuentra defectos

**Interfaces:**
- Consumes: todo lo anterior.

- [ ] **Step 1: Listar las clases CSS sin uso**

Run (desde la raíz del repo):

```bash
node -e "const fs=require('fs'),p=require('path');const walk=d=>fs.readdirSync(d,{withFileTypes:true}).flatMap(e=>e.isDirectory()?walk(p.join(d,e.name)):[p.join(d,e.name)]);const files=walk('src/frontend/src');const css=files.filter(f=>f.endsWith('.css'));const code=files.filter(f=>/\.tsx?$/.test(f)&&!/\.test\./.test(f)).map(f=>fs.readFileSync(f,'utf8')).join('\n');for(const f of css){const cls=new Set([...fs.readFileSync(f,'utf8').matchAll(/\.([a-zA-Z][\w-]*)/g)].map(m=>m[1]));const unused=[...cls].filter(c=>!code.includes(c));if(unused.length)console.log(f+': '+unused.join(', '))}"
```

Expected: una lista por archivo. Para cada clase listada, buscala con `git grep -n "<clase>" src/frontend/src` para confirmar que de verdad no se usa. Ojo con las clases que se arman con template strings, por ejemplo `` `verdict-${…}` `` o `` `suit-${…}` ``: esas **se usan**. Borrá solo las reglas cuyas clases no aparecen en ningún lado.

- [ ] **Step 2: Borrar las reglas confirmadas sin uso y verificar**

Run: `cd src/frontend && npm test && npm run build`
Expected: todo en PASS.

- [ ] **Step 3: Recorrida visual con datos reales**

Desde la raíz del repo, en el dev shell de MSVC, arrancá la app:

```powershell
scripts\dev.ps1
```

Abrí `http://localhost:5173` en el navegador. A **1280 px** de ancho, recorré las 8 secciones del menú y compará con los mockups `1-paleta.html` y `2-navegacion.html`. En cada sección revisá:

- que no quede texto ilegible (gris sobre verde, blanco sobre dorado);
- que no queden fondos blancos o claros de la paleta vieja (buscá `#fff`, `white` o `color-mix` con `--surface` claro);
- que los bordes y paneles sean coherentes;
- que la matriz tenga texto oscuro en las celdas llenas;
- que el gráfico de ganancias sea legible;
- que las cartas tengan la cara clara y los cuatro colores.

Después, a **1024 px**, plegá el menú y verificá que:

- quedan solo los íconos, con tooltip;
- al recargar sigue plegado;
- ninguna sección se desborda en horizontal.

Cada defecto se corrige en el CSS del área que corresponde, sin cambiar markup ni comportamiento. Anotá en el mensaje del commit qué secciones se ajustaron.

- [ ] **Step 4: Suite completa del repo**

Desde la raíz del repo, en el dev shell de MSVC:

```powershell
scripts\test.ps1
```

Expected: core 31, backend 362 (más 1 skipped), frontend con todos los tests en PASS (92 previos más los nuevos de las Tasks 1, 2, 3, 4 y 7) e integración 2.

- [ ] **Step 5: Paquete y e2e del launcher**

```powershell
scripts\package.ps1 -SkipTests
scripts\test.ps1 launcher
```

Expected: el paquete se arma, la prueba de humo da OK y los 9 tests del e2e del launcher pasan. Abrí `dist\POKKER\POKKER.exe` y comprobá que la app empaquetada se ve con el nuevo estilo.

- [ ] **Step 6: Commit**

```bash
git add -A src/frontend/src
git commit -m "style(ui): drop unused rules and polish sections after the visual review"
```

---

## Self-review (hecho al escribir el plan)

- **Cobertura del spec** (§2 y §3):
  - Tokens (§2.1): Task 1.
  - Contraste de 4,5:1: test de la Task 1. Ajusté all-in y 5-bet y lo dejé anotado en Global Constraints.
  - Tipografía y espaciado: tokens de la Task 1, que usan los CSS de las Tasks 3, 4 y 7.
  - Los 9 componentes de §2.2: Tasks 4 y 7. `SegmentList` y `PillGroup` comparten `ChoiceGroup`.
  - Selectores base para el markup viejo: Task 6.
  - Sidebar agrupado y plegable con `localStorage` a prueba de errores (§2.3): Tasks 2 y 3.
  - Estado del servidor abajo en el menú: Task 3.
  - Partir `index.css` (§2.3): Task 5. Borrar reglas sin uso: Task 8.
  - Todas las secciones con el nuevo look sin cambiar comportamiento (§3): Tasks 6 y 8.
  - Criterios de "hecho" (§3): pasos 3 a 5 de la Task 8.
- **Lo que pide el spec pero ya no aplica:** las secciones "fase N" deshabilitadas no existen hoy (las 8 están en `AVAILABLE`), así que la Task 3 borra ese mecanismo.
- **Desvíos del spec, todos justificados:**
  - Los títulos de grupo usan `--text-muted` y no `--text-dim`, por el contraste.
  - Se agrega el ítem "Replayer" al grupo Analizar: la sección existe y el spec no la listaba.
- **Consistencia de nombres:**
  - `readStored`, `writeStored`, `isBoolean` y `SIDEBAR_KEY` se usan igual en las Tasks 2 y 3.
  - `Option<T>` está definido en `RadioList.tsx` y se reutiliza en `ChoiceGroup`.
  - `cx` está definido en la Task 4 y se usa en la Task 7.
  - La clase `.ui-card` evita chocar con `.card`.
- **Review Focus:** los puntos 1 a 3 tienen tests en las Tasks 2 y 3. El punto 4 lo cubre el script de la Task 5. El punto 5 lo cubren el test de la Task 1 y la regla `.matrix-cell-on` de la Task 6.
