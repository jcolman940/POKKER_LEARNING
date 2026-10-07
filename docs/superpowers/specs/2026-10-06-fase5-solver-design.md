# Fase 5 — Integración de TexasSolver: diseño

Fecha: 2026-10-06 · Estado: aprobado por secciones, pendiente de revisión del documento.
Referencia: `SPEC.md` §6.4 (fuentes 3 y 4) y §7 (fase 5).

## 1. Objetivo y alcance

- Recomendación **postflop heads-up** con TexasSolver (binario externo, AGPL, nunca vendorizado).
- **Caché** de resultados en SQLite por hash del spot.
- **Cola de solves** persistente (a pedido, en lote y biblioteca) con un worker dentro del backend.
- **Biblioteca** de spots comunes (MTT y cash) que se resuelve desde las tablas preflop del usuario.
- **Heurística multiway** (3+ jugadores postflop), siempre marcada como "aproximado".

Fuera de alcance en esta fase:
- Raises y re-raises dentro de una calle: solo la **primera decisión de Hero en la calle** (misma convención del simulador: Hero no invirtió antes en la calle).
- Rake en el árbol del solver.
- EV por acción del solver: la versión de consola v0.2.0 no lo devuelve.

## 2. Hechos verificados del binario (TexasSolver v0.2.0, Windows)

Obtenidos corriendo el binario real el 2026-10-06; el código se escribe contra esto, no de memoria.

- Release: `TexasSolver-v0.2.0-Windows.zip` (39,5 MB, SHA-256 `0A9122FA0CD9384E6C1CBE0492E8A3B8AC7809890C649E1A53F77A59D6D50A7C`). Última versión publicada (nov. 2021).
- Ejecutable de consola: `console_solver.exe --input_file <cmds.txt> --resource_dir <dir>/resources --mode holdem`.
- Entrada: archivo de comandos (`set_pot`, `set_effective_stack`, `set_board Qs,Jh,2h`, `set_range_oop`/`set_range_ip` con pesos `AA:0.5`, `set_bet_sizes <oop|ip>,<flop|turn|river>,<bet|raise|donk|allin>[,sizes…]`, `set_allin_threshold`, `set_raise_limit`, `build_tree`, `set_thread_num`, `set_accuracy`, `set_max_iteration`, `set_print_interval`, `set_use_isomorphism`, `start_solve`, `set_dump_rounds`, `dump_result <archivo>`).
- Progreso: escribe `tmp_log.txt` en el directorio de trabajo, una línea JSON por intervalo: `{"exploitibility": …, "iteration": …, "time_ms": …}`.
- Salida JSON: árbol de nodos `action_node` (`player`, `actions`, `strategy.strategy` = combo → lista de frecuencias alineada con `actions`, `childrens`) y `chance_node` (`dealcards`).
  - **`player 1` = OOP, `player 0` = IP.**
  - Los montos de acción vienen **redondeados a enteros** en fichas (`BET 7.000000` para 33% de 20) → se escala ×100.
  - La estrategia está por **combo exacto** (`"7h6h"`); no hay EV en la salida.
  - **Los rangos de entrada solo aceptan clases** (`AKs`, `KJo:0.5`): un combo puntual (`AcKc`) aborta con `range str AcKc len not valid` y código 3. Los rangos se convierten a peso promedio por clase; si un rango tenía pesos distintos dentro de una clase, el resultado se marca "aproximado".
- Tiempos medidos (6 núcleos): turn chico 1,4 s de solve + ~17 s de arranque fijo; flop con rangos realistas ~107 s de solve, 121 s total, explotabilidad 0,49% del pote. `dump_rounds 1` (solo la calle actual) deja el flop en ~177 KB; `dump_rounds 2` en turn ~6,6 MB.

## 3. Arquitectura

### 3.1 Módulos nuevos — `backend/app/solver/`

