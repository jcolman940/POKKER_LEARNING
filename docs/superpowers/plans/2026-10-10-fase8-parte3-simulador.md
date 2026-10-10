# Fase 8, parte 3: Simulador con mesa ovalada. Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** reemplazar el formulario del Simulador (Mesa, Hero, Board, Rivales) por una mesa ovalada interactiva:
- asientos según la cantidad de jugadores, con vos siempre abajo;
- popover por asiento con rol, apuesta, stack, rango y cartas;
- pozo y board en el centro;
- opciones avanzadas desplegables;
- el mismo panel de resultados de siempre.

**Architecture:**
- Toda la lógica de la mesa son funciones puras en `simulator/table.ts`, con tests. Ahí está la traducción `tableToScenario`, que arma el mismo `ScenarioInput` de siempre. **El backend no cambia.**
- Tres componentes chicos (`TableView`, `SeatPopover` y `AdvancedOptions`) y un `SimulatorPage` que orquesta el estado, la persistencia, las llamadas a la API y los resultados.

**Tech Stack:** React 19, TypeScript 6, Vite 8, vitest 5 + Testing Library (jsdom), oxlint. Usa `src/ui` y `app/storage.ts` (parte 1), y `ranges/preflopFilters.ts` (parte 2).

**Spec:** [`docs/superpowers/specs/2026-10-10-rediseno-ui-design.md`](../specs/2026-10-10-rediseno-ui-design.md) §5, y §4.3 (el Simulador lee los filtros de Preflop). Mockup aprobado: [`docs/superpowers/specs/2026-10-10-rediseno-ui/4-simulador-mesa.html`](../specs/2026-10-10-rediseno-ui/4-simulador-mesa.html).

## Global Constraints

- **Sin dependencias nuevas.** Solo frontend: el backend, `ScenarioInput` y la API **no cambian**.
- **Asientos:** salen de `GET /api/simulator/positions/{n}`. Vos siempre abajo al centro y los demás en sentido horario en orden de mesa, empezando por el que está a tu izquierda.
- **Roles:** `hero` (VOS), `villain` (RIVAL), `folded` (FOLD) y `empty` (vacío). Si marcás "Vos" en otro asiento, el que eras pasa a fold y la mesa gira.
- **Apuesta en el popover:** atajos ⅓, ½, ⅔ y Pot sobre el **pozo total actual**, All-in sobre el stack, y un campo libre en bb.
- **Pozo y apuestas:** `pot_bb` del escenario es el pozo de calles anteriores más la suma de **todas** las apuestas actuales, incluida la tuya.
- **A pagar:** `to_call_bb` es `max(0, apuesta más alta − tu apuesta)`, recortado a tu stack.
- **Stack efectivo:** el menor entre tu stack y el mayor stack de los rivales.
- **Acción previa:** se arma de las apuestas en orden de mesa. La primera es `bet` (o `raise` en preflop), una mayor es `raise` y una igual o menor es `call`. Ejemplo: "CO bet 4, BTN call 4". Si se escribe a mano en las opciones avanzadas, gana el texto escrito.
- **Calle:** cuántas cartas del board se usan (0, 3, 4 o 5). Al repartir, la calle se ajusta a las cartas que trajo el board.
- **Persistencia:** `localStorage` con la clave `pokker.simulator.table`, siempre con `readStored`/`writeStored`. Si lo guardado no es válido, se descarta.
- **Sin mesa guardada:** se arranca con el formato y los jugadores de `pokker.preflop.filters` (spec §4.3), con la mesa por defecto descripta abajo.
- **Escenario inicial** (replayer o "Abrir en Simulador" de Preflop): **gana** sobre la mesa guardada.
- **Validaciones antes de llamar a la API:**
  - tiene que haber exactamente un "Vos" y al menos un rival;
  - tienen que estar tus 2 cartas;
  - el board tiene que tener las cartas que pide la calle;
  - ninguna apuesta puede superar el stack del asiento;
  - no puede haber cartas repetidas.
  
  "Analizar" queda deshabilitado mientras falle alguna, con el motivo a la vista.
- **Texto de la UI en español rioplatense.** Nada de colores sueltos: solo variables de `styles/tokens.css`.
- **Comandos** (desde `src/frontend/`): `npm test`, `npm run typecheck`, `npm run lint` y `npm run build`.
- **Rama** `fase8-simulador`, creada desde `main`. Cada commit termina con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

**Desvíos del spec, ya resueltos:**
1. **Mesa por defecto:** vos en **BTN** y un **rival en el BB**, el resto en fold, calle flop y pozo de 6,5 bb. El spec (§5.2) dice "vos en BB, los demás en fold y pozo de 1,5 bb", pero eso deja la mesa sin rival y "Analizar" deshabilitado apenas se abre. El default nuevo es el mismo que tiene hoy el Simulador. Si el escenario viene de Preflop sin board, la calle es preflop y el pozo de 1,5 bb.
2. **Botones de reparto:** quedan los dos actuales, "Completar al azar" y "Todo al azar", en lugar de un único "Repartir". Mantienen lo que existe hoy y los tests.
3. **"Repartirle mano al azar" por rival:** se quita. La interfaz `Seat` del spec no lo incluye. Las cartas de un rival siguen siendo opcionales y se eligen a mano.
4. **`stacks_bb`:** se manda solo en torneos (`{}` en cash), como hoy. El spec dice "el stack de cada asiento que no está vacío", sin distinguir formato. En cash el backend no lo usa, y mandarlo cambiaría lo que hoy recibe.

## Review Focus

1. **Cambiar la cantidad de jugadores con un rival o con vos en una posición que deja de existir.** Por ejemplo, de 9-max a 6-max con vos en UTG+2. Los asientos se rearman, vos pasás a BTN, el rival que ya no existe desaparece y no se rompe nada. Test en la Task 1.
2. **Apuestas con stacks cortos.** Un rival all-in por menos de lo que pagaste, o una apuesta mayor que tu stack. El "a pagar" se recorta a tu stack y el all-in del rival no rompe la acción previa. Tests en la Task 2.
3. **Mesa guardada corrupta, o con otra forma por una versión anterior.** Se descarta y se arranca por defecto. Tests en las Tasks 3 y 7.
4. **Escenario del replayer** con pozo, a pagar, rivales y acción previa. La mesa lo reproduce y `tableToScenario` devuelve el mismo pozo y el mismo a pagar. Test en la Task 3.
5. **Cartas repetidas entre tu mano, el board y la mano de un rival** (por ejemplo, si se cargan desde un escenario). Analizar se bloquea con "Hay cartas repetidas." Test en la Task 2.

---

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `src/frontend/src/simulator/table.ts` (nuevo) + `table.test.ts` | Tipos `Seat`, `TableState` y `AdvancedOptions`; asientos, roles, rotación y geometría; traducción a `ScenarioInput`; validaciones; mesa por defecto, desde un escenario inicial y guarda de tipo. |
| `src/frontend/src/test/tables.ts` (nuevo) | `makeTable()` y `seat()`, utilidades solo para tests. |
| `src/frontend/src/simulator/TableView.tsx` (nuevo) + test | Paño, asientos, fichas, dealer, centro (pozo y board) y tus cartas. |
| `src/frontend/src/simulator/SeatPopover.tsx` (nuevo) + test | Popover del asiento: rol, apuesta, stack, rango y cartas. |
| `src/frontend/src/simulator/AdvancedOptions.tsx` (nuevo) + test | Situación, ante, BB ante, acción previa a mano, premios y espacio para los campos del solver. |
| `src/frontend/src/simulator/table.css` (nuevo) | Estilos de la mesa (mockup `4-simulador-mesa.html`). |
| `src/frontend/src/simulator/SimulatorPage.tsx` (se reescribe) + `SimulatorPage.test.tsx` | Orquesta todo. |
| `src/frontend/src/simulator/simulator.css` (se modifica) | El layout `.simulator` pasa a 2 columnas: mesa y resultados. Se borran `.sim-config` y `.sim-results`. |
| `src/frontend/src/App.test.tsx` (se modifica) | El test de "Abrir en Simulador" verifica el asiento y ya no `#hero-pos`. |

---

### Task 1: Asientos, roles y geometría (`table.ts`, parte A)

**Files:**
- Create: `src/frontend/src/simulator/table.ts`
- Create: `src/frontend/src/test/tables.ts`
- Test: `src/frontend/src/simulator/table.test.ts`

**Interfaces:**
- Consumes: `GameFormat` y `Street` de `./types`.
- Produces (los usan todas las tareas siguientes):
  - `type SeatRole = 'hero' | 'villain' | 'folded' | 'empty'`
  - `interface Seat { position: string; role: SeatRole; bet_bb: number; stack_bb: number; range: string; hand: string | null }`
  - `interface AdvancedOptions { ante_bb: number; bb_ante_bb: number; payouts: number[]; hero_range: string; ranges_approximate: boolean; solver_preset: string; situation: string | null; previous_action: string }`
  - `interface TableState { format: GameFormat; num_players: number; street: Street; seats: Seat[]; pot_bb: number; board: string; hero_hand: string; advanced: AdvancedOptions }`
  - `DEFAULT_ADVANCED: AdvancedOptions`
  - `newSeat(position: string, stack?: number): Seat`. Por defecto: rol `folded`, stack 100, rango `'random'`.
  - `seatsFor(positions: string[], previous: Seat[], defaultStack: number): Seat[]`
  - `setRole(seats: Seat[], position: string, role: SeatRole): Seat[]`
  - `updateSeat(seats: Seat[], position: string, patch: Partial<Seat>): Seat[]`
  - `heroSeat(seats: Seat[]): Seat | undefined`
  - `villainSeats(seats: Seat[]): Seat[]`, en orden de mesa
  - `rotateFromHero(seats: Seat[]): Seat[]`
  - `seatPoint(k: number, n: number, scale?: number): { left: number; top: number }`, en porcentajes con 2 decimales
  - En `src/test/tables.ts`: `seat(position: string, role?: SeatRole, extra?: Partial<Seat>): Seat` y `makeTable(o?: Partial<TableState>): TableState`

- [ ] **Step 1: Escribir la utilidad de tests**

`src/frontend/src/test/tables.ts`:

```ts
import { DEFAULT_ADVANCED, newSeat, type Seat, type SeatRole, type TableState } from '../simulator/table'

export function seat(position: string, role: SeatRole = 'folded', extra: Partial<Seat> = {}): Seat {
  return { ...newSeat(position), role, ...extra }
}

/** 6-max cash table on the flop: Hero BTN vs BB, everyone else folded, pot 6.5bb, no bets. */
export function makeTable(o: Partial<TableState> = {}): TableState {
  return {
    format: 'cash',
    num_players: 6,
    street: 'flop',
    seats: [
      seat('LJ'),
      seat('HJ'),
      seat('CO'),
      seat('BTN', 'hero'),
      seat('SB'),
      seat('BB', 'villain'),
    ],
    pot_bb: 6.5,
    board: 'Kh7c2d',
    hero_hand: 'AhKs',
    advanced: { ...DEFAULT_ADVANCED },
    ...o,
  }
}
```

- [ ] **Step 2: Escribir el test que falla**

