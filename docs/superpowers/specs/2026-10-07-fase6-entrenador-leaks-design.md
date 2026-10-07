# Fase 6 — Entrenador y leak finder: diseño

Fecha: 2026-10-07 · Estado: aprobado por secciones, pendiente de revisión del documento.
Referencia: `SPEC.md` §6.8 y §7 (fase 6).

## 1. Objetivo y alcance

- **Entrenador:** spots de **push/fold MTT** y de **preflop desde las tablas del usuario**. El usuario elige una acción, se compara con la recomendación del sistema, se puntúa y los errores se repiten con repetición espaciada.
- **Leak finder:** compara las frecuencias reales del usuario (manos importadas) por posición y situación contra **sus tablas preflop** y contra **Nash push/fold** en torneos con stack corto. Marca desvíos significativos con muestra mínima configurable.

Fuera de alcance en esta fase:
- Spots postflop (solver) y spots tomados del historial propio en el entrenador. La tabla `hand_decisions` (§3) deja lista la base para el segundo.
- Referencias postflop para el leak finder (c-bet, fold to c-bet, WTSD…): no hay referencias calculadas y el SPEC prohíbe inventarlas.
- Capa conversacional con un modelo de lenguaje (ver §9, futuro).

## 2. Decisiones de base

- **Una sola fuente de verdad:** cada spot del entrenador es un `Scenario` (el mismo modelo del simulador) y la referencia sale de `recommend()` (fase 3). Entrenador, simulador y replayer aplican las mismas reglas: push/fold por Nash/ICM, tablas con la más cercana marcada "aproximado".
- **Puntaje:**
  - Push/fold: **pérdida de EV exacta**, `EV(mejor) − EV(elegida)` en bb (o en % del premio con ICM).
  - Tablas: **error de frecuencia** = `1 − frecuencia recomendada de la acción elegida` (fold = `1 − Σ` del resto), siempre marcado "aproximado".
- **Persistencia local:** todo en el SQLite del usuario; un solo usuario, sin cuentas.

## 3. Arquitectura

### 3.1 Backend

| Módulo | Responsabilidad |
|---|---|
| `app/domain/preflop.py` | Lógica compartida para deducir la situación preflop de un jugador a partir de las acciones (se extrae de `app/replay/service.py::_situation` sin cambiar su comportamiento). |
| `app/stats/decisions.py` | `HandRecord` → hasta **dos** decisiones preflop de Hero: la primera (RFI / vs open / squeeze / ciega vs ciega / vs all-in) y, si existe, la segunda (vs 3-bet tras abrir, vs 4-bet tras 3-betear). |
| Migración `0005` | Tabla `hand_decisions` y relleno para las manos ya importadas. |
| `app/leaks/finder.py` | Agregación, referencia, significancia, impacto y detalle por clase de mano. |
| `app/trainer/spots.py` | Generadores `pushfold` y `chart` → `TrainerSpot` (escenario, acciones ofrecidas, fuente, clave de tarjeta). |
| `app/trainer/scoring.py` | Pérdida y veredicto a partir de la salida de `recommend()`. |
| `app/trainer/srs.py` | Repetición espaciada (SM-2 simplificado) y selección del próximo spot. |
| Migración `0006` | Tablas `trainer_cards` y `trainer_attempts`. |
| `app/api/trainer.py`, `app/api/leaks.py` | Endpoints (§7). |

### 3.2 `hand_decisions`

Una fila por decisión: `hand_id` (FK a `hands`), `idx` (1 o 2), `game_format`, `table_size`, `position`, `situation`, `vs_position`, `hand_class`, `stack_bb` (efectivo), `action` (normalizada a `fold` / `limp` / `call` / `raise` / `3bet` / `4bet` / `5bet` / `allin`, las mismas claves de las tablas), y para push/fold los stacks de la mesa y antes necesarios para resolver el Nash (`spot_json`). Se llena al importar; manos sin Hero o incompletas se saltean.

### 3.3 Frontend

- Pestaña **"Entrenador"** (reemplaza el placeholder de fase 6).
- Subsección **"Leaks"** dentro de **Estadísticas**, con sus filtros.

## 4. Entrenador: generación de spots

### 4.1 Push/fold (MTT)