| Módulo | Responsabilidad |
|---|---|
| `spot.py` | `SolverSpot` normalizado (rangos OOP/IP, board, pote, stack efectivo, preset de árbol, tamaño enfrentado opcional). `spot_hash()`: SHA-256 de la forma canónica (rangos normalizados, board ordenado, montos redondeados a 0,01 bb, preset completo, versión del solver, precisión). |
| `trees.py` | Carga y valida los presets de `data/solver/trees.json`. |
| `config_gen.py` | `SolverSpot` → archivo de comandos, con fichas ×100. |
| `runner.py` | Lanza el subprocess en `var/solver/jobs/<id>/`, lee `tmp_log.txt` para el progreso, cancela y aplica timeout matando el árbol (`taskkill /T /F`). |
| `output_parser.py` | JSON del solver → árbol propio compacto (jugador como `oop`/`ip`, acciones en bb, estrategia por combo). Corrige la numeración de jugadores y desescala. |
| `cache.py` | Tabla `solver_results`; lectura y escritura del árbol comprimido (zlib). |
| `queue.py` | Tabla `solver_jobs`, encolado con deduplicación y prioridades, worker en un thread. |
| `library.py` | Familias de spots desde `data/solver/library.json`, subconjunto de flops, encolado desde las tablas y estado de cada entrada. |

### 3.2 Fuentes nuevas — `backend/app/recommend/`

- `postflop_solver.py`: `Scenario` → `SolverSpot`; caché hit → `RecommendationOut(source="solver")`; miss → encola con prioridad 0 y devuelve pendiente con `job_id`.
- `postflop_heuristic.py`: 3+ jugadores postflop → `RecommendationOut(source="heuristic", confidence="approximate")`.
- `ranges_prefill.py`: rangos de Hero y rival desde las tablas preflop.

### 3.3 Cambios en código existente

- `Scenario`: campos `hero_range: str | None`, `ranges_approximate: bool` (lo marca la UI si los rangos salieron de tablas aproximadas) y `solver_preset: str`. El tipo de pote solo lo usa el pedido de prellenado, no el `Scenario`. Quién está en posición se deduce de las posiciones (orden postflop).
- `RecommendationOut`: campo opcional `pending_job` (id, estado, progreso) y `strategy_grid` (169 clases → mezcla de acciones) para la UI.
- `recommend()`: postflop deriva a solver (HU) o heurística (multiway) en lugar del mensaje "fase 5".
- `config.py`: `POKER_SOLVER_PATH` (ya existe), `POKER_SOLVER_THREADS` (default: núcleos), `POKER_SOLVER_TIMEOUT_MIN` (30), umbrales de la heurística.
- `main.py`: router `/api/solver`; el `lifespan` arranca y detiene el worker.
- Migración Alembic `0004_solver`: `solver_results`, `solver_jobs`. La pausa de la cola se guarda en `app_meta`.

### 3.4 Flujo en el simulador (HU, postflop)

`POST /api/simulator/analyze` → `recommend()` → `SolverSpot` + hash →
- en caché: recomendación inmediata;
- no en caché: encola (o reutiliza el trabajo con el mismo hash, subiéndole la prioridad) y responde `available=false` + `pending_job`. La UI consulta `GET /api/solver/jobs/{id}` y repite el análisis al terminar.

## 4. Árboles de apuesta

Presets en `data/solver/trees.json` (editables como archivo; la UI los elige con un selector). Tamaños en % del pote.

| Preset | Flop | Turn | River |
|---|---|---|---|
| `simple` (default) | bet 33/75, raise 60 | bet 50/100, raise 60 | bet 50/100, raise 60 |
| `chico` | bet 33, raise 60 | bet 66, raise 60 | bet 75, raise 60 |
| `amplio` | bet 25/50/100, raise 50/100 | bet 33/75/125, raise 60 | bet 33/75/125, raise 60 |

Comunes: all-in en todas las calles, `allin_threshold` 0,67, `raise_limit` 3, sin donk bets, `accuracy` 0,5 (% del pote), `max_iteration` 200, `use_isomorphism` 1, `dump_rounds` 1. El preset completo entra en el hash.

### 4.1 Nodo de Hero

| Hero | `to_call` | Nodo |
|---|---|---|
| OOP | 0 | raíz |
| IP | 0 | raíz → `CHECK` |
| IP | > 0 | raíz → `BET x` (OOP apostó) |
| OOP | > 0 | raíz → `CHECK` → `BET x` (IP apostó) |

