# Fase 8: rediseño visual, Preflop y Simulador (diseño)

Fecha: 2026-10-10 · Estado: aprobado por secciones en el brainstorming, falta revisar el documento.
Mockups aprobados, en HTML estático: [`2026-10-10-rediseno-ui/`](2026-10-10-rediseno-ui/)
- `1-paleta.html`: se eligió la opción A, "Paño y oro".
- `2-navegacion.html`: se eligió la opción B, menú lateral agrupado.
- `3-preflop.html`: flujo de filtros al visor.
- `4-simulador-mesa.html`: la mesa.

## 1. Objetivo y decisiones

- **Objetivo:** que la app sea más estética y más fácil de entender, empezando por las dos secciones que más se usan para estudiar: **Preflop** y **Simulador**. Las referencias son las capturas que trajo el usuario: filtros en tarjetas con radios, visor de charts con secuencia, posiciones, stack efectivo y matriz 13×13.
- **Estilo:** oscuro con identidad propia, "**Paño y oro**": verde de mesa profundo con dorado para lo activo. No se copia el negro y cian de las capturas.
- **Navegación:** menú lateral agrupado en **Estudiar** (Preflop, Simulador, Push/Fold, Entrenador) y **Analizar** (Manos, Estadísticas, Solver). Se puede plegar a solo íconos y recuerda el estado.
- **Cómo se construye:** CSS propio con tokens (variables) y componentes React chicos y reutilizables. **No se suman dependencias**: ni Tailwind ni librerías de componentes.
- **Solo frontend.** El backend, el motor y la API no cambian. Todo lo nuevo sale de endpoints que ya existen.
- **Se entrega en tres partes en orden** (§3, §4 y §5). Cada una va en su propia rama, con tests y CI en verde, y se mergea con el OK del usuario antes de empezar la siguiente.

**Fuera de alcance:**
- El rediseño propio de Entrenador, Estadísticas, Manos, Push/Fold y Solver. Toman el nuevo look por los tokens y componentes base, pero mantienen su distribución.
- Modo claro.
- Versión para celular. El objetivo es escritorio, desde 1280 px de ancho; a 1024 px se usa con el menú plegado.
- Animaciones más allá de transiciones simples (hover, despliegue del popup).

## 2. Sistema visual (compartido)

### 2.1 Tokens

Van en `src/frontend/src/styles/tokens.css`, como variables en `:root`. Los valores salen del mockup `1-paleta.html` (opción A).

| Token | Valor | Uso |
|---|---|---|
| `--bg` | `#0d1a14` | fondo de la app |
| `--bg-deep` | `#0a140f` | menú lateral, barras |
| `--surface` | `#13261c` | tarjetas, paneles |
| `--surface-2` | `#1c3527` | ítem activo del menú, hover |
| `--line` | `#1f3a2b` | separadores |
| `--line-strong` | `#2c4a39` | bordes de controles |
| `--text` | `#e8efe9` | texto principal |
| `--text-muted` | `#8fa898` | etiquetas, texto secundario |
| `--text-dim` | `#4d6b58` | deshabilitado, títulos de grupo |
| `--gold` | `#d9b45a` | acento: activo, botón principal, selección |
| `--gold-ink` | `#1a1406` | texto sobre dorado |
| `--felt` / `--felt-edge` / `--rail` | `#1f6b45` / `#0f3d28` / `#3a2a16` | mesa del simulador |
| `--danger` | `#c2524a` | errores, rival, all-in |
| `--ok` | `#2f9e63` | éxito |

**Colores por acción** (`--action-*`). Los usa `RangeMatrix`, que ya pinta con `var(--action-<acción>)`:

| Acción | Color |
|---|---|
| raise | `#2f9e63` |
| limp | `#7fb69a` |
| call | `#4a8fd1` |
| 3bet | `#9b6bd6` |
| 4bet | `#d07a3a` |
| 5bet | `#b8543d` |
| allin | `#c2524a` |
| fold y celda vacía (`--grid-empty`) | `#1a2e23` |

