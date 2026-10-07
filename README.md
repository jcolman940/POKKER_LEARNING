# POKKER_LEARNING — Poker Study Tool

Herramienta personal de estudio de poker (rangos, equity, EV), **local-first** y solo
para análisis post-sesión y práctica: sin HUD ni asistencia en tiempo real.
La especificación completa está en [`SPEC.md`](SPEC.md).

## Estructura

```
/core        C++20: evaluador, equity, bindings pybind11 (paquete Python `pokercore`)
/backend     FastAPI: app/{api,parsers,stats,recommend,solver,db}, Alembic
/frontend    React + TypeScript + Vite (UI en español)
/data        rangos preflop (JSON), spots precalculados
/tests       fixtures de historiales, tests de integración
/scripts     test.sh, dev.sh
VERSION      versión de la app (única fuente de verdad)
```

## Requisitos

Plataforma objetivo: **Windows** (CI en `windows-latest` con MSVC). En Linux/macOS también compila.

- Visual Studio 2022 con "Desarrollo para el escritorio con C++" (MSVC) y CMake ≥ 3.20
- Python 3.12 + [uv](https://docs.astral.sh/uv/)
- Node.js ≥ 20

## Uso (Windows, PowerShell)

```powershell
cd backend; uv sync; cd ..      # instala dependencias y compila el núcleo C++ como paquete Python
cd frontend; npm install; cd ..
scripts\dev.ps1                  # backend en :8000 y frontend en :5173
scripts\test.ps1                 # core (ctest) + backend (ruff, pytest) + frontend (tsc, oxlint, vitest) + integración
scripts\test.ps1 core backend    # solo algunas suites
scripts\bench.ps1                # benchmark del evaluador y de equity
```

En Linux/macOS: `make setup | dev | test | bench | migrate` (usa `scripts/*.sh`).

## Núcleo (`pokercore`)

```python
import pokercore

pokercore.evaluate("AsKsQsJsTs2c3d")             # valor comparable (mayor = mejor)
pokercore.range_combos("22+, A2s+, AKo:0.5", dead="Ah")
r = pokercore.equity(["AA", "KK"])                # mano o rango por jugador, 2 a 10 jugadores
r.players[0].equity, r.players[0].std_error, r.exact
pokercore.equity(["QQ+,AKs", "random", "T9s"], "Td7c2h", mode="monte_carlo", iterations=100_000, seed=1)
```

Notación de rangos: `AA`, `AKs`, `AKo`, `AK`, `22+`, `A2s+`, `KTo+`, `99-55`, `A5s-A2s`, `T9s-65s`,
combos puntuales (`AhKh`), `random`, y pesos estilo PioViewer (`AA:1.0,AKs:0.5`).

## Simulador (`/api/simulator`)

- `POST /api/simulator/analyze`: recibe un `Scenario` y devuelve equity **contra el rango** de cada rival
  (exacta o Monte Carlo con error estándar), outs, pot odds, equity requerida, MDF y SPR.
  Si se fija la mano puntual de un rival, esa equity sale aparte en `equity_vs_hands` (solo informativa).
- `POST /api/simulator/deal`: completa al azar las cartas que falten (Hero, board hasta la calle pedida,
  manos de rivales opcionales) respetando las fijadas.
- `GET /api/simulator/positions/{n}` y `POST /api/ranges/parse` (validación + grilla 13×13).

Convenciones: el pote incluye la apuesta que enfrenta Hero; MDF asume que Hero no invirtió antes en la calle;
SPR = stack efectivo / pote. Un *out* es una carta que pone a Hero por delante de al menos la mitad
del rango rival (contra todos los rivales en multiway).

## Recomendación preflop (fase 3)

- **Tablas** (`/api/charts`): rangos por formato, mesa, posición, stack y situación, editables desde
  *Rangos preflop* (matriz 13×13 con frecuencias mixtas, notación, `.txt` de PioViewer, import/export JSON;
  ver `data/ranges/README.md`). Si el escenario no coincide, se usa el rango más cercano marcado como
  *aproximado* y se listan las diferencias.
- **Push/fold Nash + ICM** (`/api/pushfold/solve`, pestaña *Push/fold*): mesa completa de 2 a 10 jugadores,
  fictitious play sobre las 169 manos, ICM Malmuth-Harville con los premios que se cargan a mano (vacío =
  chip EV). Modelo con un solo caller (sin overcalls). En el simulador se usa en torneos con stack efectivo
  ≤ `POKER_PUSHFOLD_MAX_BB` (15bb por defecto) y situación RFI o vs all-in.
- La equity preflop clase vs clase sale de `data/precomputed/preflop_equity_169.npy`
  (Monte Carlo, 100k manos por par; regenerable con `scripts/gen_preflop_equity.py`).

Salida común de la recomendación: acciones con frecuencia (y EV cuando la fuente lo da), fuente
(`chart` / `nash` / `solver` / `heuristic`), confianza (exacta / aproximada), explicación corta y avisos.

## Historiales, estadísticas y replayer (fase 4)

- **Importación** (`POST /api/imports`, pestaña *Historiales*): `.txt` y `.zip`, sala detectada por contenido
  (un parser por sala en `backend/app/parsers/`), idempotente por (sala, id de mano), tolerante a errores
  con reporte de archivo/mano/línea. **Los parsers de GGPoker y PokerStars se escriben contra archivos
  reales de muestra**: hasta tenerlos, ninguna sala está soportada.
- **Modelo normalizado** `HandRecord` (`backend/app/domain/hand.py`): lo producen los parsers y lo consumen
  estadísticas, replayer y entrenador/leak finder (fase 6).
- **Estadísticas** (`/api/stats`): VPIP, PFR, 3-bet, fold to 3-bet, c-bet flop/turn, fold to c-bet, WTSD, W$SD,
  AF/AFq, winrate y winrate all-in EV (bb/100), con muestra, IC 95% y aviso de muestra insuficiente
  (`POKER_STATS_MIN_SAMPLE`). Cortes por posición, mano, stack, mesa, formato y mes; gráfico de ganancias
  (total / con showdown / sin showdown / all-in EV). Torneos: ROI, ITM y chip EV cuando hay resultados.
- **Replayer** (`/api/hands/{id}/replay`): paso a paso con la equity de Hero contra los rangos asignados y
  el botón *Analizar este spot*, que abre el simulador con el escenario armado.

## Solver postflop (fase 5)

Integra [TexasSolver v0.2.0](https://github.com/bupticybee/TexasSolver/releases/tag/v0.2.0) como binario
externo (AGPL: solo se ejecuta por subprocess, su código no se incluye).

**Instalación.** Bajá el zip de Windows de la release (SHA-256
`0A9122FA0CD9384E6C1CBE0492E8A3B8AC7809890C649E1A53F77A59D6D50A7C`), descomprimilo y apuntá al
binario `console_solver.exe` (con su carpeta de recursos al lado). Por ejemplo, en `backend/.env`:

```
POKER_SOLVER_PATH=C:\tools\TexasSolver\TexasSolver-v0.2.0-Windows\console_solver.exe
```

o bien, en PowerShell: `$env:POKER_SOLVER_PATH = 'C:\...\console_solver.exe'`. *Solver → Configuración*
muestra la ruta detectada, la versión del solver, los hilos y el tamaño de la caché (con botón para
vaciarla).

**Árboles de apuestas.** Los presets están en `data/solver/trees.json`: `chico` (por defecto),
`simple` (para turn/river) y `amplio` (lento, mucha RAM). En el Simulador se elige el preset junto al
análisis.

**Cola y prioridades.** Todos los solves pasan por una cola persistente: simulador (0) > lote (10) >
biblioteca (20). Solo las peticiones del simulador interrumpen un solve en curso; la cola se puede pausar
y sobrevive a reinicios. Resultados cacheados: repetir un análisis responde al instante.

**Biblioteca** (`data/solver/library.json`). 11 líneas (7 de MTT a 25/40bb + 4 de cash 6-max 100bb) × 25
flops representativos = **275 solves** (con `chico`, para las líneas de 100bb, del orden de decenas de horas; las de MTT a 25/40bb son más
rápidas: encolá una línea por vez, de noche). Se arma solo a partir de
**tus propias tablas preflop** (si falta una, la línea queda como "falta tabla") y una entrada pasa a
"desactualizado" cuando cambia la tabla de origen. Los 25 flops se eligen para cubrir carta alta y textura
(sesgo a amplitud, no ponderado por frecuencia). Se encola por línea o completa desde *Solver → Biblioteca*.

**Tiempos medidos en esta PC (6 núcleos, 16 GB).** Turn/river: ~8-20 s. Un flop cash SRP de 100bb:
~10 min con `chico` (190 iteraciones, explotabilidad ~0,6 %). Con `simple` el mismo flop puede superar los
30 min (el timeout, `POKER_SOLVER_TIMEOUT_MIN`) y ~9 GB de RAM: usalo para turn/river o stacks cortos.
`amplio` puede no entrar en 16 GB en flops profundos.

**Multiway.** Con más de 2 jugadores no se usa el solver sino una heurística propia (equity vs rangos,
realización por posición, semi-bluffs por outs), siempre marcada "aproximado". Los umbrales son
configurables con `POKER_HEURISTIC_*` (ver tabla). Funciona sin el binario del solver.

**Interfaz.** El Simulador suma el rango de Hero, "Prellenar desde tablas" (arma los rangos de Hero y
rivales desde tus tablas), el selector de preset y el progreso del solve pendiente. La pestaña *Solver* tiene
*Cola*, *Biblioteca* (incluye "Lote propio"), visor de estrategia (grilla 13×13, acciones con tamaños,
borrado de un resultado de la caché) y *Configuración*. Si la cola está pausada, el simulador avisa que
hay que reanudarla en *Solver → Cola*.

**Limitaciones.**
- Solo la primera decisión de Hero en la calle (no raises posteriores dentro de la calle).
- Sin rake.
- Sin EV: TexasSolver v0.2.0 no lo entrega, así que el solver muestra frecuencias y explotabilidad.
- Los rangos se envían al solver por clase de mano; el resultado se marca "aproximado" solo
  cuando los pesos de una misma clase difieren entre combos (ahí se promedian).

## Entrenador y leak finder (fase 6)

**Entrenador.** Elegís una acción para un spot, se compara con la recomendación del sistema y se puntúa.
Fuentes:
- **Push/fold MTT** (Nash/ICM): EV exacto, en bb o en unidades ICM.
- **Preflop desde tus tablas**: error de frecuencia, siempre marcado "aproximado". Las tablas de MTT de stack
  corto que el sistema resuelve por push/fold quedan fuera de esta fuente.
- **"Pintá tu rango"**: pintás en la matriz 13×13 el rango de una tabla y acción; la precisión está
  ponderada por combos (correcto ≥ 90 %, aceptable ≥ 75 %).

**Veredictos.** Push/fold: correcto si la pérdida es ≤ 0,05 (umbral de indiferencia). Tablas: correcto si la
frecuencia de tu acción es ≥ 50 % o es la más alta; aceptable entre 10 % y 50 %; error si es < 10 %.
La referencia nunca se muestra antes de responder.

**Dificultad y premios.** La dificultad (0-100 %, por defecto 50) es la proporción de manos de frontera.
Hay dos estructuras de premios incluidas (Mesa final 9 y Burbuja SNG) y las tuyas, editables desde el
entrenador. Atajos: F/C/R para fold/call/raise, 1-9 por botón y Enter para seguir.

**Repetición espaciada** (SM-2 simplificado). Un error vuelve 3 a 5 spots después dentro de la sesión; un
acierto agranda el intervalo: 1 día, 3 días y luego × facilidad. Hay modo repaso y la lista "Tus errores
frecuentes", con el botón "Entrenar solo estas".

**Leak finder** (*Estadísticas → Leaks*). Compara tus decisiones preflop reales (hasta dos por mano: la
primera y la respuesta a un 3-bet/4-bet) con tus tablas (la más cercana, marcada "aproximado" con las
diferencias) y, en torneos con ≤ 15bb en RFI o vs all-in, con el Nash de push/fold en chip EV. Para cada
clase de mano se calcula la frecuencia esperada; es un leak si n ≥ `POKER_LEAKS_MIN_SAMPLE` (50), la
esperada queda fuera del IC 95 % de Wilson y |diferencia| ≥ 5 puntos. El impacto se estima en bb/100
(push/fold, pérdida de EV exacta) o pts/100 (tablas). "Entrenar este spot" abre el entrenador filtrado.
Necesita manos importadas (los parsers de GGPoker y PokerStars esperan archivos reales).

**Limitaciones.**
- Sin spots postflop ni spots de tu propio historial en el entrenador por ahora.
- Los leaks de push/fold se miden en chip EV, no en ICM.
- Racha y objetivo diario quedan para una actualización posterior; un explicador conversacional con LLM
  está anotado en el spec (fuera de alcance).

## Configuración

Centralizada en `backend/app/config.py`. Toda opción se puede sobreescribir con
variables `POKER_*` o un archivo `.env` en `backend/`:

| Variable | Default | Uso |
|---|---|---|
| `POKER_DATA_DIR` | `./var` | Carpeta de datos locales (SQLite) |
| `POKER_DATABASE_URL` | `sqlite:///<data_dir>/poker.sqlite3` | URL de la base |
| `POKER_AUTO_MIGRATE` | `true` | Aplica migraciones al iniciar |
| `POKER_PUSHFOLD_MAX_BB` | `15` | Stack efectivo máximo para usar push/fold en torneos |
| `POKER_HERO_NAMES` | `[]` | Nombres a usar como Hero si el archivo no lo indica (JSON) |
| `POKER_STATS_MIN_SAMPLE` | `100` | Muestra mínima antes de marcar una métrica como insuficiente |
| `POKER_SOLVER_PATH` | — | Ruta a `console_solver.exe` de TexasSolver v0.2.0 (ej. en `backend/.env`) |
| `POKER_SOLVER_THREADS` | núcleos de CPU | Hilos que usa el solver |
| `POKER_SOLVER_TIMEOUT_MIN` | `30` | Tiempo máximo por solve (minutos) |
| `POKER_HEURISTIC_VALUE_SHARE` | `0.65` | Heurística multiway: fracción mínima de cada rango rival a la que Hero le gana para apostar por valor |
| `POKER_HEURISTIC_RAISE_SHARE` | `0.80` | Heurística multiway: fracción mínima de cada rango rival a la que Hero le gana para subir |
| `POKER_HEURISTIC_SEMIBLUFF_OUTS` | `8` | Heurística multiway: outs mínimos para semi-bluff |
| `POKER_HEURISTIC_REALIZATION_OOP` | `0.85` | Heurística multiway: realización de equity fuera de posición |
| `POKER_HEURISTIC_REALIZATION_LAST` | `0.95` | Heurística multiway: factor de realización de equity en posición / última en hablar |
| `POKER_HEURISTIC_MARGIN` | `0.03` | Heurística multiway: margen alrededor de los umbrales para mezclar acciones |
| `POKER_LEAKS_MIN_SAMPLE` | `50` | Muestra mínima por spot para que el leak finder marque un leak |
| `POKER_UPDATE_FEED_URL` | — | Canal de actualizaciones (fase 7) |

La versión de la app se lee de `VERSION` y se expone en `GET /api/version`.

## Licencias

TexasSolver (AGPL) se usa solo como binario externo vía subprocess; su código no se incluye en este repo.