- Mesa de 9, 6, 3 o 2 jugadores; stack de Hero entre 3 y 15bb; resto entre 5 y 40bb; BB ante de 1bb por defecto.
- Situación al azar: **foldean hasta Hero** (push/fold) o **le empujan** (call/fold contra el all-in de una posición anterior).
- Stacks tomados de un **pool fijo de ~12 configuraciones por tamaño de mesa**, resueltas una vez y cacheadas (un solve de 9 jugadores tarda ~4 s). El próximo spot se precalcula mientras el usuario responde.
- Premios: chip EV por defecto; opcional ICM con estructuras fijas (mesa final de 9, burbuja de SNG) → EV en % del premio.

### 4.2 Desde las tablas

- Se elige una tabla cargada al azar dentro de los filtros; posición, situación, rival y stack salen de la tabla.
- Acciones ofrecidas: fold + las acciones presentes en la tabla.
- Sin tablas cargadas: la fuente se deshabilita con el aviso "Cargá tablas en Rangos preflop".

### 4.3 Elección de la mano

- **50% manos de frontera:** en tablas, clases con frecuencia mixta o adyacentes al borde del rango; en push/fold, clases con `|EV(push) − EV(fold)| < 1bb`.
- **50% al azar**, ponderado por combos.

### 4.4 Puntaje y veredicto

| Fuente | Pérdida | Veredicto |
|---|---|---|
| Push/fold | `EV(mejor) − EV(elegida)` (exacta) | **Correcto** si ≤ 0,05bb (umbral "indiferente" de fase 3); **error** si no. |
| Tablas | `1 − freq(elegida)` ("aproximado") | **Correcto** si `freq ≥ 0,5` o es la más alta; **aceptable** si `0,1 ≤ freq < 0,5`; **error** si `< 0,1`. |

Feedback: acción de referencia vs. la elegida, barras de frecuencia de esa mano, EV o error, explicación de `recommend()` y grilla 13×13 con la mano marcada. **La recomendación nunca se envía al cliente antes de responder.**

## 5. Repetición espaciada y sesiones

### 5.1 Tarjeta

Clave: fuente + formato + posición + situación + rival + franja de stack + clase de mano. Franjas push/fold: 3–5, 6–8, 9–11, 12–15bb; en tablas, el stack de la tabla. Cada tarjeta guarda el último `Scenario`; al repasarla se reproduce con otro combo de la misma clase. Se crea al responder un spot nuevo.

### 5.2 Programación (SM-2 simplificado, dos niveles)

- **Dentro de la sesión:** un **error** vuelve entre 3 y 5 spots después; acertado ahí, pasa al nivel de días.
- **Entre sesiones:** `due_at`, `interval_days`, `ease` (inicial 2,5):
  - **Correcto:** 1 → 3 días → `intervalo × ease`.
  - **Aceptable:** intervalo igual; `ease − 0,05`.
  - **Error:** intervalo 0, `ease − 0,2` (mínimo 1,3) y vuelve a la cola de la sesión.

### 5.3 Selección del próximo spot (dentro de los filtros)

1. Error de la sesión cuyo turno llegó.
2. Tarjetas vencidas (`due_at ≤ ahora`), la más atrasada primero, mezcladas ~70% repaso / 30% nuevas.
3. Spot nuevo de los generadores.

### 5.4 Intentos e historial

`trainer_attempts`: sesión, tarjeta, escenario, acción elegida, acción de referencia, pérdida, veredicto, fuente, aproximado, fecha. El resumen de sesión se calcula: spots, correctos / aceptables / errores, pérdida total en bb (push/fold) y error de frecuencia promedio (tablas). "Tus errores frecuentes": top 10 tarjetas por errores, con "Entrenar solo estas". Modos: normal, "Solo repaso", "Solo mis errores frecuentes".

## 6. Leak finder

### 6.1 Referencia por decisión

- **Tablas:** la más cercana (`find_chart`); si no es exacta, el desvío se marca "aproximado" con las diferencias.
- **Push/fold:** torneo, stack efectivo ≤ `POKER_PUSHFOLD_MAX_BB` (15) y situación RFI o vs all-in → Nash con los stacks reales y antes de la mano, en **chip EV** (el historial no trae la estructura de premios), aclarado en la UI.
- **Frecuencia esperada por clase de mano** de cada decisión real, no del rango completo, para no fabricar leaks por la distribución de cartas recibidas.

### 6.2 Agrupación y significancia

- Grupo: formato + tamaño de mesa + posición + situación + rival + franja de stack.
- Por acción: frecuencia observada vs. promedio de las esperadas, con n e intervalo de Wilson 95%.
- **Leak** si: `n ≥ POKER_LEAKS_MIN_SAMPLE` (50, configurable) **y** lo esperado cae fuera del IC de lo observado **y** `|diferencia| ≥ 5` puntos. Bajo la muestra mínima: "muestra insuficiente".