`src/frontend/src/simulator/table.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { seat } from '../test/tables'
import { heroSeat, newSeat, rotateFromHero, seatPoint, seatsFor, setRole, updateSeat, villainSeats } from './table'

const SIX = ['LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']

describe('seats', () => {
  it('new seats are folded, 100bb deep and play any hand', () => {
    expect(newSeat('CO')).toEqual({ position: 'CO', role: 'folded', bet_bb: 0, stack_bb: 100, range: 'random', hand: null })
  })

  it('builds the table in position order and keeps what each position had', () => {
    const seats = seatsFor(SIX, [seat('BB', 'villain', { range: 'QQ+' }), seat('BTN', 'hero')], 100)
    expect(seats.map((s) => s.position)).toEqual(SIX)
    expect(seats.find((s) => s.position === 'BB')).toMatchObject({ role: 'villain', range: 'QQ+' })
    expect(heroSeat(seats)?.position).toBe('BTN')
  })

  it('moves the hero to BTN when its position no longer exists (9-max → 6-max)', () => {
    const seats = seatsFor(SIX, [seat('UTG+2', 'hero'), seat('UTG', 'villain')], 40)
    expect(heroSeat(seats)?.position).toBe('BTN')
    expect(villainSeats(seats)).toEqual([])
    // positions that disappear are dropped; every seat is new, with the default stack
    expect(seats.every((s) => s.stack_bb === 40)).toBe(true)
  })

  it('uses the default stack for new seats', () => {
    expect(seatsFor(SIX, [], 40).find((s) => s.position === 'CO')?.stack_bb).toBe(40)
  })

  it('keeps the seats as they are while positions are unknown', () => {
    const prev = [seat('BTN', 'hero')]
    expect(seatsFor([], prev, 100)).toBe(prev)
  })
})

describe('roles', () => {
  const table = SIX.map((p) => seat(p, p === 'BTN' ? 'hero' : p === 'BB' ? 'villain' : 'folded'))

  it('picking "Vos" on another seat folds the old hero seat and clears the new one\'s cards', () => {
    const withHand = updateSeat(table, 'BB', { hand: 'AsAd', bet_bb: 3 })
    const seats = setRole(withHand, 'BB', 'hero')
    expect(heroSeat(seats)).toMatchObject({ position: 'BB', hand: null, bet_bb: 3 })
    expect(seats.find((s) => s.position === 'BTN')).toMatchObject({ role: 'folded', bet_bb: 0 })
  })

  it('folding or emptying a seat takes back its bet', () => {
    const seats = setRole(updateSeat(table, 'BB', { bet_bb: 4 }), 'BB', 'folded')
    expect(seats.find((s) => s.position === 'BB')).toMatchObject({ role: 'folded', bet_bb: 0 })
  })

  it('lists rivals in table order', () => {
    const seats = setRole(table, 'CO', 'villain')
    expect(villainSeats(seats).map((s) => s.position)).toEqual(['CO', 'BB'])
  })
})

describe('geometry', () => {
  it('starts the drawing order at the hero, then clockwise', () => {
    const seats = SIX.map((p) => seat(p, p === 'BB' ? 'hero' : 'folded'))
    expect(rotateFromHero(seats).map((s) => s.position)).toEqual(['BB', 'LJ', 'HJ', 'CO', 'BTN', 'SB'])
  })

  it('puts the hero at the bottom centre and the next seat to the lower left', () => {
    expect(seatPoint(0, 6)).toEqual({ left: 50, top: 88 })
    const next = seatPoint(1, 6)
    expect(next.left).toBeLessThan(50)
    expect(next.top).toBeGreaterThan(48)
    const across = seatPoint(3, 6)
    expect(across).toEqual({ left: 50, top: 8 })
  })

  it('scales towards the centre for bets', () => {
    expect(seatPoint(0, 6, 0.5)).toEqual({ left: 50, top: 68 })
  })
})
```

- [ ] **Step 3: Correr el test y verificar que falla**

Run: `cd src/frontend && npx vitest run src/simulator/table.test.ts`
Expected: FAIL porque no se puede resolver `./table`.

- [ ] **Step 4: Escribir la implementación**

`src/frontend/src/simulator/table.ts`:

```ts
import type { GameFormat, Street } from './types'

export type SeatRole = 'hero' | 'villain' | 'folded' | 'empty'

export interface Seat {
  position: string
  role: SeatRole
  bet_bb: number
  stack_bb: number
  range: string
  hand: string | null
}

export interface AdvancedOptions {
  ante_bb: number
  bb_ante_bb: number
  payouts: number[]
  hero_range: string
  ranges_approximate: boolean
  solver_preset: string
  situation: string | null
  /** Typed by hand; empty = built from the bets on the table. */
  previous_action: string
}

export interface TableState {
  format: GameFormat
  num_players: number
  street: Street
  seats: Seat[]
  /** Pot from previous streets; the current bets are on the seats. */
  pot_bb: number
  board: string
  hero_hand: string
  advanced: AdvancedOptions
}

export const DEFAULT_ADVANCED: AdvancedOptions = {
  ante_bb: 0,
  bb_ante_bb: 0,
  payouts: [],
  hero_range: '',
  ranges_approximate: false,
  solver_preset: 'chico',
  situation: null,
  previous_action: '',
}

export function newSeat(position: string, stack = 100): Seat {
  return { position, role: 'folded', bet_bb: 0, stack_bb: stack, range: 'random', hand: null }
}

/** Seats in `positions` order, keeping what each position already had; there is always a hero. */
export function seatsFor(positions: string[], previous: Seat[], defaultStack: number): Seat[] {
  if (positions.length === 0) return previous
  const byPosition = new Map(previous.map((s) => [s.position, s]))
  const seats = positions.map((p) => byPosition.get(p) ?? newSeat(p, defaultStack))
  if (!seats.some((s) => s.role === 'hero')) {
    const i = Math.max(0, positions.indexOf('BTN'))
    seats[i] = { ...seats[i], role: 'hero', hand: null }
  }
  return seats
}

export function setRole(seats: Seat[], position: string, role: SeatRole): Seat[] {
  return seats.map((s) => {
    if (s.position === position) {
      const out = { ...s, role }
      if (role === 'folded' || role === 'empty') out.bet_bb = 0
      if (role === 'hero') out.hand = null // your cards live in TableState.hero_hand
      return out
    }
    if (role === 'hero' && s.role === 'hero') return { ...s, role: 'folded', bet_bb: 0 }
    return s
  })
}

export function updateSeat(seats: Seat[], position: string, patch: Partial<Seat>): Seat[] {
  return seats.map((s) => (s.position === position ? { ...s, ...patch } : s))
}

export function heroSeat(seats: Seat[]): Seat | undefined {
  return seats.find((s) => s.role === 'hero')
}

export function villainSeats(seats: Seat[]): Seat[] {
  return seats.filter((s) => s.role === 'villain')
}

/** Drawing order: the hero first (bottom centre), then clockwise in table order. */
export function rotateFromHero(seats: Seat[]): Seat[] {
  const h = seats.findIndex((s) => s.role === 'hero')
  return h <= 0 ? seats : [...seats.slice(h), ...seats.slice(0, h)]
}

const round2 = (n: number) => Math.round(n * 100) / 100

/** Seat k of n on the oval, as % of the stage; k = 0 is the bottom centre, then clockwise. */
export function seatPoint(k: number, n: number, scale = 1): { left: number; top: number } {
  const a = Math.PI / 2 + (2 * Math.PI * k) / n
  return { left: round2(50 + 42 * scale * Math.cos(a)), top: round2(48 + 40 * scale * Math.sin(a)) }
}
```

- [ ] **Step 5: Correr el test y verificar que pasa**

Run: `cd src/frontend && npx vitest run src/simulator/table.test.ts`
Expected: PASS (11 tests).

- [ ] **Step 6: Commit**

```bash
git add src/frontend/src/simulator/table.ts src/frontend/src/simulator/table.test.ts src/frontend/src/test/tables.ts
git commit -m "feat(simulator): table seats, roles and oval geometry"
```

---

### Task 2: Traducción a la API y validaciones (`table.ts`, parte B)

**Files:**
- Modify: `src/frontend/src/simulator/table.ts` (se agrega al final)
- Test: `src/frontend/src/simulator/table.test.ts` (se agregan `describe`)

**Interfaces:**
- Consumes: lo de la Task 1, y `ScenarioInput` de `./types`.
- Produces:
  - `BOARD_CARDS: Record<Street, number>`, que es `{ preflop: 0, flop: 3, turn: 4, river: 5 }`
  - `STREET_LABEL: Record<Street, string>`
  - `streetFromBoard(board: string): Street`
  - `boardForStreet(board: string, street: Street): string`
  - `totalPot(t: TableState): number`
  - `type BetPreset = 'third' | 'half' | 'twothirds' | 'pot' | 'allin'`
  - `presetBet(t: TableState, position: string, preset: BetPreset): number`
  - `previousActionFrom(t: TableState): string`
  - `tableToScenario(t: TableState): ScenarioInput`
  - `validateTable(t: TableState): string | null`, que devuelve el primer problema o `null`

- [ ] **Step 1: Escribir el test que falla**

Agregar en `src/frontend/src/simulator/table.test.ts`:
- Sumar a los imports de `./table`: `BOARD_CARDS`, `boardForStreet`, `presetBet`, `previousActionFrom`, `streetFromBoard`, `tableToScenario`, `totalPot` y `validateTable`.
- Agregar `import { makeTable } from '../test/tables'`.
- Al final del archivo:

```ts
// BB (hero) faces CO bet 4 and BTN call 4 on the flop, pot 6.5 before the bets.
function bbVsTwo() {
  return makeTable({
    seats: [
      seat('LJ'),
      seat('HJ'),
      seat('CO', 'villain', { bet_bb: 4, stack_bb: 93 }),
      seat('BTN', 'villain', { bet_bb: 4, stack_bb: 93 }),
      seat('SB'),
      seat('BB', 'hero', { stack_bb: 96 }),
    ],
  })
}

describe('streets', () => {
  it('maps board size to a street and cuts the board to the street', () => {
    expect(BOARD_CARDS).toEqual({ preflop: 0, flop: 3, turn: 4, river: 5 })
    expect(streetFromBoard('')).toBe('preflop')
    expect(streetFromBoard('AsKs')).toBe('preflop')
    expect(streetFromBoard('Kh7s2c')).toBe('flop')
    expect(streetFromBoard('Kh7s2c3d')).toBe('turn')
    expect(streetFromBoard('Kh7s2c3d9h')).toBe('river')
    expect(boardForStreet('Kh7s2c3d9h', 'flop')).toBe('Kh7s2c')
    expect(boardForStreet('Kh7s2c3d9h', 'preflop')).toBe('')
  })
})

describe('tableToScenario', () => {
  it('adds every current bet to the pot and computes what you face', () => {
    const s = tableToScenario(bbVsTwo())
    expect(s).toMatchObject({
      format: 'cash',
      num_players: 6,
      hero_position: 'BB',
      hero_hand: 'AhKs',
      board: 'Kh7c2d',
      pot_bb: 14.5,
      to_call_bb: 4,
      effective_stack_bb: 93,
      previous_action: 'CO bet 4, BTN call 4',
      stacks_bb: {},
      payouts: [],
      hero_range: null,
      solver_preset: 'chico',
    })
    expect(s.villains).toEqual([
      { position: 'CO', range: 'random', hand: null },
      { position: 'BTN', range: 'random', hand: null },
    ])
  })

  it('counts your own bet in the pot and subtracts it from what you face', () => {
    const t = bbVsTwo()
    t.seats = updateSeat(t.seats, 'BB', { bet_bb: 4 })
    t.seats = updateSeat(t.seats, 'CO', { bet_bb: 12 })
    t.seats = updateSeat(t.seats, 'BTN', { bet_bb: 0 })
    const s = tableToScenario(t)
    expect(s.pot_bb).toBe(22.5)
    expect(s.to_call_bb).toBe(8)
    expect(s.previous_action).toBe('CO bet 12, BB call 4')
  })

  it('caps what you face at your stack (short all-in)', () => {
    const t = bbVsTwo()
    t.seats = updateSeat(t.seats, 'BB', { stack_bb: 3 })
    expect(tableToScenario(t).to_call_bb).toBe(3)
  })

  it('a rival all-in for less than the top bet reads as a call', () => {
    const t = bbVsTwo()
    t.seats = updateSeat(t.seats, 'BTN', { bet_bb: 2, stack_bb: 2 })
    expect(previousActionFrom(t)).toBe('CO bet 4, BTN call 2')
  })

  it('opens with raise preflop and prefers the text typed by hand', () => {
    const t = makeTable({ street: 'preflop', board: '', seats: [seat('CO', 'villain', { bet_bb: 2.5 }), seat('BTN', 'hero')] })
    expect(previousActionFrom(t)).toBe('CO raise 2.5')
    t.advanced = { ...t.advanced, previous_action: 'CO abre 2.5bb' }
    expect(tableToScenario(t).previous_action).toBe('CO abre 2.5bb')
  })

  it('sends stacks and payouts only in tournaments', () => {
    const t = makeTable({ format: 'mtt' })
    t.advanced = { ...t.advanced, payouts: [50, 30, 20] }
    const s = tableToScenario(t)
    expect(s.stacks_bb).toMatchObject({ BTN: 100, BB: 100, CO: 100 })
    expect(s.payouts).toEqual([50, 30, 20])
  })

  it('ignores empty seats in pot and stacks', () => {
    const t = makeTable({ format: 'mtt' })
    t.seats = updateSeat(t.seats, 'LJ', { role: 'empty', bet_bb: 5 })
    const s = tableToScenario(t)
    expect(s.pot_bb).toBe(6.5)
    expect(s.stacks_bb).not.toHaveProperty('LJ')
  })
})

describe('bet presets', () => {
  it('sizes on the total pot, capped at the stack; all-in is the stack', () => {
    const t = bbVsTwo() // total pot 14.5
    expect(presetBet(t, 'BB', 'half')).toBe(7.25)
    expect(presetBet(t, 'BB', 'pot')).toBe(14.5)
    expect(presetBet(t, 'BB', 'third')).toBe(4.83)
    expect(presetBet(t, 'BB', 'twothirds')).toBe(9.67)
    expect(presetBet(t, 'BB', 'allin')).toBe(96)
    t.seats = updateSeat(t.seats, 'BB', { stack_bb: 10 })
    expect(presetBet(t, 'BB', 'pot')).toBe(10)
  })

  it('the total pot adds the bets to the previous streets', () => {
    expect(totalPot(bbVsTwo())).toBe(14.5)
  })
})

describe('validateTable', () => {
  it('accepts a complete table', () => {
    expect(validateTable(bbVsTwo())).toBeNull()
  })

  it('needs exactly one hero and at least one rival', () => {
    const t = bbVsTwo()
    expect(validateTable({ ...t, seats: updateSeat(t.seats, 'BB', { role: 'folded' }) })).toMatch(/Elegí tu asiento/)
    const noRival = t.seats.map((s) => (s.role === 'villain' ? { ...s, role: 'folded' as const } : s))
    expect(validateTable({ ...t, seats: noRival })).toMatch(/al menos un rival/)
  })

  it('needs your two cards and the board of the street', () => {
    expect(validateTable({ ...bbVsTwo(), hero_hand: 'Ah' })).toMatch(/tus dos cartas/)
    expect(validateTable({ ...bbVsTwo(), street: 'turn' })).toBe('Faltan cartas del board: el turn lleva 4.')
    expect(validateTable({ ...bbVsTwo(), street: 'preflop', board: '' })).toBeNull()
  })

  it('rejects a bet bigger than the stack', () => {
    const t = bbVsTwo()
    expect(validateTable({ ...t, seats: updateSeat(t.seats, 'CO', { bet_bb: 120 }) })).toBe(
      'La apuesta de CO supera su stack.',
    )
  })

  it('rejects repeated cards across hand, board and rivals', () => {
    const t = bbVsTwo()
    expect(validateTable({ ...t, board: 'AhQc2d' })).toBe('Hay cartas repetidas.')
    expect(validateTable({ ...t, seats: updateSeat(t.seats, 'CO', { hand: 'Kh9s' }) })).toBe('Hay cartas repetidas.')
  })
})
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd src/frontend && npx vitest run src/simulator/table.test.ts`
Expected: FAIL porque las funciones nuevas no se exportan (los 11 tests de la Task 1 siguen en PASS).

- [ ] **Step 3: Implementar (agregar al final de `table.ts`)**

En el import del principio de `table.ts`, cambiar `import type { GameFormat, Street } from './types'` por `import type { GameFormat, ScenarioInput, Street } from './types'`. Después agregar al final:

```ts
export const BOARD_CARDS: Record<Street, number> = { preflop: 0, flop: 3, turn: 4, river: 5 }
export const STREET_LABEL: Record<Street, string> = { preflop: 'Preflop', flop: 'Flop', turn: 'Turn', river: 'River' }

export function streetFromBoard(board: string): Street {
  const n = Math.floor(board.length / 2)
  return n >= 5 ? 'river' : n === 4 ? 'turn' : n === 3 ? 'flop' : 'preflop'
}

export function boardForStreet(board: string, street: Street): string {
  return board.slice(0, BOARD_CARDS[street] * 2)
}

const inPlay = (s: Seat) => s.role !== 'empty'

export function totalPot(t: TableState): number {
  return round2(t.pot_bb + t.seats.filter(inPlay).reduce((sum, s) => sum + s.bet_bb, 0))
}

export type BetPreset = 'third' | 'half' | 'twothirds' | 'pot' | 'allin'
const PRESET_SHARE: Record<Exclude<BetPreset, 'allin'>, number> = { third: 1 / 3, half: 1 / 2, twothirds: 2 / 3, pot: 1 }

export function presetBet(t: TableState, position: string, preset: BetPreset): number {
  const s = t.seats.find((x) => x.position === position)
  if (!s) return 0
  if (preset === 'allin') return s.stack_bb
  return round2(Math.min(s.stack_bb, totalPot(t) * PRESET_SHARE[preset]))
}

/** "CO bet 4, BTN call 4": table order; the opener bets (raises preflop), more raises, the same or less calls. */
export function previousActionFrom(t: TableState): string {
  const typed = t.advanced.previous_action.trim()
  if (typed) return typed
  let top = 0
  const parts: string[] = []
  for (const s of t.seats) {
    if (!inPlay(s) || s.bet_bb <= 0) continue
    const verb = top === 0 ? (t.street === 'preflop' ? 'raise' : 'bet') : s.bet_bb > top ? 'raise' : 'call'
    parts.push(`${s.position} ${verb} ${round2(s.bet_bb)}`)
    top = Math.max(top, s.bet_bb)
  }
  return parts.join(', ')
}

export function tableToScenario(t: TableState): ScenarioInput {
  const hero = heroSeat(t.seats)
  const villains = villainSeats(t.seats)
  const heroStack = hero?.stack_bb ?? 0
  const topBet = Math.max(0, ...t.seats.filter(inPlay).map((s) => s.bet_bb))
  const tournament = t.format !== 'cash'
  return {
    format: t.format,
    num_players: t.num_players,
    hero_position: hero?.position ?? null,
    hero_hand: t.hero_hand,
    villains: villains.map((v) => ({ position: v.position, range: v.range, hand: v.hand })),
    board: boardForStreet(t.board, t.street),
    pot_bb: totalPot(t),
    to_call_bb: round2(Math.min(heroStack, Math.max(0, topBet - (hero?.bet_bb ?? 0)))),
    effective_stack_bb: villains.length ? Math.min(heroStack, Math.max(...villains.map((v) => v.stack_bb))) : heroStack,
    previous_action: previousActionFrom(t),
    situation: t.advanced.situation,
    ante_bb: t.advanced.ante_bb,
    bb_ante_bb: t.advanced.bb_ante_bb,
    stacks_bb: tournament ? Object.fromEntries(t.seats.filter(inPlay).map((s) => [s.position, s.stack_bb])) : {},
    payouts: tournament ? t.advanced.payouts : [],
    hero_range: t.advanced.hero_range || null,
    ranges_approximate: t.advanced.ranges_approximate,
    solver_preset: t.advanced.solver_preset,
  }
}

/** First reason the table cannot be analyzed, or null. */
export function validateTable(t: TableState): string | null {
  if (t.seats.filter((s) => s.role === 'hero').length !== 1) return 'Elegí tu asiento: tocá un asiento y marcá "Vos".'
  const villains = villainSeats(t.seats)
  if (villains.length === 0) return 'Marcá al menos un rival en la mesa.'
  if (t.hero_hand.length !== 4) return 'Elegí tus dos cartas (o repartí al azar).'
  const need = BOARD_CARDS[t.street]
  if (Math.floor(t.board.length / 2) < need) {
    return `Faltan cartas del board: el ${STREET_LABEL[t.street].toLowerCase()} lleva ${need}.`
  }
  const over = t.seats.find((s) => inPlay(s) && s.bet_bb > s.stack_bb)
  if (over) return `La apuesta de ${over.position} supera su stack.`
  const cards = [t.hero_hand, boardForStreet(t.board, t.street), ...villains.map((v) => v.hand ?? '')].join('').match(/.{2}/g) ?? []
  if (new Set(cards).size !== cards.length) return 'Hay cartas repetidas.'
  return null
}
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `cd src/frontend && npx vitest run src/simulator/table.test.ts`
Expected: PASS (11 + 15 = 26 tests).

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/simulator/table.ts src/frontend/src/simulator/table.test.ts
git commit -m "feat(simulator): table to scenario translation, bet presets and validation"
```

---

### Task 3: Mesa por defecto, desde un escenario inicial, y guarda de tipo (`table.ts`, parte C)

**Files:**
- Modify: `src/frontend/src/simulator/table.ts` (se agrega al final)
- Test: `src/frontend/src/simulator/table.test.ts`

**Interfaces:**
- Consumes: lo de las Tasks 1 y 2.
- Produces:
  - `SIM_TABLE_KEY = 'pokker.simulator.table'`
  - `defaultTable(filters: { format: string; players: number } | null): TableState`
  - `tableFromInitial(initial: Partial<ScenarioInput>, base: TableState): TableState`
  - `isTableState(v: unknown): v is TableState`

- [ ] **Step 1: Escribir el test que falla**

Agregar a los imports de `./table`: `defaultTable`, `isTableState` y `tableFromInitial`. Después, al final de `table.test.ts`:

```ts
describe('defaultTable', () => {
  it('starts cash 6-max on the flop, you on BTN against the BB', () => {
    const t = defaultTable(null)
    expect(t).toMatchObject({ format: 'cash', num_players: 6, street: 'flop', pot_bb: 6.5, board: '', hero_hand: '' })
    expect(heroSeat(t.seats)?.position).toBe('BTN')
    expect(villainSeats(t.seats).map((s) => s.position)).toEqual(['BB'])
  })

  it('takes format and players from the Preflop filters', () => {
    expect(defaultTable({ format: 'mtt', players: 9 })).toMatchObject({ format: 'mtt', num_players: 9 })
    expect(defaultTable({ format: 'raro', players: 9 }).format).toBe('cash')
  })
})

describe('tableFromInitial', () => {
  it('opens a Preflop spot on the preflop street with the blinds in the pot', () => {
    const t = tableFromInitial(
      {
        format: 'cash',
        num_players: 6,
        hero_position: 'CO',
        effective_stack_bb: 40,
        situation: 'rfi',
        villains: [{ position: 'BB', range: 'random', hand: null }],
      },
      defaultTable(null),
    )
    expect(t).toMatchObject({ street: 'preflop', pot_bb: 1.5, board: '' })
    expect(t.advanced.situation).toBe('rfi')
    expect(heroSeat(t.seats)).toMatchObject({ position: 'CO', stack_bb: 40 })
    expect(villainSeats(t.seats)).toEqual([{ ...newSeat('BB', 40), role: 'villain' }])
  })

  it('rebuilds a replayer spot that translates back to the same pot and price', () => {
    const initial = {
      format: 'cash' as const,
      num_players: 6,
      hero_position: 'BB',
      hero_hand: 'AhKs',
      villains: [{ position: 'BTN', range: '22+,A2s+', hand: null }],
      board: 'Kh7c2d',
      pot_bb: 11.5,
      to_call_bb: 4,
      effective_stack_bb: 93,
      previous_action: 'BTN abre 2.5bb; BB paga; BTN apuesta 4',
    }
    const t = tableFromInitial(initial, defaultTable(null))
    expect(t.street).toBe('flop')
    const s = tableToScenario(t)
    expect(s.pot_bb).toBe(11.5)
    expect(s.to_call_bb).toBe(4)
    expect(s.previous_action).toBe('BTN abre 2.5bb; BB paga; BTN apuesta 4')
    expect(s.villains).toEqual([{ position: 'BTN', range: '22+,A2s+', hand: null }])
  })

  it('never seats a rival on the hero position', () => {
    const t = tableFromInitial(
      { hero_position: 'BB', villains: [{ position: 'BB', range: 'random', hand: null }] },
      defaultTable(null),
    )
    expect(villainSeats(t.seats)).toEqual([])
  })
})

describe('isTableState', () => {
  it('accepts a real table and rejects corrupt or older shapes', () => {
    expect(isTableState(defaultTable(null))).toBe(true)
    expect(isTableState(JSON.parse(JSON.stringify(defaultTable(null))))).toBe(true)
    expect(isTableState(null)).toBe(false)
    expect(isTableState({ ...defaultTable(null), seats: [{ position: 'BTN' }] })).toBe(false)
    expect(isTableState({ ...defaultTable(null), street: 'showdown' })).toBe(false)
    const noAdvanced: Record<string, unknown> = { ...defaultTable(null) }
    delete noAdvanced.advanced
    expect(isTableState(noAdvanced)).toBe(false)
  })
})
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd src/frontend && npx vitest run src/simulator/table.test.ts`
Expected: FAIL porque `defaultTable`, `tableFromInitial` e `isTableState` no se exportan.

- [ ] **Step 3: Implementar (agregar al final de `table.ts`)**

```ts
export const SIM_TABLE_KEY = 'pokker.simulator.table'
const FORMATS: GameFormat[] = ['cash', 'mtt', 'sng', 'spin']
const ROLES: SeatRole[] = ['hero', 'villain', 'folded', 'empty']

/** Cash/6-max unless the Preflop filters say otherwise: you on BTN against the BB, on the flop. */
export function defaultTable(filters: { format: string; players: number } | null): TableState {
  const format = filters && FORMATS.includes(filters.format as GameFormat) ? (filters.format as GameFormat) : 'cash'
  return {
    format,
    num_players: filters?.players ?? 6,
    street: 'flop',
    seats: [
      { ...newSeat('BTN'), role: 'hero' },
      { ...newSeat('BB'), role: 'villain' },
    ],
    pot_bb: 6.5,
    board: '',
    hero_hand: '',
    advanced: { ...DEFAULT_ADVANCED },
  }
}

/**
 * A scenario sent by Preflop or the replayer. The amount to call goes on the first rival as its
 * bet and the rest stays as pot, so tableToScenario gives back the same pot and price.
 */
export function tableFromInitial(i: Partial<ScenarioInput>, base: TableState): TableState {
  const stack = i.effective_stack_bb ?? 100
  const stackOf = (p: string) => i.stacks_bb?.[p] ?? stack
  const heroPos = i.hero_position ?? null
  const seats: Seat[] = []
  if (heroPos) seats.push({ ...newSeat(heroPos, stackOf(heroPos)), role: 'hero' })
  for (const v of i.villains ?? []) {
    if (!v.position || v.position === heroPos || seats.some((s) => s.position === v.position)) continue
    seats.push({ ...newSeat(v.position, stackOf(v.position)), role: 'villain', range: v.range || 'random', hand: v.hand ?? null })
  }
  const toCall = i.to_call_bb ?? 0
  const firstRival = seats.find((s) => s.role === 'villain')
  if (firstRival && toCall > 0) firstRival.bet_bb = toCall
  const board = i.board ?? ''
  const pot = i.pot_bb ?? (board === '' ? 1.5 : base.pot_bb)
  return {
    format: i.format ?? base.format,
    num_players: i.num_players ?? base.num_players,
    street: streetFromBoard(board),
    seats: seats.length ? seats : base.seats,
    pot_bb: round2(Math.max(0, pot - (firstRival ? toCall : 0))),
    board,
    hero_hand: i.hero_hand ?? '',
    advanced: {
      ...DEFAULT_ADVANCED,
      ante_bb: i.ante_bb ?? 0,
      bb_ante_bb: i.bb_ante_bb ?? 0,
      payouts: i.payouts ?? [],
      hero_range: i.hero_range ?? '',
      ranges_approximate: i.ranges_approximate ?? false,
      solver_preset: i.solver_preset ?? 'chico',
      situation: i.situation ?? null,
      previous_action: i.previous_action ?? '',
    },
  }
}

function isSeat(v: unknown): v is Seat {
  if (typeof v !== 'object' || v === null) return false
  const o = v as Record<string, unknown>
  return (
    typeof o.position === 'string' &&
    ROLES.includes(o.role as SeatRole) &&
    typeof o.bet_bb === 'number' &&
    typeof o.stack_bb === 'number' &&
    typeof o.range === 'string' &&
    (o.hand === null || typeof o.hand === 'string')
  )
}

export function isTableState(v: unknown): v is TableState {
  if (typeof v !== 'object' || v === null) return false
  const o = v as Record<string, unknown>
  const a = o.advanced as Record<string, unknown> | null | undefined
  return (
    FORMATS.includes(o.format as GameFormat) &&
    typeof o.num_players === 'number' &&
    typeof o.street === 'string' &&
    o.street in BOARD_CARDS &&
    Array.isArray(o.seats) &&
    o.seats.every(isSeat) &&
    typeof o.pot_bb === 'number' &&
    typeof o.board === 'string' &&
    typeof o.hero_hand === 'string' &&
    typeof a === 'object' &&
    a !== null &&
    typeof a.ante_bb === 'number' &&
    typeof a.bb_ante_bb === 'number' &&
    Array.isArray(a.payouts) &&
    typeof a.hero_range === 'string' &&
    typeof a.ranges_approximate === 'boolean' &&
    typeof a.solver_preset === 'string' &&
    (a.situation === null || typeof a.situation === 'string') &&
    typeof a.previous_action === 'string'
  )
}
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `cd src/frontend && npx vitest run src/simulator/table.test.ts`
Expected: PASS (26 + 6 = 32 tests).

- [ ] **Step 5: Typecheck y commit**

Run: `cd src/frontend && npm run typecheck`
Expected: sin errores.

```bash
git add src/frontend/src/simulator/table.ts src/frontend/src/simulator/table.test.ts
git commit -m "feat(simulator): default table, table from an initial scenario, stored-table guard"
```

---

### Task 4: La mesa dibujada (`TableView`)

**Files:**
- Create: `src/frontend/src/simulator/TableView.tsx`
- Create: `src/frontend/src/simulator/table.css`
- Test: `src/frontend/src/simulator/TableView.test.tsx`

**Interfaces:**
- Consumes:
  - de `./table`: `rotateFromHero`, `seatPoint`, `totalPot`, `BOARD_CARDS`, `Seat`, `SeatRole` y `TableState`;
  - `CardView` (`{ card: string | null; onClick?; active?; disabled?; label? }`);
  - `toSlots` de `./cards`;
  - `makeTable` y `seat` de `../test/tables`.
- Produces:
  - `type CardSlotRef = { group: 'hero' | 'board'; index: number } | { group: 'seat'; position: string; index: number }`
  - `sameSlot(a: CardSlotRef | null, b: CardSlotRef): boolean`
  - `TableView(props)` con estas props:

```ts
interface TableViewProps {
  table: TableState
  selected: string | null
  onSeatClick: (position: string) => void
  activeSlot: CardSlotRef | null
  onSlotClick: (slot: CardSlotRef) => void
  onPotChange: (pot: number) => void
  renderSeatPanel?: (
    seat: Seat,
    anchorRef: RefObject<HTMLButtonElement | null>,
    style: { left: string; top: string },
  ) => ReactNode
}
```

**Nombres accesibles que usan los tests y la página:**
- **Botón de cada asiento:** `"{pos} · {Vos|Rival|Fold|Vacío} · {stack} bb"`. El stack usa coma decimal; por ejemplo, `"BTN · Vos · 100 bb"`.
- **Cartas:** `"Hero carta 1"` y `"Hero carta 2"`. En el board, `"Flop 1"`, `"Flop 2"`, `"Flop 3"`, `"Turn"` y `"River"`. Solo se muestran como botón las casillas que usa la calle; las demás se ven apagadas.
- **Pozo:** input numérico con etiqueta `"Pozo (bb)"`.
- **Total:** texto `"Total con apuestas: X bb"`.
- **La mesa entera:** `role="group"` con nombre `"Mesa"`.

- [ ] **Step 1: Escribir el test que falla**

`src/frontend/src/simulator/TableView.test.tsx`:

```tsx
import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { makeTable, seat } from '../test/tables'
import { sameSlot, TableView } from './TableView'

function setup(table = makeTable(), extra: Partial<Parameters<typeof TableView>[0]> = {}) {
  const props = {
    table,
    selected: null,
    onSeatClick: vi.fn(),
    activeSlot: null,
    onSlotClick: vi.fn(),
    onPotChange: vi.fn(),
    ...extra,
  }
  render(<TableView {...props} />)
  return props
}