El tamaño enfrentado `x = to_call / (pot − to_call)` se **agrega exacto** al árbol del rival en esa calle (no se aproxima al tamaño más cercano).

### 4.2 Prellenado de rangos (`POST /api/solver/prefill-ranges`)

- SRP: el que abre → `raise` de la tabla RFI de su posición; el que paga → `call` de la tabla vs_open.
- 3-bet pot: el que 3-betea → `3bet` de vs_open; el que paga → `call` de vs_3bet.
- Se usa `find_chart` (tabla más cercana, con diferencias, marcada "aproximado"). Sin tabla → campo vacío y aviso.
- `confidence = exact` solo si ambos rangos vienen de tablas exactas o los cargó el usuario; si no, `approximate`.

### 4.3 Salida

Frecuencias del combo exacto de Hero, estrategia agregada y grilla 13×13 del rango de Hero en el nodo, explotabilidad lograda, preset, aviso "solo primera decisión de la calle". La explicación (valor / bluff / blockers / protección) reutiliza la heurística propia de fase 3 aplicada a la acción elegida por el solver.

## 5. Caché, cola y biblioteca

### 5.1 `solver_results`

`hash` (PK), `spot_json`, `tree` (JSON comprimido, solo la calle actual), `exploitability`, `iterations`, `solve_seconds`, `solver_version`, `preset`, `created_at`. Sin expiración. Borrado individual y vaciado total desde la UI.

### 5.2 `solver_jobs`

`id`, `spot_hash`, `spot_json`, `origin` (`simulator` / `batch` / `library`), `priority` (0 / 10 / 20), `status` (`queued` / `running` / `done` / `failed` / `cancelled`), `iteration`, `exploitability`, `error`, `pid`, `created_at`, `started_at`, `finished_at`.

- Orden: prioridad ascendente, luego antigüedad.
- Deduplicación: si el hash ya está en `queued`/`running`, se reutiliza el trabajo; un pedido más urgente sube su prioridad.
- **Desalojo**: si llega un trabajo de prioridad 0 mientras corre uno de prioridad mayor, el que corre se mata y vuelve a `queued`.
- Worker: un thread, un trabajo por vez; solo arranca si `POKER_SOLVER_PATH` es válido.
- Pausa y reanudación de la cola (persistida en `app_meta`), cancelación y reintento por trabajo.
- Al arrancar: trabajos `running` → `queued`; si el PID guardado sigue vivo y es `console_solver.exe`, se mata.

### 5.3 Lotes

`POST /api/solver/batch`: una línea (posiciones, tipo de pote, stack, formato, preset) más una lista de flops explícita o el subconjunto estándar. Prioridad 10.

### 5.4 Biblioteca

Familias en `data/solver/library.json`:
- **MTT 25 y 40 bb**: BTN vs BB, CO vs BB, SB vs BB (SRP); BB vs BTN 3-bet pot a 40 bb.
- **Cash 6-max 100 bb**: BTN vs BB, CO vs BB, SB vs BB (SRP); SB vs BTN 3-bet pot.

Flops: subconjunto fijo de **25 flops** elegido por un algoritmo reproducible que cubre texturas (alto/medio/bajo, monótono/dos palos/arcoíris, pareado, conectado). 11 líneas (7 MTT + 4 cash) × 25 flops = 275 solves (~9 h con `simple`, ~3,5 h con `chico`); se encola por familia. Prioridad 20.

- Rangos desde las tablas del usuario al encolar; el pote sale del sizing y el ante de esas tablas.
- Línea sin tabla → "falta tabla: <posición> <situación> <stack> (<formato>)", no se encola. No se inventan rangos.
- Si una tabla cambia, cambia el hash: las entradas viejas se muestran "desactualizadas" con opción de volver a encolar.

## 6. UI

### 6.1 Simulador (postflop)

- Campo "Rango de Hero" (`RangeEditor`), botón "Prellenar desde tablas" con selector de tipo de pote (SRP / 3-bet), etiqueta "aproximado" con diferencias.
- Selector de preset.
- Panel de recomendación pendiente: progreso (iteración, explotabilidad, tiempo), posición en la cola, cancelar; se actualiza solo al terminar.
- Resultado: barras de frecuencia del combo de Hero, grilla 13×13 por mezcla de acciones, explotabilidad, preset, aviso de primera decisión.
- "Analizar este spot" del replayer funciona sin cambios.

