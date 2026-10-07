# Fase 5 — Integración de TexasSolver: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recomendación postflop heads-up con TexasSolver (caché, cola persistente, lotes y biblioteca) y heurística multiway marcada como aproximada.

**Architecture:** Paquete `backend/app/solver/` con piezas chicas (presets, spot+hash, generador de comandos, runner de subprocess, parser del output, caché, cola con worker en thread, biblioteca). Dos fuentes nuevas en `backend/app/recommend/` (solver HU y heurística multiway) enchufadas en `recommend()`. Router `/api/solver`. En el frontend: simulador con rango de Hero, prellenado, preset y estado pendiente; pestaña nueva "Solver" (cola, biblioteca, visor, configuración).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 + Alembic (SQLite), `pokercore` (pybind11), pytest; React 19 + TypeScript + Vite + vitest; TexasSolver v0.2.0 consola (binario externo).

**Spec:** `docs/superpowers/specs/2026-10-06-fase5-solver-design.md`

## Global Constraints

- TexasSolver es AGPL: **nunca** se copia su código ni su binario al repo; solo se invoca por subprocess desde `POKER_SOLVER_PATH`.
- Plataforma objetivo Windows (CI `windows-latest`); todo debe funcionar también en Linux para desarrollo.
- Ningún test depende del binario real salvo los marcados `@pytest.mark.solver`, que se saltan si `POKER_SOLVER_PATH` no está definido.
- Mensajes al usuario en español; código, nombres y comentarios en inglés (igual que el resto del repo).
- Backend: `ruff` con `line-length = 100`, reglas `E,F,I,UP,B`; `ruff format`. Frontend: `tsc -b`, `oxlint`, `vitest`.
- Todo número estratégico que no salga de un cálculo exacto se marca "aproximado" (`confidence="approximate"`).
- Hechos del binario (verificados el 2026-10-06, no cambiar sin volver a verificar):
  - `player 1` = OOP, `player 0` = IP.
  - Los montos de las acciones vienen en fichas enteras → todo se escala ×100 (`CHIP_SCALE = 100`).
  - **Los rangos solo aceptan clases** (`AKs`, `AKo:0.5`, `22`); un combo puntual (`AcKc`) aborta con `range str AcKc len not valid` y código 3.
  - Progreso en `tmp_log.txt` del directorio de trabajo: una línea JSON por intervalo `{"exploitibility": <% del pote>, "iteration": n, "time_ms": t}` (sic: `exploitibility`).
  - Montos de `RAISE x` = total puesto en la calle (no el incremento). All-in ⇔ monto == stack efectivo al inicio de la calle.
  - Sin EV en la salida.