describe('TableView', () => {
  it('draws one seat per position, the hero first, with role and stack', () => {
    setup()
    const mesa = screen.getByRole('group', { name: 'Mesa' })
    const seats = within(mesa)
      .getAllByRole('button')
      .filter((b) => / · /.test(b.getAttribute('aria-label') ?? ''))
      .map((b) => b.getAttribute('aria-label'))
    expect(seats).toEqual([
      'BTN · Vos · 100 bb',
      'SB · Fold · 100 bb',
      'BB · Rival · 100 bb',
      'LJ · Fold · 100 bb',
      'HJ · Fold · 100 bb',
      'CO · Fold · 100 bb',
    ])
  })

  it('places the hero at the bottom centre', () => {
    setup()
    const hero = screen.getByRole('button', { name: /^BTN · Vos/ }).closest('.sim-seat') as HTMLElement
    expect(hero.style.left).toBe('50%')
    expect(hero.style.top).toBe('88%')
  })

  it('opens a seat and edits the pot', () => {
    const props = setup()
    fireEvent.click(screen.getByRole('button', { name: /^BB · Rival/ }))
    expect(props.onSeatClick).toHaveBeenCalledWith('BB')
    fireEvent.change(screen.getByLabelText('Pozo (bb)'), { target: { value: '12' } })
    expect(props.onPotChange).toHaveBeenCalledWith(12)
  })

  it('shows bets as chips and the total pot', () => {
    const t = makeTable({
      seats: [seat('CO', 'villain', { bet_bb: 4 }), seat('BTN', 'hero'), seat('BB', 'villain', { bet_bb: 4 })],
    })
    setup(t)
    expect(screen.getAllByText('4 bb')).toHaveLength(2)
    expect(screen.getByText('Total con apuestas: 14,5 bb')).toBeInTheDocument()
  })

  it('offers only the board cards of the street, and your two cards', () => {
    const props = setup(makeTable({ street: 'flop', board: 'Kh7c2d' }))
    expect(screen.getByRole('button', { name: 'Flop 1: K de corazones' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Turn/ })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Hero carta 1: A de corazones' }))
    expect(props.onSlotClick).toHaveBeenCalledWith({ group: 'hero', index: 0 })
  })

  it('renders the seat panel for the selected seat only', () => {
    setup(makeTable(), { selected: 'BB', renderSeatPanel: (s) => <p>panel {s.position}</p> })
    expect(screen.getByText('panel BB')).toBeInTheDocument()
    expect(screen.queryByText('panel BTN')).toBeNull()
  })

  it('compares card slots by value', () => {
    expect(sameSlot({ group: 'seat', position: 'BB', index: 1 }, { group: 'seat', position: 'BB', index: 1 })).toBe(true)
    expect(sameSlot(null, { group: 'hero', index: 0 })).toBe(false)
  })
})
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd src/frontend && npx vitest run src/simulator/TableView.test.tsx`
Expected: FAIL porque no se puede resolver `./TableView`.

- [ ] **Step 3: Escribir el componente y el CSS**

`src/frontend/src/simulator/TableView.tsx`:

```tsx
import { createRef, type ReactNode, type RefObject, useRef } from 'react'
import { CardView } from './CardView'
import { toSlots } from './cards'
import { BOARD_CARDS, rotateFromHero, type Seat, type SeatRole, seatPoint, type TableState, totalPot } from './table'
import './table.css'

export type CardSlotRef =
  | { group: 'hero' | 'board'; index: number }
  | { group: 'seat'; position: string; index: number }

export function sameSlot(a: CardSlotRef | null, b: CardSlotRef): boolean {
  if (!a || a.group !== b.group || a.index !== b.index) return false
  return a.group !== 'seat' || (b.group === 'seat' && a.position === b.position)
}

const ROLE_TAG: Record<SeatRole, string> = { hero: 'Vos', villain: 'Rival', folded: 'Fold', empty: 'Vacío' }
const BOARD_LABELS = ['Flop 1', 'Flop 2', 'Flop 3', 'Turn', 'River']
const fmt = (n: number) => String(Math.round(n * 100) / 100).replace('.', ',')

interface TableViewProps {
  table: TableState
  selected: string | null
  onSeatClick: (position: string) => void
  activeSlot: CardSlotRef | null
  onSlotClick: (slot: CardSlotRef) => void
  onPotChange: (pot: number) => void
  renderSeatPanel?: (
    seat: Seat,
    anchorRef: RefObject<HTMLButtonElement | null>,
    style: { left: string; top: string },
  ) => ReactNode
}

export function TableView({ table, selected, onSeatClick, activeSlot, onSlotClick, onPotChange, renderSeatPanel }: TableViewProps) {
  const refs = useRef(new Map<string, RefObject<HTMLButtonElement | null>>())
  const refFor = (position: string) => {
    let r = refs.current.get(position)
    if (!r) {
      r = createRef<HTMLButtonElement>()
      refs.current.set(position, r)
    }
    return r
  }
  const order = rotateFromHero(table.seats)
  const n = order.length
  const used = BOARD_CARDS[table.street]
  const board = toSlots(table.board, 5)
  const hero = toSlots(table.hero_hand, 2)

  return (
    <div className="sim-stage" role="group" aria-label="Mesa">
      <div className="sim-felt" aria-hidden="true" />
      <div className="sim-center">
        <label className="sim-pot">
          Pozo (bb)
          <input
            type="number"
            min="0"
            step="0.5"
            value={table.pot_bb}
            onChange={(e) => onPotChange(Math.max(0, Number(e.target.value) || 0))}
          />
        </label>
        <p className="sim-pot-total">Total con apuestas: {fmt(totalPot(table))} bb</p>
        <div className="sim-board">
          {board.map((card, i) =>
            i < used ? (
              <CardView
                key={i}
                card={card}
                label={BOARD_LABELS[i]}
                active={sameSlot(activeSlot, { group: 'board', index: i })}
                onClick={() => onSlotClick({ group: 'board', index: i })}
              />
            ) : (
              <span key={i} className="card card-empty sim-board-off" aria-hidden="true" />
            ),
          )}
        </div>
      </div>

      {order.map((seat, k) => {
        const p = seatPoint(k, n)
        const bet = seatPoint(k, n, 0.55)
        const dealer = seatPoint(k, n, 0.72)
        const style = { left: `${p.left}%`, top: `${p.top}%` }
        return (
          <div key={seat.position}>
            <div
              className={`sim-seat sim-seat-${seat.role}${selected === seat.position ? ' sim-seat-selected' : ''}`}
              style={style}
            >
              {seat.role === 'hero' && (
                <div className="sim-hero-cards">
                  {hero.map((card, i) => (
                    <CardView
                      key={i}
                      card={card}
                      label={`Hero carta ${i + 1}`}
                      active={sameSlot(activeSlot, { group: 'hero', index: i })}
                      onClick={() => onSlotClick({ group: 'hero', index: i })}
                    />
                  ))}
                </div>
              )}
              <button
                ref={refFor(seat.position)}
                type="button"
                className="sim-plate"
                aria-label={`${seat.position} · ${ROLE_TAG[seat.role]} · ${fmt(seat.stack_bb)} bb`}
                aria-expanded={selected === seat.position}
                onClick={() => onSeatClick(seat.position)}
              >
                <span className="sim-pos">{seat.position}</span>
                <span className="sim-stack">{fmt(seat.stack_bb)} bb</span>
                <span className="sim-tag">{ROLE_TAG[seat.role]}</span>
              </button>
            </div>
            {seat.bet_bb > 0 && seat.role !== 'empty' && (
              <div className="sim-bet" style={{ left: `${bet.left}%`, top: `${bet.top}%` }}>
                <i aria-hidden="true" />
                {fmt(seat.bet_bb)} bb
              </div>
            )}
            {seat.position === 'BTN' && (
              <div
                className="sim-dealer"
                role="img"
                aria-label="Botón del dealer"
                style={{ left: `${dealer.left + 5}%`, top: `${dealer.top}%` }}
              >
                D
              </div>
            )}
            {selected === seat.position && renderSeatPanel?.(seat, refFor(seat.position), style)}
          </div>
        )
      })}
    </div>
  )
}
```

`src/frontend/src/simulator/table.css`:

```css
.sim-stage {
  position: relative;
  height: 470px;
  min-width: 560px;
}

.sim-felt {
  position: absolute;
  inset: 12% 9% 16% 9%;
  border-radius: 220px;
  background: radial-gradient(ellipse at center, var(--felt) 0%, color-mix(in srgb, var(--felt) 70%, var(--felt-edge)) 55%, var(--felt-edge) 100%);
  border: 10px solid var(--rail);
  box-shadow:
    inset 0 0 0 3px color-mix(in srgb, var(--gold) 35%, transparent),
    0 10px 30px rgb(0 0 0 / 0.5);
}

.sim-center {
  position: absolute;
  left: 50%;
  top: 46%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.sim-pot {
  flex-direction: row;
  align-items: center;
  gap: 6px;
  color: var(--text);
  font-weight: 700;
}

.sim-pot input {
  width: 80px;
}

.sim-pot-total {
  margin: 0;
  font-size: 11px;
  color: var(--text);
}

.sim-board {
  display: flex;
  gap: 5px;
}

.sim-board-off {
  opacity: 0.25;
}

.sim-seat {
  position: absolute;
  transform: translate(-50%, -50%);
  width: 110px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.sim-plate {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 5px 6px;
  background: var(--bg-deep);
  border: 2px solid var(--line-strong);
  border-radius: var(--radius-card);
}

.sim-pos {
  font-weight: 800;
  letter-spacing: 0.06em;
}

.sim-stack {
  font-size: 11px;
  color: var(--text-muted);
}

.sim-tag {
  margin-top: 2px;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  background: var(--line-strong);
  color: var(--text);
}

.sim-seat-hero .sim-plate {
  border-color: var(--gold);
  background: var(--surface-2);
}

.sim-seat-hero .sim-tag {
  background: var(--gold);
  color: var(--gold-ink);
}

.sim-seat-villain .sim-plate {
  border-color: var(--danger);
}

.sim-seat-villain .sim-tag {
  background: var(--danger);
  color: var(--on-danger);
}

.sim-seat-folded .sim-plate,
.sim-seat-empty .sim-plate {
  opacity: 0.55;
}

.sim-seat-selected .sim-plate {
  box-shadow: 0 0 0 3px var(--gold);
}

.sim-hero-cards {
  display: flex;
  gap: 4px;
}

.sim-bet {
  position: absolute;
  transform: translate(-50%, -50%);
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 800;
  color: var(--text);
  text-shadow: 0 0 3px var(--bg);
}

.sim-bet i {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--gold);
  border: 2px dashed var(--gold-ink);
}

.sim-dealer {
  position: absolute;
  transform: translate(-50%, -50%);
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--card-bg);
  color: #111;
  font-size: 10px;
  font-weight: 900;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sim-popover-anchor {
  position: absolute;
  transform: translate(-50%, 0);
  z-index: 40;
}

.sim-popover {
  top: 46px;
  left: -95px;
  width: 230px;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.sim-popover-title {
  font-weight: 800;
  color: var(--gold);
}

.sim-presets {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.sim-field {
  border: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.sim-field legend {
  padding: 0;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-muted);
}
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `cd src/frontend && npx vitest run src/simulator/TableView.test.tsx`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/simulator/TableView.tsx src/frontend/src/simulator/TableView.test.tsx src/frontend/src/simulator/table.css
git commit -m "feat(simulator): oval table view with seats, bets, dealer, pot and board"
```

---

### Task 5: Popover del asiento (`SeatPopover`)

**Files:**
- Create: `src/frontend/src/simulator/SeatPopover.tsx`
- Test: `src/frontend/src/simulator/SeatPopover.test.tsx`

**Interfaces:**
- Consumes:
  - de `../ui`: `Popover`, `PillGroup` y `Button`;
  - `RangeEditor` (`{ id; value; onChange }`; parsea con `POST /api/ranges/parse`);
  - `CardView` y `toSlots`;
  - de `./table`: `presetBet`, `BetPreset`, `Seat`, `SeatRole` y `TableState`;
  - de `./TableView`: `CardSlotRef` y `sameSlot`.
- Produces: `SeatPopover(props)` con estas props:

```ts
interface SeatPopoverProps {
  seat: Seat
  table: TableState
  anchorRef: RefObject<HTMLButtonElement | null>
  onClose: () => void
  onRole: (role: SeatRole) => void
  onChange: (patch: Partial<Seat>) => void
  activeSlot: CardSlotRef | null
  onSlotClick: (slot: CardSlotRef) => void
}
```

Los nombres accesibles son:
- el diálogo, `"Asiento {pos}"`;
- el grupo de roles, `"Asiento"`, con los radios `Vos`, `Rival`, `Fold` y `Vacío`;
- los botones de apuesta, `⅓`, `½`, `⅔`, `Pot` y `All-in`;
- los inputs, `"Apuesta (bb)"` y `"Stack (bb)"`;
- el rango, `"Rango"`;
- las cartas, `"{pos} carta 1"` y `"{pos} carta 2"`;
- el botón para cerrar, `"Listo"`.

- [ ] **Step 1: Escribir el test que falla**

`src/frontend/src/simulator/SeatPopover.test.tsx`:

```tsx
import { fireEvent, render, screen } from '@testing-library/react'
import { useRef } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { makeTable, seat } from '../test/tables'
import { mockApi } from '../test/fetchMock'
import { SeatPopover } from './SeatPopover'
import type { Seat } from './table'

afterEach(() => vi.unstubAllGlobals())

function Harness(props: { seat: Seat; onRole?: () => void; onChange?: () => void; onSlotClick?: () => void }) {
  const anchor = useRef<HTMLButtonElement>(null)
  const table = makeTable({ seats: [seat('BTN', 'hero'), props.seat] }) // total pot 6.5 + bets
  return (
    <div>
      <button ref={anchor} type="button">
        ancla
      </button>
      <SeatPopover
        seat={props.seat}
        table={table}
        anchorRef={anchor}
        onClose={() => {}}
        onRole={props.onRole ?? (() => {})}
        onChange={props.onChange ?? (() => {})}
        activeSlot={null}
        onSlotClick={props.onSlotClick ?? (() => {})}
      />
    </div>
  )
}

describe('SeatPopover', () => {
  it('changes the role of the seat', () => {
    const onRole = vi.fn()
    render(<Harness seat={seat('BB', 'villain')} onRole={onRole} />)
    expect(screen.getByRole('dialog', { name: 'Asiento BB' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Rival' })).toBeChecked()
    fireEvent.click(screen.getByRole('radio', { name: 'Vos' }))
    expect(onRole).toHaveBeenCalledWith('hero')
  })

  it('sizes bets on the total pot and accepts a free amount and the stack', () => {
    mockApi({ 'POST /api/ranges/parse': () => ({ json: { valid: true, error: null, combos: 1326, grid: [] } }) })
    const onChange = vi.fn()
    render(<Harness seat={seat('BB', 'villain', { stack_bb: 50 })} onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: 'Pot' }))
    expect(onChange).toHaveBeenLastCalledWith({ bet_bb: 6.5 })
    fireEvent.click(screen.getByRole('button', { name: 'All-in' }))
    expect(onChange).toHaveBeenLastCalledWith({ bet_bb: 50 })
    fireEvent.change(screen.getByLabelText('Apuesta (bb)'), { target: { value: '4' } })
    expect(onChange).toHaveBeenLastCalledWith({ bet_bb: 4 })
    fireEvent.change(screen.getByLabelText('Stack (bb)'), { target: { value: '93' } })
    expect(onChange).toHaveBeenLastCalledWith({ stack_bb: 93 })
  })

  it('edits the range and optional cards of a rival', () => {
    mockApi({ 'POST /api/ranges/parse': () => ({ json: { valid: true, error: null, combos: 1326, grid: [] } }) })
    const onChange = vi.fn()
    const onSlotClick = vi.fn()
    render(<Harness seat={seat('BB', 'villain')} onChange={onChange} onSlotClick={onSlotClick} />)
    fireEvent.change(screen.getByLabelText('Rango'), { target: { value: 'QQ+' } })
    expect(onChange).toHaveBeenLastCalledWith({ range: 'QQ+' })
    fireEvent.click(screen.getByRole('button', { name: 'BB carta 1: vacía' }))
    expect(onSlotClick).toHaveBeenCalledWith({ group: 'seat', position: 'BB', index: 0 })
  })

  it('a folded seat only offers the role', () => {
    render(<Harness seat={seat('CO', 'folded')} />)
    expect(screen.queryByLabelText('Apuesta (bb)')).toBeNull()
    expect(screen.queryByLabelText('Rango')).toBeNull()
  })
})
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd src/frontend && npx vitest run src/simulator/SeatPopover.test.tsx`
Expected: FAIL porque no se puede resolver `./SeatPopover`.

- [ ] **Step 3: Escribir el componente**

Antes de escribir el componente, verificá en `RangeEditor.tsx` que el `<textarea>` (o `<input>`) que recibe el texto del rango tenga `id={id}`. El `<label htmlFor>` del popover depende de eso. Si el `id` está en otro elemento, ajustá el `htmlFor` y anotalo como ruling.

`src/frontend/src/simulator/SeatPopover.tsx`:

```tsx
import type { RefObject } from 'react'
import { Button, PillGroup, Popover } from '../ui'
import { CardView } from './CardView'
import { toSlots } from './cards'
import { RangeEditor } from './RangeEditor'
import { type BetPreset, presetBet, type Seat, type SeatRole, type TableState } from './table'
import { type CardSlotRef, sameSlot } from './TableView'

const ROLES: { value: SeatRole; label: string }[] = [
  { value: 'hero', label: 'Vos' },
  { value: 'villain', label: 'Rival' },
  { value: 'folded', label: 'Fold' },
  { value: 'empty', label: 'Vacío' },
]
const PRESETS: [BetPreset, string][] = [
  ['third', '⅓'],
  ['half', '½'],
  ['twothirds', '⅔'],
  ['pot', 'Pot'],
  ['allin', 'All-in'],
]

interface SeatPopoverProps {
  seat: Seat
  table: TableState
  anchorRef: RefObject<HTMLButtonElement | null>
  onClose: () => void
  onRole: (role: SeatRole) => void
  onChange: (patch: Partial<Seat>) => void
  activeSlot: CardSlotRef | null
  onSlotClick: (slot: CardSlotRef) => void
}

const amount = (value: string) => Math.max(0, Number(value) || 0)

export function SeatPopover({ seat, table, anchorRef, onClose, onRole, onChange, activeSlot, onSlotClick }: SeatPopoverProps) {
  const playing = seat.role === 'hero' || seat.role === 'villain'
  const rangeId = `seat-${seat.position}-range`
  return (
    <Popover open onClose={onClose} anchorRef={anchorRef} label={`Asiento ${seat.position}`} className="sim-popover">
      <div className="sim-popover-title">{seat.position}</div>
      <PillGroup legend="Asiento" options={ROLES} value={seat.role} onChange={onRole} />
      {playing && (
        <>
          <fieldset className="sim-field">
            <legend>Apuesta en esta calle</legend>
            <div className="sim-presets">
              {PRESETS.map(([preset, label]) => (
                <Button
                  key={preset}
                  size="sm"
                  onClick={() => onChange({ bet_bb: presetBet(table, seat.position, preset) })}
                >
                  {label}
                </Button>
              ))}
            </div>
            <label>
              Apuesta (bb)
              <input
                type="number"
                min="0"
                step="0.5"
                value={seat.bet_bb}
                onChange={(e) => onChange({ bet_bb: amount(e.target.value) })}
              />
            </label>
          </fieldset>
          <label>
            Stack (bb)
            <input
              type="number"
              min="0"
              step="1"
              value={seat.stack_bb}
              onChange={(e) => onChange({ stack_bb: amount(e.target.value) })}
            />
          </label>
        </>
      )}
      {seat.role === 'villain' && (
        <>
          <label htmlFor={rangeId}>Rango</label>
          <RangeEditor id={rangeId} value={seat.range} onChange={(range) => onChange({ range })} />
          <p className="field-label">Cartas (opcional)</p>
          <div className="card-slots">
            {toSlots(seat.hand, 2).map((card, i) => (
              <CardView
                key={i}
                card={card}
                label={`${seat.position} carta ${i + 1}`}
                active={sameSlot(activeSlot, { group: 'seat', position: seat.position, index: i })}
                onClick={() => onSlotClick({ group: 'seat', position: seat.position, index: i })}
              />
            ))}
          </div>
        </>
      )}
      <Button size="sm" onClick={onClose}>
        Listo
      </Button>
    </Popover>
  )
}
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `cd src/frontend && npx vitest run src/simulator/SeatPopover.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/simulator/SeatPopover.tsx src/frontend/src/simulator/SeatPopover.test.tsx
git commit -m "feat(simulator): seat popover with role, bet presets, stack, range and cards"
```

---

### Task 6: Opciones avanzadas (`AdvancedOptions`)

**Files:**
- Create: `src/frontend/src/simulator/AdvancedOptions.tsx`
- Test: `src/frontend/src/simulator/AdvancedOptions.test.tsx`

**Interfaces:**
- Consumes: `AdvancedOptions` y `TableState` de `./table`, y `SITUATIONS` de `../ranges/labels`.
- Produces:
  - `AdvancedPanel(props: { table: TableState; onChange: (advanced: AdvancedOptions) => void; autoAction: string; children?: ReactNode })`
  - `parsePayouts(text: string): number[]`

El componente se llama `AdvancedPanel` para no chocar con el tipo `AdvancedOptions`. Es un `<details>` cuyo `<summary>` dice "Opciones avanzadas". `children` recibe los campos del solver (`PostflopSolverFields`), que la página pasa cuando corresponde.

- [ ] **Step 1: Escribir el test que falla**

`src/frontend/src/simulator/AdvancedOptions.test.tsx`:

```tsx
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { makeTable } from '../test/tables'
import { AdvancedPanel, parsePayouts } from './AdvancedOptions'

describe('AdvancedPanel', () => {
  it('edits situation, antes and a typed previous action', () => {
    const onChange = vi.fn()
    const table = makeTable()
    render(<AdvancedPanel table={table} onChange={onChange} autoAction="CO bet 4, BTN call 4" />)
    expect(screen.getByText('Opciones avanzadas')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Situación preflop'), { target: { value: 'vs_open' } })
    expect(onChange).toHaveBeenLastCalledWith({ ...table.advanced, situation: 'vs_open' })
    fireEvent.change(screen.getByLabelText('Ante (bb)'), { target: { value: '0.12' } })
    expect(onChange).toHaveBeenLastCalledWith({ ...table.advanced, ante_bb: 0.12 })

    const action = screen.getByLabelText('Acción previa')
    expect(action).toHaveAttribute('placeholder', 'CO bet 4, BTN call 4')
    fireEvent.change(action, { target: { value: 'CO abre 2.5bb' } })
    expect(onChange).toHaveBeenLastCalledWith({ ...table.advanced, previous_action: 'CO abre 2.5bb' })
  })

  it('shows payouts only in tournaments', () => {
    const onChange = vi.fn()
    const { rerender } = render(<AdvancedPanel table={makeTable()} onChange={onChange} autoAction="" />)
    expect(screen.queryByLabelText(/Premios/)).toBeNull()
    const mtt = makeTable({ format: 'mtt' })
    rerender(<AdvancedPanel table={mtt} onChange={onChange} autoAction="" />)
    fireEvent.change(screen.getByLabelText(/Premios/), { target: { value: '50, 30; 20' } })
    expect(onChange).toHaveBeenLastCalledWith({ ...mtt.advanced, payouts: [50, 30, 20] })
  })

  it('renders the solver fields it receives', () => {
    render(
      <AdvancedPanel table={makeTable()} onChange={() => {}} autoAction="">
        <p>campos del solver</p>
      </AdvancedPanel>,
    )
    expect(screen.getByText('campos del solver')).toBeInTheDocument()
  })
})

describe('parsePayouts', () => {
  it('splits on commas, semicolons and spaces and drops junk', () => {
    expect(parsePayouts('50, 30;20  x -5')).toEqual([50, 30, 20])
    expect(parsePayouts('')).toEqual([])
  })
})
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd src/frontend && npx vitest run src/simulator/AdvancedOptions.test.tsx`
Expected: FAIL porque no se puede resolver `./AdvancedOptions`.

- [ ] **Step 3: Escribir el componente**

`src/frontend/src/simulator/AdvancedOptions.tsx`:

```tsx
import { type ReactNode, useState } from 'react'
import { SITUATIONS } from '../ranges/labels'
import type { AdvancedOptions, TableState } from './table'

export function parsePayouts(text: string): number[] {
  return text
    .split(/[,;\s]+/)
    .filter(Boolean)
    .map(Number)
    .filter((n) => Number.isFinite(n) && n >= 0)
}

const amount = (value: string) => Math.max(0, Number(value) || 0)

interface Props {
  table: TableState
  onChange: (advanced: AdvancedOptions) => void
  /** Previous action built from the bets, shown as the placeholder. */
  autoAction: string
  children?: ReactNode
}

export function AdvancedPanel({ table, onChange, autoAction, children }: Props) {
  const a = table.advanced
  const [payoutText, setPayoutText] = useState(a.payouts.join(', '))
  const set = (patch: Partial<AdvancedOptions>) => onChange({ ...a, ...patch })
  return (
    <details className="panel sim-advanced">
      <summary>Opciones avanzadas</summary>
      <div className="field-row">
        <label>
          Situación preflop
          <select value={a.situation ?? ''} onChange={(e) => set({ situation: e.target.value || null })}>
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
          <input type="number" min="0" step="0.01" value={a.ante_bb} onChange={(e) => set({ ante_bb: amount(e.target.value) })} />
        </label>
        <label>
          BB ante (bb)
          <input
            type="number"
            min="0"
            step="0.1"
            value={a.bb_ante_bb}
            onChange={(e) => set({ bb_ante_bb: amount(e.target.value) })}
          />
        </label>
      </div>
      <label>
        Acción previa
        <input
          type="text"
          value={a.previous_action}
          placeholder={autoAction || 'Se arma con las apuestas de la mesa'}
          onChange={(e) => set({ previous_action: e.target.value })}
        />
      </label>
      {table.format !== 'cash' && (
        <label>
          Premios que quedan (vacío = chip EV)
          <input
            type="text"
            value={payoutText}
            placeholder="Ej.: 50, 30, 20"
            onChange={(e) => {
              setPayoutText(e.target.value)
              set({ payouts: parsePayouts(e.target.value) })
            }}
          />
        </label>
      )}
      {children}
    </details>
  )
}
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `cd src/frontend && npx vitest run src/simulator/AdvancedOptions.test.tsx`
Expected: PASS (4 tests). Los `<details>` cerrados igual exponen su contenido en jsdom, así que los `getByLabelText` encuentran los campos.

- [ ] **Step 5: Commit**

```bash
git add src/frontend/src/simulator/AdvancedOptions.tsx src/frontend/src/simulator/AdvancedOptions.test.tsx
git commit -m "feat(simulator): advanced options panel (situation, antes, typed action, payouts)"
```

---

### Task 7: `SimulatorPage` con la mesa

**Files:**
- Modify (se reescribe): `src/frontend/src/simulator/SimulatorPage.tsx`
- Modify (se reescribe): `src/frontend/src/simulator/SimulatorPage.test.tsx`
- Modify: `src/frontend/src/simulator/simulator.css` (layout)
- Modify: `src/frontend/src/App.test.tsx` (test "opens a preflop spot in the simulator…")

**Interfaces:**
- Consumes:
  - todo `table.ts` (Tasks 1–3), `TableView` (4), `SeatPopover` (5) y `AdvancedPanel` (6);
  - los existentes `CardPicker`, `ResultsPanel` (`{ analysis; villainLabels; onSolveDone }`) y `PostflopSolverFields` (props sin cambios);
  - `fetchSolverStatus` y `prefillRanges` de `../solver/api`;
  - `readStored`/`writeStored`;
  - `isPreflopFilters`, `PREFLOP_FILTERS_KEY` y `PreflopFilters` de `../ranges/preflopFilters`;
  - de `../ui`: `Button`, `Chip`, `PillGroup` y `Popover`.
- Produces: `SimulatorPage({ initial?: InitialScenario })` y `export type InitialScenario = Partial<ScenarioInput>`, sin cambios para `App.tsx`.

- [ ] **Step 1: Reescribir los tests de la página (fallan)**

`src/frontend/src/simulator/SimulatorPage.test.tsx` (reemplaza el archivo):

```tsx
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/fetchMock'
import { SimulatorPage } from './SimulatorPage'
import type { Analysis } from './types'

afterEach(() => {
  vi.unstubAllGlobals()
  window.localStorage.clear()
})

const POSITIONS = ['LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']

const equity = (hero: number) => ({
  hero: { equity: hero, win: hero, tie: 0, lose: 1 - hero, std_error: 0 },
  villains: [{ equity: 1 - hero, win: 1 - hero, tie: 0, lose: hero, std_error: 0 }],
  exact: true,
  samples: 44,
})

const ANALYSIS: Analysis = {
  street: 'turn',
  equity: equity(0.7),
  equity_vs_hands: equity(2 / 44),
  outs: { available: true, currently_ahead: true, hero_share: 0.67, cards: [], count: 0, unseen: 44 },
  metrics: { pot_odds: 2, required_equity: 1 / 3, mdf: 0.5, spr: 4 },
  ranges: [{ text: 'KK,QQ', combos: 9 }],
  recommendation: {
    available: true,
    message: null,
    source: 'chart',
    confidence: 'approximate',
    hand_class: 'AA',
    actions: [
      { action: 'raise', frequency: 0.75, ev: null, label: null, amount_bb: null },
      { action: 'fold', frequency: 0.25, ev: null, label: null, amount_bb: null },
    ],
    ev_unit: null,
    reference: 'Fuente externa: Pokalab · BTN RFI',
    explanation: ['Valor: la mano está en la mitad fuerte de tu rango de raise.'],
    warnings: ['Stack del rango: 100bb (escenario: 40bb)'],
    pending_job: null,
    strategy_grid: [],
  },
}

function baseRoutes(extra: Parameters<typeof mockApi>[0] = {}) {
  return mockApi({
    'GET /api/simulator/positions': () => ({ json: POSITIONS }),
    'POST /api/ranges/parse': () => ({ json: { valid: true, error: null, combos: 1326, grid: Array(169).fill(1) } }),
    ...extra,
  })
}

const seatButton = (name: RegExp) => screen.getByRole('button', { name })

describe('SimulatorPage', () => {
  it('draws the table: you on BTN at the bottom against the BB', async () => {
    baseRoutes()
    render(<SimulatorPage />)
    await screen.findByRole('button', { name: /^LJ · Fold/ })
    expect(seatButton(/^BTN · Vos · 100 bb/)).toBeInTheDocument()
    expect(seatButton(/^BB · Rival/)).toBeInTheDocument()
  })

  it('picks cards with the picker and disables cards already used', () => {
    baseRoutes()
    render(<SimulatorPage />)
    fireEvent.click(screen.getByRole('button', { name: 'Hero carta 1: vacía' }))
    const picker = screen.getByRole('dialog', { name: 'Elegir carta' })
    fireEvent.click(within(picker).getByRole('button', { name: 'A de corazones' }))
    expect(screen.getByRole('button', { name: 'Hero carta 1: A de corazones' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Flop 1: vacía' }))
    const picker2 = screen.getByRole('dialog', { name: 'Elegir carta' })
    expect(within(picker2).getByRole('button', { name: 'A de corazones' })).toBeDisabled()
  })

  it('keeps Analizar disabled with the reason until the table is complete', () => {
    baseRoutes()
    render(<SimulatorPage />)
    expect(screen.getByRole('button', { name: 'Analizar' })).toBeDisabled()
    expect(screen.getByText('Elegí tus dos cartas (o repartí al azar).')).toBeInTheDocument()
  })

  it('deals, follows the street of the dealt board and shows the analysis', async () => {
    const fetchMock = baseRoutes({
      'POST /api/simulator/deal': () => ({ json: { hero_hand: 'AhAd', board: 'Kh7s2c3d', villain_hands: [null] } }),
      'POST /api/simulator/analyze': () => ({ json: ANALYSIS }),
    })
    render(<SimulatorPage />)
    await screen.findByRole('button', { name: /^LJ · Fold/ })
    fireEvent.click(screen.getByRole('button', { name: 'Todo al azar' }))
    expect(await screen.findByRole('button', { name: 'Hero carta 1: A de corazones' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Turn: 3 de diamantes' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Turn' })).toBeChecked()

    fireEvent.click(screen.getByRole('button', { name: 'Analizar' }))
    expect(await screen.findByText('70.0%', { selector: '.big-number' })).toBeInTheDocument()
    expect(screen.getByText('Fuente externa: Pokalab · BTN RFI')).toBeInTheDocument()

    const call = fetchMock.mock.calls.find(([url]) => String(url) === '/api/simulator/analyze')
    const sent = JSON.parse(String(call?.[1]?.body))
    expect(sent).toMatchObject({ hero_position: 'BTN', hero_hand: 'AhAd', board: 'Kh7s2c3d', pot_bb: 6.5, to_call_bb: 0 })
    expect(sent.villains).toEqual([{ position: 'BB', range: 'random', hand: null }])
  })

  it('builds the scenario from the seats: BB facing CO bet and BTN call', async () => {
    const fetchMock = baseRoutes({ 'POST /api/simulator/analyze': () => ({ json: ANALYSIS }) })
    render(<SimulatorPage initial={{ hero_position: 'BB', hero_hand: 'AhKs', board: 'Kh7c2d', pot_bb: 6.5, villains: [] }} />)
    await screen.findByRole('button', { name: /^LJ · Fold/ })

    for (const pos of ['CO', 'BTN']) {
      fireEvent.click(seatButton(new RegExp(`^${pos} ·`)))
      const dialog = screen.getByRole('dialog', { name: `Asiento ${pos}` })
      fireEvent.click(within(dialog).getByRole('radio', { name: 'Rival' }))
      fireEvent.change(within(dialog).getByLabelText('Apuesta (bb)'), { target: { value: '4' } })
      fireEvent.click(within(dialog).getByRole('button', { name: 'Listo' }))
    }
    expect(screen.getByText('Total con apuestas: 14,5 bb')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Analizar' }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([u]) => String(u) === '/api/simulator/analyze')).toBe(true))
    const call = fetchMock.mock.calls.find(([url]) => String(url) === '/api/simulator/analyze')
    expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({
      hero_position: 'BB',
      pot_bb: 14.5,
      to_call_bb: 4,
      previous_action: 'CO bet 4, BTN call 4',
      villains: [
        { position: 'CO', range: 'random', hand: null },
        { position: 'BTN', range: 'random', hand: null },
      ],
    })
  })

  it('moves you to another seat and rotates the table', async () => {
    baseRoutes()
    render(<SimulatorPage />)
    await screen.findByRole('button', { name: /^LJ · Fold/ })
    fireEvent.click(seatButton(/^SB ·/))
    fireEvent.click(within(screen.getByRole('dialog', { name: 'Asiento SB' })).getByRole('radio', { name: 'Vos' }))
    expect(seatButton(/^SB · Vos/)).toBeInTheDocument()
    expect(seatButton(/^BTN · Fold/)).toBeInTheDocument()
    const mesa = screen.getByRole('group', { name: 'Mesa' })
    const first = within(mesa).getAllByRole('button').find((b) => / · /.test(b.getAttribute('aria-label') ?? ''))
    expect(first).toHaveAccessibleName(/^SB · Vos/)
  })

  it('remembers the table and drops a corrupt stored one', async () => {
    baseRoutes()
    const first = render(<SimulatorPage />)
    await screen.findByRole('button', { name: /^LJ · Fold/ })
    fireEvent.change(screen.getByLabelText('Pozo (bb)'), { target: { value: '20' } })
    first.unmount()
    render(<SimulatorPage />)
    expect(screen.getByLabelText('Pozo (bb)')).toHaveValue(20)
  })

  it('a corrupt stored table falls back to the default', () => {
    baseRoutes()
    window.localStorage.setItem('pokker.simulator.table', '{"format":"cash","seats":[{"position":1}]}')
    render(<SimulatorPage />)
    expect(screen.getByLabelText('Pozo (bb)')).toHaveValue(6.5)
  })

  it('starts with the players of the Preflop filters when nothing is stored', async () => {
    mockApi({
      'GET /api/simulator/positions/9': () => ({
        json: ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB'],
      }),
      'POST /api/ranges/parse': () => ({ json: { valid: true, error: null, combos: 1326, grid: [] } }),
    })
    window.localStorage.setItem(
      'pokker.preflop.filters',
      JSON.stringify({ format: 'mtt', source: 'all', rake: 'all', players: 9 }),
    )
    render(<SimulatorPage />)
    expect(await screen.findByRole('button', { name: /^UTG\+2 · Fold/ })).toBeInTheDocument()
    expect(screen.getByText(/Torneo \(MTT\) · 9-max/)).toBeInTheDocument()
  })

  it('shows API validation errors in Spanish', async () => {
    baseRoutes({
      'POST /api/simulator/deal': () => ({ json: { hero_hand: 'AhAd', board: 'AsKs', villain_hands: [null] } }),
      'POST /api/simulator/analyze': () => ({
        status: 422,
        json: { detail: [{ msg: 'Value error, El board debe tener 0, 3, 4 o 5 cartas' }] },
      }),
    })
    render(<SimulatorPage />)
    fireEvent.click(screen.getByRole('button', { name: 'Completar al azar' }))
    await screen.findByRole('button', { name: 'Hero carta 1: A de corazones' })
    fireEvent.click(screen.getByRole('button', { name: 'Analizar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('El board debe tener 0, 3, 4 o 5 cartas')
  })
})
```

En `src/frontend/src/App.test.tsx`, en el test `'opens a preflop spot in the simulator with the position preset'`, reemplazar:

```tsx
    // Hero and each rival have a "Posición" select; the hero one is #hero-pos.
    await waitFor(() => expect(document.getElementById('hero-pos')).toHaveValue('CO'))
```

por:

```tsx
    expect(await screen.findByRole('button', { name: /^CO · Vos/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^BB · Rival/ })).toBeInTheDocument()
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd src/frontend && npx vitest run src/simulator/SimulatorPage.test.tsx src/App.test.tsx`
Expected: FAIL. El formulario viejo no tiene botones de asiento ni el grupo "Mesa".

- [ ] **Step 3: Reescribir `SimulatorPage.tsx`**

`src/frontend/src/simulator/SimulatorPage.tsx` (reemplaza el archivo):

```tsx
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
import { type CardSlotRef, sameSlot, TableView } from './TableView'
import type { Analysis, DealRequest, DealResult, GameFormat, ScenarioInput, Street } from './types'

/** A scenario to start from (e.g. a spot sent by the hand replayer or Preflop). */
export type InitialScenario = Partial<ScenarioInput>

const FORMAT_LABEL: Record<GameFormat, string> = { cash: 'Cash', mtt: 'Torneo (MTT)', sng: 'Sit & Go', spin: 'Spin & Go' }
const STREETS: Street[] = ['preflop', 'flop', 'turn', 'river']
const MAX_PLAYERS = 10
const message = (e: unknown) => (e instanceof Error ? e.message : String(e))
const storedFilters = (v: unknown): v is PreflopFilters | null => v === null || isPreflopFilters(v)

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
    setTable((t) => {
      if (slot.group === 'hero') {
        const s = toSlots(t.hero_hand, 2)
        s[slot.index] = card
        return { ...t, hero_hand: joinSlots(s) }
      }
      if (slot.group === 'board') {
        const s = toSlots(t.board, 5)
        s[slot.index] = card
        return { ...t, board: joinSlots(s) }
      }
      const s = toSlots(t.seats.find((x) => x.position === slot.position)?.hand, 2)
      s[slot.index] = card
      return { ...t, seats: updateSeat(t.seats, slot.position, { hand: joinSlots(s) || null }) }
    })
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
            <div className="sim-popover-anchor" style={style}>
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
```

- [ ] **Step 4: Layout en `simulator.css`**

En `src/frontend/src/simulator/simulator.css`, reemplazar el bloque que va desde `.simulator {` hasta la regla `.sim-results { … }` inclusive (incluye el `@media (max-width: 860px)` de `.simulator` y `.sim-config, .results`) por:

```css
.simulator {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: var(--space-5);
  align-items: start;
}

@media (max-width: 1100px) {
  .simulator {
    grid-template-columns: minmax(0, 1fr);
  }
}

.sim-main,
.sim-side,
.results {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  min-width: 0;
}

.sim-main {
  overflow-x: auto;
}

.sim-side {
  position: sticky;
  top: var(--space-4);
}

.sim-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.sim-config {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}

.sim-config-pop {
  top: 36px;
  left: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.sim-actions {
  display: flex;
  gap: var(--space-2);
}

.sim-advanced summary {
  cursor: pointer;
  font-weight: 700;
}
```

Después confirmá que `.sim-config` y `.sim-results` no quedan usados en ningún `.tsx`: `git grep -n "sim-results\|sim-config\b" src/frontend/src`. Tiene que aparecer solo el `.sim-config` nuevo de `SimulatorPage`.

- [ ] **Step 5: Correr los tests y verificar que pasan**

Run: `cd src/frontend && npx vitest run src/simulator src/App.test.tsx`
Expected: PASS. `SimulatorPage` tiene 10 tests. `App` sigue con 5. Los demás tests de `src/simulator` siguen en verde.

- [ ] **Step 6: Suite completa, typecheck, lint y build**

Run: `cd src/frontend && npm test && npm run typecheck && npm run lint && npm run build`
Expected: todo en PASS, sin errores.

- [ ] **Step 7: Commit**

```bash
git add -A src/frontend/src
git commit -m "feat(simulator): interactive oval table replaces the scenario form"
```

---

### Task 8: Recorrida visual y verificación completa

**Files:**
- Modify: `src/frontend/src/simulator/table.css` y `simulator.css`, solo si la recorrida encuentra defectos

- [ ] **Step 1: Levantar la app con una carpeta de datos aparte**

La base del usuario (`var/`) **no se toca**. Desde la raíz del repo:

```powershell
$env:POKER_DATA_DIR = "$env:TEMP\pokker-review"
scripts\dev.ps1
```

Si la carpeta temporal está vacía, importá `tests/fixtures/ranges/preflop-review.json` desde Preflop. Así hay rangos para "Abrir en Simulador" y para "Prellenar desde tablas".

- [ ] **Step 2: Recorrida contra el mockup `4-simulador-mesa.html`, a 1280 px y a 1024 px**

- **Mesa:** el paño ovalado tiene la baranda. Hay 6 asientos (9 al cambiar a 9-max), vos abajo al centro y la ficha D junto al BTN.
- **Asientos:** tocar un asiento abre su popover. "Rival" muestra la apuesta, el stack, el rango y las cartas. ⅓, ½, ⅔ y Pot calculan sobre el total. Las fichas aparecen entre el asiento y el centro.
- **Ejemplo del mockup:** BB contra CO y BTN, con 4 bb cada uno en el flop K♥7♣2♦. El total da 14,5. Analizar envía la acción previa "CO bet 4, BTN call 4".
- **Cambiar** a 9-max: se redibujan los asientos y los datos de las posiciones que siguen existiendo se conservan.
- **Calle:** las casillas del board se habilitan según la calle. "Todo al azar" en turn llena 4 cartas.
- **Opciones avanzadas:** en torneos aparecen los premios. Con 1 rival y flop, aparecen los campos del solver y "Prellenar desde tablas".
- **Persistencia:** al recargar, la mesa vuelve como estaba.
- **Abrir en Simulador** desde Preflop: llega con tu posición y el rival de ese rango, en preflop.
- **A 1024 px con el menú plegado:** los resultados bajan debajo de la mesa y no hay desborde horizontal de la página. La mesa puede desplazarse dentro de su columna.

Cada defecto se corrige en el CSS de la mesa, o con un test que falle primero si es de lógica, y se anota en el commit.

- [ ] **Step 3: Suite completa del repo, paquete y e2e del launcher**

Desde la raíz del repo, en el dev shell de MSVC, con POKKER cerrado:

```powershell
scripts\test.ps1
scripts\package.ps1 -SkipTests
scripts\test.ps1 launcher
```

Expected:
- core 31, backend 362 (más 1 skipped), integración 2;
- frontend con todos los tests en PASS;
- el paquete se arma con la prueba de humo en OK;
- el e2e del launcher pasa sus 9 tests.

- [ ] **Step 4: Commit**

```bash
git add -A src/frontend/src
git commit -m "style(simulator): table polish after the visual review"
```

Si no hubo cambios, este paso no aplica.

---

## Self-review (hecho al escribir el plan)

- **Cobertura del spec §5:**
  - §5.1, barra superior (chip con Cambiar y popover de formato, jugadores y stack; calles): Task 7.
  - §5.1, la mesa (paño, N asientos, vos abajo, horario, dealer, pos/stack/rol, fichas): Tasks 1 y 4.
  - §5.1, el centro (pozo editable, total, board con `CardPicker`) y tus cartas con "Repartir": Tasks 4 y 7. El reparto conserva los dos botones actuales (desvío 2).
  - §5.1, el popover (rol con rotación, ⅓/½/⅔/Pot sobre el total, All-in sobre el stack, campo libre, stack, rango con `RangeEditor`, cartas opcionales): Tasks 1, 2 y 5. "Prellenar desde tablas" queda en los campos del solver, como hoy.
  - §5.1, panel derecho (los resultados actuales y Analizar dorado): Task 7.
  - §5.1, opciones avanzadas (ante, BB ante, ICM, rango de Hero, preset, tipo de pozo, agresor): Task 6 y `PostflopSolverFields` en la Task 7. Los "stacks por posición" ahora son el stack de cada asiento.
  - §5.2, estado y traducción: el `Seat` y el `TableState` del spec más `AdvancedOptions` (Task 1), `tableToScenario` (Task 2) y la persistencia con fallback (Tasks 3 y 7).
  - §5.3, validaciones: Task 2, más "tus dos cartas", que el Simulador ya exigía.
  - §4.3, lectura de los filtros de Preflop: Tasks 3 y 7.
- **Desvíos:** los 4 están explicados en Global Constraints.
- **Consistencia de nombres:**
  - `Seat`, `TableState`, `AdvancedOptions`, `DEFAULT_ADVANCED`, `newSeat`, `seatsFor`, `setRole`, `updateSeat`, `heroSeat`, `villainSeats`, `rotateFromHero` y `seatPoint` (Task 1) se usan igual en las Tasks 2 a 7.
  - `BOARD_CARDS`, `STREET_LABEL`, `streetFromBoard`, `boardForStreet`, `totalPot`, `presetBet`, `BetPreset`, `previousActionFrom`, `tableToScenario` y `validateTable` (Task 2) también.
  - Lo mismo `SIM_TABLE_KEY`, `defaultTable`, `tableFromInitial` e `isTableState` (Task 3), y `CardSlotRef` y `sameSlot` (Task 4).
  - El componente de la Task 6 se llama `AdvancedPanel`, y su archivo `AdvancedOptions.tsx`.
- **Review Focus:**
  1. Cambio de jugadores: Task 1, "moves the hero to BTN…".
  2. Stacks cortos: Task 2, "caps what you face…" y "a rival all-in for less…".
  3. Mesa guardada corrupta: Task 3 (`isTableState`) y Task 7 ("a corrupt stored table…").
  4. Escenario del replayer: Task 3, "rebuilds a replayer spot…".
  5. Cartas repetidas: Task 2, "rejects repeated cards…".