### 6.2 Pestaña "Solver"

1. **Cola**: estado, progreso, origen, prioridad; pausar/reanudar cola; cancelar/reintentar.
2. **Biblioteca**: familias → líneas → flops con estado (resuelto / en cola / falta tabla / desactualizado); "Encolar familia", "Encolar línea", "Lote propio".
3. **Visor de estrategia**: navegación por el árbol de la calle, grilla 13×13 por nodo y mezcla agregada.
4. **Configuración**: solver detectado y versión, hilos, tamaño de la caché, vaciar caché.

## 7. Heurística multiway (3+ jugadores)

`source="heuristic"`, `confidence="approximate"` siempre. Entradas: equity de Hero contra todos los rangos (motor actual) y, por rival, la fracción del rango a la que Hero le gana.

- Sin apuesta enfrente:
  - **bet (valor)** si Hero le gana a ≥ 65% de *cada* rango;
  - **bet (semi-bluff)** con ≥ 8 outs y Hero último en actuar;
  - si no, **check**.
- Con apuesta enfrente: equity requerida por pot odds, ajustada por realización (÷0,85 si Hero queda OOP ante algún rival, ÷0,95 si cierra la acción):
  - **raise** si le gana a ≥ 80% de cada rango;
  - **call** si la equity alcanza la requerida;
  - si no, **fold**.
- A ±3 puntos de un umbral: mezcla 50/50 con aviso "cerca del umbral".
- Sin EV.
- Explicación: valor, protección (adelante pero con muchos outs rivales), bluff con draws/blockers.
- Los umbrales (65%, 80%, 0,85, 0,95, ±3) son heurísticas propias, configurables en `config.py`, citadas como "umbral heurístico".

## 8. Errores

| Caso | Comportamiento |
|---|---|
| Sin solver configurado o binario inexistente | Worker no arranca; recomendación HU: "configurá el solver"; la heurística multiway sigue disponible. |
| Rango vacío tras card removal | 422 antes de encolar, indicando qué rango. |
| Mano de Hero fuera de su rango | Se resuelve igual; se muestra el rango con aviso "tu mano no está en tu rango". |
| Salida con error o sin JSON | `failed` con las últimas líneas del log; reintentable. |
| Timeout | Se mata el árbol de procesos; `failed: timeout`. |
| JSON inesperado | `failed` con el error de parseo; se conserva la salida. |
| Reinicio del backend | `running` → `queued`; se mata el PID huérfano. |

Directorio de trabajo por trabajo: `var/solver/jobs/<id>/`; se borra al terminar bien; de los fallidos se conservan los últimos 5.

## 9. Tests

- **Fixtures reales**: 2–3 salidas del binario (river y turn chicos, `dump_rounds 1`) commiteadas en `backend/tests/fixtures/solver/` (datos de salida, no código AGPL).
- **Solver falso**: script Python que imita `console_solver.exe` (lee comandos, escribe `tmp_log.txt` progresivamente, copia un fixture; modos fallo / cuelgue / lento).
- Unitarios: `config_gen` contra archivo de referencia; estabilidad del hash; `output_parser` (numeración de jugadores, desescalado, los 4 nodos de Hero); cola (deduplicación, prioridad, desalojo, cancelación, timeout, recuperación); heurística multiway con casos armados; biblioteca (25 flops reproducibles, tabla faltante, desactualizado); prellenado SRP y 3-bet.
- **Integración real** (marca `solver`): spot de river con el binario; se salta sin `POKER_SOLVER_PATH`. Se corre localmente y en el CI de Windows, bajando el zip con `actions/cache`.
- Frontend (vitest): estado pendiente con progreso, resultado con grilla, lista de la cola, navegación del visor.
- Manual en navegador: spot de turn de punta a punta y un trabajo de biblioteca.

Al terminar la fase: parar, resumir lo hecho y lo pendiente, y esperar confirmación (`SPEC.md` §8).