Las acciones de postflop (`check`, `bet`) conservan sus variables actuales, reajustadas para que contrasten con la paleta. Todo par de color de texto sobre fondo debe dar un contraste de al menos 4,5:1 en texto normal.

**Tipografía:** pila del sistema (`'Segoe UI', system-ui, sans-serif`), sin fuentes externas, para que funcione offline. Los títulos de sección son de 20 a 22 px en peso 800. Las etiquetas van en MAYÚSCULAS, a 10 u 11 px, con espaciado de letras de 0,1em.

**Espaciado y radios:** escala de 4, 8, 12, 16, 24 y 32 px. Radios de 6 px en controles, 10 px en tarjetas y 12 px en contenedores grandes.

### 2.2 Componentes base

Van en `src/frontend/src/ui/`. Cada uno tiene una sola responsabilidad y estilos en su propio archivo CSS.

| Componente | Qué es |
|---|---|
| `Button` | Variantes `primary` (dorado), `secondary` (superficie) y `ghost`, con tamaño `sm` o `md` y estado `disabled`. |
| `Card` | Tarjeta con título opcional en MAYÚSCULAS. |
| `RadioList` | Lista de opciones con radio a la derecha y un contador opcional en gris (las tarjetas de filtros). Las opciones con contador 0 se ven apagadas pero se pueden elegir. Se navega con las flechas del teclado. |
| `PillGroup` | Botones de selección única en fila (posiciones, calles). Admite opciones apagadas. |
| `SegmentList` | Lista vertical de selección única (la secuencia de Preflop). |
| `Chip` | Resumen de filtros con la acción "Cambiar". |
| `Popover` | Panel flotante anclado a un elemento. Se cierra con Esc o con un clic afuera, y devuelve el foco al ancla. |
| `Select` | El `<select>` nativo con el estilo de la app. |
| `Stat` | Número grande con una etiqueta (equity, % del rango). |

Los botones e inputs actuales que no se migren a estos componentes toman el estilo a través de selectores base en `styles/base.css`.

### 2.3 Estructura de la app y menú lateral

- `App.tsx` pasa de pestañas arriba a un layout `Sidebar` más contenido.
- `Sidebar`:
  - Logo "♠ POKKER" con un botón « / » que pliega y despliega el menú. Desplegado mide unos 170 px; plegado, unos 48 px y muestra solo íconos con tooltip.
  - Grupos "Estudiar" y "Analizar".
  - El indicador de estado del servidor o de la app, que hoy está en la barra, va abajo de todo.
- El estado plegado se guarda en `localStorage` (`pokker.sidebar.collapsed`), dentro de un try/catch. Si falla, el menú arranca desplegado.
- Las secciones que hoy salen marcadas "fase N" siguen igual de deshabilitadas dentro del menú.
- El `index.css` actual (1135 líneas) se parte así:
  - `styles/tokens.css` y `styles/base.css`: reset, tipografía y controles base.
  - Un CSS por sección, junto a su página: `ranges/preflop.css`, `simulator/table.css`, etc.
  - Los estilos que quedan sin uso se borran.

## 3. Parte 1: base visual

Alcance: §2 completo.
- Todas las secciones existentes se ven con la paleta nueva y el menú lateral, **sin cambiar su comportamiento**.
- La migración a los componentes base en las secciones viejas es mínima: botones primarios y paneles a `Button` y `Card` donde sea directo. El resto se ajusta con CSS.

**Hecho cuando:**
- Las 8 secciones se ven coherentes con el mockup.
- El menú se pliega y recuerda su estado.
- Los tests actuales pasan; solo se ajustan los que dependían del markup de las pestañas.

## 4. Parte 2: Preflop

Reemplaza a la página actual de rangos (`ranges/ChartsPage.tsx`). El nombre de la sección pasa a ser **Preflop**.

### 4.1 Paso 1: filtros

Son cuatro tarjetas `RadioList`. Cada valor muestra entre paréntesis la cantidad de rangos que tiene:

| Tarjeta | Campo | Opciones |
|---|---|---|
| **Juego** | `game_format` | Cash, Torneos (mtt), Sit & Go (sng), Spin & Go (spin). Siempre se muestran las 4. |
| **Fuente** | `source` | Todas, más las fuentes presentes. |
| **Stake / rake** | `rake` | Todos, más los valores presentes. Los rangos sin `rake` cuentan solo en "Todos". |
| **Jugadores** | `players` | Los valores presentes, como "N-max". Si no hay ninguno, 6-max y 9-max. |

Los contadores de cada tarjeta tienen en cuenta lo elegido en las demás. Por ejemplo, con Cash elegido, Jugadores cuenta solo los rangos de cash.

- **Aplicar** lleva al visor.
- Los filtros se guardan en `localStorage` (`pokker.preflop.filters`). Si existen, la sección abre directo en el visor; si no, abre en el paso 1.
- **Sin rangos cargados:** el paso 1 muestra un estado vacío que explica cómo cargar rangos e incluye los botones "Importar set (.json)" y "Crear rango".

### 4.2 Paso 2: visor

Sigue el mockup `3-preflop.html`.

**Barra superior**
- `Chip` con el resumen de filtros y "Cambiar", que vuelve al paso 1.
- Herramientas:
  - **Copiar rango:** copia el rango visible al portapapeles en notación de texto, una línea por acción.
  - **Editar:** abre el `ChartEditor` actual con el estilo nuevo.
  - **Nuevo:** abre el editor con el contexto ya cargado (formato, jugadores, posición, situación, stack).
  - **Importar / exportar:** abre un panel con las funciones de hoy: importar set, exportar todo, exportar propios y calculados, y la tabla completa de rangos con Editar y Borrar.

**Columna izquierda**
- **Secuencia:** `SegmentList` con las situaciones en orden: Open raise (RFI), vs open, vs 3-bet, vs 4-bet, Squeeze, Ciega vs ciega, vs all-in. Las que no tienen rangos con los filtros actuales se ven apagadas.
- **Stack efectivo:** `Select` con los `stack_bb` disponibles para filtros, secuencia y posición, ordenados.

**Centro**
- **Tu posición:** `PillGroup` con las posiciones de `GET /api/simulator/positions/{players}`. Si se eligieron varios valores de `players`, se usa el del filtro. Las posiciones sin rango se ven apagadas.
- **Rival:** segunda fila de botones con los `vs_position` presentes. Solo aparece en situaciones que tienen rival (todas menos RFI).
- **Leyenda:** cada acción presente con su color y el % de manos (con `pctOfHands`), más Fold con el resto. No hay una categoría "Mixto" aparte: el "Mixto" dorado del mockup era ilustrativo. Las manos mixtas se ven en la matriz como celdas partidas.
- **Matriz:** el `RangeMatrix` actual. Las celdas mixtas se ven partidas por color, como ya hace.

**Columna derecha**
- `Stat` con el % del rango jugado (todo lo que no es fold) y la cantidad de combos.
- Detalle de la mano bajo el mouse: las frecuencias de esa celda.
- Accesos a **"Abrir en Simulador"** y **"Entrenar este spot"**. El segundo abre el Entrenador con `InitialFilters`, por el mismo camino que usa hoy el leak finder (`setTrainer` en `App.tsx`). Le pasa `positions: [posición]`, `situations: [situación]` y `formats: [formato]`, más `sources: [fuente]` si la fuente no es "Todas".

**Selección automática**
- Al cambiar un control, los controles que siguen se reajustan al primer valor disponible.
- Cuando la combinación actual queda sin rango, se ve un estado vacío "No hay un rango para BTN · vs 3-bet · 100bb" con el botón "Crear este rango", que abre el editor con los datos ya cargados.

**Rangos repetidos**
- Si más de un rango coincide (por ejemplo, con "Todas las fuentes"), aparece un `Select` arriba de la matriz: "2 rangos: Pokalab · Propio". Por defecto se elige el más reciente (`updated_at`).

### 4.3 Datos