- Comandos (desde `backend/`, con `uv` en el PATH): tests `uv run pytest -q <ruta>`; lint `uv run ruff check . && uv run ruff format --check .`. Desde `frontend/`: `npm run typecheck`, `npm run lint`, `npm test`.
- Commits con la identidad git ya configurada (jcolman940) y la línea `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Binario local para pruebas manuales/integración: `C:\PROYECTOS\POKKER\tools\TexasSolver\TexasSolver-v0.2.0-Windows\console_solver.exe`.

## Mapa de archivos

Backend — crear:
- `app/solver/trees.py` — presets de árbol (`TreePreset`, `StreetSizes`, `load_presets`, `get_preset`).
- `app/solver/spot.py` — `SolverSpot`, `spot_hash`, `to_solver_range`, constantes del solver.
- `app/solver/config_gen.py` — `generate_config(spot, threads) -> str`.
- `app/solver/output_parser.py` — `StrategyNode`, `SolverAction`, `parse_output`, `find_hero_node`, `canonical_combo`, serialización.
- `app/solver/runner.py` — `run_solver`, `Progress`, `SolverError`, `SolverStopped`, `kill_tree`.
- `app/solver/cache.py` — lectura/escritura de `solver_results`.
- `app/solver/queue.py` — `enqueue`, `next_job`, `cancel_job`, `retry_job`, `recover_jobs`, pausa, `SolverWorker`.
- `app/solver/flops.py` — `representative_flops(n)`.
- `app/solver/library.py` — familias, `build_line_spots`, estado y encolado.
- `app/solver/worker_registry.py` — arranque/parada del worker global.
- `app/simulator/outs.py` — `compute_outs` y `showdown_share` movidos desde `service.py` (evita import circular).
- `app/recommend/postflop_solver.py`, `app/recommend/postflop_heuristic.py`, `app/recommend/ranges_prefill.py`.
- `app/api/solver.py` — router `/api/solver`.
- `alembic/versions/0004_solver.py`.
- `data/solver/trees.json`, `data/solver/library.json`.
- Tests: `tests/fake_solver.py`, `tests/fixtures/solver/*`, `tests/test_solver_trees.py`, `test_solver_spot.py`, `test_solver_config.py`, `test_solver_output.py`, `test_solver_runner.py`, `test_solver_cache.py`, `test_solver_queue.py`, `test_solver_flops.py`, `test_solver_library.py`, `test_postflop_solver.py`, `test_postflop_heuristic.py`, `test_ranges_prefill.py`, `test_solver_api.py`, `test_solver_real.py`.

Backend — modificar: `app/config.py`, `app/db/models.py`, `app/domain/scenario.py`, `app/recommend/schemas.py`, `app/recommend/engine.py`, `app/simulator/service.py`, `app/main.py`, `pyproject.toml` (marker), `tests/conftest.py`.

Frontend — crear: `src/solver/types.ts`, `src/solver/api.ts`, `src/solver/SolverPage.tsx`, `src/solver/QueuePanel.tsx`, `src/solver/LibraryPanel.tsx`, `src/solver/StrategyViewer.tsx`, `src/solver/SettingsPanel.tsx`, `src/solver/SolverPage.test.tsx`, `src/simulator/PostflopSolverFields.tsx`, `src/simulator/PendingSolve.tsx`, `src/simulator/PostflopSolver.test.tsx`.
Frontend — modificar: `src/App.tsx`, `src/simulator/types.ts`, `src/simulator/SimulatorPage.tsx`, `src/simulator/RecommendationPanel.tsx`, `src/ranges/labels.ts`, `src/index.css`.

Otros: `.github/workflows/ci.yml`, `README.md`.

---

### Task 1: Fixtures reales del solver y solver falso

**Files:**
- Create: `backend/tests/fixtures/solver/river_spot.txt`, `backend/tests/fixtures/solver/river_out.json`, `backend/tests/fixtures/solver/river_log.txt`
- Create: `backend/tests/fixtures/solver/turn_spot.txt`, `backend/tests/fixtures/solver/turn_out.json`
- Create: `backend/tests/fake_solver.py`
- Create: `backend/tests/test_fake_solver.py`

**Interfaces:**
- Produces: fixtures (los `*_spot.txt` son exactamente lo que `generate_config` de la Task 4 debe producir con `threads=6`); `tests/fake_solver.py` invocable como `python fake_solver.py --input_file X --resource_dir Y --mode holdem`, controlado por env `FAKE_SOLVER_MODE` (`ok`|`fail`|`hang`|`garbage`|`no_output`), `FAKE_SOLVER_FIXTURE` (ruta del JSON a copiar), `FAKE_SOLVER_DELAY` (segundos entre líneas de log, default `0.05`).

- [ ] **Step 1: Escribir `river_spot.txt`**

```text
set_pot 2000
set_effective_stack 9000
set_board Qs,Jh,2h,7c,3d
set_range_oop AQs,A5s,KQs,QJs,KJo:0.5,JTs,T9s,99,88,77,22
set_range_ip AA,AKs,AJs,A2s,AKo,KK,KQo,QQ,JJ,TT,76s
set_bet_sizes oop,river,bet,50,100
set_bet_sizes oop,river,raise,60
set_bet_sizes oop,river,allin
set_bet_sizes ip,river,bet,50,100
set_bet_sizes ip,river,raise,60
set_bet_sizes ip,river,allin
set_allin_threshold 0.67
set_raise_limit 3
build_tree
set_thread_num 6
set_accuracy 0.5
set_max_iteration 200
set_print_interval 10
set_use_isomorphism 1
start_solve
set_dump_rounds 1
dump_result result.json
```

- [ ] **Step 2: Escribir `turn_spot.txt`** (preset `chico`, OOP apuesta 50% inyectado en turn)

```text
set_pot 2000
set_effective_stack 9000
set_board Qs,Jh,2h,7c
set_range_oop AQs,A5s,KQs,QJs,KJo:0.5,JTs,T9s,99,88,77,22
set_range_ip AA,AKs,AJs,A2s,AKo,KK,KQo,QQ,JJ,TT,76s
set_bet_sizes oop,turn,bet,50,66
set_bet_sizes oop,turn,raise,60
set_bet_sizes oop,turn,allin
set_bet_sizes oop,river,bet,75
set_bet_sizes oop,river,raise,60
set_bet_sizes oop,river,allin
set_bet_sizes ip,turn,bet,66
set_bet_sizes ip,turn,raise,60
set_bet_sizes ip,turn,allin
set_bet_sizes ip,river,bet,75
set_bet_sizes ip,river,raise,60
set_bet_sizes ip,river,allin
set_allin_threshold 0.67
set_raise_limit 3
build_tree
set_thread_num 6
set_accuracy 0.5
set_max_iteration 200
set_print_interval 10
set_use_isomorphism 1
start_solve
set_dump_rounds 1
dump_result result.json
```

- [ ] **Step 3: Generar los outputs con el binario real**

Run (PowerShell, desde `backend/tests/fixtures/solver`):
```powershell
$ts = 'C:\PROYECTOS\POKKER\tools\TexasSolver\TexasSolver-v0.2.0-Windows'
foreach ($name in 'river', 'turn') {
  $tmp = New-Item -ItemType Directory -Force "$env:TEMP\ts_$name"
  Copy-Item "${name}_spot.txt" "$tmp\cmds.txt"
  Push-Location $tmp
  & "$ts\console_solver.exe" --input_file cmds.txt --resource_dir "$ts\resources" --mode holdem | Out-Null
  Pop-Location
  Copy-Item "$tmp\result.json" "${name}_out.json"
  if ($name -eq 'river') { Copy-Item "$tmp\tmp_log.txt" 'river_log.txt' }
}
Get-ChildItem | Select-Object Name, Length
```
Expected: `river_out.json` y `turn_out.json` existen, cada uno < 2 MB; `river_log.txt` tiene varias líneas JSON con `"exploitibility"`. Verificar con `python -c "import json;d=json.load(open('turn_out.json'));print(d['player'],d['actions'])"` → `1 ['CHECK', 'BET 1000.000000', 'BET 1320.000000', 'BET 9000.000000']` (si el orden o los montos difieren, el fixture real manda: anotar los valores reales y usarlos en las Tasks 5 y 9).

- [ ] **Step 4: Escribir el test del solver falso (falla porque no existe)**

```python
# backend/tests/test_fake_solver.py
import json
import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "solver"
FAKE = Path(__file__).parent / "fake_solver.py"


def run_fake(tmp_path, mode, monkeypatch=None):
    (tmp_path / "cmds.txt").write_text("set_pot 2000\ndump_result result.json\n")
    env = {
        "FAKE_SOLVER_MODE": mode,
        "FAKE_SOLVER_FIXTURE": str(FIXTURES / "river_out.json"),
        "FAKE_SOLVER_DELAY": "0",
        "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", ""),
    }
    return subprocess.run(
        [sys.executable, str(FAKE), "--input_file", "cmds.txt", "--resource_dir", "x",
         "--mode", "holdem"],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30,
    )


def test_ok_writes_log_and_result(tmp_path):
    proc = run_fake(tmp_path, "ok")
    assert proc.returncode == 0
    lines = (tmp_path / "tmp_log.txt").read_text().splitlines()
    assert json.loads(lines[-1])["iteration"] == 30
    assert json.loads((tmp_path / "result.json").read_text())["player"] == 1


def test_fail_exits_3(tmp_path):
    proc = run_fake(tmp_path, "fail")
    assert proc.returncode == 3
    assert "len not valid" in proc.stdout
    assert not (tmp_path / "result.json").exists()


def test_garbage_writes_invalid_json(tmp_path):
    assert run_fake(tmp_path, "garbage").returncode == 0
    assert (tmp_path / "result.json").read_text() == "{not json"
```

- [ ] **Step 5: Correr y ver que falla**

Run: `uv run pytest -q tests/test_fake_solver.py`
Expected: FAIL (`fake_solver.py` no existe → returncode 2).

- [ ] **Step 6: Escribir `tests/fake_solver.py`**

```python
"""Stand-in for TexasSolver's console_solver.exe, driven by environment variables.

FAKE_SOLVER_MODE: ok | fail | hang | garbage | no_output
FAKE_SOLVER_FIXTURE: JSON copied to the `dump_result` path in `ok` mode
FAKE_SOLVER_DELAY: seconds between progress lines (default 0.05)
"""

import itertools
import json
import os
import shutil
import sys
import time
from pathlib import Path


def main(argv: list[str]) -> int:
    args = dict(zip(argv[1::2], argv[2::2], strict=False))
    commands = Path(args["--input_file"]).read_text().splitlines()
    out = next(line.split(" ", 1)[1] for line in commands if line.startswith("dump_result "))
    mode = os.environ.get("FAKE_SOLVER_MODE", "ok")
    delay = float(os.environ.get("FAKE_SOLVER_DELAY", "0.05"))

    if mode == "fail":
        print("terminate called after throwing an instance of 'std::runtime_error'")
        print("  what():   range str AcKc len not valid ")
        return 3

    steps = itertools.count(1) if mode == "hang" else range(1, 4)
    with Path("tmp_log.txt").open("w") as log:
        for i in steps:
            entry = {"exploitibility": 10.0 / i, "iteration": i * 10, "time_ms": i * 100}
            log.write(json.dumps(entry) + "\n")
            log.flush()
            time.sleep(delay)

    if mode == "garbage":
        Path(out).write_text("{not json")
    elif mode == "ok":
        shutil.copy(os.environ["FAKE_SOLVER_FIXTURE"], out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 7: Correr y ver que pasa**

Run: `uv run pytest -q tests/test_fake_solver.py`
Expected: 3 passed.

- [ ] **Step 8: Commit**

```bash
git add backend/tests/fixtures/solver backend/tests/fake_solver.py backend/tests/test_fake_solver.py
git commit -m "test(solver): real TexasSolver fixtures and a fake solver for tests"
```

---

### Task 2: Presets de árbol y configuración del solver

**Files:**
- Create: `data/solver/trees.json`
- Create: `backend/app/solver/trees.py`
- Modify: `backend/app/config.py` (settings del solver)
- Test: `backend/tests/test_solver_trees.py`

**Interfaces:**
- Produces:
  - `StreetSizes(bet: tuple[float, ...], raise_: tuple[float, ...])` (frozen dataclass)
  - `TreePreset(name: str, label: str, streets: dict[str, StreetSizes])` con `canonical() -> dict`
  - `load_presets(path: Path | None = None) -> dict[str, TreePreset]`, `get_preset(name: str) -> TreePreset` (ValueError `"Preset de árbol desconocido: <name>"`)
  - `STREETS = ("flop", "turn", "river")`
  - Settings nuevos: `solver_threads: int`, `solver_timeout_min: float = 30`, `solver_trees_file: Path`, `solver_library_file: Path`, `heuristic_value_share = 0.65`, `heuristic_raise_share = 0.80`, `heuristic_semibluff_outs = 8`, `heuristic_realization_oop = 0.85`, `heuristic_realization_last = 0.95`, `heuristic_margin = 0.03`.

- [ ] **Step 1: Escribir `data/solver/trees.json`**

```json
{
  "simple": {
    "label": "Simple",
    "flop": {"bet": [33, 75], "raise": [60]},
    "turn": {"bet": [50, 100], "raise": [60]},
    "river": {"bet": [50, 100], "raise": [60]}
  },
  "chico": {
    "label": "Chico (rápido)",
    "flop": {"bet": [33], "raise": [60]},
    "turn": {"bet": [66], "raise": [60]},
    "river": {"bet": [75], "raise": [60]}
  },
  "amplio": {
    "label": "Amplio (lento)",
    "flop": {"bet": [25, 50, 100], "raise": [50, 100]},
    "turn": {"bet": [33, 75, 125], "raise": [60]},
    "river": {"bet": [33, 75, 125], "raise": [60]}
  }
}
```

- [ ] **Step 2: Escribir el test (falla)**

```python
# backend/tests/test_solver_trees.py
import json

import pytest

from app.solver.trees import STREETS, get_preset, load_presets


def test_bundled_presets():
    presets = load_presets()
    assert set(presets) == {"simple", "chico", "amplio"}
    simple = presets["simple"]
    assert simple.streets["flop"].bet == (33.0, 75.0)
    assert simple.streets["river"].raise_ == (60.0,)
    assert all(s in simple.streets for s in STREETS)


def test_canonical_is_json_stable():
    a = get_preset("simple").canonical()
    assert json.dumps(a, sort_keys=True) == json.dumps(get_preset("simple").canonical(), sort_keys=True)
    assert a["flop"]["bet"] == [33.0, 75.0]


def test_unknown_preset():
    with pytest.raises(ValueError, match="Preset de árbol desconocido: x"):
        get_preset("x")


@pytest.mark.parametrize(
    "street_cfg",
    [{"bet": [0], "raise": [60]}, {"bet": [400], "raise": [60]}, {"bet": [], "raise": [60]}],
)
def test_invalid_sizes(tmp_path, street_cfg):
    bad = {"p": {"label": "P", "flop": street_cfg, "turn": street_cfg, "river": street_cfg}}
    path = tmp_path / "trees.json"
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        load_presets(path)
```

- [ ] **Step 3: Correr y ver que falla**

Run: `uv run pytest -q tests/test_solver_trees.py`
Expected: FAIL `ModuleNotFoundError: app.solver.trees`.

- [ ] **Step 4: Agregar settings en `app/config.py`**

En la clase `Settings`, reemplazar el bloque del solver:
```python
    # External postflop solver (TexasSolver console binary, AGPL: never vendored).
    solver_path: Path | None = None
    solver_threads: int = Field(default_factory=lambda: os.cpu_count() or 4)
    solver_timeout_min: float = 30.0
    solver_trees_file: Path = REPO_ROOT / "data" / "solver" / "trees.json"
    solver_library_file: Path = REPO_ROOT / "data" / "solver" / "library.json"

    # Multiway postflop heuristic thresholds (own heuristics, not solver output).
    heuristic_value_share: float = 0.65
    heuristic_raise_share: float = 0.80
    heuristic_semibluff_outs: int = 8
    heuristic_realization_oop: float = 0.85
    heuristic_realization_last: float = 0.95
    heuristic_margin: float = 0.03
```

- [ ] **Step 5: Escribir `app/solver/trees.py`**

```python
"""Bet-tree presets for TexasSolver (sizes in % of the pot)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.config import get_settings

STREETS = ("flop", "turn", "river")
MAX_SIZE_PCT = 300.0


@dataclass(frozen=True)
class StreetSizes:
    bet: tuple[float, ...]
    raise_: tuple[float, ...]


@dataclass(frozen=True)
class TreePreset:
    name: str
    label: str
    streets: dict[str, StreetSizes]

    def canonical(self) -> dict:
        return {
            "name": self.name,
            **{
                s: {"bet": list(self.streets[s].bet), "raise": list(self.streets[s].raise_)}
                for s in STREETS
            },
        }


def _sizes(values: list, where: str) -> tuple[float, ...]:
    sizes = tuple(sorted({float(v) for v in values}))
    if not sizes or any(not 0 < v <= MAX_SIZE_PCT for v in sizes):
        raise ValueError(f"Tamaños inválidos en {where}: deben estar entre 0 y {MAX_SIZE_PCT:g}%")
    return sizes


def _parse(name: str, raw: dict) -> TreePreset:
    streets = {}
    for street in STREETS:
        cfg = raw.get(street)
        if not isinstance(cfg, dict):
            raise ValueError(f"El preset {name} no define la calle {street}")
        streets[street] = StreetSizes(
            bet=_sizes(cfg.get("bet", []), f"{name}.{street}.bet"),
            raise_=_sizes(cfg.get("raise", []), f"{name}.{street}.raise"),
        )
    return TreePreset(name=name, label=str(raw.get("label", name)), streets=streets)


def load_presets(path: Path | None = None) -> dict[str, TreePreset]:
    data = json.loads((path or get_settings().solver_trees_file).read_text(encoding="utf-8"))
    return {name: _parse(name, raw) for name, raw in data.items()}


@lru_cache
def _bundled() -> dict[str, TreePreset]:
    return load_presets()


def get_preset(name: str) -> TreePreset:
    try:
        return _bundled()[name]
    except KeyError:
        raise ValueError(f"Preset de árbol desconocido: {name}") from None
```

- [ ] **Step 6: Correr y ver que pasa**

Run: `uv run pytest -q tests/test_solver_trees.py`
Expected: 6 passed.

- [ ] **Step 7: Commit**

```bash
git add data/solver/trees.json backend/app/solver/trees.py backend/app/config.py backend/tests/test_solver_trees.py
git commit -m "feat(solver): bet-tree presets and solver settings"
```

---

### Task 3: `SolverSpot`, conversión de rangos y hash

**Files:**
- Create: `backend/app/solver/spot.py`
- Test: `backend/tests/test_solver_spot.py`

**Interfaces:**
- Consumes: `TreePreset`, `get_preset` (Task 2); `pokercore.range_grid`, `pokercore.range_combos`, `pokercore.hand_class_names`; `app.recommend.preflop_equity.hand_class(hand: str) -> str`.
- Produces:
  - `Side = Literal["oop", "ip"]`
  - `SOLVER_VERSION = "texassolver-0.2.0"`, `CHIP_SCALE = 100`, `ACCURACY = 0.5`, `MAX_ITERATION = 200`, `ALLIN_THRESHOLD = 0.67`, `RAISE_LIMIT = 3`
  - `SolverRange(text: str, approximated: bool)`; `to_solver_range(text: str) -> SolverRange` (ValueError si queda vacío)
  - `SolverSpot(board: tuple[str, ...], pot_bb: float, stack_bb: float, range_oop: str, range_ip: str, preset: TreePreset, bettor: Side | None = None, facing_bet_pct: float | None = None)` frozen, con `street -> str`, `canonical() -> dict`, `spot_hash() -> str`, `to_json() -> dict`, `SolverSpot.from_json(d) -> SolverSpot`, `label() -> str`.
  - `facing_pct(to_call_bb: float, pot_before_bet_bb: float) -> float` (redondeo a entero %).

- [ ] **Step 1: Escribir el test (falla)**

```python
# backend/tests/test_solver_spot.py
import pytest

from app.solver.spot import SolverSpot, facing_pct, to_solver_range
from app.solver.trees import get_preset

OOP = "AQs,KQs,QJs,JTs,T9s,99,88,77,22,A5s,KJo:0.5"
IP = "AA,KK,QQ,AK,AJs,KQo,JJ,TT,76s,A2s"


def make(**kw):
    base = dict(
        board=("Qs", "Jh", "2h", "7c", "3d"),
        pot_bb=20.0,
        stack_bb=90.0,
        range_oop=to_solver_range(OOP).text,
        range_ip=to_solver_range(IP).text,
        preset=get_preset("simple"),
    )
    base.update(kw)
    return SolverSpot(**base)


def test_to_solver_range_orders_by_grid_and_keeps_weights():
    r = to_solver_range(OOP)
    assert r.text == "AQs,A5s,KQs,QJs,KJo:0.5,JTs,T9s,99,88,77,22"
    assert r.approximated is False


def test_to_solver_range_flags_combo_specific_ranges():
    r = to_solver_range("AhKh")
    assert r.text == "AKs:0.25"
    assert r.approximated is True


def test_to_solver_range_rejects_empty():
    with pytest.raises(ValueError):
        to_solver_range("AA:0")


def test_street_from_board():
    assert make().street == "river"
    assert make(board=("Qs", "Jh", "2h")).street == "flop"


def test_hash_is_stable_and_sensitive():
    assert make().spot_hash() == make().spot_hash()
    assert len(make().spot_hash()) == 64
    assert make().spot_hash() != make(pot_bb=21.0).spot_hash()
    assert make().spot_hash() != make(preset=get_preset("chico")).spot_hash()
    assert make().spot_hash() != make(bettor="oop", facing_bet_pct=50.0).spot_hash()


def test_board_order_does_not_change_the_flop_hash():
    a = make(board=("Qs", "Jh", "2h"))
    b = make(board=("2h", "Qs", "Jh"))
    assert a.spot_hash() == b.spot_hash()


def test_board_order_matters_for_turn_card():
    a = make(board=("Qs", "Jh", "2h", "7c"))
    b = make(board=("Qs", "Jh", "7c", "2h"))
    assert a.spot_hash() != b.spot_hash()


def test_json_roundtrip():
    spot = make(bettor="ip", facing_bet_pct=75.0)
    assert SolverSpot.from_json(spot.to_json()) == spot


def test_facing_pct_rounds_to_integer_percent():
    assert facing_pct(6.6, 20.0) == 33.0
    assert facing_pct(10.0, 20.0) == 50.0
```

- [ ] **Step 2: Correr y ver que falla**

Run: `uv run pytest -q tests/test_solver_spot.py`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Escribir `app/solver/spot.py`**

```python
"""A postflop spot as the solver sees it, its canonical form and its cache key."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

import pokercore

from app.recommend.preflop_equity import hand_class
from app.solver.trees import TreePreset, get_preset

Side = Literal["oop", "ip"]

SOLVER_VERSION = "texassolver-0.2.0"
CHIP_SCALE = 100  # the solver rounds amounts to whole chips: 1bb = 100 chips
ACCURACY = 0.5  # target exploitability, % of the pot
MAX_ITERATION = 200
ALLIN_THRESHOLD = 0.67
RAISE_LIMIT = 3
STREET_BY_CARDS = {3: "flop", 4: "turn", 5: "river"}


@dataclass(frozen=True)
class SolverRange:
    text: str  # class-level notation the solver accepts ("AKs,KJo:0.5")
    approximated: bool  # True when combo-level weights had to be averaged per class


def _class_size(name: str) -> int:
    if len(name) == 2:
        return 6
    return 4 if name.endswith("s") else 12


def to_solver_range(text: str) -> SolverRange:
    """Our notation (classes, combos, weights) -> class-level notation for TexasSolver.

    TexasSolver rejects specific combos, so each class gets its average weight; when the
    combos of a class had different weights the result is flagged as approximated.
    """
    names = pokercore.hand_class_names()
    grid = pokercore.range_grid(text)
    parts = []
    for name, weight in zip(names, grid, strict=True):
        if weight < 0.0005:
            continue
        parts.append(name if weight >= 0.9995 else f"{name}:{round(weight, 3):g}")
    if not parts:
        raise ValueError("El rango está vacío")

    weights_by_class: dict[str, list[float]] = defaultdict(list)
    for combo, weight in pokercore.range_combos(text):
        weights_by_class[hand_class(combo)].append(weight)
    approximated = any(
        len(ws) != _class_size(cls) or max(ws) - min(ws) > 1e-6
        for cls, ws in weights_by_class.items()
    )
    return SolverRange(text=",".join(parts), approximated=approximated)


def facing_pct(to_call_bb: float, pot_before_bet_bb: float) -> float:
    """Bet size as a whole % of the pot before the bet (the solver works in whole %)."""
    return float(round(100 * to_call_bb / pot_before_bet_bb))


@dataclass(frozen=True)
class SolverSpot:
    board: tuple[str, ...]
    pot_bb: float  # pot at the start of the street
    stack_bb: float  # effective stack at the start of the street
    range_oop: str
    range_ip: str
    preset: TreePreset
    bettor: Side | None = None  # who bet the size hero faces (injected into the tree)
    facing_bet_pct: float | None = None

    @property
    def street(self) -> str:
        return STREET_BY_CARDS[len(self.board)]

    def canonical(self) -> dict:
        flop = sorted(self.board[:3])
        return {
            "solver": SOLVER_VERSION,
            "accuracy": ACCURACY,
            "max_iteration": MAX_ITERATION,
            "allin_threshold": ALLIN_THRESHOLD,
            "raise_limit": RAISE_LIMIT,
            "board": [*flop, *self.board[3:]],
            "pot": round(self.pot_bb, 2),
            "stack": round(self.stack_bb, 2),
            "range_oop": self.range_oop,
            "range_ip": self.range_ip,
            "preset": self.preset.canonical(),
            "bettor": self.bettor,
            "facing_bet_pct": self.facing_bet_pct,
        }

    def spot_hash(self) -> str:
        blob = json.dumps(self.canonical(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()

    def to_json(self) -> dict:
        return {
            "board": list(self.board),
            "pot_bb": self.pot_bb,
            "stack_bb": self.stack_bb,
            "range_oop": self.range_oop,
            "range_ip": self.range_ip,
            "preset": self.preset.name,
            "bettor": self.bettor,
            "facing_bet_pct": self.facing_bet_pct,
        }

    @classmethod
    def from_json(cls, d: dict) -> SolverSpot:
        return cls(
            board=tuple(d["board"]),
            pot_bb=d["pot_bb"],
            stack_bb=d["stack_bb"],
            range_oop=d["range_oop"],
            range_ip=d["range_ip"],
            preset=get_preset(d["preset"]),
            bettor=d.get("bettor"),
            facing_bet_pct=d.get("facing_bet_pct"),
        )

    def label(self) -> str:
        board = " ".join(self.board)
        text = f"{self.street.capitalize()} {board} · pote {self.pot_bb:g}bb · stack {self.stack_bb:g}bb"
        if self.bettor and self.facing_bet_pct:
            text += f" · {self.bettor.upper()} apuesta {self.facing_bet_pct:g}%"
        return text
```

Nota: `hand_class` en `preflop_equity.py` recibe una mano de 4 caracteres (`"AhKh"`) y devuelve la clase (`"AKs"`); los combos de `pokercore.range_combos` tienen ese formato.

- [ ] **Step 4: Correr y ver que pasa**

Run: `uv run pytest -q tests/test_solver_spot.py`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/solver/spot.py backend/tests/test_solver_spot.py
git commit -m "feat(solver): SolverSpot, class-level range conversion and spot hash"
```

---

### Task 4: Generador del archivo de comandos

**Files:**
- Create: `backend/app/solver/config_gen.py`
- Test: `backend/tests/test_solver_config.py`

**Interfaces:**
- Consumes: `SolverSpot`, constantes de `spot.py`, `STREETS`.
- Produces: `RESULT_FILE = "result.json"`, `PRINT_INTERVAL = 10`, `chips(bb: float) -> int`, `generate_config(spot: SolverSpot, threads: int) -> str` (termina en `\n`).

- [ ] **Step 1: Escribir el test golden (falla)**

```python
# backend/tests/test_solver_config.py
from pathlib import Path

from app.solver.config_gen import chips, generate_config
from app.solver.spot import SolverSpot, to_solver_range
from app.solver.trees import get_preset

FIXTURES = Path(__file__).parent / "fixtures" / "solver"
OOP = to_solver_range("AQs,KQs,QJs,JTs,T9s,99,88,77,22,A5s,KJo:0.5").text
IP = to_solver_range("AA,KK,QQ,AK,AJs,KQo,JJ,TT,76s,A2s").text


def test_river_matches_fixture():
    spot = SolverSpot(("Qs", "Jh", "2h", "7c", "3d"), 20.0, 90.0, OOP, IP, get_preset("simple"))
    assert generate_config(spot, threads=6) == (FIXTURES / "river_spot.txt").read_text()


def test_turn_injects_the_faced_size_and_covers_river():
    spot = SolverSpot(
        ("Qs", "Jh", "2h", "7c"), 20.0, 90.0, OOP, IP, get_preset("chico"),
        bettor="oop", facing_bet_pct=50.0,
    )
    assert generate_config(spot, threads=6) == (FIXTURES / "turn_spot.txt").read_text()


def test_injected_size_already_in_preset_is_not_duplicated():
    spot = SolverSpot(
        ("Qs", "Jh", "2h", "7c", "3d"), 20.0, 90.0, OOP, IP, get_preset("simple"),
        bettor="ip", facing_bet_pct=50.0,
    )
    text = generate_config(spot, threads=2)
    assert "set_bet_sizes ip,river,bet,50,100\n" in text


def test_chips_scale():
    assert chips(20.0) == 2000
    assert chips(0.125) == 12
```

- [ ] **Step 2: Correr y ver que falla**

Run: `uv run pytest -q tests/test_solver_config.py`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Escribir `app/solver/config_gen.py`**

```python
"""SolverSpot -> TexasSolver console command file."""

from __future__ import annotations

from app.solver.spot import (
    ACCURACY,
    ALLIN_THRESHOLD,
    CHIP_SCALE,
    MAX_ITERATION,
    RAISE_LIMIT,
    Side,
    SolverSpot,
)
from app.solver.trees import STREETS

RESULT_FILE = "result.json"
PRINT_INTERVAL = 10


def chips(bb: float) -> int:
    return round(bb * CHIP_SCALE)


def _fmt(sizes: tuple[float, ...]) -> str:
    return ",".join(f"{s:g}" for s in sizes)


def _bets(spot: SolverSpot, side: Side, street: str) -> tuple[float, ...]:
    sizes = spot.preset.streets[street].bet
    if street == spot.street and side == spot.bettor and spot.facing_bet_pct:
        sizes = tuple(sorted({*sizes, spot.facing_bet_pct}))
    return sizes


def generate_config(spot: SolverSpot, threads: int) -> str:
    streets = STREETS[STREETS.index(spot.street) :]
    lines = [
        f"set_pot {chips(spot.pot_bb)}",
        f"set_effective_stack {chips(spot.stack_bb)}",
        f"set_board {','.join(spot.board)}",
        f"set_range_oop {spot.range_oop}",
        f"set_range_ip {spot.range_ip}",
    ]
    for side in ("oop", "ip"):
        for street in streets:
            lines.append(f"set_bet_sizes {side},{street},bet,{_fmt(_bets(spot, side, street))}")
            lines.append(
                f"set_bet_sizes {side},{street},raise,{_fmt(spot.preset.streets[street].raise_)}"
            )
            lines.append(f"set_bet_sizes {side},{street},allin")
    lines += [
        f"set_allin_threshold {ALLIN_THRESHOLD:g}",
        f"set_raise_limit {RAISE_LIMIT}",
        "build_tree",
        f"set_thread_num {threads}",
        f"set_accuracy {ACCURACY:g}",
        f"set_max_iteration {MAX_ITERATION}",
        f"set_print_interval {PRINT_INTERVAL}",
        "set_use_isomorphism 1",
        "start_solve",
        "set_dump_rounds 1",
        f"dump_result {RESULT_FILE}",
    ]
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Correr y ver que pasa**

Run: `uv run pytest -q tests/test_solver_config.py`
Expected: 4 passed. (Si el fixture se guardó con CRLF, normalizarlo a LF: `.gitattributes` con `backend/tests/fixtures/solver/*.txt text eol=lf`, agregarlo en este commit.)

- [ ] **Step 5: Commit**

```bash
git add backend/app/solver/config_gen.py backend/tests/test_solver_config.py
git commit -m "feat(solver): command-file generator with x100 chip scaling and faced-size injection"
```

---

### Task 5: Parser del output y navegación al nodo de Hero

**Files:**
- Create: `backend/app/solver/output_parser.py`
- Test: `backend/tests/test_solver_output.py`

**Interfaces:**
- Consumes: `CHIP_SCALE`, `Side` (Task 3); fixtures de la Task 1.
- Produces:
  - `SolverAction(kind: str, amount_bb: float | None)` frozen, `kind ∈ {"check","bet","call","raise","fold","allin"}`, con `label(pot_bb: float) -> str`
  - `StrategyNode(player: Side, actions: list[SolverAction], strategy: dict[str, list[float]], children: dict[int, StrategyNode])` con `child(kind: str, amount_bb: float | None = None) -> StrategyNode | None`, `range_mix(weights: dict[str, float]) -> list[float]`, `class_layers(weights: dict[str, float]) -> list[list[float]]`, `to_dict() -> dict`, `StrategyNode.from_dict(d) -> StrategyNode`
  - `canonical_combo(combo: str) -> str` (`"2c2d"`→`"2d2c"`, `"KhAh"`→`"AhKh"`)
  - `parse_output(raw: dict, stack_bb: float) -> StrategyNode`
  - `HeroNode(node: StrategyNode, warnings: list[str])`; `find_hero_node(root, hero: Side, facing_bet_bb: float) -> HeroNode` (ValueError si el nodo no existe)

- [ ] **Step 1: Escribir el test (falla)**

```python
# backend/tests/test_solver_output.py
import json
from pathlib import Path

import pytest

from app.solver.output_parser import (
    SolverAction,
    StrategyNode,
    canonical_combo,
    find_hero_node,
    parse_output,
)

FIXTURES = Path(__file__).parent / "fixtures" / "solver"


@pytest.fixture(scope="module")
def river():
    return parse_output(json.loads((FIXTURES / "river_out.json").read_text()), stack_bb=90.0)


@pytest.fixture(scope="module")
def turn():
    return parse_output(json.loads((FIXTURES / "turn_out.json").read_text()), stack_bb=90.0)


def test_canonical_combo():
    assert canonical_combo("2c2d") == "2d2c"
    assert canonical_combo("KhAh") == "AhKh"
    assert canonical_combo("AhKh") == "AhKh"


def test_root_is_oop_and_amounts_are_unscaled(river):
    assert river.player == "oop"
    assert river.actions == [
        SolverAction("check", None),
        SolverAction("bet", 10.0),
        SolverAction("bet", 20.0),
        SolverAction("allin", 90.0),
    ]


def test_strategies_are_distributions(river):
    for freqs in river.strategy.values():
        assert len(freqs) == len(river.actions)
        assert sum(freqs) == pytest.approx(1.0, abs=1e-3)
    assert all(canonical_combo(c) == c for c in river.strategy)


def test_children_alternate_players_and_stop_at_street_end(river):
    after_check = river.child("check")
    assert after_check is not None and after_check.player == "ip"
    vs_bet = river.child("bet", 10.0)
    assert vs_bet.player == "ip"
    assert {a.kind for a in vs_bet.actions} >= {"call", "fold"}
    assert vs_bet.child("call") is None  # showdown / next street: not kept


def test_turn_faced_size_was_injected(turn):
    assert SolverAction("bet", 10.0) in turn.actions  # 50% of 20bb


@pytest.mark.parametrize(
    ("hero", "facing", "expected"),
    [
        ("oop", 0.0, lambda root: root),
        ("ip", 0.0, lambda root: root.child("check")),
        ("ip", 10.0, lambda root: root.child("bet", 10.0)),
    ],
)
def test_find_hero_node(river, hero, facing, expected):
    found = find_hero_node(river, hero, facing)
    assert found.node is expected(river)
    assert found.node.player == hero
    assert found.warnings == []


def test_find_hero_node_oop_facing_bet_after_check(river):
    found = find_hero_node(river, "oop", 10.0)
    assert found.node.player == "oop"
    assert {a.kind for a in found.node.actions} >= {"call", "fold"}


def test_find_hero_node_warns_when_size_is_adjusted(river):
    found = find_hero_node(river, "ip", 11.0)
    assert found.node.player == "ip"
    assert found.warnings and "10" in found.warnings[0]


def test_dict_roundtrip(river):
    assert StrategyNode.from_dict(river.to_dict()) == river


def test_range_mix_weights_combos(river):
    combos = list(river.strategy)[:2]
    mix = river.range_mix({combos[0]: 1.0, combos[1]: 0.0})
    assert mix == pytest.approx(river.strategy[combos[0]])
```

Nota: si en la Task 1 el fixture real mostró otro orden o montos, ajustar `test_root_is_oop_and_amounts_are_unscaled` a los valores reales (el fixture manda).

- [ ] **Step 2: Correr y ver que falla**

Run: `uv run pytest -q tests/test_solver_output.py`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Escribir `app/solver/output_parser.py`**

```python
"""TexasSolver JSON output -> compact strategy tree for the current street.

Facts about the raw format (verified against v0.2.0):
- `player` 1 is OOP and 0 is IP.
- Action strings: CHECK, CALL, FOLD, "BET <chips>", "RAISE <chips>" (RAISE is the
  street total, not the increment); amounts are whole chips (x CHIP_SCALE).
- Chance nodes (next street / showdown) are dropped: we only keep the street solved.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pokercore

from app.recommend.preflop_equity import hand_class
from app.solver.spot import CHIP_SCALE, Side

RANKS = "23456789TJQKA"
SUITS = "cdhs"
PLAYER = {1: "oop", 0: "ip"}


def canonical_combo(combo: str) -> str:
    a, b = combo[:2], combo[2:]
    key = lambda c: (RANKS.index(c[0]), SUITS.index(c[1]))  # noqa: E731
    hi, lo = sorted((a, b), key=key, reverse=True)
    return hi + lo


@dataclass(frozen=True)
class SolverAction:
    kind: str  # check / bet / call / raise / fold / allin
    amount_bb: float | None = None

    def label(self, pot_bb: float) -> str:
        if self.amount_bb is None:
            return self.kind.capitalize()
        if self.kind == "allin":
            return f"All-in ({self.amount_bb:g}bb)"
        if self.kind == "bet" and pot_bb > 0:
            return f"Bet {round(100 * self.amount_bb / pot_bb)}% ({self.amount_bb:g}bb)"
        return f"{self.kind.capitalize()} a {self.amount_bb:g}bb"


@dataclass
class StrategyNode:
    player: Side
    actions: list[SolverAction]
    strategy: dict[str, list[float]]
    children: dict[int, StrategyNode] = field(default_factory=dict)

    def child(self, kind: str, amount_bb: float | None = None) -> StrategyNode | None:
        for i, action in enumerate(self.actions):
            if action.kind == kind and (amount_bb is None or action.amount_bb == amount_bb):
                return self.children.get(i)
        return None

    def range_mix(self, weights: dict[str, float]) -> list[float]:
        totals = [0.0] * len(self.actions)
        mass = 0.0
        for combo, freqs in self.strategy.items():
            w = weights.get(combo, 0.0)
            if w <= 0:
                continue
            mass += w
            for i, f in enumerate(freqs):
                totals[i] += w * f
        return [t / mass for t in totals] if mass > 0 else totals

    def class_layers(self, weights: dict[str, float]) -> list[list[float]]:
        """Per action, the 169-class grid of (range weight x frequency), averaged per class."""
        index = {n: i for i, n in enumerate(pokercore.hand_class_names())}
        sums = [[0.0] * 169 for _ in self.actions]
        counts = [0] * 169
        for combo, freqs in self.strategy.items():
            w = weights.get(combo, 0.0)
            cls = index[hand_class(combo)]
            counts[cls] += 1
            for i, f in enumerate(freqs):
                sums[i][cls] += w * f
        return [[s / counts[c] if counts[c] else 0.0 for c, s in enumerate(row)] for row in sums]

    def to_dict(self) -> dict:
        return {
            "p": self.player,
            "a": [[a.kind, a.amount_bb] for a in self.actions],
            "s": self.strategy,
            "c": {str(i): n.to_dict() for i, n in self.children.items()},
        }

    @classmethod
    def from_dict(cls, d: dict) -> StrategyNode:
        return cls(
            player=d["p"],
            actions=[SolverAction(k, a) for k, a in d["a"]],
            strategy=d["s"],
            children={int(i): cls.from_dict(n) for i, n in d["c"].items()},
        )


def _action(text: str, stack_chips: int) -> SolverAction:
    head, _, amount = text.partition(" ")
    kind = head.lower()
    if not amount:
        return SolverAction(kind)
    chips = round(float(amount))
    if chips >= stack_chips:
        kind = "allin"
    return SolverAction(kind, chips / CHIP_SCALE)


def _parse_node(raw: dict, stack_chips: int) -> StrategyNode | None:
    if raw.get("node_type") != "action_node":
        return None
    actions = [_action(a, stack_chips) for a in raw["actions"]]
    strategy = {
        canonical_combo(c): [float(x) for x in freqs]
        for c, freqs in raw["strategy"]["strategy"].items()
    }
    children = {}
    for i, text in enumerate(raw["actions"]):
        sub = raw.get("childrens", {}).get(text)
        node = _parse_node(sub, stack_chips) if sub else None
        if node is not None:
            children[i] = node
    return StrategyNode(PLAYER[raw["player"]], actions, strategy, children)


def parse_output(raw: dict, stack_bb: float) -> StrategyNode:
    try:
        node = _parse_node(raw, round(stack_bb * CHIP_SCALE))
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError(f"Salida del solver con formato inesperado: {e}") from e
    if node is None:
        raise ValueError("La salida del solver no empieza en un nodo de acción")
    return node


@dataclass
class HeroNode:
    node: StrategyNode
    warnings: list[str]


def _facing(node: StrategyNode, facing_bet_bb: float) -> tuple[StrategyNode, list[str]]:
    bets = [(i, a) for i, a in enumerate(node.actions) if a.kind in ("bet", "allin")]
    if not bets:
        raise ValueError("El árbol no tiene apuestas en este nodo")
    i, best = min(bets, key=lambda x: abs((x[1].amount_bb or 0) - facing_bet_bb))
    child = node.children.get(i)
    if child is None:
        raise ValueError("El árbol no tiene el nodo de respuesta a la apuesta")
    warnings = []
    if abs((best.amount_bb or 0) - facing_bet_bb) > 0.01:
        warnings.append(
            f"Apuesta ajustada de {facing_bet_bb:g}bb a {best.amount_bb:g}bb (tamaño del árbol)."
        )
    return child, warnings


def find_hero_node(root: StrategyNode, hero: Side, facing_bet_bb: float) -> HeroNode:
    if hero == "oop" and facing_bet_bb <= 0:
        return HeroNode(root, [])
    after_check = root.child("check")
    if hero == "ip" and facing_bet_bb <= 0:
        if after_check is None:
            raise ValueError("El árbol no tiene el nodo después del check")
        return HeroNode(after_check, [])
    if hero == "ip":
        return HeroNode(*_facing(root, facing_bet_bb))
    if after_check is None:
        raise ValueError("El árbol no tiene el nodo después del check")
    return HeroNode(*_facing(after_check, facing_bet_bb))
```

- [ ] **Step 4: Correr y ver que pasa**

Run: `uv run pytest -q tests/test_solver_output.py`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/solver/output_parser.py backend/tests/test_solver_output.py
git commit -m "feat(solver): output parser (player swap, unscaling) and hero-node lookup"
```

---

### Task 6: Runner del subprocess

**Files:**
- Create: `backend/app/solver/runner.py`
- Test: `backend/tests/test_solver_runner.py`

**Interfaces:**
- Consumes: `RESULT_FILE` (Task 4); `tests/fake_solver.py` (Task 1).
- Produces:
  - `Progress(iteration: int, exploitability: float | None, elapsed_ms: int)` (dataclass)
  - `class SolverError(Exception)`; `class SolverStopped(Exception)` con atributo `reason: str`
  - `solver_command(solver_path: Path, input_file: str) -> list[str]` (un `.py` se corre con `sys.executable`; `--resource_dir` = `solver_path.parent / "resources"`)
  - `kill_tree(pid: int) -> None`
  - `run_solver(commands: str, workdir: Path, solver_path: Path, *, timeout_s: float, on_start: Callable[[int], None] | None = None, on_progress: Callable[[Progress], None] | None = None, should_stop: Callable[[], str | None] | None = None, poll_s: float = 0.5) -> tuple[dict, Progress]` — devuelve el JSON crudo y el último progreso. `should_stop` devuelve un motivo (`"cancelled"`/`"preempted"`) o `None`.

- [ ] **Step 1: Escribir el test (falla)**

```python
# backend/tests/test_solver_runner.py
from pathlib import Path

import pytest

from app.solver.runner import Progress, SolverError, SolverStopped, run_solver, solver_command

FIXTURES = Path(__file__).parent / "fixtures" / "solver"
FAKE = Path(__file__).parent / "fake_solver.py"
COMMANDS = "set_pot 2000\ndump_result result.json\n"


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setenv("FAKE_SOLVER_FIXTURE", str(FIXTURES / "river_out.json"))
    monkeypatch.setenv("FAKE_SOLVER_DELAY", "0.01")

    def set_mode(mode):
        monkeypatch.setenv("FAKE_SOLVER_MODE", mode)

    return set_mode


def test_command_for_python_script_uses_interpreter():
    cmd = solver_command(FAKE, "cmds.txt")
    assert cmd[1] == str(FAKE)
    assert cmd[2:4] == ["--input_file", "cmds.txt"]
    assert cmd[-2:] == ["--mode", "holdem"]


def test_ok_returns_raw_output_and_progress(tmp_path, fake):
    fake("ok")
    seen: list[Progress] = []
    pids: list[int] = []
    raw, last = run_solver(
        COMMANDS, tmp_path, FAKE, timeout_s=30, on_start=pids.append,
        on_progress=seen.append, poll_s=0.01,
    )
    assert raw["player"] == 1
    assert last.iteration == 30
    assert last.exploitability == pytest.approx(10 / 3)
    assert pids and seen
    assert (tmp_path / "cmds.txt").read_text() == COMMANDS


def test_failure_reports_last_output_lines(tmp_path, fake):
    fake("fail")
    with pytest.raises(SolverError, match="len not valid"):
        run_solver(COMMANDS, tmp_path, FAKE, timeout_s=30, poll_s=0.01)


def test_missing_output(tmp_path, fake):
    fake("no_output")
    with pytest.raises(SolverError, match="no escribió"):
        run_solver(COMMANDS, tmp_path, FAKE, timeout_s=30, poll_s=0.01)


def test_garbage_output(tmp_path, fake):
    fake("garbage")
    with pytest.raises(SolverError, match="ilegible"):
        run_solver(COMMANDS, tmp_path, FAKE, timeout_s=30, poll_s=0.01)


def test_timeout_kills_the_process(tmp_path, fake):
    fake("hang")
    with pytest.raises(SolverError, match="timeout"):
        run_solver(COMMANDS, tmp_path, FAKE, timeout_s=0.5, poll_s=0.05)


def test_should_stop(tmp_path, fake):
    fake("hang")
    with pytest.raises(SolverStopped) as exc:
        run_solver(
            COMMANDS, tmp_path, FAKE, timeout_s=30, poll_s=0.05, should_stop=lambda: "cancelled"
        )
    assert exc.value.reason == "cancelled"
```

- [ ] **Step 2: Correr y ver que falla**

Run: `uv run pytest -q tests/test_solver_runner.py`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Escribir `app/solver/runner.py`**

```python
"""Runs the TexasSolver console binary as a subprocess and follows its progress."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.solver.config_gen import RESULT_FILE

INPUT_FILE = "cmds.txt"
LOG_FILE = "tmp_log.txt"  # written by the solver itself
STDOUT_FILE = "stdout.txt"


@dataclass
class Progress:
    iteration: int = 0
    exploitability: float | None = None  # % of the pot
    elapsed_ms: int = 0


class SolverError(Exception):
    pass


class SolverStopped(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def solver_command(solver_path: Path, input_file: str) -> list[str]:
    prefix = [sys.executable, str(solver_path)] if solver_path.suffix == ".py" else [str(solver_path)]
    resources = solver_path.parent / "resources"
    return [*prefix, "--input_file", input_file, "--resource_dir", str(resources), "--mode", "holdem"]


def kill_tree(pid: int) -> None:
    """Kills a process and its children (the solver spawns worker threads/processes)."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True)
    else:
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _read_progress(log: Path, last: Progress) -> Progress:
    if not log.exists():
        return last
    for line in reversed(log.read_text(errors="replace").splitlines()):
        try:
            entry = json.loads(line)
        except ValueError:
            continue  # partially written line
        return Progress(
            iteration=int(entry.get("iteration", 0)),
            exploitability=entry.get("exploitibility"),
            elapsed_ms=int(entry.get("time_ms", 0)),
        )
    return last


def _tail(path: Path, lines: int = 5) -> str:
    if not path.exists():
        return ""
    return "\n".join(path.read_text(errors="replace").strip().splitlines()[-lines:])


def run_solver(
    commands: str,
    workdir: Path,
    solver_path: Path,
    *,
    timeout_s: float,
    on_start: Callable[[int], None] | None = None,
    on_progress: Callable[[Progress], None] | None = None,
    should_stop: Callable[[], str | None] | None = None,
    poll_s: float = 0.5,
) -> tuple[dict, Progress]:
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / INPUT_FILE).write_text(commands)
    for name in (RESULT_FILE, LOG_FILE):
        (workdir / name).unlink(missing_ok=True)

    kwargs: dict = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    with (workdir / STDOUT_FILE).open("w") as out:
        proc = subprocess.Popen(
            solver_command(solver_path, INPUT_FILE),
            cwd=workdir, stdout=out, stderr=subprocess.STDOUT, **kwargs,
        )
        if on_start:
            on_start(proc.pid)
        progress = Progress()
        started = time.monotonic()
        try:
            while proc.poll() is None:
                time.sleep(poll_s)
                current = _read_progress(workdir / LOG_FILE, progress)
                if current != progress:
                    progress = current
                    if on_progress:
                        on_progress(progress)
                if should_stop and (reason := should_stop()):
                    raise SolverStopped(reason)
                if time.monotonic() - started > timeout_s:
                    raise SolverError(f"timeout: el solve superó {timeout_s / 60:g} min")
        except BaseException:
            kill_tree(proc.pid)
            proc.wait()
            raise

    progress = _read_progress(workdir / LOG_FILE, progress)
    if proc.returncode != 0:
        raise SolverError(
            f"El solver terminó con código {proc.returncode}: {_tail(workdir / STDOUT_FILE)}"
        )
    result = workdir / RESULT_FILE
    if not result.exists():
        raise SolverError(f"El solver no escribió el resultado: {_tail(workdir / STDOUT_FILE)}")
    try:
        return json.loads(result.read_text()), progress
    except ValueError as e:
        raise SolverError(f"Salida del solver ilegible: {e}") from e
```

- [ ] **Step 4: Correr y ver que pasa**

Run: `uv run pytest -q tests/test_solver_runner.py`
Expected: 7 passed. Verificar además que no quedó ningún `python` colgado del modo `hang`: `Get-Process python` no debe mostrar procesos nuevos.

- [ ] **Step 5: Commit**

```bash
git add backend/app/solver/runner.py backend/tests/test_solver_runner.py
git commit -m "feat(solver): subprocess runner with progress, timeout, stop and tree kill"
```

---

### Task 7: Tablas, migración 0004 y caché

**Files:**
- Modify: `backend/app/db/models.py` (agregar `SolverResult`, `SolverJob`; importar `LargeBinary`)
- Create: `backend/alembic/versions/0004_solver.py`
- Create: `backend/app/solver/cache.py`
- Test: `backend/tests/test_solver_cache.py`; agregar caso en `backend/tests/test_migrations.py`

**Interfaces:**
- Consumes: `SolverSpot`, `StrategyNode` (Tasks 3, 5).
- Produces:
  - ORM `SolverResult` (`hash` PK str64, `spot` JSON, `tree` bytes zlib, `exploitability` float|None, `iterations` int, `solve_seconds` float, `solver_version` str, `preset` str, `library_key` str|None, `created_at`).
  - ORM `SolverJob` (`id`, `spot_hash`, `spot` JSON, `label` str, `origin` str, `priority` int, `status` str, `iteration` int, `exploitability` float|None, `error` text|None, `pid` int|None, `library_key` str|None, `created_at`, `started_at`, `finished_at`).
  - `CachedResult(spot: SolverSpot, tree: StrategyNode, exploitability: float | None, iterations: int, solve_seconds: float, created_at: datetime)`
  - `get_result(session, spot_hash) -> CachedResult | None`, `store_result(session, spot, tree, progress: Progress, solve_seconds, library_key=None) -> None` (hace commit), `delete_result(session, spot_hash) -> bool`, `clear_cache(session) -> int`, `cache_stats(session) -> tuple[int, int]` (entradas, bytes), `result_hashes_for_library(session, library_key) -> set[str]`.
- Session de tests: `tests/conftest.py` gana el fixture `db_session` (SQLite en `tmp_path` con migraciones).

- [ ] **Step 1: Agregar el fixture `db_session` en `tests/conftest.py`**

En el fixture `client` existente agregar `monkeypatch.delenv("POKER_SOLVER_PATH", raising=False)` junto al `delenv` de `POKER_DATABASE_URL` (el CI define esa variable para el test real; sin esto el worker arrancaría en cada test de API). Y agregar:

```python
@pytest.fixture
def db_session(tmp_path, monkeypatch):
    monkeypatch.setenv("POKER_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("POKER_DATABASE_URL", raising=False)
    monkeypatch.delenv("POKER_SOLVER_PATH", raising=False)
    from app.config import get_settings
    from app.db.session import _session_factory, get_engine, run_migrations

    get_settings.cache_clear()
    get_engine.cache_clear()
    _session_factory.cache_clear()
    run_migrations()
    with _session_factory()() as session:
        yield session
    get_engine().dispose()
    get_settings.cache_clear()
    get_engine.cache_clear()
    _session_factory.cache_clear()
```

- [ ] **Step 2: Escribir el test (falla)**

```python
# backend/tests/test_solver_cache.py
import json
from pathlib import Path

from app.solver.cache import cache_stats, clear_cache, delete_result, get_result, store_result
from app.solver.output_parser import parse_output
from app.solver.runner import Progress
from app.solver.spot import SolverSpot, to_solver_range
from app.solver.trees import get_preset

FIXTURES = Path(__file__).parent / "fixtures" / "solver"


def spot():
    return SolverSpot(
        ("Qs", "Jh", "2h", "7c", "3d"), 20.0, 90.0,
        to_solver_range("AQs,KQs,QJs,JTs,T9s,99,88,77,22,A5s,KJo:0.5").text,
        to_solver_range("AA,KK,QQ,AK,AJs,KQo,JJ,TT,76s,A2s").text,
        get_preset("simple"),
    )


def tree():
    return parse_output(json.loads((FIXTURES / "river_out.json").read_text()), 90.0)


def test_store_and_get(db_session):
    s, t = spot(), tree()
    assert get_result(db_session, s.spot_hash()) is None
    store_result(db_session, s, t, Progress(200, 0.4, 1500), solve_seconds=18.2)
    cached = get_result(db_session, s.spot_hash())
    assert cached.tree == t
    assert cached.spot == s
    assert cached.exploitability == 0.4
    assert cached.iterations == 200
    entries, size = cache_stats(db_session)
    assert entries == 1 and size > 0


def test_store_is_idempotent(db_session):
    s, t = spot(), tree()
    store_result(db_session, s, t, Progress(200, 0.4, 1), 1.0)
    store_result(db_session, s, t, Progress(200, 0.3, 1), 1.0)
    assert cache_stats(db_session)[0] == 1
    assert get_result(db_session, s.spot_hash()).exploitability == 0.3


def test_delete_and_clear(db_session):
    s, t = spot(), tree()
    store_result(db_session, s, t, Progress(), 1.0)
    assert delete_result(db_session, s.spot_hash()) is True
    assert delete_result(db_session, s.spot_hash()) is False
    store_result(db_session, s, t, Progress(), 1.0)
    assert clear_cache(db_session) == 1
    assert cache_stats(db_session) == (0, 0)
```

Agregar en `tests/test_migrations.py` (siguiendo el estilo existente del archivo) una aserción de que tras `run_migrations()` existen las tablas `solver_results` y `solver_jobs` (`sqlalchemy.inspect(engine).get_table_names()`).

- [ ] **Step 3: Correr y ver que falla**

Run: `uv run pytest -q tests/test_solver_cache.py tests/test_migrations.py`
Expected: FAIL (`ModuleNotFoundError: app.solver.cache` / tablas inexistentes).

- [ ] **Step 4: Agregar los modelos en `app/db/models.py`**

Agregar `LargeBinary` al import de `sqlalchemy` y al final:
```python
class SolverResult(Base):
    """A solved postflop spot (current street only), keyed by the spot hash."""

    __tablename__ = "solver_results"

    hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    spot: Mapped[dict] = mapped_column(JSON)
    tree: Mapped[bytes] = mapped_column(LargeBinary)  # zlib-compressed StrategyNode JSON
    exploitability: Mapped[float | None] = mapped_column(Float, nullable=True)
    iterations: Mapped[int] = mapped_column(Integer, default=0)
    solve_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    solver_version: Mapped[str] = mapped_column(String(32))
    preset: Mapped[str] = mapped_column(String(32))
    library_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SolverJob(Base):
    """A queued/running/finished solve. Survives restarts (running -> queued on startup)."""

    __tablename__ = "solver_jobs"
    __table_args__ = (Index("ix_solver_jobs_pick", "status", "priority", "id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    spot_hash: Mapped[str] = mapped_column(String(64), index=True)
    spot: Mapped[dict] = mapped_column(JSON)
    label: Mapped[str] = mapped_column(String(200))
    origin: Mapped[str] = mapped_column(String(16))  # simulator / batch / library
    priority: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))  # queued/running/done/failed/cancelled
    iteration: Mapped[int] = mapped_column(Integer, default=0)
    exploitability: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    library_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 5: Escribir la migración `alembic/versions/0004_solver.py`**

```python
"""solver results and jobs

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "solver_results",
        sa.Column("hash", sa.String(length=64), primary_key=True),
        sa.Column("spot", sa.JSON(), nullable=False),
        sa.Column("tree", sa.LargeBinary(), nullable=False),
        sa.Column("exploitability", sa.Float(), nullable=True),
        sa.Column("iterations", sa.Integer(), nullable=False),
        sa.Column("solve_seconds", sa.Float(), nullable=False),
        sa.Column("solver_version", sa.String(length=32), nullable=False),
        sa.Column("preset", sa.String(length=32), nullable=False),
        sa.Column("library_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_solver_results_library_key", "solver_results", ["library_key"])
    op.create_table(
        "solver_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("spot_hash", sa.String(length=64), nullable=False),
        sa.Column("spot", sa.JSON(), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("iteration", sa.Integer(), nullable=False),
        sa.Column("exploitability", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("pid", sa.Integer(), nullable=True),
        sa.Column("library_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_solver_jobs_pick", "solver_jobs", ["status", "priority", "id"])
    op.create_index("ix_solver_jobs_spot_hash", "solver_jobs", ["spot_hash"])
    op.create_index("ix_solver_jobs_library_key", "solver_jobs", ["library_key"])


def downgrade() -> None:
    op.drop_index("ix_solver_jobs_library_key", table_name="solver_jobs")
    op.drop_index("ix_solver_jobs_spot_hash", table_name="solver_jobs")
    op.drop_index("ix_solver_jobs_pick", table_name="solver_jobs")
    op.drop_table("solver_jobs")
    op.drop_index("ix_solver_results_library_key", table_name="solver_results")
    op.drop_table("solver_results")
```

- [ ] **Step 6: Escribir `app/solver/cache.py`**

```python
"""Solved spots in SQLite, keyed by the spot hash. Results never expire: any change in
the solver version, preset or inputs changes the hash."""

from __future__ import annotations

import json
import zlib
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models import SolverResult
from app.solver.output_parser import StrategyNode
from app.solver.runner import Progress
from app.solver.spot import SOLVER_VERSION, SolverSpot


@dataclass
class CachedResult:
    spot: SolverSpot
    tree: StrategyNode
    exploitability: float | None
    iterations: int
    solve_seconds: float
    created_at: datetime


def _pack(tree: StrategyNode) -> bytes:
    return zlib.compress(json.dumps(tree.to_dict(), separators=(",", ":")).encode(), 6)


def _unpack(blob: bytes) -> StrategyNode:
    return StrategyNode.from_dict(json.loads(zlib.decompress(blob)))


def get_result(session: Session, spot_hash: str) -> CachedResult | None:
    row = session.get(SolverResult, spot_hash)
    if row is None:
        return None
    return CachedResult(
        spot=SolverSpot.from_json(row.spot),
        tree=_unpack(row.tree),
        exploitability=row.exploitability,
        iterations=row.iterations,
        solve_seconds=row.solve_seconds,
        created_at=row.created_at,
    )


def store_result(
    session: Session,
    spot: SolverSpot,
    tree: StrategyNode,
    progress: Progress,
    solve_seconds: float,
    library_key: str | None = None,
) -> None:
    row = session.get(SolverResult, spot.spot_hash()) or SolverResult(hash=spot.spot_hash())
    row.spot = spot.to_json()
    row.tree = _pack(tree)
    row.exploitability = progress.exploitability
    row.iterations = progress.iteration
    row.solve_seconds = solve_seconds
    row.solver_version = SOLVER_VERSION
    row.preset = spot.preset.name
    row.library_key = library_key or row.library_key
    session.add(row)
    session.commit()


def delete_result(session: Session, spot_hash: str) -> bool:
    deleted = session.execute(delete(SolverResult).where(SolverResult.hash == spot_hash)).rowcount
    session.commit()
    return deleted > 0


def clear_cache(session: Session) -> int:
    deleted = session.execute(delete(SolverResult)).rowcount
    session.commit()
    return deleted


def cache_stats(session: Session) -> tuple[int, int]:
    entries, size = session.execute(
        select(func.count(SolverResult.hash), func.coalesce(func.sum(func.length(SolverResult.tree)), 0))
    ).one()
    return int(entries), int(size)


def result_hashes_for_library(session: Session, library_key: str) -> set[str]:
    return set(
        session.scalars(select(SolverResult.hash).where(SolverResult.library_key == library_key))
    )
```

- [ ] **Step 7: Correr y ver que pasa**

Run: `uv run pytest -q tests/test_solver_cache.py tests/test_migrations.py`
Expected: all passed.

- [ ] **Step 8: Commit**

```bash
git add backend/app/db/models.py backend/alembic/versions/0004_solver.py backend/app/solver/cache.py backend/tests/conftest.py backend/tests/test_solver_cache.py backend/tests/test_migrations.py
git commit -m "feat(solver): solver_results/solver_jobs tables and result cache"
```

---

### Task 8: Cola persistente y worker

**Files:**
- Create: `backend/app/solver/queue.py`
- Test: `backend/tests/test_solver_queue.py`

**Interfaces:**
- Consumes: `SolverJob` (Task 7), `run_solver`, `SolverError`, `SolverStopped`, `kill_tree`, `Progress` (Task 6), `generate_config` (Task 4), `parse_output` (Task 5), `store_result` (Task 7), `SolverSpot` (Task 3), `AppMeta`.
- Produces:
  - `Origin(StrEnum)`: `SIMULATOR="simulator"`, `BATCH="batch"`, `LIBRARY="library"`; `PRIORITY = {SIMULATOR: 0, BATCH: 10, LIBRARY: 20}`
  - `JobStatus(StrEnum)`: `QUEUED`, `RUNNING`, `DONE`, `FAILED`, `CANCELLED`; `ACTIVE = {QUEUED, RUNNING}`
  - `enqueue(session, spot: SolverSpot, origin: Origin, library_key: str | None = None) -> SolverJob`
  - `next_job(session) -> SolverJob | None`; `queue_position(session, job) -> int | None` (1 = el próximo; `None` si no está en cola)
  - `cancel_job(session, job_id) -> SolverJob`; `retry_job(session, job_id) -> SolverJob` (ValueError si no aplica)
  - `recover_jobs(session) -> int`
  - `is_paused(session) -> bool`; `set_paused(session, paused: bool) -> None`
  - `SolverWorker(session_factory: Callable[[], Session], solver_path: Path, data_dir: Path, *, threads: int, timeout_s: float, poll_s: float = 1.0, run_poll_s: float = 0.5)` con `start()`, `stop()`, `run_once() -> bool`.

- [ ] **Step 1: Escribir el test (falla)**

```python
# backend/tests/test_solver_queue.py
import threading
import time
from pathlib import Path

import pytest

from app.db.models import SolverJob
from app.solver.cache import get_result
from app.solver.queue import (
    JobStatus,
    Origin,
    SolverWorker,
    cancel_job,
    enqueue,
    is_paused,
    next_job,
    queue_position,
    recover_jobs,
    retry_job,
    set_paused,
)
from app.solver.spot import SolverSpot, to_solver_range
from app.solver.trees import get_preset

FIXTURES = Path(__file__).parent / "fixtures" / "solver"
FAKE = Path(__file__).parent / "fake_solver.py"


def spot(pot=20.0):
    return SolverSpot(
        ("Qs", "Jh", "2h", "7c", "3d"), pot, 90.0,
        to_solver_range("AQs,KQs,QJs,JTs,T9s,99,88,77,22,A5s,KJo:0.5").text,
        to_solver_range("AA,KK,QQ,AK,AJs,KQo,JJ,TT,76s,A2s").text,
        get_preset("simple"),
    )


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setenv("FAKE_SOLVER_FIXTURE", str(FIXTURES / "river_out.json"))
    monkeypatch.setenv("FAKE_SOLVER_DELAY", "0.01")
    monkeypatch.setenv("FAKE_SOLVER_MODE", "ok")
    return lambda mode: monkeypatch.setenv("FAKE_SOLVER_MODE", mode)


@pytest.fixture
def worker(db_session, tmp_path):
    from app.db.session import _session_factory

    return SolverWorker(
        _session_factory(), FAKE, tmp_path, threads=2, timeout_s=30, poll_s=0.05, run_poll_s=0.02
    )


def test_enqueue_dedupes_and_bumps_priority(db_session):
    a = enqueue(db_session, spot(), Origin.LIBRARY)
    b = enqueue(db_session, spot(), Origin.SIMULATOR)
    assert a.id == b.id
    assert b.priority == 0
    assert db_session.query(SolverJob).count() == 1


def test_order_by_priority_then_age(db_session):
    lib = enqueue(db_session, spot(20), Origin.LIBRARY)
    batch = enqueue(db_session, spot(21), Origin.BATCH)
    sim = enqueue(db_session, spot(22), Origin.SIMULATOR)
    assert next_job(db_session).id == sim.id
    assert queue_position(db_session, sim) == 1
    assert queue_position(db_session, batch) == 2
    assert queue_position(db_session, lib) == 3


def test_worker_solves_and_caches(db_session, worker, fake):
    job = enqueue(db_session, spot(), Origin.SIMULATOR)
    assert worker.run_once() is True
    db_session.refresh(job)
    assert job.status == JobStatus.DONE
    assert job.iteration == 30
    assert get_result(db_session, spot().spot_hash()) is not None
    assert worker.run_once() is False  # nothing left


def test_enqueue_of_cached_spot_returns_done_job(db_session, worker, fake):
    enqueue(db_session, spot(), Origin.SIMULATOR)
    worker.run_once()
    again = enqueue(db_session, spot(), Origin.SIMULATOR)
    assert again.status == JobStatus.DONE


def test_failure_is_recorded_and_retryable(db_session, worker, fake):
    fake("fail")
    job = enqueue(db_session, spot(), Origin.BATCH)
    worker.run_once()
    db_session.refresh(job)
    assert job.status == JobStatus.FAILED
    assert "len not valid" in job.error
    fake("ok")
    retry_job(db_session, job.id)
    worker.run_once()
    db_session.refresh(job)
    assert job.status == JobStatus.DONE


def test_cancel_queued_job(db_session):
    job = enqueue(db_session, spot(), Origin.BATCH)
    assert cancel_job(db_session, job.id).status == JobStatus.CANCELLED
    assert next_job(db_session) is None


def test_cancel_running_job_stops_the_solver(db_session, worker, fake):
    fake("hang")
    job = enqueue(db_session, spot(), Origin.BATCH)
    t = threading.Thread(target=worker.run_once)
    t.start()
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        db_session.refresh(job)
        if job.status == JobStatus.RUNNING and job.iteration > 0:
            break
        time.sleep(0.02)
    cancel_job(db_session, job.id)
    t.join(10)
    db_session.refresh(job)
    assert job.status == JobStatus.CANCELLED


def test_simulator_job_preempts_running_batch(db_session, worker, fake):
    fake("hang")
    batch = enqueue(db_session, spot(20), Origin.BATCH)
    t = threading.Thread(target=worker.run_once)
    t.start()
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        db_session.refresh(batch)
        if batch.status == JobStatus.RUNNING:
            break
        time.sleep(0.02)
    enqueue(db_session, spot(21), Origin.SIMULATOR)
    t.join(10)
    db_session.refresh(batch)
    assert batch.status == JobStatus.QUEUED
    assert batch.priority == 10


def test_pause_blocks_the_worker(db_session, worker, fake):
    enqueue(db_session, spot(), Origin.BATCH)
    set_paused(db_session, True)
    assert is_paused(db_session)
    assert worker.run_once() is False
    set_paused(db_session, False)
    assert worker.run_once() is True


def test_recover_requeues_running_jobs(db_session):
    job = enqueue(db_session, spot(), Origin.BATCH)
    job.status = JobStatus.RUNNING
    job.pid = 999999  # not alive
    db_session.commit()
    assert recover_jobs(db_session) == 1
    db_session.refresh(job)
    assert job.status == JobStatus.QUEUED and job.pid is None


def test_failed_workdirs_are_capped(db_session, worker, fake, tmp_path):
    fake("fail")
    for pot in range(20, 27):
        enqueue(db_session, spot(pot), Origin.BATCH)
        worker.run_once()
    jobs_dir = tmp_path / "solver" / "jobs"
    assert len(list(jobs_dir.iterdir())) == 5
```

- [ ] **Step 2: Correr y ver que falla**

Run: `uv run pytest -q tests/test_solver_queue.py`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Escribir `app/solver/queue.py`**

```python
"""Persistent solve queue (SQLite) and the single background worker.

One solve runs at a time (the solver already uses every core). A simulator request
preempts a running batch/library job, which goes back to the queue.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AppMeta, SolverJob, SolverResult
from app.solver.cache import store_result
from app.solver.config_gen import generate_config
from app.solver.output_parser import parse_output
from app.solver.runner import Progress, SolverError, SolverStopped, kill_tree, run_solver
from app.solver.spot import SolverSpot

log = logging.getLogger(__name__)

PAUSED_KEY = "solver_queue_paused"
KEEP_FAILED_DIRS = 5


class Origin(StrEnum):
    SIMULATOR = "simulator"
    BATCH = "batch"
    LIBRARY = "library"


PRIORITY = {Origin.SIMULATOR: 0, Origin.BATCH: 10, Origin.LIBRARY: 20}


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


ACTIVE = {JobStatus.QUEUED, JobStatus.RUNNING}


def _now() -> datetime:
    return datetime.now(UTC)


def enqueue(
    session: Session, spot: SolverSpot, origin: Origin, library_key: str | None = None
) -> SolverJob:
    spot_hash = spot.spot_hash()
    priority = PRIORITY[origin]
    active = session.scalars(
        select(SolverJob).where(SolverJob.spot_hash == spot_hash, SolverJob.status.in_(ACTIVE))
    ).first()
    if active is not None:
        if priority < active.priority:
            active.priority = priority
            session.commit()
        return active
    cached = session.get(SolverResult, spot_hash) is not None
    job = SolverJob(
        spot_hash=spot_hash,
        spot=spot.to_json(),
        label=spot.label(),
        origin=origin,
        priority=priority,
        status=JobStatus.DONE if cached else JobStatus.QUEUED,
        iteration=0,
        library_key=library_key,
        finished_at=_now() if cached else None,
    )
    session.add(job)
    session.commit()
    return job


def _queued(session: Session):
    return select(SolverJob).where(SolverJob.status == JobStatus.QUEUED).order_by(
        SolverJob.priority, SolverJob.id
    )


def next_job(session: Session) -> SolverJob | None:
    return session.scalars(_queued(session).limit(1)).first()


def queue_position(session: Session, job: SolverJob) -> int | None:
    if job.status != JobStatus.QUEUED:
        return None
    ids = list(session.scalars(_queued(session).with_only_columns(SolverJob.id)))
    return ids.index(job.id) + 1


def _get(session: Session, job_id: int) -> SolverJob:
    job = session.get(SolverJob, job_id)
    if job is None:
        raise ValueError(f"No existe el trabajo {job_id}")
    return job


def cancel_job(session: Session, job_id: int) -> SolverJob:
    job = _get(session, job_id)
    if job.status not in ACTIVE:
        raise ValueError("Solo se puede cancelar un trabajo en cola o corriendo")
    job.status = JobStatus.CANCELLED  # a running worker sees this and stops the solver
    job.finished_at = _now()
    session.commit()
    return job


def retry_job(session: Session, job_id: int) -> SolverJob:
    job = _get(session, job_id)
    if job.status not in (JobStatus.FAILED, JobStatus.CANCELLED):
        raise ValueError("Solo se puede reintentar un trabajo fallido o cancelado")
    job.status = JobStatus.QUEUED
    job.error = None
    job.iteration = 0
    job.exploitability = None
    job.finished_at = None
    session.commit()
    return job


def _is_solver_process(pid: int) -> bool:
    """True only if `pid` is alive AND is a TexasSolver process (PIDs get reused).

    Never use os.kill(pid, 0) for this on Windows: there it calls TerminateProcess.
    """
    if os.name == "nt":
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True,
        ).stdout.lower()
        return "console_solver" in out
    try:
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().decode(errors="replace").lower()
    except OSError:
        return False
    return "console_solver" in cmdline


def recover_jobs(session: Session) -> int:
    """Startup: jobs left running by a previous backend go back to the queue."""
    jobs = session.scalars(select(SolverJob).where(SolverJob.status == JobStatus.RUNNING)).all()
    for job in jobs:
        if job.pid and _is_solver_process(job.pid):
            kill_tree(job.pid)
        job.status = JobStatus.QUEUED
        job.pid = None
        job.started_at = None
    session.commit()
    return len(jobs)


def is_paused(session: Session) -> bool:
    meta = session.get(AppMeta, PAUSED_KEY)
    return meta is not None and meta.value == "1"


def set_paused(session: Session, paused: bool) -> None:
    session.merge(AppMeta(key=PAUSED_KEY, value="1" if paused else "0"))
    session.commit()


class SolverWorker:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        solver_path: Path,
        data_dir: Path,
        *,
        threads: int,
        timeout_s: float,
        poll_s: float = 1.0,
        run_poll_s: float = 0.5,
    ):
        self._sessions = session_factory
        self._solver_path = solver_path
        self._jobs_dir = data_dir / "solver" / "jobs"
        self._threads = threads
        self._timeout_s = timeout_s
        self._poll_s = poll_s
        self._run_poll_s = run_poll_s
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        with self._sessions() as session:
            recover_jobs(session)
        self._thread = threading.Thread(target=self._loop, name="solver-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                worked = self.run_once()
            except Exception:  # keep the worker alive; the job itself records errors
                log.exception("solver worker iteration failed")
                worked = False
            if not worked:
                self._stop.wait(self._poll_s)

    def run_once(self) -> bool:
        with self._sessions() as session:
            if is_paused(session):
                return False
            job = next_job(session)
            if job is None:
                return False
            job.status = JobStatus.RUNNING
            job.started_at = _now()
            job.iteration = 0
            session.commit()
            job_id, priority = job.id, job.priority
            spot = SolverSpot.from_json(job.spot)
            library_key = job.library_key

        workdir = self._jobs_dir / str(job_id)
        started = time.monotonic()
        try:
            raw, progress = run_solver(
                generate_config(spot, self._threads),
                workdir,
                self._solver_path,
                timeout_s=self._timeout_s,
                on_start=lambda pid: self._update(job_id, pid=pid),
                on_progress=lambda p: self._update(
                    job_id, iteration=p.iteration, exploitability=p.exploitability
                ),
                should_stop=lambda: self._should_stop(job_id, priority),
                poll_s=self._run_poll_s,
            )
            tree = parse_output(raw, spot.stack_bb)
        except SolverStopped as stop:
            self._finish_stopped(job_id, stop.reason)
            shutil.rmtree(workdir, ignore_errors=True)
            return True
        except (SolverError, ValueError) as e:
            self._finish(job_id, JobStatus.FAILED, error=str(e))
            self._prune_failed()
            return True

        with self._sessions() as session:
            store_result(
                session, spot, tree, progress, time.monotonic() - started, library_key
            )
        self._finish(job_id, JobStatus.DONE, progress=progress)
        shutil.rmtree(workdir, ignore_errors=True)
        return True

    def _update(self, job_id: int, **fields) -> None:
        with self._sessions() as session:
            job = session.get(SolverJob, job_id)
            for k, v in fields.items():
                setattr(job, k, v)
            session.commit()

    def _should_stop(self, job_id: int, priority: int) -> str | None:
        if self._stop.is_set():
            return "shutdown"
        with self._sessions() as session:
            if session.get(SolverJob, job_id).status == JobStatus.CANCELLED:
                return "cancelled"
            if priority > 0:
                urgent = session.scalars(
                    _queued(session).where(SolverJob.priority < priority).limit(1)
                ).first()
                if urgent is not None:
                    return "preempted"
        return None

    def _finish_stopped(self, job_id: int, reason: str) -> None:
        with self._sessions() as session:
            job = session.get(SolverJob, job_id)
            job.pid = None
            if reason in ("preempted", "shutdown"):
                job.status = JobStatus.QUEUED
                job.started_at = None
            session.commit()  # cancelled jobs already have their final status

    def _finish(
        self, job_id: int, status: JobStatus, *, error: str | None = None,
        progress: Progress | None = None,
    ) -> None:
        with self._sessions() as session:
            job = session.get(SolverJob, job_id)
            job.status = status
            job.error = error
            job.pid = None
            job.finished_at = _now()
            if progress:
                job.iteration = progress.iteration
                job.exploitability = progress.exploitability
            session.commit()

    def _prune_failed(self) -> None:
        if not self._jobs_dir.exists():
            return
        dirs = sorted(
            (d for d in self._jobs_dir.iterdir() if d.is_dir()),
            key=lambda d: d.stat().st_mtime,
        )
        for d in dirs[:-KEEP_FAILED_DIRS]:
            shutil.rmtree(d, ignore_errors=True)
```

- [ ] **Step 4: Correr y ver que pasa**

Run: `uv run pytest -q tests/test_solver_queue.py`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/solver/queue.py backend/tests/test_solver_queue.py
git commit -m "feat(solver): persistent queue with dedupe, priorities, preemption and worker"
```

---

### Task 9: Fuente "solver" en la recomendación postflop HU

**Files:**
- Modify: `backend/app/domain/scenario.py` (campos `hero_range`, `ranges_approximate`, `solver_preset`)
- Modify: `backend/app/recommend/schemas.py` (`ActionOut.label/amount_bb`, `PendingJobOut`, `StrategyLayerOut`, `RecommendationOut.pending_job/strategy_grid`)
- Create: `backend/app/simulator/outs.py` (mover `compute_outs`, `_share` → `showdown_share`)
- Modify: `backend/app/simulator/service.py` (importar desde `outs.py`)
- Create: `backend/app/recommend/postflop_solver.py`
- Modify: `backend/app/recommend/engine.py` (derivar postflop)
- Create: `backend/app/solver/worker_registry.py`
- Test: `backend/tests/test_postflop_solver.py`

**Interfaces:**
- Consumes: `SolverSpot`, `to_solver_range`, `facing_pct` (Task 3), `get_preset` (Task 2), `get_result`, `CachedResult` (Task 7), `enqueue`, `queue_position`, `Origin` (Task 8), `find_hero_node`, `canonical_combo` (Task 5), `postflop_order` (`app.domain.positions`).
- Produces:
  - `Scenario.hero_range: str | None = None`, `Scenario.ranges_approximate: bool = False`, `Scenario.solver_preset: str = "simple"`.
  - `ActionOut.label: str | None = None`, `ActionOut.amount_bb: float | None = None`.
  - `PendingJobOut(id: int, status: str, iteration: int, exploitability: float | None, position: int | None)`; `StrategyLayerOut(action: str, label: str, grid: list[float])`.
  - `RecommendationOut.pending_job: PendingJobOut | None = None`, `RecommendationOut.strategy_grid: list[StrategyLayerOut] = []`.
  - `hero_side(scenario) -> Side`; `build_solver_spot(scenario) -> BuiltSpot(spot: SolverSpot, hero: Side, facing_bet_bb: float, approximated: list[str])`; `recommend_solver(scenario, session) -> RecommendationOut`.
  - `worker_registry.solver_available() -> bool`.
  - `app.simulator.outs.compute_outs(hero, villain_ranges, board) -> OutsOut`, `showdown_share(strength) -> float`.

- [ ] **Step 1: Mover `compute_outs` a `app/simulator/outs.py`**

Crear `app/simulator/outs.py` con el contenido actual de `_share` (renombrado `showdown_share`) y `compute_outs` (copiados tal cual desde `service.py`, con sus imports: `pokercore`, `DECK`, `parse_cards`, `OutsOut`). En `service.py` borrar ambas funciones y agregar `from app.simulator.outs import compute_outs`. Correr `uv run pytest -q tests/test_simulator.py` → pasa sin cambios.

- [ ] **Step 2: Ampliar `Scenario`, `schemas.py` y crear `worker_registry.py`**

En `Scenario` (después de `villains`):
```python
    # Postflop solver inputs. Hero's range is required for a heads-up solve; the UI can
    # prefill it (and the villain's) from the preflop charts, flagging approximations.
    hero_range: str | None = None
    ranges_approximate: bool = False
    solver_preset: str = "simple"
```
En `_validate`, antes del chequeo de posiciones:
```python
        if self.hero_range is not None:
            if not self.hero_range.strip():
                self.hero_range = None
            else:
                try:
                    pokercore.range_combos(self.hero_range)
                except ValueError as e:
                    raise ValueError(f"Rango inválido de Hero: {e}") from e
```
En `recommend/schemas.py`:
```python
class ActionOut(BaseModel):
    action: str  # fold / call / raise / 3bet / allin / check / bet ...
    frequency: float
    ev: float | None = None
    label: str | None = None  # e.g. "Bet 75% (6bb)" when an action has several sizes
    amount_bb: float | None = None


class PendingJobOut(BaseModel):
    id: int
    status: str
    iteration: int
    exploitability: float | None
    position: int | None  # place in the queue (1 = next), None when running


class StrategyLayerOut(BaseModel):
    action: str
    label: str
    grid: list[float]  # 169 classes, range weight x frequency
```
y en `RecommendationOut` agregar `pending_job: PendingJobOut | None = None` y `strategy_grid: list[StrategyLayerOut] = []`.

`app/solver/worker_registry.py`:
```python
"""The process-wide solver worker (started by the app lifespan when the solver exists)."""

from __future__ import annotations

from app.config import get_settings
from app.db.session import _session_factory
from app.solver.queue import SolverWorker

_worker: SolverWorker | None = None


def solver_available() -> bool:
    path = get_settings().solver_path
    return path is not None and path.is_file()


def start_worker() -> None:
    global _worker
    if _worker is not None or not solver_available():
        return
    s = get_settings()
    _worker = SolverWorker(
        _session_factory(), s.solver_path, s.data_dir,
        threads=s.solver_threads, timeout_s=s.solver_timeout_min * 60,
    )
    _worker.start()


def stop_worker() -> None:
    global _worker
    if _worker is not None:
        _worker.stop()
        _worker = None
```

- [ ] **Step 3: Escribir el test (falla)**

```python
# backend/tests/test_postflop_solver.py
import json
from pathlib import Path

import pytest

from app.domain.scenario import Scenario, Villain
from app.recommend.postflop_solver import build_solver_spot, hero_side, recommend_solver
from app.solver.cache import store_result
from app.solver.output_parser import parse_output
from app.solver.runner import Progress

FIXTURES = Path(__file__).parent / "fixtures" / "solver"
OOP = "AQs,KQs,QJs,JTs,T9s,99,88,77,22,A5s,KJo:0.5"
IP = "AA,KK,QQ,AK,AJs,KQo,JJ,TT,76s,A2s"


def scenario(**kw):
    base = dict(
        num_players=6, hero_position="BB", hero_hand="QhQc", hero_range=OOP,
        villains=[Villain(position="BTN", range=IP)], board="QsJh2h7c3d",
        pot_bb=20.0, to_call_bb=0.0, effective_stack_bb=90.0,
    )
    base.update(kw)
    return Scenario(**base)


def cache_river(session):
    built = build_solver_spot(scenario())
    tree = parse_output(json.loads((FIXTURES / "river_out.json").read_text()), 90.0)
    store_result(session, built.spot, tree, Progress(200, 0.42, 1), 18.0)
    return built


def test_hero_side():
    assert hero_side(scenario()) == "oop"
    assert hero_side(scenario(hero_position="BTN", villains=[Villain(position="BB", range=OOP)])) == "ip"


def test_spot_puts_ranges_on_the_right_side():
    built = build_solver_spot(
        scenario(hero_position="BTN", hero_range=IP, villains=[Villain(position="BB", range=OOP)])
    )
    assert built.hero == "ip"
    assert built.spot.range_oop.startswith("AQs")
    assert built.spot.range_ip.startswith("AA")


def test_facing_bet_injects_size_and_uses_pot_before_bet():
    built = build_solver_spot(scenario(pot_bb=30.0, to_call_bb=10.0))
    assert built.spot.pot_bb == 20.0
    assert built.spot.bettor == "ip"
    assert built.spot.facing_bet_pct == 50.0
    assert built.facing_bet_bb == 10.0


def test_missing_hero_range(db_session):
    rec = recommend_solver(scenario(hero_range=None), db_session)
    assert not rec.available and "rango de Hero" in rec.message


def test_missing_positions(db_session):
    rec = recommend_solver(scenario(hero_position=None), db_session)
    assert not rec.available and "posiciones" in rec.message


def test_uncached_without_solver_explains_configuration(db_session, monkeypatch):
    monkeypatch.setattr("app.recommend.postflop_solver.solver_available", lambda: False)
    rec = recommend_solver(scenario(), db_session)
    assert not rec.available and "POKER_SOLVER_PATH" in rec.message


def test_uncached_enqueues_a_simulator_job(db_session, monkeypatch):
    monkeypatch.setattr("app.recommend.postflop_solver.solver_available", lambda: True)
    rec = recommend_solver(scenario(), db_session)
    assert not rec.available
    assert rec.source == "solver"
    assert rec.pending_job.status == "queued" and rec.pending_job.position == 1


def test_cached_spot_returns_hero_combo_strategy(db_session):
    cache_river(db_session)
    rec = recommend_solver(scenario(), db_session)
    assert rec.available and rec.source == "solver" and rec.confidence == "exact"
    assert sum(a.frequency for a in rec.actions) == pytest.approx(1.0, abs=1e-3)
    assert {a.action for a in rec.actions} <= {"check", "bet", "allin"}
    assert len(rec.strategy_grid) == len(rec.actions)
    assert all(len(layer.grid) == 169 for layer in rec.strategy_grid)
    assert "explotabilidad" in rec.reference
    assert any("primera decisión" in w for w in rec.warnings)


def test_hand_outside_range_shows_range_strategy(db_session):
    cache_river(db_session)
    rec = recommend_solver(scenario(hero_hand="8s6s"), db_session)
    assert rec.available
    assert any("no está en tu rango" in w for w in rec.warnings)


def test_approximate_when_ranges_flagged(db_session):
    cache_river(db_session)
    rec = recommend_solver(scenario(ranges_approximate=True), db_session)
    assert rec.confidence == "approximate"
```

- [ ] **Step 4: Correr y ver que falla**

Run: `uv run pytest -q tests/test_postflop_solver.py`
Expected: FAIL `ModuleNotFoundError: app.recommend.postflop_solver`.

- [ ] **Step 5: Escribir `app/recommend/postflop_solver.py`**

```python
"""Heads-up postflop recommendation from TexasSolver (cached) or a pending solve."""

from __future__ import annotations

from dataclasses import dataclass

import pokercore
from sqlalchemy.orm import Session

from app.domain.cards import parse_cards
from app.domain.positions import postflop_order
from app.domain.scenario import Scenario
from app.recommend.schemas import ActionOut, PendingJobOut, RecommendationOut, StrategyLayerOut
from app.simulator.outs import showdown_share
from app.solver.cache import CachedResult, get_result
from app.solver.output_parser import StrategyNode, canonical_combo, find_hero_node
from app.solver.queue import Origin, enqueue, queue_position
from app.solver.spot import Side, SolverSpot, facing_pct, to_solver_range
from app.solver.trees import get_preset
from app.solver.worker_registry import solver_available

AGGRESSIVE = {"bet", "raise", "allin"}
FIRST_DECISION = "Solo primera decisión de la calle: raises y re-raises previos no se modelan."


@dataclass
class BuiltSpot:
    spot: SolverSpot
    hero: Side
    facing_bet_bb: float
    approximated: list[str]


def hero_side(scenario: Scenario) -> Side:
    order = postflop_order(scenario.num_players)
    villain = scenario.villains[0].position
    if not scenario.hero_position or not villain:
        raise ValueError("Indicá las posiciones de Hero y del rival para usar el solver.")
    return "oop" if order.index(scenario.hero_position) < order.index(villain) else "ip"


def build_solver_spot(scenario: Scenario) -> BuiltSpot:
    hero = hero_side(scenario)
    if not scenario.hero_range:
        raise ValueError("Cargá el rango de Hero (o prellenalo desde las tablas) para usar el solver.")
    hero_r = to_solver_range(scenario.hero_range)
    villain_r = to_solver_range(scenario.villains[0].range)
    approximated = []
    if hero_r.approximated:
        approximated.append("Rango de Hero promediado por clase (el solver no acepta combos sueltos).")
    if villain_r.approximated:
        approximated.append("Rango rival promediado por clase (el solver no acepta combos sueltos).")

    to_call = scenario.to_call_bb
    pot_before = scenario.pot_bb - to_call
    villain_side: Side = "ip" if hero == "oop" else "oop"
    facing = to_call > 0 and to_call < scenario.effective_stack_bb
    spot = SolverSpot(
        board=tuple(parse_cards(scenario.board)),
        pot_bb=round(pot_before, 2),
        stack_bb=round(scenario.effective_stack_bb, 2),
        range_oop=hero_r.text if hero == "oop" else villain_r.text,
        range_ip=villain_r.text if hero == "oop" else hero_r.text,
        preset=get_preset(scenario.solver_preset),
        bettor=villain_side if facing else None,
        facing_bet_pct=facing_pct(to_call, pot_before) if facing else None,
    )
    return BuiltSpot(spot, hero, to_call, approximated)


def _unavailable(message: str) -> RecommendationOut:
    return RecommendationOut(available=False, message=message, source="solver")


def _range_weights(range_text: str, dead: str) -> dict[str, float]:
    return {canonical_combo(c): w for c, w in pokercore.range_combos(range_text, dead)}


def _explain(scenario: Scenario, node: StrategyNode, freqs: list[float]) -> list[str]:
    out = []
    main = max(range(len(freqs)), key=freqs.__getitem__)
    if sorted(freqs)[-1] < 0.85:
        out.append("Estrategia mixta: alterná las acciones según sus frecuencias.")
    share = showdown_share(
        pokercore.hand_strength(scenario.hero_hand, scenario.villains[0].range, scenario.board)
    )
    kind = node.actions[main].kind
    if kind in AGGRESSIVE:
        if share >= 0.6:
            out.append("Valor: tu mano le gana a la mayor parte del rango rival que paga.")
        else:
            out.append("Bluff/semi-bluff: poca equity al showdown, apuesta por fold equity.")
    elif kind == "call":
        out.append("Bluff-catcher / realización de equity: pagar rinde más que subir o foldear.")
    elif kind == "check":
        out.append("Check: la mano rinde más controlando el pote que apostando.")
    return out


def _from_cache(scenario: Scenario, built: BuiltSpot, cached: CachedResult) -> RecommendationOut:
    hero_node = find_hero_node(cached.tree, built.hero, built.facing_bet_bb)
    node = hero_node.node
    warnings = [FIRST_DECISION, *hero_node.warnings, *built.approximated]
    hero_range_text = built.spot.range_oop if node.player == "oop" else built.spot.range_ip
    weights = _range_weights(hero_range_text, scenario.board)
    combo = canonical_combo(scenario.hero_hand)
    pot = built.spot.pot_bb
    if combo in node.strategy:
        freqs = node.strategy[combo]
    else:
        freqs = node.range_mix(weights)
        warnings.append(
            "Tu mano no está en tu rango: se muestra la estrategia del rango. "
            "Agregala al rango para ver la suya."
        )
    layers = node.class_layers(weights)
    exact = not built.approximated and not scenario.ranges_approximate
    expl = cached.exploitability
    return RecommendationOut(
        available=True,
        source="solver",
        confidence="exact" if exact else "approximate",
        actions=[
            ActionOut(action=a.kind, frequency=f, label=a.label(pot), amount_bb=a.amount_bb)
            for a, f in zip(node.actions, freqs, strict=True)
        ],
        reference=(
            f"TexasSolver · preset {built.spot.preset.label} · explotabilidad "
            f"{expl:.2f}% del pote" if expl is not None else "TexasSolver"
        ),
        explanation=_explain(scenario, node, freqs),
        warnings=warnings,
        strategy_grid=[
            StrategyLayerOut(action=a.kind, label=a.label(pot), grid=g)
            for a, g in zip(node.actions, layers, strict=True)
        ],
    )


def recommend_solver(scenario: Scenario, session: Session) -> RecommendationOut:
    try:
        built = build_solver_spot(scenario)
    except ValueError as e:
        return _unavailable(str(e))
    cached = get_result(session, built.spot.spot_hash())
    if cached is not None:
        return _from_cache(scenario, built, cached)
    if not solver_available():
        return _unavailable(
            "El solver no está configurado: definí POKER_SOLVER_PATH con la ruta de "
            "console_solver.exe de TexasSolver."
        )
    job = enqueue(session, built.spot, Origin.SIMULATOR)
    return RecommendationOut(
        available=False,
        source="solver",
        message="Resolviendo el spot con el solver…",
        pending_job=PendingJobOut(
            id=job.id, status=job.status, iteration=job.iteration,
            exploitability=job.exploitability, position=queue_position(session, job),
        ),
    )
```

- [ ] **Step 6: Derivar postflop en `engine.py`**

Reemplazar el bloque inicial de `recommend()`:
```python
    if scenario.street != Street.PREFLOP:
        if len(scenario.villains) == 1:
            return recommend_solver(scenario, session)
        return recommend_heuristic(scenario)
```
con `from app.recommend.postflop_solver import recommend_solver` y, provisoriamente hasta la Task 11, `from app.recommend.postflop_heuristic import recommend_heuristic` apuntando a un módulo con:
```python
def recommend_heuristic(scenario):  # replaced in Task 11
    return unavailable("Postflop multiway: heurística en construcción.")
```
(la Task 11 reemplaza el cuerpo completo). Actualizar el docstring del módulo: "Postflop: solver HU (TexasSolver, con caché y cola) o heurística multiway."

- [ ] **Step 7: Correr y ver que pasa**

Run: `uv run pytest -q tests/test_postflop_solver.py tests/test_simulator.py tests/test_recommend.py`
Expected: all passed. Si `test_recommend.py` tenía un test del mensaje "fase 5", actualizarlo a lo nuevo (sin rango de Hero → mensaje "rango de Hero").

- [ ] **Step 8: Commit**

```bash
git add backend/app backend/tests/test_postflop_solver.py backend/tests/test_recommend.py
git commit -m "feat(recommend): heads-up postflop source backed by the solver cache and queue"
```

---

### Task 10: Prellenado de rangos desde las tablas

**Files:**
- Create: `backend/app/recommend/ranges_prefill.py`
- Test: `backend/tests/test_ranges_prefill.py`

**Interfaces:**
- Consumes: `find_chart`, `ChartQuery` (`app.recommend.charts`), `grid_to_text` (`preflop_equity`), `GameFormat`, `Situation`.
- Produces:
  - `PotType(StrEnum)`: `SRP="srp"`, `THREE_BET="3bet"`
  - `PrefillQuery(game_format: GameFormat, players: int, aggressor: str, caller: str, pot_type: PotType, stack_bb: float, ante_bb: float = 0.0)` (posiciones)
  - `PrefillRange(text: str | None, approximate: bool, notes: list[str], missing: str | None)`
  - `PrefillResult(aggressor: PrefillRange, caller: PrefillRange)`
  - `prefill_ranges(session, q: PrefillQuery) -> PrefillResult`

- [ ] **Step 1: Escribir el test (falla)**

```python
# backend/tests/test_ranges_prefill.py
from app.db.models import PreflopChart
from app.domain.scenario import GameFormat
from app.recommend.ranges_prefill import PotType, PrefillQuery, prefill_ranges


def grid(classes: dict[str, float]):
    import pokercore

    names = pokercore.hand_class_names()
    return [classes.get(n, 0.0) for n in names]


def chart(session, **kw):
    base = dict(
        name="c", source="custom", game_format="cash", players=6, stack_bb=100.0,
        ante_bb=0.0, note="", vs_position=None, open_size_bb=2.5, rake=None,
    )
    base.update(kw)
    session.add(PreflopChart(**base))
    session.commit()


def q(**kw):
    base = dict(
        game_format=GameFormat.CASH, players=6, aggressor="BTN", caller="BB",
        pot_type=PotType.SRP, stack_bb=100.0,
    )
    base.update(kw)
    return PrefillQuery(**base)


def test_srp_uses_rfi_raise_and_vs_open_call(db_session):
    chart(db_session, position="BTN", situation="rfi", actions={"raise": grid({"AA": 1, "KK": 1})})
    chart(
        db_session, position="BB", vs_position="BTN", situation="vs_open",
        actions={"call": grid({"QQ": 1, "JJ": 0.5}), "3bet": grid({"AA": 1})},
    )
    r = prefill_ranges(db_session, q())
    assert r.aggressor.text == "AA,KK" and not r.aggressor.approximate
    assert r.caller.text == "QQ,JJ:0.5"


def test_3bet_pot(db_session):
    chart(
        db_session, position="BB", vs_position="BTN", situation="vs_open",
        actions={"3bet": grid({"AA": 1})},
    )
    chart(
        db_session, position="BTN", vs_position="BB", situation="vs_3bet",
        actions={"call": grid({"QQ": 1})},
    )
    r = prefill_ranges(db_session, q(aggressor="BB", caller="BTN", pot_type=PotType.THREE_BET))
    assert r.aggressor.text == "AA"
    assert r.caller.text == "QQ"


def test_nearest_chart_is_marked_approximate(db_session):
    chart(db_session, position="BTN", situation="rfi", stack_bb=40.0, actions={"raise": grid({"AA": 1})})
    r = prefill_ranges(db_session, q())
    assert r.aggressor.approximate
    assert any("Stack del rango" in n for n in r.aggressor.notes)


def test_missing_chart(db_session):
    r = prefill_ranges(db_session, q())
    assert r.aggressor.text is None
    assert r.aggressor.missing == "BTN RFI"
    assert r.caller.missing == "BB vs open de BTN"
```

- [ ] **Step 2: Correr y ver que falla**

Run: `uv run pytest -q tests/test_ranges_prefill.py`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Escribir `app/recommend/ranges_prefill.py`**

```python
"""Postflop starting ranges taken from the user's preflop charts.

SRP:    aggressor = RFI "raise"      caller = vs_open "call"
3-bet:  aggressor = vs_open "3bet"   caller = vs_3bet "call"
The small blind's charts may be stored as blind-vs-blind, so it is tried as a fallback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from sqlalchemy.orm import Session

from app.domain.scenario import GameFormat, Situation
from app.recommend.charts import ChartQuery, find_chart
from app.recommend.preflop_equity import grid_to_text


class PotType(StrEnum):
    SRP = "srp"
    THREE_BET = "3bet"


@dataclass(frozen=True)
class PrefillQuery:
    game_format: GameFormat
    players: int
    aggressor: str
    caller: str
    pot_type: PotType
    stack_bb: float
    ante_bb: float = 0.0


@dataclass
class PrefillRange:
    text: str | None
    approximate: bool = False
    notes: list[str] = field(default_factory=list)
    missing: str | None = None


@dataclass
class PrefillResult:
    aggressor: PrefillRange
    caller: PrefillRange


def _lookup(
    session: Session, q: PrefillQuery, position: str, vs: str | None,
    situations: list[Situation], action: str, label: str,
) -> PrefillRange:
    for situation in situations:
        match = find_chart(
            session,
            ChartQuery(
                game_format=q.game_format, players=q.players, position=position,
                situation=situation, stack_bb=q.stack_bb, vs_position=vs, ante_bb=q.ante_bb,
            ),
        )
        if match is None:
            continue
        values = match.chart.actions.get(action)
        if not values or max(values) <= 0:
            continue
        return PrefillRange(
            text=grid_to_text(values), approximate=not match.exact, notes=match.mismatches
        )
    return PrefillRange(text=None, missing=label)


def prefill_ranges(session: Session, q: PrefillQuery) -> PrefillResult:
    a, c = q.aggressor, q.caller
    if q.pot_type == PotType.SRP:
        opener_sits = [Situation.RFI, Situation.BVB] if a == "SB" else [Situation.RFI]
        caller_sits = [Situation.VS_OPEN, Situation.BVB] if a == "SB" else [Situation.VS_OPEN]
        return PrefillResult(
            aggressor=_lookup(session, q, a, None, opener_sits, "raise", f"{a} RFI"),
            caller=_lookup(session, q, c, a, caller_sits, "call", f"{c} vs open de {a}"),
        )
    return PrefillResult(
        aggressor=_lookup(
            session, q, a, c, [Situation.VS_OPEN], "3bet", f"{a} 3-bet vs {c}"
        ),
        caller=_lookup(session, q, c, a, [Situation.VS_3BET], "call", f"{c} vs 3-bet de {a}"),
    )
```

Nota: `grid_to_text` ya existe en `preflop_equity.py` (fase 3) y produce notación como `"AA,KK"` / `"JJ:0.5"`; si su formato difiere del esperado en el test, el test se ajusta a lo que produce `grid_to_text` (es la fuente de verdad para la notación de la UI).

- [ ] **Step 4: Correr y ver que pasa**

Run: `uv run pytest -q tests/test_ranges_prefill.py`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/recommend/ranges_prefill.py backend/tests/test_ranges_prefill.py
git commit -m "feat(recommend): prefill postflop ranges from preflop charts"
```

---

### Task 11: Heurística multiway

**Files:**
- Modify (reemplazo completo): `backend/app/recommend/postflop_heuristic.py`
- Test: `backend/tests/test_postflop_heuristic.py`

**Interfaces:**
- Consumes: `compute_outs`, `showdown_share` (Task 9), `pot_metrics` (`app.domain.metrics`), `postflop_order`, settings `heuristic_*` (Task 2), `pokercore.equity`, `pokercore.hand_strength`.
- Produces: `recommend_heuristic(scenario: Scenario) -> RecommendationOut` (`source="heuristic"`, `confidence="approximate"`, `ev=None`).

- [ ] **Step 1: Escribir el test (falla)**

```python
# backend/tests/test_postflop_heuristic.py
from app.domain.scenario import Scenario, Villain
from app.recommend.postflop_heuristic import recommend_heuristic


def scen(hero, board, ranges, *, pot=10.0, to_call=0.0, hero_pos="BTN", positions=("SB", "BB")):
    return Scenario(
        num_players=6, hero_position=hero_pos, hero_hand=hero, board=board,
        villains=[Villain(position=p, range=r) for p, r in zip(positions, ranges, strict=True)],
        pot_bb=pot, to_call_bb=to_call, effective_stack_bb=100.0,
    )


def freq(rec, action):
    return sum(a.frequency for a in rec.actions if a.action == action)


def test_always_heuristic_and_approximate():
    rec = recommend_heuristic(scen("AsAd", "AhKc2d", ["random", "random"]))
    assert rec.source == "heuristic" and rec.confidence == "approximate"
    assert all(a.ev is None for a in rec.actions)
    assert any("umbral heurístico" in e for e in rec.explanation)


def test_nuts_bets_for_value():
    rec = recommend_heuristic(scen("AsAd", "AhKc2d", ["random", "random"]))
    assert freq(rec, "bet") == 1.0


def test_air_checks():
    rec = recommend_heuristic(scen("3c4d", "AhKcJd", ["QQ+,AK", "TT+,AQ+"]))
    assert freq(rec, "check") == 1.0


def test_air_folds_to_overbet():
    rec = recommend_heuristic(
        scen("3c4d", "AhKcJd", ["QQ+,AK", "TT+,AQ+"], pot=40.0, to_call=20.0)
    )
    assert freq(rec, "fold") == 1.0


def test_monster_raises_facing_a_bet():
    rec = recommend_heuristic(
        scen("AsAd", "AhKc2d", ["random", "random"], pot=15.0, to_call=5.0)
    )
    assert freq(rec, "raise") >= 0.5


def test_semibluff_needs_outs_and_last_position():
    rec = recommend_heuristic(scen("9h8h", "Th7h2c", ["QQ+,AK", "TT+,AQ+"]))
    assert freq(rec, "bet") == 1.0  # OESD + flush draw, BTN is last
    rec = recommend_heuristic(
        scen("9h8h", "Th7h2c", ["QQ+,AK", "TT+,AQ+"], hero_pos="SB", positions=("BB", "BTN"))
    )
    assert freq(rec, "bet") == 0.0


def test_near_threshold_is_mixed(monkeypatch):
    from app.config import get_settings

    rec = recommend_heuristic(scen("AsAd", "AhKc2d", ["random", "random"]))
    share = float(rec.reference.split("le ganás a ")[1].split("%")[0]) / 100
    monkeypatch.setattr(get_settings(), "heuristic_value_share", share - 0.01)
    mixed = recommend_heuristic(scen("AsAd", "AhKc2d", ["random", "random"]))
    assert freq(mixed, "bet") == 0.5 and freq(mixed, "check") == 0.5
    assert any("cerca del umbral" in w for w in mixed.warnings)
```

Nota: `test_near_threshold_is_mixed` depende de que `reference` incluya "le ganás a NN% de cada rango" (ver Step 3).

- [ ] **Step 2: Correr y ver que falla**

Run: `uv run pytest -q tests/test_postflop_heuristic.py`
Expected: FAIL (el módulo provisorio devuelve `unavailable`).

- [ ] **Step 3: Reemplazar `app/recommend/postflop_heuristic.py`**

```python
"""Multiway postflop (3+ players): own equity-based heuristics, always approximate.

Inputs: hero's equity against every range at once and, per villain, the share of the
range hero beats right now. Thresholds come from settings (`heuristic_*`) and are cited
as "umbral heurístico" in the explanation: they are not solver output.
"""

from __future__ import annotations

import pokercore

from app.config import get_settings
from app.domain.metrics import pot_metrics
from app.domain.positions import postflop_order
from app.domain.scenario import Scenario
from app.recommend.schemas import ActionOut, RecommendationOut
from app.simulator.outs import compute_outs, showdown_share

THRESHOLD_NOTE = "umbral heurístico, no sale de un solver"


def _hero_is_last(scenario: Scenario) -> bool:
    positions = [scenario.hero_position, *(v.position for v in scenario.villains)]
    if not all(positions):
        return False
    order = postflop_order(scenario.num_players)
    return max(positions, key=order.index) == scenario.hero_position


def _pick(primary: str, secondary: str, near: bool) -> list[ActionOut]:
    if near:
        return [ActionOut(action=primary, frequency=0.5), ActionOut(action=secondary, frequency=0.5)]
    return [ActionOut(action=primary, frequency=1.0), ActionOut(action=secondary, frequency=0.0)]


def recommend_heuristic(scenario: Scenario) -> RecommendationOut:
    s = get_settings()
    ranges = [v.range for v in scenario.villains]
    shares = [
        showdown_share(pokercore.hand_strength(scenario.hero_hand, r, scenario.board))
        for r in ranges
    ]
    min_share = min(shares)
    equity = pokercore.equity(
        [scenario.hero_hand, *ranges], scenario.board,
        iterations=s.equity_iterations, exact_limit=s.equity_exact_limit,
    ).players[0].equity
    last = _hero_is_last(scenario)
    outs = compute_outs(scenario.hero_hand, ranges, scenario.board)
    explanation: list[str] = []
    warnings: list[str] = []

    if scenario.to_call_bb <= 0:
        near = abs(min_share - s.heuristic_value_share) < s.heuristic_margin
        if min_share >= s.heuristic_value_share or near:
            actions = _pick("bet", "check", near)
            explanation.append(
                f"Valor: le ganás a ≥ {s.heuristic_value_share:.0%} de cada rango ({THRESHOLD_NOTE})."
            )
        elif outs.available and outs.count >= s.heuristic_semibluff_outs and last:
            actions = _pick("bet", "check", False)
            explanation.append(
                f"Semi-bluff: {outs.count} outs y actuás último ({THRESHOLD_NOTE})."
            )
        else:
            actions = _pick("check", "bet", False)
            explanation.append("Check: sin valor claro contra todos los rangos ni draw fuerte.")
        if near:
            warnings.append("Spot cerca del umbral: mezclá las dos acciones.")
    else:
        metrics = pot_metrics(scenario.pot_bb, scenario.to_call_bb, scenario.effective_stack_bb)
        factor = s.heuristic_realization_last if last else s.heuristic_realization_oop
        need = (metrics.required_equity or 0.0) / factor
        near_raise = abs(min_share - s.heuristic_raise_share) < s.heuristic_margin
        if min_share >= s.heuristic_raise_share or near_raise:
            actions = [
                ActionOut(action="raise", frequency=0.5 if near_raise else 1.0),
                ActionOut(action="call", frequency=0.5 if near_raise else 0.0),
                ActionOut(action="fold", frequency=0.0),
            ]
            explanation.append(
                f"Valor: le ganás a ≥ {s.heuristic_raise_share:.0%} de cada rango ({THRESHOLD_NOTE})."
            )
            if near_raise:
                warnings.append("Spot cerca del umbral: mezclá raise y call.")
        else:
            near_call = abs(equity - need) < s.heuristic_margin
            if equity >= need or near_call:
                call = 0.5 if near_call else 1.0
                actions = [
                    ActionOut(action="call", frequency=call),
                    ActionOut(action="fold", frequency=1.0 - call),
                ]
            else:
                actions = [ActionOut(action="call", frequency=0.0), ActionOut(action="fold", frequency=1.0)]
            explanation.append(
                f"Pot odds: necesitás {need:.0%} de equity (ajustada por realización ×{factor:g}, "
                f"{THRESHOLD_NOTE}); tenés {equity:.0%}."
            )
            if near_call:
                warnings.append("Spot cerca del umbral: mezclá call y fold.")

    if min_share >= 0.5 and len(scenario.board) < 10 and equity < min_share - 0.1:
        explanation.append("Protección: vas adelante pero los rangos rivales tienen muchos outs.")
    if any(a.action in ("bet", "raise") and a.frequency > 0 for a in actions) and min_share < 0.5:
        if "A" in {scenario.hero_hand[0], scenario.hero_hand[2]}:
            explanation.append("Blockers: tu A reduce los combos fuertes del rival.")

    return RecommendationOut(
        available=True,
        source="heuristic",
        confidence="approximate",
        actions=actions,
        reference=(
            f"Heurística multiway: equity {equity:.0%} contra todos; le ganás a "
            f"{min_share * 100:.1f}% de cada rango (mínimo)."
        ),
        explanation=explanation,
        warnings=warnings,
    )
```

Nota: `len(scenario.board) < 10` significa "no es river" (el board se guarda como string de 2 caracteres por carta).

- [ ] **Step 4: Correr y ver que pasa**

Run: `uv run pytest -q tests/test_postflop_heuristic.py`
Expected: all passed. Si `test_semibluff_needs_outs_and_last_position` falla porque `compute_outs` no cuenta ≥ 8 outs con esos rangos, cambiar el board/rangos del test por uno donde `compute_outs` devuelva ≥ 8 (verificarlo con `uv run python -c "from app.simulator.outs import compute_outs; print(compute_outs('9h8h',['QQ+,AK','TT+,AQ+'],'Th7h2c').count)"`), no el umbral.

- [ ] **Step 5: Commit**

```bash
git add backend/app/recommend/postflop_heuristic.py backend/tests/test_postflop_heuristic.py
git commit -m "feat(recommend): multiway postflop heuristic (always approximate)"
```

---

### Task 12: Flops representativos y biblioteca

**Files:**
- Create: `backend/app/solver/flops.py`
- Create: `data/solver/library.json`
- Create: `backend/app/solver/library.py`
- Test: `backend/tests/test_solver_flops.py`, `backend/tests/test_solver_library.py`

**Interfaces:**
- Consumes: `prefill_ranges`, `PrefillQuery`, `PotType` (Task 10), `SolverSpot`, `to_solver_range` (Task 3), `get_preset` (Task 2), `enqueue`, `Origin`, `JobStatus`, `ACTIVE` (Task 8), `SolverJob`, `SolverResult` (Task 7), `postflop_order`.
- Produces:
  - `representative_flops(n: int = 25) -> list[str]` (cada flop como `"AhKd2c"`, determinístico)
  - `LineSpec(id: str, label: str, aggressor: str, caller: str, pot_type: PotType, stack_bb: float, open_size_bb: float, threebet_size_bb: float | None = None)`
  - `Family(id: str, label: str, game_format: GameFormat, players: int, ante_total_bb: float, preset: str, lines: list[LineSpec])`
  - `load_library(path: Path | None = None) -> list[Family]`
  - `LineSpots(spots: dict[str, SolverSpot], missing: list[str], approximate: bool)`; `build_line_spots(session, family: Family, line: LineSpec, flops: list[str]) -> LineSpots`
  - `library_key(family_id, line_id, flop) -> str` (`"mtt/btn_bb_25/AhKd2c"`)
  - `EntryStatus`: `"solved" | "queued" | "running" | "missing_chart" | "outdated" | "pending"`
  - `library_status(session, families) -> list[dict]` (familia → líneas → entradas `{flop, status, spot_hash, job_id}` + `missing`)
  - `enqueue_line(session, family, line, flops=None, origin=Origin.LIBRARY) -> int` (cantidad encolada)

- [ ] **Step 1: Tests de flops (fallan)**

```python
# backend/tests/test_solver_flops.py
from app.solver.flops import representative_flops


def suits(flop):
    return {flop[1], flop[3], flop[5]}


def ranks(flop):
    return [flop[0], flop[2], flop[4]]


def test_25_unique_and_deterministic():
    a = representative_flops()
    assert len(a) == 25 and len(set(a)) == 25
    assert a == representative_flops()


def test_covers_textures():
    flops = representative_flops()
    assert any(len(suits(f)) == 1 for f in flops)  # monotone
    assert any(len(suits(f)) == 2 for f in flops)  # two-tone
    assert any(len(suits(f)) == 3 for f in flops)  # rainbow
    assert any(len(set(ranks(f))) == 2 for f in flops)  # paired
    assert any(ranks(f)[0] == "A" for f in flops)
    assert any(ranks(f)[0] in "98765432" for f in flops)  # low boards
```

- [ ] **Step 2: Correr y ver que falla**

Run: `uv run pytest -q tests/test_solver_flops.py`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Escribir `app/solver/flops.py`**

```python
"""A reproducible subset of flops covering the main textures.

All 22,100 flops are reduced to suit-isomorphic classes (weighted by how many real
flops they stand for), grouped by texture, and picked round-robin from the most
frequent textures so the subset reflects how often each texture comes up.
"""

from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
from itertools import combinations

RANKS = "23456789TJQKA"
SUITS = "shdc"  # canonical suit names in order of first appearance
DECK = [r + s for r in RANKS for s in "cdhs"]


def _canonical(cards: tuple[str, ...]) -> str:
    ordered = sorted(cards, key=lambda c: (RANKS.index(c[0]), "cdhs".index(c[1])), reverse=True)
    mapping: dict[str, str] = {}
    out = []
    for c in ordered:
        mapping.setdefault(c[1], SUITS[len(mapping)])
        out.append(c[0] + mapping[c[1]])
    return "".join(out)


def _texture(flop: str) -> tuple[str, str, str]:
    ranks = [flop[0], flop[2], flop[4]]
    suits = {flop[1], flop[3], flop[5]}
    hi = RANKS.index(ranks[0])
    high = "A" if hi == 12 else "K-Q" if hi >= 10 else "J-T" if hi >= 8 else "9-"
    suit = {1: "mono", 2: "two-tone", 3: "rainbow"}[len(suits)]
    idx = sorted({RANKS.index(r) for r in ranks})
    if len(idx) < 3:
        shape = "paired"
    elif idx[-1] - idx[0] <= 4:
        shape = "connected"
    else:
        shape = "disconnected"
    return high, suit, shape


@lru_cache
def _classes() -> dict[str, int]:
    weights: dict[str, int] = defaultdict(int)
    for cards in combinations(DECK, 3):
        weights[_canonical(cards)] += 1
    return dict(weights)


def representative_flops(n: int = 25) -> list[str]:
    groups: dict[tuple[str, str, str], list[tuple[int, str]]] = defaultdict(list)
    for flop, weight in _classes().items():
        groups[_texture(flop)].append((weight, flop))
    for members in groups.values():
        members.sort(key=lambda x: (-x[0], x[1]))
    order = sorted(groups, key=lambda k: (-sum(w for w, _ in groups[k]), k))
    picked: list[str] = []
    depth = 0
    while len(picked) < n:
        added = False
        for key in order:
            if depth < len(groups[key]) and len(picked) < n:
                picked.append(groups[key][depth][1])
                added = True
        if not added:
            break
        depth += 1
    return picked
```

Nota: los palos canónicos (`s,h,d,c`) son solo nombres; para el solver cualquier asignación isomorfa da la misma estrategia.

- [ ] **Step 4: Correr y ver que pasa**

Run: `uv run pytest -q tests/test_solver_flops.py`
Expected: 2 passed.

- [ ] **Step 5: Escribir `data/solver/library.json`**

```json
{
  "families": [
    {
      "id": "mtt",
      "label": "MTT",
      "game_format": "mtt",
      "players": 9,
      "ante_total_bb": 1.0,
      "preset": "simple",
      "lines": [
        {"id": "btn_bb_25", "label": "BTN vs BB · SRP · 25bb", "aggressor": "BTN", "caller": "BB", "pot_type": "srp", "stack_bb": 25, "open_size_bb": 2.0},
        {"id": "co_bb_25", "label": "CO vs BB · SRP · 25bb", "aggressor": "CO", "caller": "BB", "pot_type": "srp", "stack_bb": 25, "open_size_bb": 2.0},
        {"id": "sb_bb_25", "label": "SB vs BB · SRP · 25bb", "aggressor": "SB", "caller": "BB", "pot_type": "srp", "stack_bb": 25, "open_size_bb": 2.5},
        {"id": "btn_bb_40", "label": "BTN vs BB · SRP · 40bb", "aggressor": "BTN", "caller": "BB", "pot_type": "srp", "stack_bb": 40, "open_size_bb": 2.2},
        {"id": "co_bb_40", "label": "CO vs BB · SRP · 40bb", "aggressor": "CO", "caller": "BB", "pot_type": "srp", "stack_bb": 40, "open_size_bb": 2.2},
        {"id": "sb_bb_40", "label": "SB vs BB · SRP · 40bb", "aggressor": "SB", "caller": "BB", "pot_type": "srp", "stack_bb": 40, "open_size_bb": 2.5},
        {"id": "bb_btn_3b_40", "label": "BB vs BTN · 3-bet pot · 40bb", "aggressor": "BB", "caller": "BTN", "pot_type": "3bet", "stack_bb": 40, "open_size_bb": 2.2, "threebet_size_bb": 9.0}
      ]
    },
    {
      "id": "cash",
      "label": "Cash 6-max 100bb",
      "game_format": "cash",
      "players": 6,
      "ante_total_bb": 0.0,
      "preset": "simple",
      "lines": [
        {"id": "btn_bb", "label": "BTN vs BB · SRP", "aggressor": "BTN", "caller": "BB", "pot_type": "srp", "stack_bb": 100, "open_size_bb": 2.5},
        {"id": "co_bb", "label": "CO vs BB · SRP", "aggressor": "CO", "caller": "BB", "pot_type": "srp", "stack_bb": 100, "open_size_bb": 2.5},
        {"id": "sb_bb", "label": "SB vs BB · SRP", "aggressor": "SB", "caller": "BB", "pot_type": "srp", "stack_bb": 100, "open_size_bb": 3.0},
        {"id": "sb_btn_3b", "label": "SB vs BTN · 3-bet pot", "aggressor": "SB", "caller": "BTN", "pot_type": "3bet", "stack_bb": 100, "open_size_bb": 2.5, "threebet_size_bb": 11.0}
      ]
    }
  ]
}
```

Son 7 + 4 = 11 líneas: el spec decía 13 contando 2 stacks × 3 SRP + 3-bet en MTT (6 + 1) y 3 SRP + 3-bet en cash (4) = 11. Corregir en el README el total: 11 líneas × 25 flops = 275 solves (~9 h con `simple`, ~3,5 h con `chico`).

- [ ] **Step 6: Tests de biblioteca (fallan)**

```python
# backend/tests/test_solver_library.py
import pytest

from app.db.models import PreflopChart, SolverJob
from app.solver.flops import representative_flops
from app.solver.library import build_line_spots, enqueue_line, library_status, load_library

FLOP = representative_flops()[0]  # library_status only lists the representative flops


def grid(classes):
    import pokercore

    return [classes.get(n, 0.0) for n in pokercore.hand_class_names()]


def add_cash_btn_bb_charts(session, raise_classes=None):
    common = dict(source="custom", game_format="cash", players=6, stack_bb=100.0, ante_bb=0.0,
                  note="", rake=None, open_size_bb=2.5)
    session.add(PreflopChart(name="btn rfi", position="BTN", vs_position=None, situation="rfi",
                             actions={"raise": grid(raise_classes or {"AA": 1, "KK": 1, "AKs": 1})}, **common))
    session.add(PreflopChart(name="bb vs btn", position="BB", vs_position="BTN", situation="vs_open",
                             actions={"call": grid({"QQ": 1, "JJ": 1, "AQs": 1})}, **common))
    session.commit()


@pytest.fixture
def cash():
    fam = next(f for f in load_library() if f.id == "cash")
    return fam, next(line for line in fam.lines if line.id == "btn_bb")


def test_library_definition_loads():
    fams = load_library()
    assert {f.id for f in fams} == {"mtt", "cash"}
    assert sum(len(f.lines) for f in fams) == 11


def test_build_line_spots_pot_and_stack(db_session, cash):
    add_cash_btn_bb_charts(db_session)
    fam, line = cash
    built = build_line_spots(db_session, fam, line, ["AhKd2c"])
    spot = built.spots["AhKd2c"]
    assert spot.pot_bb == 5.5  # 2.5 + 2.5 + SB 0.5
    assert spot.stack_bb == 97.5
    assert spot.range_ip.startswith("AA")  # BTN (aggressor) is IP vs BB
    assert spot.range_oop.startswith("QQ") or "AQs" in spot.range_oop
    assert built.missing == []


def test_missing_chart_is_reported_and_not_enqueued(db_session, cash):
    fam, line = cash
    built = build_line_spots(db_session, fam, line, ["AhKd2c"])
    assert built.spots == {}
    assert built.missing == ["falta tabla: BTN RFI (cash, 100bb)", "falta tabla: BB vs open de BTN (cash, 100bb)"]
    assert enqueue_line(db_session, fam, line) == 0


def test_enqueue_line_and_status(db_session, cash):
    add_cash_btn_bb_charts(db_session)
    fam, line = cash
    assert enqueue_line(db_session, fam, line, [FLOP, "7s7h2d"]) == 2
    assert db_session.query(SolverJob).count() == 2
    status = library_status(db_session, [fam])
    entries = {e["flop"]: e["status"] for e in status[0]["lines"][0]["entries"]}
    assert entries[FLOP] == "queued"


def test_outdated_when_chart_changes(db_session, cash):
    from app.solver.cache import store_result
    from app.solver.output_parser import SolverAction, StrategyNode
    from app.solver.runner import Progress
    from app.solver.library import library_key

    add_cash_btn_bb_charts(db_session)
    fam, line = cash
    spot = build_line_spots(db_session, fam, line, [FLOP]).spots[FLOP]
    tree = StrategyNode("oop", [SolverAction("check")], {"AsAd": [1.0]})
    store_result(db_session, spot, tree, Progress(), 1.0, library_key(fam.id, line.id, FLOP))
    chart = db_session.query(PreflopChart).filter_by(position="BTN").one()
    chart.actions = {"raise": grid({"AA": 1})}
    db_session.commit()
    status = library_status(db_session, [fam])
    line_status = next(lst for lst in status[0]["lines"] if lst["id"] == "btn_bb")
    entry = next(e for e in line_status["entries"] if e["flop"] == FLOP)
    assert entry["status"] == "outdated"
```

- [ ] **Step 7: Correr y ver que falla**

Run: `uv run pytest -q tests/test_solver_library.py`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 8: Escribir `app/solver/library.py`**

```python
"""Library of common spots, solved from the user's own preflop charts.

Pot at the flop = both players' preflop investment + dead blinds + antes.
Stack at the flop = starting stack - investment. Lines without charts are reported
("falta tabla …") and never enqueued: no ranges are made up.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import SolverJob, SolverResult
from app.domain.positions import postflop_order
from app.domain.scenario import GameFormat
from app.recommend.ranges_prefill import PotType, PrefillQuery, prefill_ranges
from app.solver.flops import representative_flops
from app.solver.queue import ACTIVE, JobStatus, Origin, enqueue
from app.solver.spot import SolverSpot, to_solver_range
from app.solver.trees import get_preset

BLINDS = {"SB": 0.5, "BB": 1.0}


class LineSpec(BaseModel):
    id: str
    label: str
    aggressor: str
    caller: str
    pot_type: PotType
    stack_bb: float = Field(gt=0)
    open_size_bb: float = Field(gt=0)
    threebet_size_bb: float | None = Field(default=None, gt=0)


class Family(BaseModel):
    id: str
    label: str
    game_format: GameFormat
    players: int
    ante_total_bb: float = 0.0
    preset: str = "simple"
    lines: list[LineSpec]


def load_library(path: Path | None = None) -> list[Family]:
    data = json.loads((path or get_settings().solver_library_file).read_text(encoding="utf-8"))
    return [Family(**f) for f in data["families"]]


def library_key(family_id: str, line_id: str, flop: str) -> str:
    return f"{family_id}/{line_id}/{flop}"


@dataclass
class LineSpots:
    spots: dict[str, SolverSpot]
    missing: list[str]
    approximate: bool


def _pot_and_stack(family: Family, line: LineSpec) -> tuple[float, float]:
    invested = line.open_size_bb if line.pot_type == PotType.SRP else line.threebet_size_bb
    if invested is None:
        raise ValueError(f"La línea {line.id} necesita threebet_size_bb")
    dead_blinds = sum(v for p, v in BLINDS.items() if p not in (line.aggressor, line.caller))
    return round(2 * invested + dead_blinds + family.ante_total_bb, 2), line.stack_bb - invested


def build_line_spots(
    session: Session, family: Family, line: LineSpec, flops: list[str]
) -> LineSpots:
    ante = family.ante_total_bb / family.players
    result = prefill_ranges(
        session,
        PrefillQuery(
            game_format=family.game_format, players=family.players, aggressor=line.aggressor,
            caller=line.caller, pot_type=line.pot_type, stack_bb=line.stack_bb, ante_bb=ante,
        ),
    )
    where = f"({family.game_format}, {line.stack_bb:g}bb)"
    missing = [f"falta tabla: {r.missing} {where}" for r in (result.aggressor, result.caller) if r.missing]
    if missing:
        return LineSpots({}, missing, False)
    aggr = to_solver_range(result.aggressor.text)
    call = to_solver_range(result.caller.text)
    order = postflop_order(family.players)
    aggressor_is_oop = order.index(line.aggressor) < order.index(line.caller)
    pot, stack = _pot_and_stack(family, line)
    preset = get_preset(family.preset)
    spots = {
        flop: SolverSpot(
            board=(flop[0:2], flop[2:4], flop[4:6]),
            pot_bb=pot,
            stack_bb=stack,
            range_oop=aggr.text if aggressor_is_oop else call.text,
            range_ip=call.text if aggressor_is_oop else aggr.text,
            preset=preset,
        )
        for flop in flops
    }
    approximate = (
        result.aggressor.approximate or result.caller.approximate
        or aggr.approximated or call.approximated
    )
    return LineSpots(spots, [], approximate)


def enqueue_line(
    session: Session, family: Family, line: LineSpec, flops: list[str] | None = None,
    origin: Origin = Origin.LIBRARY,
) -> int:
    built = build_line_spots(session, family, line, flops or representative_flops())
    count = 0
    for flop, spot in built.spots.items():
        job = enqueue(session, spot, origin, library_key(family.id, line.id, flop))
        count += job.status != JobStatus.DONE
    return count


def library_status(session: Session, families: list[Family]) -> list[dict]:
    flops = representative_flops()
    out = []
    for family in families:
        lines = []
        for line in family.lines:
            built = build_line_spots(session, family, line, flops)
            entries = []
            for flop in flops:
                key = library_key(family.id, line.id, flop)
                spot = built.spots.get(flop)
                entries.append(_entry_status(session, key, flop, spot))
            lines.append({
                "id": line.id, "label": line.label, "missing": built.missing,
                "approximate": built.approximate, "entries": entries,
            })
        out.append({"id": family.id, "label": family.label, "preset": family.preset, "lines": lines})
    return out


def _entry_status(session: Session, key: str, flop: str, spot: SolverSpot | None) -> dict:
    if spot is None:
        return {"flop": flop, "status": "missing_chart", "spot_hash": None, "job_id": None}
    h = spot.spot_hash()
    if session.get(SolverResult, h) is not None:
        return {"flop": flop, "status": "solved", "spot_hash": h, "job_id": None}
    job = session.scalars(
        select(SolverJob).where(SolverJob.spot_hash == h, SolverJob.status.in_(ACTIVE))
    ).first()
    if job is not None:
        return {"flop": flop, "status": job.status, "spot_hash": h, "job_id": job.id}
    old = session.scalars(select(SolverResult.hash).where(SolverResult.library_key == key)).first()
    status = "outdated" if old is not None else "pending"
    return {"flop": flop, "status": status, "spot_hash": old, "job_id": None}
```

- [ ] **Step 9: Correr y ver que pasa**

Run: `uv run pytest -q tests/test_solver_flops.py tests/test_solver_library.py`
Expected: all passed. (Si `grid_to_text` ordena clases distinto, ajustar solo las aserciones `startswith` del test al texto real.)

- [ ] **Step 10: Commit**

```bash
git add backend/app/solver/flops.py backend/app/solver/library.py data/solver/library.json backend/tests/test_solver_flops.py backend/tests/test_solver_library.py
git commit -m "feat(solver): representative flops and the spot library built from user charts"
```

---

### Task 13: API `/api/solver` y arranque del worker

**Files:**
- Create: `backend/app/api/solver.py`
- Modify: `backend/app/main.py` (router y lifespan)
- Test: `backend/tests/test_solver_api.py`

**Interfaces:**
- Consumes: todo lo anterior; `get_session`; `worker_registry.start_worker/stop_worker/solver_available`.
- Produces (todas bajo `/api/solver`):
  - `GET /status` → `{configured: bool, path: str|null, threads: int, paused: bool, cache_entries: int, cache_bytes: int, presets: [{name, label}]}`
  - `GET /jobs?status=` → `JobOut[]` (`id, label, origin, priority, status, iteration, exploitability, error, position, created_at, started_at, finished_at, spot_hash`), ordenados: activos primero por prioridad, luego los últimos 50 terminados.
  - `GET /jobs/{id}` → `JobOut`; `POST /jobs/{id}/cancel` → `JobOut`; `POST /jobs/{id}/retry` → `JobOut`
  - `POST /queue/pause` y `POST /queue/resume` → `{paused: bool}`
  - `DELETE /cache` → `{deleted: int}`; `DELETE /cache/{hash}` → 204 / 404
  - `POST /prefill-ranges` (`PrefillIn`: `game_format, players, aggressor, caller, pot_type, stack_bb, ante_bb`) → `{aggressor: PrefillRangeOut, caller: PrefillRangeOut}`
  - `POST /batch` (`BatchIn`: `game_format, players, ante_total_bb, preset, line: LineSpec sin id/label, flops: list[str] | null`) → `{enqueued: int, missing: list[str]}`
  - `GET /library` → estado de `library_status`; `POST /library/enqueue` (`{family: str, line: str | null}`) → `{enqueued: int, missing: list[str]}`
  - `GET /results/{hash}/node?path=` (`path` = índices separados por punto, vacío = raíz) → `NodeOut {player, label, path, actions: [{index, kind, label, amount_bb, frequency, has_child}], layers: StrategyLayerOut[]}`

- [ ] **Step 1: Escribir el test (falla)**

```python
# backend/tests/test_solver_api.py
import json
from pathlib import Path

from app.solver.spot import SolverSpot, to_solver_range
from app.solver.trees import get_preset

FIXTURES = Path(__file__).parent / "fixtures" / "solver"


def river_spot():
    return SolverSpot(
        ("Qs", "Jh", "2h", "7c", "3d"), 20.0, 90.0,
        to_solver_range("AQs,KQs,QJs,JTs,T9s,99,88,77,22,A5s,KJo:0.5").text,
        to_solver_range("AA,KK,QQ,AK,AJs,KQo,JJ,TT,76s,A2s").text,
        get_preset("simple"),
    )


def store(spot):
    from app.db.session import _session_factory
    from app.solver.cache import store_result
    from app.solver.output_parser import parse_output
    from app.solver.runner import Progress

    tree = parse_output(json.loads((FIXTURES / "river_out.json").read_text()), 90.0)
    with _session_factory()() as s:
        store_result(s, spot, tree, Progress(200, 0.4, 1), 18.0)


def test_status_without_solver(client):
    body = client.get("/api/solver/status").json()
    assert body["configured"] is False
    assert {p["name"] for p in body["presets"]} == {"simple", "chico", "amplio"}
    assert body["cache_entries"] == 0


def test_pause_resume(client):
    assert client.post("/api/solver/queue/pause").json() == {"paused": True}
    assert client.get("/api/solver/status").json()["paused"] is True
    assert client.post("/api/solver/queue/resume").json() == {"paused": False}


def test_jobs_lifecycle(client):
    from app.db.session import _session_factory
    from app.solver.queue import Origin, enqueue

    with _session_factory()() as s:
        job_id = enqueue(s, river_spot(), Origin.BATCH).id
    jobs = client.get("/api/solver/jobs").json()
    assert jobs[0]["id"] == job_id and jobs[0]["position"] == 1
    assert client.post(f"/api/solver/jobs/{job_id}/cancel").json()["status"] == "cancelled"
    assert client.post(f"/api/solver/jobs/{job_id}/retry").json()["status"] == "queued"
    assert client.get("/api/solver/jobs/999").status_code == 404


def test_node_navigation(client):
    spot = river_spot()
    store(spot)
    root = client.get(f"/api/solver/results/{spot.spot_hash()}/node").json()
    assert root["player"] == "oop" and root["path"] == ""
    assert abs(sum(a["frequency"] for a in root["actions"]) - 1) < 1e-3
    check = next(a for a in root["actions"] if a["kind"] == "check")
    child = client.get(
        f"/api/solver/results/{spot.spot_hash()}/node", params={"path": str(check["index"])}
    ).json()
    assert child["player"] == "ip"
    assert len(child["layers"][0]["grid"]) == 169
    assert client.get(f"/api/solver/results/{spot.spot_hash()}/node?path=9.9").status_code == 404


def test_cache_delete(client):
    spot = river_spot()
    store(spot)
    assert client.get("/api/solver/status").json()["cache_entries"] == 1
    assert client.delete(f"/api/solver/cache/{spot.spot_hash()}").status_code == 204
    assert client.delete(f"/api/solver/cache/{spot.spot_hash()}").status_code == 404
    store(spot)
    assert client.delete("/api/solver/cache").json() == {"deleted": 1}


def test_library_reports_missing_charts(client):
    body = client.get("/api/solver/library").json()
    assert {f["id"] for f in body} == {"mtt", "cash"}
    line = body[1]["lines"][0]
    assert line["missing"] and line["entries"][0]["status"] == "missing_chart"
    r = client.post("/api/solver/library/enqueue", json={"family": "cash", "line": "btn_bb"}).json()
    assert r["enqueued"] == 0 and r["missing"]


def test_prefill_endpoint(client):
    r = client.post("/api/solver/prefill-ranges", json={
        "game_format": "cash", "players": 6, "aggressor": "BTN", "caller": "BB",
        "pot_type": "srp", "stack_bb": 100,
    }).json()
    assert r["aggressor"]["text"] is None and r["aggressor"]["missing"] == "BTN RFI"


def test_simulator_postflop_without_solver(client):
    r = client.post("/api/simulator/analyze", json={
        "num_players": 6, "hero_position": "BB", "hero_hand": "QhQc",
        "hero_range": "AQs,KQs,QJs,JTs,T9s,99,88,77,22,A5s,KJo:0.5",
        "villains": [{"position": "BTN", "range": "AA,KK,QQ,AK,AJs,KQo,JJ,TT,76s,A2s"}],
        "board": "QsJh2h7c3d", "pot_bb": 20, "to_call_bb": 0, "effective_stack_bb": 90,
    }).json()
    assert r["recommendation"]["available"] is False
    assert "POKER_SOLVER_PATH" in r["recommendation"]["message"]
```

- [ ] **Step 2: Correr y ver que falla**

Run: `uv run pytest -q tests/test_solver_api.py`
Expected: FAIL (404 en `/api/solver/...`).

- [ ] **Step 3: Escribir `app/api/solver.py`**

```python
from datetime import datetime
from typing import Annotated

import pokercore
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.db.models import SolverJob
from app.domain.scenario import GameFormat
from app.recommend.ranges_prefill import PotType, PrefillQuery, prefill_ranges
from app.recommend.schemas import StrategyLayerOut
from app.solver import queue as q
from app.solver.cache import cache_stats, clear_cache, delete_result, get_result
from app.solver.flops import representative_flops
from app.solver.library import (
    Family,
    LineSpec,
    build_line_spots,
    enqueue_line,
    library_status,
    load_library,
)
from app.solver.output_parser import canonical_combo
from app.solver.trees import load_presets
from app.solver.worker_registry import solver_available

router = APIRouter(prefix="/solver", tags=["solver"])
DbSession = Annotated[Session, Depends(get_session)]


class JobOut(BaseModel):
    id: int
    label: str
    origin: str
    priority: int
    status: str
    iteration: int
    exploitability: float | None
    error: str | None
    position: int | None
    spot_hash: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


def _job_out(session: Session, job: SolverJob) -> JobOut:
    return JobOut(
        id=job.id, label=job.label, origin=job.origin, priority=job.priority, status=job.status,
        iteration=job.iteration, exploitability=job.exploitability, error=job.error,
        position=q.queue_position(session, job), spot_hash=job.spot_hash,
        created_at=job.created_at, started_at=job.started_at, finished_at=job.finished_at,
    )


def _job(session: Session, job_id: int) -> SolverJob:
    job = session.get(SolverJob, job_id)
    if job is None:
        raise HTTPException(404, f"No existe el trabajo {job_id}")
    return job


@router.get("/status")
def status(session: DbSession) -> dict:
    s = get_settings()
    entries, size = cache_stats(session)
    return {
        "configured": solver_available(),
        "path": str(s.solver_path) if s.solver_path else None,
        "threads": s.solver_threads,
        "paused": q.is_paused(session),
        "cache_entries": entries,
        "cache_bytes": size,
        "presets": [{"name": p.name, "label": p.label} for p in load_presets().values()],
    }


@router.get("/jobs", response_model=list[JobOut])
def jobs(session: DbSession) -> list[JobOut]:
    active = session.scalars(
        select(SolverJob).where(SolverJob.status.in_(q.ACTIVE))
        .order_by(SolverJob.status.desc(), SolverJob.priority, SolverJob.id)
    ).all()
    done = session.scalars(
        select(SolverJob).where(SolverJob.status.not_in(q.ACTIVE))
        .order_by(SolverJob.id.desc()).limit(50)
    ).all()
    return [_job_out(session, j) for j in [*active, *done]]


@router.get("/jobs/{job_id}", response_model=JobOut)
def job(job_id: int, session: DbSession) -> JobOut:
    return _job_out(session, _job(session, job_id))


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
def cancel(job_id: int, session: DbSession) -> JobOut:
    _job(session, job_id)
    return _job_out(session, q.cancel_job(session, job_id))


@router.post("/jobs/{job_id}/retry", response_model=JobOut)
def retry(job_id: int, session: DbSession) -> JobOut:
    _job(session, job_id)
    return _job_out(session, q.retry_job(session, job_id))


@router.post("/queue/pause")
def pause(session: DbSession) -> dict:
    q.set_paused(session, True)
    return {"paused": True}


@router.post("/queue/resume")
def resume(session: DbSession) -> dict:
    q.set_paused(session, False)
    return {"paused": False}


@router.delete("/cache")
def delete_cache(session: DbSession) -> dict:
    return {"deleted": clear_cache(session)}


@router.delete("/cache/{spot_hash}", status_code=204)
def delete_cached(spot_hash: str, session: DbSession) -> Response:
    if not delete_result(session, spot_hash):
        raise HTTPException(404, "Ese resultado no está en la caché")
    return Response(status_code=204)


class PrefillIn(BaseModel):
    game_format: GameFormat
    players: int = Field(ge=2, le=10)
    aggressor: str
    caller: str
    pot_type: PotType
    stack_bb: float = Field(gt=0)
    ante_bb: float = Field(default=0.0, ge=0)


@router.post("/prefill-ranges")
def prefill(body: PrefillIn, session: DbSession) -> dict:
    result = prefill_ranges(session, PrefillQuery(**body.model_dump()))
    return {"aggressor": result.aggressor.__dict__, "caller": result.caller.__dict__}


class BatchLine(BaseModel):
    aggressor: str
    caller: str
    pot_type: PotType
    stack_bb: float = Field(gt=0)
    open_size_bb: float = Field(gt=0)
    threebet_size_bb: float | None = Field(default=None, gt=0)


class BatchIn(BaseModel):
    game_format: GameFormat
    players: int = Field(ge=2, le=10)
    ante_total_bb: float = Field(default=0.0, ge=0)
    preset: str = "simple"
    line: BatchLine
    flops: list[str] | None = None


@router.post("/batch")
def batch(body: BatchIn, session: DbSession) -> dict:
    line = LineSpec(id="batch", label="Lote", **body.line.model_dump())
    family = Family(
        id="batch", label="Lote", game_format=body.game_format, players=body.players,
        ante_total_bb=body.ante_total_bb, preset=body.preset, lines=[line],
    )
    flops = [f.replace(" ", "") for f in body.flops] if body.flops else None
    if flops:
        for f in flops:
            if len(f) != 6:
                raise ValueError(f"Flop inválido: {f}")
    missing = build_line_spots(session, family, line, flops or ["AhKd2c"]).missing
    enqueued = 0 if missing else enqueue_line(session, family, line, flops, q.Origin.BATCH)
    return {"enqueued": enqueued, "missing": missing}


@router.get("/library")
def library(session: DbSession) -> list[dict]:
    return library_status(session, load_library())


class LibraryEnqueueIn(BaseModel):
    family: str
    line: str | None = None


@router.post("/library/enqueue")
def library_enqueue(body: LibraryEnqueueIn, session: DbSession) -> dict:
    family = next((f for f in load_library() if f.id == body.family), None)
    if family is None:
        raise HTTPException(404, f"No existe la familia {body.family}")
    lines = [ln for ln in family.lines if body.line in (None, ln.id)]
    if not lines:
        raise HTTPException(404, f"No existe la línea {body.line}")
    enqueued, missing = 0, []
    for line in lines:
        built = build_line_spots(session, family, line, representative_flops()[:1])
        if built.missing:
            missing += [f"{line.label}: {m}" for m in built.missing]
            continue
        enqueued += enqueue_line(session, family, line)
    return {"enqueued": enqueued, "missing": missing}


class NodeActionOut(BaseModel):
    index: int
    kind: str
    label: str
    amount_bb: float | None
    frequency: float
    has_child: bool


class NodeOut(BaseModel):
    player: str
    path: str
    actions: list[NodeActionOut]
    layers: list[StrategyLayerOut]


@router.get("/results/{spot_hash}/node", response_model=NodeOut)
def node(spot_hash: str, session: DbSession, path: str = "") -> NodeOut:
    cached = get_result(session, spot_hash)
    if cached is None:
        raise HTTPException(404, "Ese resultado no está en la caché")
    current = cached.tree
    for step in filter(None, path.split(".")):
        child = current.children.get(int(step))
        if child is None:
            raise HTTPException(404, "Ese nodo no existe en el árbol")
        current = child
    spot = cached.spot
    rng = spot.range_oop if current.player == "oop" else spot.range_ip
    weights = {
        canonical_combo(c): w for c, w in pokercore.range_combos(rng, "".join(spot.board))
    }
    mix = current.range_mix(weights)
    layers = current.class_layers(weights)
    return NodeOut(
        player=current.player,
        path=path,
        actions=[
            NodeActionOut(
                index=i, kind=a.kind, label=a.label(spot.pot_bb), amount_bb=a.amount_bb,
                frequency=mix[i], has_child=i in current.children,
            )
            for i, a in enumerate(current.actions)
        ],
        layers=[
            StrategyLayerOut(action=a.kind, label=a.label(spot.pot_bb), grid=g)
            for a, g in zip(current.actions, layers, strict=True)
        ],
    )
```

- [ ] **Step 4: Registrar el router y el worker en `main.py`**

```python
from app.api import charts, hands, pushfold, ranges, simulator, solver, stats, system
from app.solver.worker_registry import start_worker, stop_worker


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if get_settings().auto_migrate:
        run_migrations()
    start_worker()  # no-op unless POKER_SOLVER_PATH points to an existing binary
    yield
    stop_worker()
```
y `app.include_router(solver.router, prefix=settings.api_prefix)` junto a los demás. `ValueError` ya se traduce a 422 por el handler existente (`cancel_job`/`retry_job` en estado inválido).

- [ ] **Step 5: Correr y ver que pasa**

Run: `uv run pytest -q tests/test_solver_api.py && uv run pytest -q`
Expected: all passed (suite completa en verde).

- [ ] **Step 6: Lint y commit**

Run: `uv run ruff check . && uv run ruff format --check .` → sin errores (si `format --check` falla, `uv run ruff format .`).
```bash
git add backend/app/api/solver.py backend/app/main.py backend/tests/test_solver_api.py
git commit -m "feat(api): /api/solver (status, jobs, queue, cache, prefill, batch, library, viewer)"
```

---

### Task 14: Test con el binario real y CI

**Files:**
- Modify: `backend/pyproject.toml` (marker `solver`)
- Create: `backend/tests/test_solver_real.py`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `SolverWorker`, `enqueue`, `recommend_solver`, `Scenario`.

- [ ] **Step 1: Registrar el marker**

En `[tool.pytest.ini_options]` de `pyproject.toml`:
```toml
markers = ["solver: runs the real TexasSolver binary (needs POKER_SOLVER_PATH)"]
```

- [ ] **Step 2: Escribir el test**

```python
# backend/tests/test_solver_real.py
import os
from pathlib import Path

import pytest

from app.domain.scenario import Scenario, Villain
from app.recommend.postflop_solver import build_solver_spot, recommend_solver
from app.solver.queue import JobStatus, Origin, SolverWorker, enqueue

SOLVER = os.environ.get("POKER_SOLVER_PATH")
pytestmark = [
    pytest.mark.solver,
    pytest.mark.skipif(not SOLVER or not Path(SOLVER).is_file(), reason="POKER_SOLVER_PATH no definido"),
]


def test_real_river_solve_end_to_end(db_session, tmp_path):
    from app.db.session import _session_factory

    scenario = Scenario(
        num_players=6, hero_position="BTN", hero_hand="AhKc",
        hero_range="AA,KK,QQ,AK,AJs,KQo,JJ,TT,76s,A2s",
        villains=[Villain(position="BB", range="AQs,KQs,QJs,JTs,T9s,99,88,77,22,A5s,KJo:0.5")],
        board="QsJh2h7c3d", pot_bb=30.0, to_call_bb=10.0, effective_stack_bb=90.0,
    )
    built = build_solver_spot(scenario)
    job = enqueue(db_session, built.spot, Origin.SIMULATOR)
    worker = SolverWorker(
        _session_factory(), Path(SOLVER), tmp_path, threads=os.cpu_count() or 2, timeout_s=600
    )
    assert worker.run_once()
    db_session.refresh(job)
    assert job.status == JobStatus.DONE, job.error
    assert job.exploitability is not None and job.exploitability < 2.0

    rec = recommend_solver(scenario, db_session)
    assert rec.available and rec.source == "solver"
    assert {a.action for a in rec.actions} >= {"call", "fold"}
    assert sum(a.frequency for a in rec.actions) == pytest.approx(1.0, abs=1e-3)
```

- [ ] **Step 3: Correrlo localmente con el binario**

Run (PowerShell, desde `backend/`):
```powershell
$env:POKER_SOLVER_PATH = 'C:\PROYECTOS\POKKER\tools\TexasSolver\TexasSolver-v0.2.0-Windows\console_solver.exe'
uv run pytest -q -m solver
```
Expected: 1 passed (~20–30 s). Sin la variable: `uv run pytest -q -m solver` → 1 skipped.

- [ ] **Step 4: CI — bajar el binario con caché y correr el test real**

En `.github/workflows/ci.yml`, antes del paso `Backend`:
```yaml
      - name: Cache TexasSolver
        id: texassolver
        uses: actions/cache@v4
        with:
          path: ${{ runner.temp }}/TexasSolver
          key: texassolver-v0.2.0-windows

      - name: Download TexasSolver (AGPL, external binary; not part of the repo)
        if: steps.texassolver.outputs.cache-hit != 'true'
        run: |
          $zip = Join-Path $env:RUNNER_TEMP 'ts.zip'
          Invoke-WebRequest https://github.com/bupticybee/TexasSolver/releases/download/v0.2.0/TexasSolver-v0.2.0-Windows.zip -OutFile $zip
          $hash = (Get-FileHash $zip -Algorithm SHA256).Hash
          if ($hash -ne '0A9122FA0CD9384E6C1CBE0492E8A3B8AC7809890C649E1A53F77A59D6D50A7C') { throw "Hash inesperado: $hash" }
          Expand-Archive $zip -DestinationPath (Join-Path $env:RUNNER_TEMP 'TexasSolver')

      - name: Point the backend at TexasSolver
        run: |
          "POKER_SOLVER_PATH=$env:RUNNER_TEMP\TexasSolver\TexasSolver-v0.2.0-Windows\console_solver.exe" | Out-File -Append $env:GITHUB_ENV
```
El paso `Backend` existente (`scripts/test.ps1 backend`) ya corre `pytest -q`, que incluye el test `solver` porque la variable queda definida.

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/tests/test_solver_real.py .github/workflows/ci.yml
git commit -m "test(solver): end-to-end solve with the real binary, locally and in Windows CI"
```

---

### Task 15: Simulador — rango de Hero, prellenado, preset y solve pendiente

**Files:**
- Modify: `frontend/src/simulator/types.ts`
- Create: `frontend/src/solver/types.ts`, `frontend/src/solver/api.ts`
- Create: `frontend/src/simulator/PostflopSolverFields.tsx`, `frontend/src/simulator/PendingSolve.tsx`
- Modify: `frontend/src/simulator/SimulatorPage.tsx`, `frontend/src/simulator/RecommendationPanel.tsx`
- Modify: `frontend/src/ranges/labels.ts` (etiquetas `check`, `bet`), `frontend/src/index.css` (`--action-check`, `--action-bet`)
- Test: `frontend/src/simulator/PostflopSolver.test.tsx`

**Interfaces:**
- Consumes: endpoints de la Task 13; `RangeEditor` (`{id, value, onChange}`), `RangeMatrix` (`{layers: {action, grid}[], caption?}`), `getJson`/`postJson` de `api/client.ts`, `mockApi` de `test/fetchMock.ts`.
- Produces:
  - `ScenarioInput` gana `hero_range: string | null`, `ranges_approximate: boolean`, `solver_preset: string`.
  - `RecommendedAction` gana `label: string | null`, `amount_bb: number | null`; `Recommendation` gana `pending_job: PendingJob | null`, `strategy_grid: StrategyLayer[]`.
  - `src/solver/types.ts`: `PendingJob`, `StrategyLayer`, `SolverJob`, `SolverStatus`, `PrefillRange`, `PrefillResponse`, `LibraryFamily`, `LibraryLine`, `LibraryEntry`, `SolverNode`.
  - `src/solver/api.ts`: `fetchSolverStatus()`, `fetchJob(id)`, `fetchJobs()`, `cancelJob(id)`, `retryJob(id)`, `pauseQueue()`, `resumeQueue()`, `clearCache()`, `prefillRanges(body)`, `fetchLibrary()`, `enqueueLibrary(family, line)`, `fetchNode(hash, path)`.
  - `<PostflopSolverFields>` props: `{ heroRange, onHeroRange, preset, onPreset, presets, prefill: () => Promise<void>, prefillNotes: string[], potType, onPotType, aggressor, onAggressor }`.
  - `<PendingSolve job onDone onCancel />`.

- [ ] **Step 1: Tipos y API del solver**

`src/solver/types.ts`:
```ts
export interface PendingJob {
  id: number
  status: string
  iteration: number
  exploitability: number | null
  position: number | null
}

export interface StrategyLayer {
  action: string
  label: string
  grid: number[]
}

export interface SolverJob {
  id: number
  label: string
  origin: 'simulator' | 'batch' | 'library'
  priority: number
  status: 'queued' | 'running' | 'done' | 'failed' | 'cancelled'
  iteration: number
  exploitability: number | null
  error: string | null
  position: number | null
  spot_hash: string
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface SolverStatus {
  configured: boolean
  path: string | null
  threads: number
  paused: boolean
  cache_entries: number
  cache_bytes: number
  presets: { name: string; label: string }[]
}

export interface PrefillRange {
  text: string | null
  approximate: boolean
  notes: string[]
  missing: string | null
}

export interface PrefillResponse {
  aggressor: PrefillRange
  caller: PrefillRange
}

export interface LibraryEntry {
  flop: string
  status: 'solved' | 'queued' | 'running' | 'missing_chart' | 'outdated' | 'pending'
  spot_hash: string | null
  job_id: number | null
}

export interface LibraryLine {
  id: string
  label: string
  missing: string[]
  approximate: boolean
  entries: LibraryEntry[]
}

export interface LibraryFamily {
  id: string
  label: string
  preset: string
  lines: LibraryLine[]
}

export interface SolverNodeAction {
  index: number
  kind: string
  label: string
  amount_bb: number | null
  frequency: number
  has_child: boolean
}

export interface SolverNode {
  player: 'oop' | 'ip'
  path: string
  actions: SolverNodeAction[]
  layers: StrategyLayer[]
}
```

`src/solver/api.ts`:
```ts
import { deleteJson, getJson, postJson } from '../api/client'
import type {
  LibraryFamily,
  PrefillResponse,
  SolverJob,
  SolverNode,
  SolverStatus,
} from './types'

const BASE = '/api/solver'

export const fetchSolverStatus = () => getJson<SolverStatus>(`${BASE}/status`)
export const fetchJobs = () => getJson<SolverJob[]>(`${BASE}/jobs`)
export const fetchJob = (id: number) => getJson<SolverJob>(`${BASE}/jobs/${id}`)
export const cancelJob = (id: number) => postJson<SolverJob>(`${BASE}/jobs/${id}/cancel`, {})
export const retryJob = (id: number) => postJson<SolverJob>(`${BASE}/jobs/${id}/retry`, {})
export const pauseQueue = () => postJson<{ paused: boolean }>(`${BASE}/queue/pause`, {})
export const resumeQueue = () => postJson<{ paused: boolean }>(`${BASE}/queue/resume`, {})
export const clearCache = () => deleteJson(`${BASE}/cache`)
export const fetchLibrary = () => getJson<LibraryFamily[]>(`${BASE}/library`)
export const enqueueLibrary = (family: string, line: string | null) =>
  postJson<{ enqueued: number; missing: string[] }>(`${BASE}/library/enqueue`, { family, line })
export const fetchNode = (hash: string, path: string) =>
  getJson<SolverNode>(`${BASE}/results/${hash}/node?path=${encodeURIComponent(path)}`)

export interface PrefillRequest {
  game_format: string
  players: number
  aggressor: string
  caller: string
  pot_type: 'srp' | '3bet'
  stack_bb: number
  ante_bb: number
}

export const prefillRanges = (body: PrefillRequest) =>
  postJson<PrefillResponse>(`${BASE}/prefill-ranges`, body)
```

En `src/simulator/types.ts`: agregar a `ScenarioInput` `hero_range: string | null`, `ranges_approximate: boolean`, `solver_preset: string`; a `RecommendedAction` `label: string | null` y `amount_bb: number | null`; a `Recommendation` `pending_job: PendingJob | null` y `strategy_grid: StrategyLayer[]` (importando los tipos de `../solver/types`).

En `src/ranges/labels.ts` agregar a `ACTION_LABEL`: `check: 'Check'`, `bet: 'Bet'`. En `index.css`, en los bloques de tokens de color de acciones (claro y oscuro) agregar `--action-check` y `--action-bet` reutilizando los colores ya validados: `--action-check: var(--action-call);` y `--action-bet: var(--action-raise);` (mismos tonos que call/raise para no introducir colores nuevos sin validar).

- [ ] **Step 2: Escribir el test (falla)**

```tsx
// frontend/src/simulator/PostflopSolver.test.tsx
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/fetchMock'
import { PendingSolve } from './PendingSolve'
import { PostflopSolverFields } from './PostflopSolverFields'
import { RecommendationPanel } from './RecommendationPanel'
import type { Recommendation } from './types'

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

const baseRec: Recommendation = {
  available: true,
  message: null,
  source: 'solver',
  confidence: 'exact',
  hand_class: null,
  actions: [
    { action: 'check', frequency: 0.4, ev: null, label: 'Check', amount_bb: null },
    { action: 'bet', frequency: 0.6, ev: null, label: 'Bet 75% (15bb)', amount_bb: 15 },
  ],
  ev_unit: null,
  reference: 'TexasSolver · preset Simple · explotabilidad 0.42% del pote',
  explanation: [],
  warnings: ['Solo primera decisión de la calle: raises y re-raises previos no se modelan.'],
  pending_job: null,
  strategy_grid: [
    { action: 'check', label: 'Check', grid: Array(169).fill(0.4) },
    { action: 'bet', label: 'Bet 75% (15bb)', grid: Array(169).fill(0.6) },
  ],
}

describe('solver recommendation', () => {
  it('shows sized actions and the strategy grid', () => {
    render(<RecommendationPanel rec={baseRec} />)
    expect(screen.getByText('Bet 75% (15bb)')).toBeInTheDocument()
    expect(screen.getByText(/explotabilidad 0.42%/)).toBeInTheDocument()
    expect(screen.getByRole('group', { name: /Estrategia del rango de Hero/ })).toBeInTheDocument()
  })

  it('polls a pending job and reports when it is done', async () => {
    let calls = 0
    mockApi({
      'GET /api/solver/jobs/7': () => {
        calls += 1
        return {
          json: {
            id: 7, status: calls < 2 ? 'running' : 'done', iteration: calls * 50,
            exploitability: 1.2, position: null,
          },
        }
      },
    })
    const onDone = vi.fn()
    render(
      <PendingSolve
        job={{ id: 7, status: 'queued', iteration: 0, exploitability: null, position: 2 }}
        onDone={onDone}
        intervalMs={10}
      />,
    )
    expect(screen.getByText(/Posición en la cola: 2/)).toBeInTheDocument()
    await waitFor(() => expect(onDone).toHaveBeenCalled())
  })

  it('cancels a pending job', async () => {
    const api = mockApi({
      'GET /api/solver/jobs/7': () => ({
        json: { id: 7, status: 'running', iteration: 10, exploitability: 3, position: null },
      }),
      'POST /api/solver/jobs/7/cancel': () => ({
        json: { id: 7, status: 'cancelled', iteration: 10, exploitability: 3, position: null },
      }),
    })
    render(
      <PendingSolve
        job={{ id: 7, status: 'running', iteration: 10, exploitability: 3, position: null }}
        onDone={() => {}}
        intervalMs={1000}
      />,
    )
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Cancelar solve' })))
    expect(api).toHaveBeenCalledWith('/api/solver/jobs/7/cancel', expect.anything())
    expect(await screen.findByText(/cancelado/i)).toBeInTheDocument()
  })

  it('prefill button calls back and shows notes', async () => {
    const prefill = vi.fn(async () => {})
    render(
      <PostflopSolverFields
        heroRange=""
        onHeroRange={() => {}}
        preset="simple"
        onPreset={() => {}}
        presets={[{ name: 'simple', label: 'Simple' }]}
        prefill={prefill}
        prefillNotes={['Stack del rango: 40bb (escenario: 100bb)']}
        potType="srp"
        onPotType={() => {}}
        aggressor="hero"
        onAggressor={() => {}}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Prellenar desde tablas' }))
    expect(prefill).toHaveBeenCalled()
    expect(screen.getByText(/Stack del rango/)).toBeInTheDocument()
    expect(screen.getByText('Aproximado')).toBeInTheDocument()
  })
})
```

- [ ] **Step 3: Correr y ver que falla**

Run: `npm test -- src/simulator/PostflopSolver.test.tsx` (desde `frontend/`)
Expected: FAIL (módulos `PendingSolve`/`PostflopSolverFields` inexistentes).

- [ ] **Step 4: Escribir `PendingSolve.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { cancelJob, fetchJob } from '../solver/api'
import type { PendingJob } from '../solver/types'

interface Props {
  job: PendingJob
  onDone: () => void
  intervalMs?: number
}

export function PendingSolve({ job: initial, onDone, intervalMs = 1500 }: Props) {
  const [job, setJob] = useState(initial)
  const [error, setError] = useState<string | null>(null)
  const finished = ['done', 'failed', 'cancelled'].includes(job.status)

  useEffect(() => {
    if (finished) return
    const timer = setInterval(() => {
      fetchJob(job.id)
        .then((j) => {
          setJob(j)
          if (j.status === 'done') onDone()
          if (j.status === 'failed') setError(j.error ?? 'El solve falló')
        })
        .catch((e: unknown) => setError(String(e)))
    }, intervalMs)
    return () => clearInterval(timer)
  }, [job.id, finished, intervalMs, onDone])

  async function cancel() {
    setJob(await cancelJob(job.id))
  }

  return (
    <section className="panel panel-muted" aria-labelledby="pending-title" aria-live="polite">
      <h3 id="pending-title">Recomendación · resolviendo con el solver</h3>
      {job.status === 'queued' && job.position !== null && (
        <p>Posición en la cola: {job.position}</p>
      )}
      {job.status === 'running' && (
        <p>
          Iteración {job.iteration}
          {job.exploitability !== null && ` · explotabilidad ${job.exploitability.toFixed(2)}% del pote`}
        </p>
      )}
      {job.status === 'cancelled' && <p>Solve cancelado.</p>}
      {error && <p className="error">{error}</p>}
      {!finished && (
        <button type="button" onClick={() => void cancel()}>
          Cancelar solve
        </button>
      )}
    </section>
  )
}
```

- [ ] **Step 5: Escribir `PostflopSolverFields.tsx`**

```tsx
import { RangeEditor } from './RangeEditor'

interface Props {
  heroRange: string
  onHeroRange: (v: string) => void
  preset: string
  onPreset: (v: string) => void
  presets: { name: string; label: string }[]
  prefill: () => Promise<void>
  prefillNotes: string[]
  potType: 'srp' | '3bet'
  onPotType: (v: 'srp' | '3bet') => void
  aggressor: 'hero' | 'villain'
  onAggressor: (v: 'hero' | 'villain') => void
}

export function PostflopSolverFields(p: Props) {
  return (
    <fieldset className="solver-fields">
      <legend>Solver postflop (heads-up)</legend>
      <div className="row">
        <label>
          Pote
          <select value={p.potType} onChange={(e) => p.onPotType(e.target.value as 'srp' | '3bet')}>
            <option value="srp">Simple (open + call)</option>
            <option value="3bet">3-bet</option>
          </select>
        </label>
        <label>
          Agresor preflop
          <select
            value={p.aggressor}
            onChange={(e) => p.onAggressor(e.target.value as 'hero' | 'villain')}
          >
            <option value="hero">Hero</option>
            <option value="villain">Rival 1</option>
          </select>
        </label>
        <button type="button" onClick={() => void p.prefill()}>
          Prellenar desde tablas
        </button>
        <label>
          Árbol
          <select value={p.preset} onChange={(e) => p.onPreset(e.target.value)}>
            {p.presets.map((x) => (
              <option key={x.name} value={x.name}>
                {x.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      {p.prefillNotes.length > 0 && (
        <div className="small">
          <span className="badge badge-warn">Aproximado</span>
          <ul>
            {p.prefillNotes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </div>
      )}
      <label htmlFor="hero-range">Rango de Hero</label>
      <RangeEditor id="hero-range" value={p.heroRange} onChange={p.onHeroRange} />
    </fieldset>
  )
}
```

- [ ] **Step 6: `RecommendationPanel` — etiquetas con tamaño y grilla**

En el `map` de acciones usar `key={a.label ?? a.action}` y como nombre `{a.label ?? ACTION_LABEL[a.action] ?? a.action}`. Después de la lista de acciones agregar:
```tsx
      {rec.strategy_grid.length > 0 && (
        <RangeMatrix
          layers={rec.strategy_grid.map((l) => ({ action: l.action, grid: l.grid }))}
          caption="Estrategia del rango de Hero en este nodo"
        />
      )}
```
(importando `RangeMatrix` de `../ranges/RangeMatrix`; ya renderiza `role="group"` con `aria-label={caption}`).

- [ ] **Step 7: Enchufar en `SimulatorPage.tsx`**

Estado nuevo:
```tsx
  const [heroRange, setHeroRange] = useState('')
  const [rangesApprox, setRangesApprox] = useState(false)
  const [prefillNotes, setPrefillNotes] = useState<string[]>([])
  const [preset, setPreset] = useState('simple')
  const [presets, setPresets] = useState<{ name: string; label: string }[]>([])
  const [potType, setPotType] = useState<'srp' | '3bet'>('srp')
  const [aggressor, setAggressor] = useState<'hero' | 'villain'>('villain')

  useEffect(() => {
    fetchSolverStatus()
      .then((s) => setPresets(s.presets))
      .catch(() => setPresets([{ name: 'simple', label: 'Simple' }]))
  }, [])
```
Función de prellenado (usa las posiciones y el formato del formulario existente; `villains[0]` es Rival 1):
```tsx
  async function prefill() {
    const villainPos = villains[0]?.position
    if (!heroPosition || !villainPos) {
      setError('Indicá las posiciones de Hero y del Rival 1 para prellenar.')
      return
    }
    const [aggr, caller] = aggressor === 'hero' ? [heroPosition, villainPos] : [villainPos, heroPosition]
    const r = await prefillRanges({
      game_format: format, players: numPlayers, aggressor: aggr, caller,
      pot_type: potType, stack_bb: effectiveStack, ante_bb: ante,
    })
    const heroPart = aggressor === 'hero' ? r.aggressor : r.caller
    const villPart = aggressor === 'hero' ? r.caller : r.aggressor
    if (heroPart.text) setHeroRange(heroPart.text)
    if (villPart.text) updateVillain(0, { range: villPart.text })
    const notes = [...heroPart.notes, ...villPart.notes]
    const missing = [heroPart.missing, villPart.missing].filter(Boolean) as string[]
    setPrefillNotes([...notes, ...missing.map((m) => `Falta tabla: ${m}`)])
    setRangesApprox(heroPart.approximate || villPart.approximate || missing.length > 0)
  }
```
(Usar los nombres reales de las variables de estado del formulario de `SimulatorPage.tsx`: posición de Hero, formato, cantidad de jugadores, stack efectivo, ante y el setter de rivales; si se llaman distinto, adaptar los nombres, no la lógica.)

En el armado del `scenario` que se envía a `/api/simulator/analyze` agregar `hero_range: heroRange || null`, `ranges_approximate: rangesApprox`, `solver_preset: preset`. Mostrar `<PostflopSolverFields …/>` solo cuando el board tiene 3+ cartas y hay exactamente un rival. En el render de la recomendación:
```tsx
      {analysis.recommendation.pending_job ? (
        <PendingSolve
          key={analysis.recommendation.pending_job.id}
          job={analysis.recommendation.pending_job}
          onDone={() => void analyze()}
        />
      ) : (
        <RecommendationPanel rec={analysis.recommendation} />
      )}
```
Editar el rango de Hero a mano pone `rangesApprox` en `false` y limpia `prefillNotes`.

- [ ] **Step 8: Correr y ver que pasa**

Run (desde `frontend/`): `npm test && npm run typecheck && npm run lint`
Expected: todo en verde (incluidos los tests existentes de `SimulatorPage.test.tsx`; si alguno arma un `Recommendation` literal, agregarle `pending_job: null, strategy_grid: []`).

- [ ] **Step 9: Commit**

```bash
git add frontend/src
git commit -m "feat(ui): simulator solver fields, range prefill, pending solve and strategy grid"
```

---

### Task 16: Pestaña "Solver" (cola, biblioteca, visor, configuración)

**Files:**
- Create: `frontend/src/solver/SolverPage.tsx`, `QueuePanel.tsx`, `LibraryPanel.tsx`, `StrategyViewer.tsx`, `SettingsPanel.tsx`, `SolverPage.test.tsx`
- Modify: `frontend/src/App.tsx` (sección `solver`, fase 5, disponible)

**Interfaces:**
- Consumes: `src/solver/api.ts` y `types.ts` (Task 15), `RangeMatrix`.
- Produces: `<SolverPage />`; `<StrategyViewer hash={string} title={string} />`.

- [ ] **Step 1: Escribir el test (falla)**

```tsx
// frontend/src/solver/SolverPage.test.tsx
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/fetchMock'
import { SolverPage } from './SolverPage'

afterEach(() => vi.unstubAllGlobals())

const status = {
  configured: true, path: 'C:/ts/console_solver.exe', threads: 6, paused: false,
  cache_entries: 3, cache_bytes: 120000, presets: [{ name: 'simple', label: 'Simple' }],
}
const job = {
  id: 1, label: 'River Qs Jh 2h 7c 3d · pote 20bb', origin: 'batch', priority: 10,
  status: 'running', iteration: 40, exploitability: 2.5, error: null, position: null,
  spot_hash: 'h', created_at: '2026-10-06T00:00:00Z', started_at: null, finished_at: null,
}
const library = [{
  id: 'cash', label: 'Cash 6-max 100bb', preset: 'simple',
  lines: [{
    id: 'btn_bb', label: 'BTN vs BB · SRP', missing: [], approximate: false,
    entries: [{ flop: 'AsKh2d', status: 'solved', spot_hash: 'abc', job_id: null }],
  }],
}]
const node = {
  player: 'oop', path: '',
  actions: [
    { index: 0, kind: 'check', label: 'Check', amount_bb: null, frequency: 0.7, has_child: true },
    { index: 1, kind: 'bet', label: 'Bet 33% (1.8bb)', amount_bb: 1.8, frequency: 0.3, has_child: true },
  ],
  layers: [
    { action: 'check', label: 'Check', grid: Array(169).fill(0.7) },
    { action: 'bet', label: 'Bet 33% (1.8bb)', grid: Array(169).fill(0.3) },
  ],
}

function routes(extra = {}) {
  return mockApi({
    'GET /api/solver/status': () => ({ json: status }),
    'GET /api/solver/jobs': () => ({ json: [job] }),
    'GET /api/solver/library': () => ({ json: library }),
    'GET /api/solver/results/abc/node': () => ({ json: node }),
    'POST /api/solver/queue/pause': () => ({ json: { paused: true } }),
    ...extra,
  })
}

describe('SolverPage', () => {
  it('lists the queue and pauses it', async () => {
    const api = routes()
    render(<SolverPage />)
    expect(await screen.findByText(/River Qs Jh/)).toBeInTheDocument()
    expect(screen.getByText(/Iteración 40/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Pausar cola' }))
    await waitFor(() =>
      expect(api).toHaveBeenCalledWith('/api/solver/queue/pause', expect.anything()),
    )
  })

  it('opens a solved library flop in the viewer and navigates', async () => {
    routes()
    render(<SolverPage />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Biblioteca' }))
    fireEvent.click(await screen.findByRole('button', { name: /AsKh2d/ }))
    expect(await screen.findByText('Bet 33% (1.8bb)')).toBeInTheDocument()
    expect(screen.getByText(/OOP actúa/)).toBeInTheDocument()
  })

  it('shows configuration', async () => {
    routes()
    render(<SolverPage />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Configuración' }))
    expect(await screen.findByText(/console_solver.exe/)).toBeInTheDocument()
    expect(screen.getByText(/3 resultados/)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Correr y ver que falla**

Run: `npm test -- src/solver/SolverPage.test.tsx`
Expected: FAIL (módulo inexistente).

- [ ] **Step 3: Escribir los componentes**

`SolverPage.tsx`:
```tsx
import { useState } from 'react'
import { LibraryPanel } from './LibraryPanel'
import { QueuePanel } from './QueuePanel'
import { SettingsPanel } from './SettingsPanel'
import { StrategyViewer } from './StrategyViewer'

const TABS = [
  { id: 'queue', label: 'Cola' },
  { id: 'library', label: 'Biblioteca' },
  { id: 'settings', label: 'Configuración' },
] as const

export function SolverPage() {
  const [tab, setTab] = useState<(typeof TABS)[number]['id']>('queue')
  const [viewing, setViewing] = useState<{ hash: string; title: string } | null>(null)
  return (
    <div className="solver-page">
      <div role="tablist" aria-label="Solver" className="subtabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            type="button"
            aria-selected={tab === t.id}
            className={`tab${tab === t.id ? ' tab-active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === 'queue' && <QueuePanel />}
      {tab === 'library' && <LibraryPanel onOpen={(hash, title) => setViewing({ hash, title })} />}
      {tab === 'settings' && <SettingsPanel />}
      {viewing && <StrategyViewer key={viewing.hash} hash={viewing.hash} title={viewing.title} />}
    </div>
  )
}
```

`QueuePanel.tsx`:
```tsx
import { useCallback, useEffect, useState } from 'react'
import {
  cancelJob,
  fetchJobs,
  fetchSolverStatus,
  pauseQueue,
  resumeQueue,
  retryJob,
} from './api'
import type { SolverJob } from './types'

const STATUS_LABEL: Record<SolverJob['status'], string> = {
  queued: 'En cola',
  running: 'Resolviendo',
  done: 'Resuelto',
  failed: 'Falló',
  cancelled: 'Cancelado',
}
const ORIGIN_LABEL = { simulator: 'Simulador', batch: 'Lote', library: 'Biblioteca' }

export function QueuePanel() {
  const [jobs, setJobs] = useState<SolverJob[]>([])
  const [paused, setPaused] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(() => {
    Promise.all([fetchJobs(), fetchSolverStatus()])
      .then(([j, s]) => {
        setJobs(j)
        setPaused(s.paused)
      })
      .catch((e: unknown) => setError(String(e)))
  }, [])

  useEffect(() => {
    refresh()
    const timer = setInterval(refresh, 2000)
    return () => clearInterval(timer)
  }, [refresh])

  async function toggle() {
    const r = paused ? await resumeQueue() : await pauseQueue()
    setPaused(r.paused)
  }

  return (
    <section className="panel" aria-labelledby="queue-title">
      <div className="panel-header">
        <h3 id="queue-title">Cola de solves</h3>
        <button type="button" onClick={() => void toggle()}>
          {paused ? 'Reanudar cola' : 'Pausar cola'}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {jobs.length === 0 && <p className="muted">No hay trabajos.</p>}
      <ul className="job-list">
        {jobs.map((j) => (
          <li key={j.id}>
            <span>{j.label}</span>
            <span className="badge">{ORIGIN_LABEL[j.origin]}</span>
            <span className="badge">{STATUS_LABEL[j.status]}</span>
            {j.status === 'queued' && j.position !== null && <span>#{j.position}</span>}
            {j.status === 'running' && (
              <span>
                Iteración {j.iteration}
                {j.exploitability !== null && ` · ${j.exploitability.toFixed(2)}%`}
              </span>
            )}
            {j.error && <span className="error small">{j.error}</span>}
            {(j.status === 'queued' || j.status === 'running') && (
              <button type="button" onClick={() => void cancelJob(j.id).then(refresh)}>
                Cancelar
              </button>
            )}
            {(j.status === 'failed' || j.status === 'cancelled') && (
              <button type="button" onClick={() => void retryJob(j.id).then(refresh)}>
                Reintentar
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
```

`LibraryPanel.tsx`:
```tsx
import { useCallback, useEffect, useState } from 'react'
import { enqueueLibrary, fetchLibrary } from './api'
import type { LibraryEntry, LibraryFamily } from './types'

const ENTRY_LABEL: Record<LibraryEntry['status'], string> = {
  solved: 'resuelto',
  queued: 'en cola',
  running: 'resolviendo',
  missing_chart: 'falta tabla',
  outdated: 'desactualizado',
  pending: 'sin resolver',
}

export function LibraryPanel({ onOpen }: { onOpen: (hash: string, title: string) => void }) {
  const [families, setFamilies] = useState<LibraryFamily[]>([])
  const [message, setMessage] = useState<string | null>(null)
  const refresh = useCallback(() => {
    fetchLibrary()
      .then(setFamilies)
      .catch((e: unknown) => setMessage(String(e)))
  }, [])
  useEffect(refresh, [refresh])

  async function enqueue(family: string, line: string | null) {
    const r = await enqueueLibrary(family, line)
    setMessage(
      r.missing.length > 0
        ? `Encolados: ${r.enqueued}. ${r.missing.join(' · ')}`
        : `Encolados: ${r.enqueued}.`,
    )
    refresh()
  }

  return (
    <section className="panel" aria-labelledby="library-title">
      <h3 id="library-title">Biblioteca de spots</h3>
      {message && <p className="small">{message}</p>}
      {families.map((f) => (
        <details key={f.id} open>
          <summary>
            {f.label} · preset {f.preset}{' '}
            <button type="button" onClick={() => void enqueue(f.id, null)}>
              Encolar familia
            </button>
          </summary>
          {f.lines.map((line) => (
            <div key={line.id} className="library-line">
              <h4>
                {line.label}
                {line.approximate && <span className="badge badge-warn">Aproximado</span>}{' '}
                <button type="button" onClick={() => void enqueue(f.id, line.id)}>
                  Encolar línea
                </button>
              </h4>
              {line.missing.map((m) => (
                <p key={m} className="small muted">
                  {m}
                </p>
              ))}
              <ul className="flop-list">
                {line.entries.map((e) => (
                  <li key={e.flop}>
                    {e.status === 'solved' && e.spot_hash ? (
                      <button
                        type="button"
                        onClick={() => onOpen(e.spot_hash as string, `${line.label} · ${e.flop}`)}
                      >
                        {e.flop}
                      </button>
                    ) : (
                      <span>{e.flop}</span>
                    )}{' '}
                    <span className="small muted">{ENTRY_LABEL[e.status]}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </details>
      ))}
    </section>
  )
}
```

`StrategyViewer.tsx`:
```tsx
import { useEffect, useState } from 'react'
import { RangeMatrix } from '../ranges/RangeMatrix'
import { fetchNode } from './api'
import type { SolverNode } from './types'

export function StrategyViewer({ hash, title }: { hash: string; title: string }) {
  const [path, setPath] = useState<{ index: number; label: string }[]>([])
  const [node, setNode] = useState<SolverNode | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchNode(hash, path.map((p) => p.index).join('.'))
      .then(setNode)
      .catch((e: unknown) => setError(String(e)))
  }, [hash, path])

  return (
    <section className="panel" aria-labelledby="viewer-title">
      <h3 id="viewer-title">{title}</h3>
      <nav aria-label="Camino en el árbol" className="small">
        <button type="button" onClick={() => setPath([])}>
          Raíz
        </button>
        {path.map((p, i) => (
          <button key={i} type="button" onClick={() => setPath(path.slice(0, i + 1))}>
            {' › '}
            {p.label}
          </button>
        ))}
      </nav>
      {error && <p className="error">{error}</p>}
      {node && (
        <>
          <p>{node.player === 'oop' ? 'OOP actúa' : 'IP actúa'}</p>
          <ul className="rec-actions">
            {node.actions.map((a) => (
              <li key={a.index}>
                <span className="rec-action-name">{a.label}</span>
                <span className="rec-freq">{Math.round(a.frequency * 100)}%</span>
                {a.has_child && (
                  <button
                    type="button"
                    onClick={() => setPath([...path, { index: a.index, label: a.label }])}
                  >
                    Ver respuesta
                  </button>
                )}
              </li>
            ))}
          </ul>
          <RangeMatrix
            layers={node.layers.map((l) => ({ action: l.action, grid: l.grid }))}
            caption="Estrategia del rango en este nodo"
          />
        </>
      )}
    </section>
  )
}
```

`SettingsPanel.tsx`:
```tsx
import { useEffect, useState } from 'react'
import { clearCache, fetchSolverStatus } from './api'
import type { SolverStatus } from './types'

export function SettingsPanel() {
  const [status, setStatus] = useState<SolverStatus | null>(null)
  const refresh = () => {
    fetchSolverStatus().then(setStatus).catch(() => setStatus(null))
  }
  useEffect(refresh, [])
  if (!status) return <p className="muted">Cargando…</p>
  return (
    <section className="panel" aria-labelledby="settings-title">
      <h3 id="settings-title">Configuración del solver</h3>
      <p>
        {status.configured
          ? `Solver: ${status.path}`
          : 'Solver no configurado: definí POKER_SOLVER_PATH con la ruta de console_solver.exe.'}
      </p>
      <p>Hilos: {status.threads}</p>
      <p>
        Caché: {status.cache_entries} resultados · {(status.cache_bytes / 1024 / 1024).toFixed(1)} MB{' '}
        <button
          type="button"
          onClick={() => {
            if (window.confirm('¿Vaciar toda la caché del solver?')) void clearCache().then(refresh)
          }}
        >
          Vaciar caché
        </button>
      </p>
    </section>
  )
}
```

En `App.tsx`: agregar `{ id: 'solver', label: 'Solver', phase: 5 }` antes de `trainer`, sumar `'solver'` a `AVAILABLE` y renderizar `{section === 'solver' && <SolverPage />}` junto a las demás secciones.

- [ ] **Step 4: Correr y ver que pasa**

Run: `npm test && npm run typecheck && npm run lint`
Expected: todo en verde.

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat(ui): Solver tab with queue, library, strategy viewer and settings"
```

---

### Task 17: README, verificación completa y cierre de fase

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Actualizar el README**

Agregar la sección "## Solver postflop (fase 5)" con: requisito de bajar TexasSolver v0.2.0 (link a la release, SHA-256), definir `POKER_SOLVER_PATH` (ejemplo en PowerShell con `.env` en `backend/`), presets de `data/solver/trees.json`, cola y prioridades, biblioteca (11 líneas × 25 flops = 275 solves, se alimenta de tus tablas), heurística multiway (umbrales configurables `POKER_HEURISTIC_*`), limitaciones (solo primera decisión de la calle, sin rake, sin EV del solver, rangos por clase). Agregar las variables nuevas a la tabla de configuración: `POKER_SOLVER_THREADS`, `POKER_SOLVER_TIMEOUT_MIN`, `POKER_HEURISTIC_VALUE_SHARE`, `POKER_HEURISTIC_RAISE_SHARE`, `POKER_HEURISTIC_SEMIBLUFF_OUTS`, `POKER_HEURISTIC_REALIZATION_OOP`, `POKER_HEURISTIC_REALIZATION_LAST`, `POKER_HEURISTIC_MARGIN`. Cambiar el título "fase 4, en curso" por "fase 4" y quitar `/solver` de "llegan en fases futuras" si aparece.

- [ ] **Step 2: Suites completas**

Run (PowerShell en Developer Shell, desde la raíz, con `POKER_SOLVER_PATH` definido):
```powershell
.\scripts\test.ps1
```
Expected: `All requested suites passed.` (core, backend con el test `solver` real, frontend, integración).

- [ ] **Step 3: Verificación manual en el navegador**

1. `.\scripts\dev.ps1` con `backend/.env` que tenga `POKER_SOLVER_PATH=...console_solver.exe`.
2. Pestaña *Rangos preflop*: cargar una tabla BTN RFI y una BB vs open de BTN (cash, 6 jugadores, 100bb).
3. *Simulador*: 6 jugadores, Hero BB con `QhQc`, Rival 1 BTN, board `Qs Jh 2h 7c` (turn), pote 20, a pagar 0, stack 90. "Prellenar desde tablas" (pote simple, agresor Rival 1) → rangos completos. Analizar → panel "resolviendo" con iteraciones → al terminar, acciones con tamaños, grilla 13×13, explotabilidad.
4. Repetir el análisis → respuesta inmediata (caché).
5. *Solver → Biblioteca*: "Encolar línea" en Cash BTN vs BB → 25 trabajos en *Cola*; pausar y reanudar; cancelar uno; al resolverse uno, abrirlo en el visor y navegar "Ver respuesta".
6. Simulador con 3 jugadores en el flop → recomendación "Heurística" con "Aproximado".
7. Vista móvil (375 px): sin scroll horizontal en Simulador y Solver.

- [ ] **Step 4: Commit y push**

```bash
git add README.md
git commit -m "docs: phase 5 solver integration"
git push origin main
```

- [ ] **Step 5: Cierre de fase (SPEC §8)**

Parar y resumir al usuario: lo hecho, lo verificado (suites, test real, recorrido manual), lo pendiente (parsers GG/PS de fase 4, raises dentro de la calle, rake, EV del solver no disponible en v0.2.0) y esperar confirmación antes de la fase 6.
