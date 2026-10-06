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

- CMake ≥ 3.20, compilador C++20 (GCC 13 / Clang 16 / MSVC 2022), Ninja
- Python 3.12 + [uv](https://docs.astral.sh/uv/)
- Node.js ≥ 20

## Uso

```bash
make setup     # instala dependencias (uv compila el núcleo C++ como paquete Python)
make dev       # backend en :8000 y frontend en :5173
make test      # core (ctest) + backend (ruff, pytest) + frontend (tsc, oxlint, vitest) + integración
make migrate   # aplica migraciones Alembic
```

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
