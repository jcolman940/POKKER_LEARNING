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

## Historiales, estadísticas y replayer (fase 4, en curso)

- **Importación** (`POST /api/imports`, pestaña *Historiales*): `.txt` y `.zip`, sala detectada por contenido
  (un parser por sala en `backend/app/parsers/`), idempotente por (sala, id de mano), tolerante a errores
  con reporte de archivo/mano/línea. **Los parsers de GGPoker y PokerStars se escriben contra archivos
  reales de muestra**: hasta tenerlos, ninguna sala está soportada.
- **Modelo normalizado** `HandRecord` (`backend/app/domain/hand.py`): lo producen los parsers y lo consumen
  estadísticas, replayer y (fase 6) entrenador.
- **Estadísticas** (`/api/stats`): VPIP, PFR, 3-bet, fold to 3-bet, c-bet flop/turn, fold to c-bet, WTSD, W$SD,
  AF/AFq, winrate y winrate all-in EV (bb/100), con muestra, IC 95% y aviso de muestra insuficiente
  (`POKER_STATS_MIN_SAMPLE`). Cortes por posición, mano, stack, mesa, formato y mes; gráfico de ganancias
  (total / con showdown / sin showdown / all-in EV). Torneos: ROI, ITM y chip EV cuando hay resultados.
- **Replayer** (`/api/hands/{id}/replay`): paso a paso con la equity de Hero contra los rangos asignados y
  el botón *Analizar este spot*, que abre el simulador con el escenario armado.

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
| `POKER_SOLVER_PATH` | — | Binario de TexasSolver (fase 5) |
| `POKER_UPDATE_FEED_URL` | — | Canal de actualizaciones (fase 7) |

La versión de la app se lee de `VERSION` y se expone en `GET /api/version`.

## Licencias

TexasSolver (AGPL) se usa solo como binario externo vía subprocess; su código no se incluye en este repo.