### 6.3 Impacto y orden

- Push/fold: **pérdida real de EV** (`Σ EV(mejor) − EV(hecha)`) en bb/100 manos (exacta).
- Tablas: `|diferencia| × frecuencia del spot` ("aproximado").
- Orden por impacto descendente.

### 6.4 Detalle

Texto ("Abrís 18% desde BTN; tu tabla abre 45% (n=230, IC 15–23%)"), las clases que más contribuyen, grilla 13×13 por desvío y botón **"Entrenar este spot"** (abre el entrenador filtrado, vencidas primero).

### 6.5 Casos borde

Sin manos: "Importá historiales para ver tus leaks (los parsers de GG/PS llegan con tus archivos)". Sin tablas: solo push/fold, con aviso. Filtros iguales a Estadísticas.

## 7. API

- `GET /api/trainer/sources` → fuentes disponibles y motivo si alguna no lo está.
- `POST /api/trainer/sessions` → crea sesión (filtros, fuentes, modo).
- `POST /api/trainer/sessions/{id}/next` → próximo spot (sin la referencia).
- `POST /api/trainer/spots/{spot_id}/answer` → puntaje y feedback; **idempotente** por `spot_id`.
- `GET /api/trainer/sessions/{id}` → resumen; `GET /api/trainer/frequent-errors`.
- `GET /api/leaks` (filtros de Estadísticas) → lista ordenada; `GET /api/leaks/{group_key}` → detalle.

## 8. UI y errores

- **Entrenador:** fuentes, filtros y modo arriba; spot al centro (mesa compacta, cartas grandes, botones de acción); atajos **F** fold, **C** call, **R** raise/push, **1–9** por botón, **Enter** siguiente; resumen de sesión y errores frecuentes al costado; en móvil, botones fijos abajo.
- **Leaks:** tabla ordenada por impacto (spot, observado vs esperado con IC, n, impacto, aproximado); fila expandible con detalle.

| Caso | Comportamiento |
|---|---|
| Fuente "tablas" sin tablas | Deshabilitada con aviso; si es la única, mensaje en lugar del spot. |
| Ningún spot cumple los filtros | "No hay spots para estos filtros" + limpiar filtros. |
| Solve push/fold lento | Precálculo del siguiente; si aún tarda, "preparando spot…". |
| Tabla de una tarjeta editada o borrada | Se regenera con la tabla actual; si ya no existe, la tarjeta se archiva. |
| Respuesta duplicada | Idempotente por `spot_id`. |
| Manos sin Hero o incompletas | No generan decisiones. |

Configuración nueva: `POKER_LEAKS_MIN_SAMPLE` (50).

## 9. Futuro (fuera de alcance): capa conversacional

Un modelo de lenguaje como **explicador**, nunca como fuente de las decisiones (no calcula equity ni EV y puede equivocarse con convicción):
- explicaciones conversacionales de un spot, armadas con los datos estructurados reales (frecuencias, EV, rangos, blockers);
- revisión de sesión y plan de estudio a partir de los leaks;
- preguntas de concepto.

Condiciones: decidir modelo local (respeta local-first, explica peor) vs. en la nube (mejor, pero las manos salen de la PC, costo por uso, requiere internet); siempre post-sesión, sin asistencia en tiempo real. El diseño de esta fase ya expone feedback y leaks como datos estructurados, que es lo que esa capa necesitaría.

## 10. Tests

- `hand_decisions`: manos sintéticas de la sala falsa (RFI, vs open, open + fold a 3-bet, squeeze, ciega vs ciega, vs all-in) y relleno de la migración.
- Puntaje: pérdida de EV contra push/fold ya validado (Nash HU publicado a 10bb); error de frecuencia con tablas de test.
- Repetición espaciada: reglas de intervalo/ease, piso de ease, orden de selección y mezcla 70/30.
- Leak finder: manos sintéticas con un leak conocido (abrir 10% desde BTN vs tabla de 45%), IC de Wilson, muestra mínima, esperada por clase, impacto de push/fold en bb/100.
- API: ciclo de sesión, ocultamiento de la referencia antes de responder, idempotencia.
- Frontend (vitest): atajos, ocultamiento de la referencia, feedback, tabla de leaks, puente "Entrenar este spot".
- Manual en navegador: sesión push/fold, sesión desde tablas y leaks con manos sintéticas.

Al terminar la fase: parar, resumir y esperar confirmación (`SPEC.md` §8).