- Se cargan una vez con `GET /api/charts` (el mismo de hoy) y se recargan después de guardar, borrar o importar.
- El filtrado y los contadores se calculan en el cliente, con funciones puras en `ranges/preflopFilters.ts`. No se agregan endpoints.
- **Contrato con el Simulador:**
  - Los filtros elegidos (formato y jugadores) se comparten a través de `localStorage`, para que la mesa arranque con esa cantidad de asientos.
  - "Abrir en Simulador" usa el mecanismo `initial` / `spot` de `App.tsx` que ya usa el replayer. Pasa `format`, `num_players`, `hero_position`, `effective_stack_bb` y `situation`.

## 5. Parte 3: Simulador con mesa

Reemplaza el formulario de "Mesa", "Hero", "Board" y "Rivales" de `simulator/SimulatorPage.tsx` por una mesa interactiva. Sigue el mockup `4-simulador-mesa.html`.

### 5.1 Pantalla

**Barra superior**
- `Chip` con formato, jugadores y stack, más "Cambiar". Abre un popover chico con Formato, Jugadores y Stack efectivo por defecto.
- `PillGroup` de calles: Preflop, Flop, Turn y River.

**Mesa**
- Óvalo de paño con baranda, dibujado con CSS y sin imágenes. Tiene N asientos según los jugadores.
- **Vos siempre abajo al centro.** Los demás asientos siguen en sentido horario en orden de mesa, empezando por el que está a tu izquierda.
- Ficha de dealer junto al BTN.

**Cada asiento muestra:**
- posición;
- stack;
- etiqueta del rol: VOS (dorado), RIVAL (rojo), FOLD (apagado) o vacío;
- la apuesta de la calle como fichas con monto, entre el asiento y el centro.

**Centro de la mesa**
- **Pozo:** se edita con un clic. Es el pozo de calles anteriores; abajo se muestra el total con las apuestas actuales.
- **Board:** 5 espacios de carta. La calle elegida decide cuántos se usan. Al tocar un espacio se abre el `CardPicker` actual, que ya bloquea las cartas usadas.

**Tus cartas**
- Arriba de tu asiento, con el `CardPicker`.
- El botón "Repartir" completa al azar lo que falte, usando `POST /api/simulator/deal` como hoy.

**Popover del asiento** (al tocar un asiento)
- **Rol:** Vos, Rival, Fold o Vacío. Si elegís "Vos" en otro asiento, la mesa gira.
- **Apuesta:** atajos ⅓, ½, ⅔ y Pot sobre el pozo total actual, All-in sobre el stack, y un campo libre en bb.
- **Stack** en bb.
- **Rango** (solo rivales): se precarga desde las tablas con "Prellenar desde tablas", que ya existe. Muestra el nombre y el %, y deja ver o editar la matriz con el `RangeEditor` actual.
- **Cartas** (opcional): como hoy, la equity contra esa mano exacta sale aparte.

**Panel derecho**
- Los resultados actuales (`ResultsPanel`, `RecommendationPanel` y `PendingSolve`) con el estilo nuevo.
- Equity grande con barra, pot odds, equity requerida, MDF, SPR y outs.
- Recomendación con chips por acción y "por qué" desplegable.
- Botón dorado **Analizar**.

**Opciones avanzadas**
- Se despliegan debajo del panel: ante, BB ante, stacks por posición e ICM (payouts), rango de Hero, preset del solver, tipo de pozo (SRP o 3-bet) y agresor.
- Conservan los controles y el comportamiento de hoy.

### 5.2 Estado y traducción a la API

**Estado de la mesa**

```ts
interface Seat {
  position: string
  role: 'hero' | 'villain' | 'folded' | 'empty'
  bet_bb: number
  stack_bb: number
  range: string
  hand: string | null
}
interface TableState {
  format: GameFormat
  num_players: number
  street: Street
  seats: Seat[]
  pot_bb: number          // pozo de calles anteriores
  board: string
  hero_hand: string
  advanced: AdvancedOptions
}
```

**Traducción a la API**

Una función pura, `tableToScenario(table): ScenarioInput`, en `simulator/table.ts`, arma el mismo `ScenarioInput` que se manda hoy:

| Campo | Cómo se calcula |
|---|---|
| `hero_position` | la posición del asiento con rol `hero` |
| `villains` | los asientos con rol `villain`, en orden de mesa, con `{position, range, hand}` |
| `pot_bb` | `table.pot_bb` más la suma de todas las apuestas actuales (de todos los asientos, incluida la tuya) |
| `to_call_bb` | `max(0, apuesta más alta − tu apuesta)`, recortado a tu stack |
| `effective_stack_bb` | el mínimo entre tu stack y el mayor stack de los rivales |
| `stacks_bb` | el stack de cada asiento que no está vacío |
| `previous_action` | se arma de las apuestas. Ejemplo: "CO bet 4, BTN call 4". La mayor es "bet" (o "raise" en preflop) y las iguales a la mayor son "call". Si no hay apuestas, queda vacío. |
| `situation` | la que venga de Preflop o del modo avanzado; si no hay, `null` como hoy |

Los demás campos (`format`, `num_players`, `board`, `hero_hand`, `ante_bb`, `bb_ante_bb`, `payouts`, `hero_range`, `ranges_approximate` y `solver_preset`) pasan directo.

**Persistencia**
- La última mesa se guarda en `localStorage` (`pokker.simulator.table`), igual que los filtros.
- Si el valor guardado no se puede leer, se descarta y la mesa arranca por defecto: vos en BB, los demás en fold y pozo de 1,5 bb.

### 5.3 Validaciones

Se muestran sobre la mesa o en el popover, antes de llamar a la API. Si alguna falla, el botón **Analizar** queda deshabilitado con el motivo a la vista:

- tiene que haber exactamente un asiento "Vos" y al menos un rival;
- no puede haber cartas repetidas (el picker ya las bloquea);
- ninguna apuesta puede superar el stack del asiento;
- el board tiene que tener las cartas que pide la calle (3, 4 o 5), o quedar vacío si se va a usar "Repartir".

Los errores de la API se muestran en el panel derecho, como hoy.

## 6. Tests

- **Se adaptan los existentes:**
  - `ChartsPage.test.tsx` pasa a probar el Preflop nuevo.
  - `SimulatorPage.test.tsx` y `PostflopSolver.test.tsx` pasan a armar el escenario a través de la mesa.
- **Nuevos, unitarios (funciones puras):**
  - `tableToScenario`: pozo, a pagar con y sin tu apuesta, multiway, all-in recortado al stack, acción previa, asientos vacíos.
  - Rotación de asientos con vos abajo para 6 y 9 jugadores.
  - `preflopFilters`: contadores cruzados, opciones apagadas, autoselección en cascada, rangos repetidos y elección del más reciente.
- **Nuevos, de componentes:**
  - menú plegable que recuerda el estado (con `localStorage` simulado y también con `localStorage` que tira error);
  - `RadioList` y `PillGroup` con teclado;
  - `Popover` que se cierra con Esc y con clic afuera y devuelve el foco.
- **Flujo completo con la API simulada:**
  - Preflop: filtros, visor, "Abrir en Simulador".
  - Simulador: armar BB contra CO y BTN en el flop, analizar y verificar el `ScenarioInput` enviado.
- **Verificación manual al final de cada parte:** recorrer las pantallas en el navegador con datos reales en 1280 px y en 1024 px con el menú plegado. Además pasan la suite completa (`scripts\test.ps1`), `package.ps1` y el CI.

## 7. Riesgos

- **Que las secciones viejas queden raras con la paleta nueva.** Para eso la parte 1 se cierra recién cuando todas se ven bien, antes de pasar a la parte 2.
- **El tamaño de `SimulatorPage.tsx` (530 líneas).** Se divide en `TableView`, `SeatPopover`, `TableCenter`, `AdvancedOptions` y la lógica pura en `table.ts`, para que cada archivo tenga una sola responsabilidad.
- **Que la API cambie el formato del escenario.** No pasa: `ScenarioInput` no cambia y los tests de `tableToScenario` lo fijan.
