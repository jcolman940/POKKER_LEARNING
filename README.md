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

## Configuración

Centralizada en `backend/app/config.py`. Toda opción se puede sobreescribir con
variables `POKER_*` o un archivo `.env` en `backend/`:

| Variable | Default | Uso |
|---|---|---|
| `POKER_DATA_DIR` | `./var` | Carpeta de datos locales (SQLite) |
| `POKER_DATABASE_URL` | `sqlite:///<data_dir>/poker.sqlite3` | URL de la base |
| `POKER_AUTO_MIGRATE` | `true` | Aplica migraciones al iniciar |
| `POKER_SOLVER_PATH` | — | Binario de TexasSolver (fase 5) |
| `POKER_UPDATE_FEED_URL` | — | Canal de actualizaciones (fase 7) |

La versión de la app se lee de `VERSION` y se expone en `GET /api/version`.

## Licencias

TexasSolver (AGPL) se usa solo como binario externo vía subprocess; su código no se incluye en este repo.
