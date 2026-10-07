# Fase 6 — Entrenador y leak finder: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entrenador (push/fold MTT + preflop desde tablas + "Pintá tu rango", con repetición espaciada, dificultad configurable y estructuras de premios propias) y leak finder preflop (tablas + Nash push/fold) sobre las manos importadas.

**Architecture:** Las decisiones preflop de Hero se extraen una vez por mano a la tabla `hand_decisions` (con relleno idempotente al arrancar). El leak finder agrega esa tabla contra referencias calculadas por clase de mano. El entrenador genera `Scenario`s y usa `recommend()` (fase 3) como única fuente de la respuesta; la repetición espaciada vive en SQLite. UI: pestaña "Entrenador" y subsección "Leaks" en Estadísticas.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 + Alembic (SQLite), numpy, pytest; React 19 + TypeScript + Vite + vitest.

**Spec:** `docs/superpowers/specs/2026-10-07-fase6-entrenador-leaks-design.md`

## Global Constraints

- La respuesta de referencia de un spot **nunca** se envía al cliente antes de que el usuario responda.
- Pérdida en push/fold = `EV(mejor) − EV(elegida)` exacta, en `bb` (o `$`/% con ICM). Pérdida en tablas = `1 − freq(elegida)` (fold = `1 − Σ`), siempre "aproximado". "Pintá tu rango" = error ponderado por combos, "aproximado".
- Veredictos: push/fold correcto si pérdida ≤ 0,05 × escala (mismo `INDIFFERENT_EV` de `app/recommend/engine.py`), si no error. Tablas: correcto si `freq ≥ 0,5` o es la más alta; aceptable si `0,1 ≤ freq < 0,5`; error si `< 0,1`. Rango: correcto ≥ 90% de precisión, aceptable ≥ 75%, error < 75%.
- SM-2 simplificado: ease inicial 2,5; correcto: intervalo 0→1→3→`round(intervalo × ease)` días; aceptable: intervalo igual, `ease − 0,05`; error: intervalo 0, `ease − 0,2` (mínimo 1,3) y reaparece en la sesión 3 a 5 spots después. Selección: cola de la sesión → vencidas (~70%) / nuevas (~30%) → nuevas.
- Leak: `n ≥ POKER_LEAKS_MIN_SAMPLE` (50) **y** esperada fuera del IC de Wilson 95% de la observada **y** `|diferencia| ≥ 0,05`. Frecuencia esperada **por clase de mano** de cada decisión.
- No se inventan referencias: sin tablas, la fuente "tablas" del entrenador y los leaks de tablas se deshabilitan con aviso.
- Mensajes al usuario en español (voseo); código y comentarios en inglés. Backend: ruff (line-length 100, `E,F,I,UP,B`) + `ruff format`. Frontend: `tsc -b`, `oxlint`, `vitest`.
- Comandos (desde `backend/`): `uv run pytest -q <ruta>`, `uv run ruff check .`, `uv run ruff format --check .`; desde `frontend/`: `npm test`, `npm run typecheck`, `npm run lint`.
- Commits con la identidad git configurada y el trailer `Co-Authored-By` del modelo que escribe el commit.

## Mapa de archivos

Backend — crear: `app/domain/preflop.py`, `app/stats/decisions.py`, `app/leaks/__init__.py`, `app/leaks/finder.py`, `app/trainer/__init__.py`, `app/trainer/srs.py`, `app/trainer/spots.py`, `app/trainer/scoring.py`, `app/trainer/ranges.py`, `app/trainer/service.py`, `app/api/leaks.py`, `app/api/trainer.py`, `alembic/versions/0005_hand_decisions.py`, `alembic/versions/0006_trainer.py`; tests `tests/test_preflop_situation.py`, `test_decisions.py`, `test_leaks.py`, `test_trainer_srs.py`, `test_trainer_spots.py`, `test_trainer_ranges.py`, `test_trainer_api.py`, `test_leaks_api.py`.
Backend — modificar: `app/replay/service.py`, `app/db/models.py`, `app/parsers/importer.py`, `app/main.py`, `app/config.py`.
Frontend — crear: `src/trainer/types.ts`, `src/trainer/api.ts`, `src/trainer/TrainerPage.tsx`, `src/trainer/SpotView.tsx`, `src/trainer/Feedback.tsx`, `src/trainer/RangeDrill.tsx`, `src/trainer/SessionSidebar.tsx`, `src/trainer/PayoutsEditor.tsx`, `src/trainer/TrainerPage.test.tsx`, `src/stats/LeaksPanel.tsx`, `src/stats/LeaksPanel.test.tsx`.
Frontend — modificar: `src/App.tsx`, `src/stats/StatsPage.tsx`, `src/ranges/RangeMatrix.tsx` (prop `highlight`), `src/index.css`.
Otros: `README.md`.

---

### Task 1: Situación preflop compartida

**Files:**
- Create: `backend/app/domain/preflop.py`
- Modify: `backend/app/replay/service.py` (usar la función nueva; borrar `_situation`)
- Test: `backend/tests/test_preflop_situation.py`

**Interfaces:**
- Produces: `preflop_situation(positions: dict[str, str], hero: str, before: list[Action], folded: set[str]) -> Situation` — `positions` = posición de cada jugador repartido; `before` = acciones preflop (sin posts) previas a la decisión de Hero; `folded` = jugadores que ya foldearon.

- [ ] **Step 1: Test (falla)**

```python
# backend/tests/test_preflop_situation.py
from app.domain.preflop import preflop_situation
from app.domain.scenario import Situation
from tests.hands import act

POS = {"U": "LJ", "H": "HJ", "C": "CO", "B": "BTN", "S": "SB", "Hero": "BB"}


def test_rfi_when_folded_to_hero():
    assert preflop_situation(POS, "B", [act("p", "U", "fold")], {"U"}) == Situation.RFI


def test_vs_open():
    assert preflop_situation(POS, "B", [act("p", "C", "raise", 2.5)], set()) == Situation.VS_OPEN


def test_squeeze_when_open_was_called():
    before = [act("p", "C", "raise", 2.5), act("p", "B", "call", 2.5)]
    assert preflop_situation(POS, "Hero", before, set()) == Situation.SQUEEZE


def test_bvb_unopened_and_sb_open():
    folded = {"U", "H", "C", "B"}
    assert preflop_situation(POS, "S", [], folded) == Situation.BVB
    assert preflop_situation(POS, "Hero", [act("p", "S", "raise", 3)], folded) == Situation.BVB


def test_vs_3bet_and_vs_4bet():
    before = [act("p", "B", "raise", 2.5), act("p", "Hero", "raise", 11)]
    assert preflop_situation(POS, "B", before, set()) == Situation.VS_3BET
    before4 = before + [act("p", "B", "raise", 25)]
    assert preflop_situation(POS, "Hero", before4, set()) == Situation.VS_4BET


def test_vs_allin():
    before = [act("p", "C", "raise", 12, all_in=True)]
    assert preflop_situation(POS, "B", before, set()) == Situation.VS_ALLIN
```

- [ ] **Step 2: Correr y ver que falla** — `uv run pytest -q tests/test_preflop_situation.py` → `ModuleNotFoundError`.

- [ ] **Step 3: Crear `app/domain/preflop.py`** moviendo la lógica de `app/replay/service.py::_situation` sin cambiar su comportamiento:

```python
"""Preflop situation of a player at a decision point (shared by replay and stats)."""

from __future__ import annotations

from app.domain.hand import AGGRESSIVE, Action, ActionType
from app.domain.scenario import Situation


def preflop_situation(
    positions: dict[str, str], hero: str, before: list[Action], folded: set[str]
) -> Situation:
    raises = [a for a in before if a.type in AGGRESSIVE]
    others = [a for a in raises if a.player != hero]
    hero_raised = any(a.player == hero for a in raises)
    pos = positions[hero]
    if raises and raises[-1].all_in and raises[-1].player != hero:
        return Situation.VS_ALLIN
    if not raises:
        active = [p for p in positions if p not in folded and p != hero]
        if pos in ("SB", "BB") and all(positions[p] in ("SB", "BB") for p in active):
            return Situation.BVB
        return Situation.RFI
    if len(raises) == 1:
        opener = raises[0]
        if pos == "BB" and positions.get(opener.player) == "SB":
            return Situation.BVB
        after = before[before.index(opener) + 1 :]
        if any(a.type == ActionType.CALL and a.player != hero for a in after):
            return Situation.SQUEEZE
        return Situation.VS_OPEN
    if len(raises) == 2 or (hero_raised and len(others) == 1):
        return Situation.VS_3BET
    return Situation.VS_4BET
```

En `app/replay/service.py`: borrar `_situation` y en `_scenario` usar `preflop_situation(state.pos, hero, preflop, set(state.folded))`. Verificar que `state.pos` contiene solo jugadores repartidos (las claves de `state.stacks`); si contiene más, pasar `{p: state.pos[p] for p in state.stacks}`.

- [ ] **Step 4: Correr** — `uv run pytest -q tests/test_preflop_situation.py tests/test_replay.py` → todo pasa (el replayer no cambia de comportamiento).

- [ ] **Step 5: Commit** — `refactor(domain): shared preflop situation for replay and stats`.

---

### Task 2: Decisiones preflop por mano (`hand_decisions`)

**Files:**
- Create: `backend/app/stats/decisions.py`, `backend/alembic/versions/0005_hand_decisions.py`
- Modify: `backend/app/db/models.py` (modelo `HandDecision`, relación `Hand.decisions`), `backend/app/parsers/importer.py` (agregar decisiones a cada fila), `backend/app/main.py` (relleno en el lifespan)
- Test: `backend/tests/test_decisions.py`

**Interfaces:**
- Consumes: `preflop_situation` (Task 1), `HandRecord.positions()`, `.dealt_seats`, `.table_size`, `.stack_of(p)`, `hand_class` (`app.recommend.preflop_equity`), `TOURNAMENT_FORMATS`, `AppMeta`.
- Produces:
  - `Decision` (dataclass): `idx: int, game_format: str, table_size: int, position: str, situation: str, vs_position: str | None, hand_class: str, stack_bb: float, action: str, spot: dict | None`.
  - `extract_decisions(record: HandRecord) -> list[Decision]` (0, 1 o 2).
  - `DECISIONS_VERSION = 1`; `backfill_decisions(session) -> int` (recalcula todas si `AppMeta["decisions_version"]` difiere; idempotente).
  - ORM `HandDecision` (tabla `hand_decisions`): `id`, `hand_id` (FK `hands.id`, `ondelete="CASCADE"`), `idx`, `game_format`, `table_size`, `position`, `situation`, `vs_position` (nullable), `hand_class`, `stack_bb`, `action`, `spot` (JSON, nullable). Índice `ix_hand_decisions_spot(game_format, position, situation)`. `Hand.decisions = relationship(HandDecision, cascade="all, delete-orphan")`.

Reglas de extracción:
- Solo acciones preflop; se ignoran los posts (`POSTS`).
- Decisión 1 = primera acción voluntaria de Hero que no sea `check` (un check del BB no es decisión). Decisión 2 = siguiente acción de Hero que no sea `check`, solo si la decisión 1 fue agresiva y alguien re-subió después.
- `situation = preflop_situation(record.positions(), hero, before, folded)` con `before` = acciones previas sin posts.
- Acción normalizada: `fold`; `call` → `limp` si no hubo subidas antes, si no `call`; `raise`/`bet` → `allin` si `all_in`, si no por subidas previas: 0 → `raise`, 1 → `3bet`, 2 → `4bet`, 3+ → `5bet`.
- `vs_position` = posición del último agresor antes de la decisión (None si no hubo).
- `stack_bb` = `min(stack de Hero, max(stack de los activos)) / bb` al inicio de la mano, redondeado a 2 decimales.
- `spot` (solo torneos con `stack_bb ≤ settings.pushfold_max_bb` y situación `rfi` o `vs_allin`): `{"stacks_bb": {pos: stack/bb}, "ante_bb": ante/bb}`.
- Sin `hero`, sin `hero_cards` o con datos inconsistentes → `[]`.

- [ ] **Step 1: Test (falla)**

```python
# backend/tests/test_decisions.py
from app.domain.scenario import GameFormat
from app.stats.decisions import extract_decisions
from tests.hands import act, make_hand

SIX = {"U": 100, "H": 100, "C": 100, "Hero": 100, "S": 100, "B": 100}  # Hero on BTN


def d(record):
    return [(x.idx, x.position, x.situation, x.vs_position, x.action) for x in extract_decisions(record)]


def test_rfi_open():
    r = make_hand(SIX, [act("p", "U", "fold"), act("p", "H", "fold"), act("p", "C", "fold"),
                        act("p", "Hero", "raise", 2.5)], button="Hero", hero_cards="AhKh")
    assert d(r) == [(1, "BTN", "rfi", None, "raise")]
    assert extract_decisions(r)[0].hand_class == "AKs"
    assert extract_decisions(r)[0].stack_bb == 100.0


def test_fold_vs_open():
    r = make_hand(SIX, [act("p", "U", "fold"), act("p", "H", "fold"), act("p", "C", "raise", 2.5),
                        act("p", "Hero", "fold")], button="Hero")
    assert d(r) == [(1, "BTN", "vs_open", "CO", "fold")]


def test_open_then_fold_to_3bet_gives_two_decisions():
    r = make_hand(SIX, [act("p", "U", "fold"), act("p", "H", "fold"), act("p", "C", "fold"),
                        act("p", "Hero", "raise", 2.5), act("p", "S", "raise", 11),
                        act("p", "B", "fold"), act("p", "Hero", "fold")], button="Hero")
    assert d(r) == [(1, "BTN", "rfi", None, "raise"), (2, "BTN", "vs_3bet", "SB", "fold")]


def test_limp_and_3bet_labels():
    r = make_hand(SIX, [act("p", "U", "call", 1), act("p", "H", "fold"), act("p", "C", "fold"),
                        act("p", "Hero", "call", 1)], button="Hero")
    assert d(r)[0][4] == "limp"
    r2 = make_hand(SIX, [act("p", "U", "raise", 2.5), act("p", "H", "fold"), act("p", "C", "fold"),
                         act("p", "Hero", "raise", 8)], button="Hero")
    assert d(r2)[0][4] == "3bet"


def test_bb_check_is_not_a_decision():
    r = make_hand({"S": 100, "Hero": 100}, [act("p", "S", "call", 0.5), act("p", "Hero", "check")],
                  button="S")
    assert extract_decisions(r) == []


def test_pushfold_spot_in_tournament():
    stacks = {"U": 20, "H": 30, "C": 25, "Hero": 10, "S": 40, "B": 15}
    r = make_hand(stacks, [act("p", "U", "fold"), act("p", "H", "fold"), act("p", "C", "fold"),
                           act("p", "Hero", "raise", 10, all_in=True)],
                  button="Hero", ante=0.125, game_type=GameFormat.MTT)
    (dec,) = extract_decisions(r)
    assert dec.action == "allin" and dec.situation == "rfi"
    assert dec.spot["stacks_bb"]["BTN"] == 10.0 and dec.spot["ante_bb"] == 0.125


def test_no_hero_no_decisions():
    r = make_hand(SIX, [act("p", "U", "fold")], button="Hero", hero=None)
    assert extract_decisions(r) == []


def test_import_stores_decisions_and_backfill_is_idempotent(client, fake_room):
    from app.db.models import HandDecision
    from app.db.session import _session_factory
    from app.stats.decisions import backfill_decisions
    from tests.fake_parser import fake_file

    r = make_hand(SIX, [act("p", "U", "fold"), act("p", "H", "fold"), act("p", "C", "fold"),
                        act("p", "Hero", "raise", 2.5)], button="Hero")
    resp = client.post("/api/imports", files={"files": ("h.txt", fake_file(r), "text/plain")})
    assert resp.status_code == 200
    with _session_factory()() as s:
        assert s.query(HandDecision).count() == 1
        assert backfill_decisions(s) == 0  # already at current version
```

(Si el endpoint de importación usa otro nombre de campo para los archivos, copiarlo de `tests/test_import.py`.)

- [ ] **Step 2: Correr y ver que falla** — `uv run pytest -q tests/test_decisions.py`.

- [ ] **Step 3: Modelo + migración 0005** — en `models.py` agregar `HandDecision` con las columnas de la interfaz y `Hand.decisions` (importar `relationship`). Migración `0005_hand_decisions.py` (`down_revision="0004"`) con `create_table` + índice, en el estilo de `0004_solver.py`.

- [ ] **Step 4: `app/stats/decisions.py`**

```python
"""Hero's preflop decisions in a hand (up to two), for the leak finder and the trainer."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import AppMeta, Hand, HandDecision
from app.domain.hand import AGGRESSIVE, POSTS, ActionType, HandRecord
from app.domain.preflop import preflop_situation
from app.domain.scenario import TOURNAMENT_FORMATS, Situation, Street
from app.recommend.preflop_equity import hand_class

DECISIONS_VERSION = 1
VERSION_KEY = "decisions_version"
RAISE_LABEL = {0: "raise", 1: "3bet", 2: "4bet"}


@dataclass
class Decision:
    idx: int
    game_format: str
    table_size: int
    position: str
    situation: str
    vs_position: str | None
    hand_class: str
    stack_bb: float
    action: str
    spot: dict | None


def _label(a, raises_before: int) -> str:
    if a.type == ActionType.FOLD:
        return "fold"
    if a.type == ActionType.CALL:
        return "call" if raises_before else "limp"
    if a.all_in:
        return "allin"
    return RAISE_LABEL.get(raises_before, "5bet")


def extract_decisions(record: HandRecord) -> list[Decision]:
    hero = record.hero
    if not hero or not record.hero_cards:
        return []
    try:
        positions = record.positions()
        cls = hand_class(record.hero_cards)
    except (ValueError, KeyError):
        return []
    if hero not in positions:
        return []
    bb = record.bb
    preflop = [a for a in record.actions if a.street == Street.PREFLOP and a.type not in POSTS]
    others = [p for p in positions if p != hero]
    hero_stack = record.stack_of(hero)
    eff = min(hero_stack, max((record.stack_of(p) for p in others), default=0.0))
    stack_bb = round(eff / bb, 2)
    settings = get_settings()
    out: list[Decision] = []
    folded: set[str] = set()
    first_index: int | None = None
    for i, a in enumerate(preflop):
        if a.player != hero:
            if a.type == ActionType.FOLD:
                folded.add(a.player)
            continue
        if a.type == ActionType.CHECK:
            continue
        before = preflop[:i]
        raises = [b for b in before if b.type in AGGRESSIVE]
        if first_index is not None:
            # A second decision only when hero was aggressive and got re-raised.
            first_aggressive = out[0].action not in ("fold", "call", "limp")
            reraised = any(
                b.type in AGGRESSIVE and b.player != hero for b in preflop[first_index + 1 : i]
            )
            if not (first_aggressive and reraised):
                break
        situation = preflop_situation(positions, hero, before, folded)
        vs = next((positions[b.player] for b in reversed(raises)), None)
        spot = None
        if (
            record.game_type in TOURNAMENT_FORMATS
            and stack_bb <= settings.pushfold_max_bb
            and situation in (Situation.RFI, Situation.VS_ALLIN)
        ):
            spot = {
                "stacks_bb": {positions[s.name]: round(s.stack / bb, 4) for s in record.dealt_seats},
                "ante_bb": round(record.ante / bb, 4),
            }
        out.append(Decision(
            idx=len(out) + 1, game_format=record.game_type.value, table_size=record.table_size,
            position=positions[hero], situation=situation.value, vs_position=vs,
            hand_class=cls, stack_bb=stack_bb, action=_label(a, len(raises)), spot=spot,
        ))
        if first_index is None:
            first_index = i
        if len(out) == 2 or out[-1].action == "fold":
            break
    return out
```

Los tests de Step 1 son el contrato; si algún detalle del código choca con ellos, gana el test.

```python
def decision_rows(record: HandRecord) -> list[HandDecision]:
    return [HandDecision(**asdict(d)) for d in extract_decisions(record)]


def backfill_decisions(session: Session) -> int:
    meta = session.get(AppMeta, VERSION_KEY)
    if meta is not None and meta.value == str(DECISIONS_VERSION):
        return 0
    count = 0
    for hand in session.scalars(select(Hand)):
        hand.decisions = decision_rows(HandRecord.model_validate(hand.record))
        count += 1
    session.merge(AppMeta(key=VERSION_KEY, value=str(DECISIONS_VERSION)))
    session.commit()
    return count
```

- [ ] **Step 5: Enganchar** — en `importer.hand_row` agregar `row.decisions = decision_rows(record)`; en `main.py` lifespan, después de las migraciones: `with _session_factory()() as s: backfill_decisions(s)`.

- [ ] **Step 6: Correr** — `uv run pytest -q tests/test_decisions.py` y luego la suite completa del backend → todo pasa.

- [ ] **Step 7: Commit** — `feat(stats): hero preflop decisions per hand (hand_decisions)`.

---

### Task 3: Leak finder (backend + API)

**Files:**
- Create: `backend/app/leaks/__init__.py`, `backend/app/leaks/finder.py`, `backend/app/api/leaks.py`
- Modify: `backend/app/config.py` (`leaks_min_sample: int = 50`), `backend/app/main.py` (router)
- Test: `backend/tests/test_leaks.py`, `backend/tests/test_leaks_api.py`

**Interfaces:**
- Consumes: `HandDecision`, `Hand`, `StatsFilter` y `wilson` (`app.stats.engine`), `stats_filter` (`app.api.filters`), `find_chart`/`ChartQuery`, `solve_spot` (`app.recommend.engine`), `class_index`, `preflop_order`, `INDIFFERENT_EV`.
- Produces:
  - `stack_bucket(stack_bb: float, pushfold: bool) -> str` — pushfold: `"3-5"|"6-8"|"9-11"|"12-15"` (≤5 → `"3-5"`); profundo: `"16-30"|"31-60"|"61-120"|"120+"`.
  - `ActionLeak(action, observed, expected, ci_low, ci_high, diff, significant)`; `LeakGroup(key, label, game_format, table_size, position, situation, vs_position, stack_bucket, source: "chart"|"nash", approximate: bool, notes: list[str], n: int, insufficient: bool, actions: list[ActionLeak], impact: float, impact_unit: "bb/100"|"pts/100", ev_loss_bb: float | None)`.
  - `LeakDetail(group: LeakGroup, top_classes: list[{"hand_class","n","observed","expected","diff"}], grid: list[float | None])`.
  - `find_leaks(session, filters: StatsFilter) -> LeakReport(total_hands: int, min_sample: int, leaks: list[LeakGroup], insufficient: list[LeakGroup], other: list[LeakGroup], warnings: list[str])`.
  - `leak_detail(session, filters, key) -> LeakDetail | None`.
  - API: `GET /api/leaks` → `LeakReport`; `GET /api/leaks/detail?key=…` (+ filtros) → `LeakDetail` (404 si no existe).

Algoritmo:
1. Cargar `HandDecision` unido a `Hand` con `filters.apply(select(...))`; `total_hands` = manos con Hero en el filtro.
2. Por decisión, referencia:
   - **nash** si `spot` no es None: `solve_spot(stacks en preflop_order(table_size), ante_bb, 0.0, [])`; esperado por acción: RFI → `{"allin": push[pos][cls], "fold": 1 − …}`; VS_ALLIN → `{"call": call[(vs, pos)][cls], "fold": …}` (la acción `allin` de Hero cuenta como `call`). EV: `push_ev`/`call_ev`; pérdida = `max(EV) − EV(hecha)`.
   - **chart** en otro caso: `find_chart(ChartQuery(format, table_size, position, situation, stack_bb, vs_position, ante_bb=0))`; esperado = `{a: g[cls]}` + `fold = max(0, 1 − Σ)`; si no hay tabla, la decisión no entra (y se suma a un aviso).
   - Cachear referencia por (fuente, chart id o spot normalizado).
3. Agrupar por `key = f"{fmt}|{size}|{pos}|{sit}|{vs or '-'}|{bucket}|{source}"`.
4. Por grupo y acción (unión de observadas y esperadas): `k` = veces hecha, `n` = decisiones, `observed, lo, hi = wilson(k, n)`, `expected = mean(esperadas)`, `diff = observed − expected`, `significant = n ≥ min and not (lo ≤ expected ≤ hi) and |diff| ≥ 0.05`.
5. Impacto: nash → `Σ pérdida / total_hands × 100` en `bb/100` (y `ev_loss_bb = Σ pérdida`); chart → `max |diff| × n / total_hands × 100` en `pts/100`, `approximate=True`. `approximate` también si la tabla no es exacta (con `notes` = mismatches).
6. Clasificación: `insufficient` si `n < min`; `leaks` si alguna acción es significativa; resto en `other`. Ordenar `leaks` por impacto descendente.
7. Detalle: para la acción con mayor `|diff|`, por clase: n, observada, esperada, diff; `top_classes` = 10 con mayor `|Σ(observado − esperado)|`; `grid` (169) = diff promedio por clase o `None` sin datos.
8. Avisos: sin decisiones → "Importá historiales para ver tus leaks (los parsers de GG/PS llegan con tus archivos)."; decisiones sin tabla → "Hay N decisiones sin tabla de referencia: cargalas en Rangos preflop."

- [ ] **Step 1: Tests (fallan)** — `tests/test_leaks.py` con un helper que inserta en la DB (`db_session`) manos sintéticas vía `make_hand` + `importer.hand_row` (o creando `Hand` + `HandDecision` directamente con `decision_rows`), y una tabla BTN RFI cash 6 jugadores 100bb con raise = un rango del ~45% (`range_vector("22+,A2s+,K5s+,Q8s+,J8s+,T8s+,97s+,86s+,75s+,65s,54s,A8o+,KTo+,QTo+,JTo")`). Casos:
  - 60 decisiones BTN RFI donde Hero solo abre AA–TT y AKs (resto fold, clases variadas al azar con semilla fija) → aparece en `leaks` con acción `raise`, `observed < expected`, `significant`, `impact_unit == "pts/100"`, `approximate`.
  - 20 decisiones iguales → `insufficient`.
  - Esperada por clase: 60 decisiones RFI con solo manos que la tabla abre 100% y Hero las abre todas → **no** es leak (`expected ≈ 1`).
  - Push/fold: 60 decisiones MTT RFI 10bb en BTN con `spot` y Hero foldeando manos que Nash empuja → `source == "nash"`, `impact_unit == "bb/100"`, `ev_loss_bb > 0`.
  - `stack_bucket` (bordes 5/6, 15/16, 30/31, 60/61, 120/121).
  - `leak_detail` devuelve `top_classes` y `grid` de 169.
  - Sin decisiones → aviso de importar.
  `tests/test_leaks_api.py`: `GET /api/leaks` (vacío con aviso) y `GET /api/leaks/detail?key=x` → 404.
- [ ] **Step 2: RED** — correr y capturar el fallo.
- [ ] **Step 3: Implementar** `finder.py`, `api/leaks.py` (respuestas pydantic con los campos de la interfaz; reutilizar `FilterDep` de `api/stats.py`), setting y router.
- [ ] **Step 4: GREEN** — tests nuevos + suite completa + ruff.
- [ ] **Step 5: Commit** — `feat(leaks): preflop leak finder vs charts and push/fold Nash`.

---

### Task 4: Modelos del entrenador y repetición espaciada

**Files:**
- Create: `backend/app/trainer/__init__.py`, `backend/app/trainer/srs.py`, `backend/alembic/versions/0006_trainer.py`
- Modify: `backend/app/db/models.py`
- Test: `backend/tests/test_trainer_srs.py`

**Interfaces:**
- Produces:
  - ORM `TrainerSession` (`trainer_sessions`): `id`, `created_at`, `filters` JSON (`{"sources": [...], "formats": [...], "positions": [...], "situations": [...], "stack_buckets": [...], "mode": "normal"|"review"|"frequent", "difficulty": 0-100, "payout_id": int|None, "card_ids": list[int]|None}`), `relearn` JSON (lista `[{card_id, due_after}]`), `spots_served` int.
  - ORM `TrainerCard` (`trainer_cards`): `id`, `key` (unique, str 200), `source` (`pushfold`|`chart`|`range`), `scenario` JSON (último escenario/definición), `ease` float (2.5), `interval_days` int (0), `due_at` datetime nullable, `reps` int, `lapses` int, `archived` bool, `created_at`, `updated_at`.
  - ORM `TrainerAttempt` (`trainer_attempts`): `id`, `spot_id` (str 36, unique), `session_id` FK, `card_id` FK nullable, `source`, `scenario` JSON, `offered` JSON (acciones ofrecidas o definición del ejercicio), `answer` JSON nullable, `reference` JSON (recomendación completa, **solo servidor**), `loss` float nullable, `loss_unit` str nullable, `verdict` str nullable (`correct`|`acceptable`|`error`), `approximate` bool, `created_at`, `answered_at` nullable.
  - ORM `PayoutStructure` (`payout_structures`): `id`, `name` (unique), `payouts` JSON (lista de floats ≥ 0), `builtin` bool.
  - `srs.py`: `INITIAL_EASE = 2.5`, `MIN_EASE = 1.3`; `Verdict = Literal["correct","acceptable","error"]`; `schedule(card_state: CardState, verdict, now: datetime) -> CardState` con `CardState(ease, interval_days, due_at, reps, lapses)`; `relearn_offset(rng) -> int` (3–5); `pick_kind(rng, has_due: bool, has_relearn_due: bool) -> "relearn"|"due"|"new"` (relearn si toca; si hay vencidas, 70% due / 30% new; si no, new).

- [ ] **Step 1: Tests (fallan)** — `tests/test_trainer_srs.py`:

```python
from datetime import UTC, datetime, timedelta
import random

from app.trainer.srs import INITIAL_EASE, MIN_EASE, CardState, pick_kind, relearn_offset, schedule

NOW = datetime(2026, 10, 7, tzinfo=UTC)
NEW = CardState(ease=INITIAL_EASE, interval_days=0, due_at=None, reps=0, lapses=0)


def test_correct_grows_interval():
    s1 = schedule(NEW, "correct", NOW)
    assert s1.interval_days == 1 and s1.due_at == NOW + timedelta(days=1)
    s2 = schedule(s1, "correct", NOW)
    assert s2.interval_days == 3
    s3 = schedule(s2, "correct", NOW)
    assert s3.interval_days == round(3 * s2.ease)


def test_acceptable_keeps_interval_and_lowers_ease():
    s = schedule(CardState(2.5, 3, NOW, 2, 0), "acceptable", NOW)
    assert s.interval_days == 3 and s.ease == 2.45


def test_error_resets_and_floors_ease():
    s = schedule(CardState(1.4, 10, NOW, 5, 0), "error", NOW)
    assert s.interval_days == 0 and s.ease == MIN_EASE and s.lapses == 1 and s.due_at == NOW


def test_relearn_offset_range():
    rng = random.Random(1)
    assert all(3 <= relearn_offset(rng) <= 5 for _ in range(100))


def test_pick_kind_mix():
    rng = random.Random(7)
    kinds = [pick_kind(rng, has_due=True, has_relearn_due=False) for _ in range(1000)]
    assert 0.65 < kinds.count("due") / 1000 < 0.75
    assert pick_kind(rng, has_due=True, has_relearn_due=True) == "relearn"
    assert pick_kind(rng, has_due=False, has_relearn_due=False) == "new"
```

- [ ] **Step 2: RED.**
- [ ] **Step 3: Implementar** modelos, migración `0006_trainer.py` (`down_revision="0005"`; insertar 2 estructuras builtin: `"Mesa final 9 (100)"` = `[30, 20, 14, 10, 8, 6.5, 5, 3.75, 2.75]` y `"Burbuja SNG 4 de 3 premios"` = `[50, 30, 20]`), y `srs.py`:

```python
"""Simplified SM-2 scheduling for trainer cards."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

INITIAL_EASE = 2.5
MIN_EASE = 1.3
REVIEW_SHARE = 0.7
Verdict = Literal["correct", "acceptable", "error"]


@dataclass(frozen=True)
class CardState:
    ease: float
    interval_days: int
    due_at: datetime | None
    reps: int
    lapses: int


def schedule(s: CardState, verdict: Verdict, now: datetime) -> CardState:
    if verdict == "error":
        ease = max(MIN_EASE, round(s.ease - 0.2, 2))
        return CardState(ease, 0, now, s.reps + 1, s.lapses + 1)
    if verdict == "acceptable":
        ease = max(MIN_EASE, round(s.ease - 0.05, 2))
        interval = s.interval_days
    else:
        ease = s.ease
        interval = 1 if s.interval_days == 0 else 3 if s.interval_days == 1 else round(
            s.interval_days * s.ease
        )
    return CardState(ease, interval, now + timedelta(days=interval), s.reps + 1, s.lapses)


def relearn_offset(rng: random.Random) -> int:
    return rng.randint(3, 5)


def pick_kind(rng: random.Random, has_due: bool, has_relearn_due: bool) -> str:
    if has_relearn_due:
        return "relearn"
    if has_due and rng.random() < REVIEW_SHARE:
        return "due"
    return "new"
```

- [ ] **Step 4: GREEN** (incluye `tests/test_migrations.py`).
- [ ] **Step 5: Commit** — `feat(trainer): models, migration and spaced-repetition scheduling`.

---

### Task 5: Generadores de spots y puntaje

**Files:**
- Create: `backend/app/trainer/spots.py`, `backend/app/trainer/scoring.py`
- Test: `backend/tests/test_trainer_spots.py`

**Interfaces:**
- Consumes: `Scenario`, `Villain`, `Situation`, `GameFormat`; `recommend(scenario, session)` y `solve_spot`, `INDIFFERENT_EV` (`app.recommend.engine`); `PreflopChart`; `class_names`, `combos_per_class`, `class_index` (`preflop_equity`); `preflop_order`; `stack_bucket` (Task 3).
- Produces:
  - `TrainerSpot(source: "pushfold"|"chart", scenario: Scenario, offered: list[str], card_key: str, chart_id: int | None)`.
  - `PUSHFOLD_TABLES = (9, 6, 3, 2)`; `pushfold_pool(table_size) -> list[list[float]]` (12 configuraciones determinísticas por tamaño, `random.Random(table_size)`: Hero 3–15bb en cada posición posible, resto 5–40bb, enteros).
  - `generate_pushfold(session, rng, filters: dict, payouts: list[float]) -> TrainerSpot | None`.
  - `generate_chart(session, rng, filters: dict) -> TrainerSpot | None` (None si no hay tablas que cumplan los filtros).
  - `pick_hand(rng, weights_by_class: np.ndarray, frontier: np.ndarray, difficulty: int) -> str` → combo concreto (p. ej. `"Ah5h"`) con probabilidad `difficulty/100` de salir de la frontera (ponderada por combos) y el resto ponderado por combos sobre todas las clases.
  - `chart_frontier(actions: dict[str, list[float]]) -> np.ndarray` (169 bools: frecuencia mixta `0 < Σ < 1`, o clase dentro/fuera del rango con un vecino de grilla del lado opuesto).
  - `pushfold_frontier(ev_act: np.ndarray, ev_fold: float, scale: float) -> np.ndarray` (`|ev_act − ev_fold| < 1 × scale`).
  - `card_key(spot) -> str`: `pushfold|{fmt}|{pos}|{sit}|{vs or '-'}|{bucket}|{cls}` / `chart|{chart_id}|{cls}`.
  - `scoring.score_hand(rec: RecommendationOut, chosen: str, payouts_scale: float) -> Score(loss, loss_unit, verdict, approximate, best: str, freq_chosen: float)`:
    - fuente `nash`: `best = argmax ev`; `loss = max(ev) − ev(chosen)`; `verdict = "correct" if loss <= INDIFFERENT_EV * scale else "error"`; `loss_unit = rec.ev_unit`; `approximate = rec.confidence == "approximate"`.
    - fuente `chart`: `freq_chosen` (0 si no está); `loss = 1 − freq_chosen`; `best` = acción de mayor frecuencia; veredicto por las reglas de Global Constraints; `loss_unit = "freq"`; `approximate = True`.

Reglas de generación:
- push/fold: elegir tamaño de mesa de los filtros (default los 4), configuración del pool, posición de Hero (no BB en RFI), situación RFI o VS_ALLIN (50/50; VS_ALLIN requiere una posición anterior a Hero que empuje: el pusher es la posición anterior con mayor push range, elegida al azar entre las anteriores). Escenario: `format=mtt`, `num_players`, `hero_position`, `situation`, `effective_stack_bb = stack de Hero`, `stacks_bb` por posición, `bb_ante_bb = 1.0`, `payouts`, `villains=[Villain(position=pusher or "BB")]`, `hero_hand` vía `pick_hand` con la frontera de esa decisión (resolver con `solve_spot` para obtener EVs). `offered = ["allin","fold"]` o `["call","fold"]`.
- tablas: elegir tabla al azar entre las que cumplen filtros (formato, posiciones, situaciones); escenario con los datos de la tabla (`format`, `num_players=players`, `hero_position=position`, `situation`, `effective_stack_bb=stack_bb`, `ante_bb`, `villains=[Villain(position=vs_position or <cualquier otra posición>)]`); `offered = ["fold", *acciones de la tabla con alguna frecuencia > 0]`.

- [ ] **Step 1: Tests (fallan)** — `tests/test_trainer_spots.py` (con `db_session`):
  - `pushfold_pool(9)` devuelve 12 listas de 9 stacks, determinístico.
  - `generate_pushfold` con `rng = Random(3)`: `recommend(spot.scenario, s)` da `source == "nash"`, `available`; `offered` coherente con la situación; la recomendación **no** viaja en `TrainerSpot`.
  - `pick_hand` con `difficulty=100` siempre devuelve clases de la frontera; con 0, nunca se fuerza (test estadístico con semilla).
  - `generate_chart` sin tablas → `None`; con una tabla BTN RFI → escenario coincide con la tabla y `offered == ["fold","raise"]`.
  - `score_hand`: con un `RecommendationOut` nash armado (allin ev 1.2, fold ev 0.0) → elegir fold da `loss == 1.2`, `error`; con diferencias 0.03 → `correct`. Con uno de tabla (raise 0.3, fold 0.7) → raise: `loss 0.7`, `acceptable`; fold: `loss 0.3`, `correct`; con call ausente → `loss 1`, `error`.
  - HU a 10bb: SB push AA → `correct` (contra el Nash validado de fase 3).
- [ ] **Step 2: RED.** - [ ] **Step 3: Implementar.** - [ ] **Step 4: GREEN + suite + ruff.**
- [ ] **Step 5: Commit** — `feat(trainer): push/fold and chart spot generators with EV/frequency scoring`.

---

### Task 6: "Pintá tu rango" (backend)

**Files:**
- Create: `backend/app/trainer/ranges.py`
- Test: `backend/tests/test_trainer_ranges.py`

**Interfaces:**
- Consumes: `PreflopChart`, `combos_per_class`, `class_names`.
- Produces:
  - `RangeDrill(chart_id: int, action: str, title: str, card_key: str)` — `title` p. ej. `"Pintá el rango de raise: BTN RFI · cash 6 jugadores · 100bb"`; `card_key = f"range|{chart_id}|{action}"`.
  - `generate_range_drill(session, rng, filters: dict) -> RangeDrill | None` (tabla al azar dentro de filtros; acción al azar entre las de la tabla con alguna frecuencia > 0).
  - `score_range(target: list[float], painted: list[float]) -> RangeScore(precision: float, error: float, verdict, diff_grid: list[float], top_classes: list[{"hand_class","target","painted","weight"}])` — `error = Σ combos_c × |painted_c − target_c| / Σ combos_c × max(target_c, painted_c)` sobre clases donde `max > 0` (si ninguna, error 0); `precision = 1 − error`; veredicto: ≥0,9 correct, ≥0,75 acceptable, si no error; `diff_grid = painted − target`; `top_classes` = 10 con mayor `combos × |diff|`. `painted` se valida: 169 valores en [0,1] (si no, `ValueError("El rango pintado debe tener 169 valores entre 0 y 1")`).

- [ ] **Step 1: Tests** — idéntico → precisión 1, `correct`; vacío vs tabla no vacía → precisión 0, `error`; mitad de los combos faltantes → ~0,5; `top_classes` ordenado por peso (pares pesan 6, suited 4, offsuit 12); validación de longitud/rango; `generate_range_drill` sin tablas → None.
- [ ] **Step 2: RED.** - [ ] **Step 3: Implementar.** - [ ] **Step 4: GREEN.**
- [ ] **Step 5: Commit** — `feat(trainer): paint-your-range drill scoring`.

---

### Task 7: Servicio de sesiones y API del entrenador

**Files:**
- Create: `backend/app/trainer/service.py`, `backend/app/api/trainer.py`
- Modify: `backend/app/main.py` (router)
- Test: `backend/tests/test_trainer_api.py`

**Interfaces:**
- Consumes: Tasks 4–6, `recommend`.
- Produces (`/api/trainer`):
  - `GET /sources` → `{"pushfold": {"available": true}, "chart": {"available": bool, "reason": str|None}, "range": {...}}`.
  - `GET /payouts` / `POST /payouts {name, payouts}` / `DELETE /payouts/{id}` (las builtin no se borran → 422).
  - `POST /sessions {sources, formats, positions, situations, stack_buckets, mode, difficulty=50, payout_id=None, card_ids=None}` → `{id, filters}`. Validar: al menos una fuente disponible (si no, 422 con el motivo).
  - `POST /sessions/{id}/next` → `SpotOut`: `{spot_id, kind: "hand"|"range", source, scenario (sin recomendación), offered, title, card_id|None, review: bool}`; 409 "No hay spots para estos filtros" si nada cumple.
  - `POST /spots/{spot_id}/answer {action}` (mano) o `{painted: [169]}` (rango) → `FeedbackOut`: `{verdict, loss, loss_unit, approximate, chosen, best, recommendation (RecommendationOut completa, solo para mano), reference_layers: [{action, grid[169]}] (solo mano: tablas → las acciones de la tabla `chart_id` del spot; push/fold → el rango `push[pos]` como `allin` o `call[(pusher, pos)]` como `call` de `solve_spot`), hand_index (índice 0–168 de la clase de Hero), range (target, diff_grid, top_classes, precision — solo rango), card: {interval_days, due_at, ease}}`. **Idempotente**: si el spot ya tiene respuesta, devuelve el mismo feedback sin reprogramar.
  - `GET /sessions/{id}` → resumen `{spots, correct, acceptable, error, ev_loss_bb (suma push/fold en bb), avg_freq_error (tablas), avg_precision (rango)}`.
  - `GET /frequent-errors?limit=10` → tarjetas con más `lapses` (no archivadas): `{card_id, key, source, label, lapses, reps}`.
- Lógica de `next` (`service.next_spot`):
  1. `rng = random.Random()` (los tests inyectan semilla vía parámetro del servicio).
  2. Cola de la sesión: si algún `relearn.due_after <= spots_served` → esa tarjeta.
  3. Si no, `pick_kind`: `due` = tarjetas no archivadas con `due_at <= ahora`, fuente en la sesión, que cumplen filtros (y `card_ids` si el modo es `frequent`), la más atrasada primero; modo `review` = solo vencidas (si no hay, 409 "No hay repasos pendientes").
  4. `new`: fuente elegida al azar entre las de la sesión → generador correspondiente (push/fold usa `payouts` de la estructura elegida o `[]`).
  5. Una tarjeta repasada regenera su escenario: mano → mismo `scenario` con otro combo de la misma clase (palos al azar, sin chocar con cartas del board, que en preflop no hay); tabla borrada → archivar y pedir otro; rango → misma tabla y acción.
  6. Guardar `TrainerAttempt` con `reference` (la recomendación o el rango objetivo) y devolver el spot **sin** referencia; `spots_served += 1`.
- Lógica de `answer`: puntuar (Task 5/6), crear o actualizar la tarjeta por `card_key` (con `scenario`), `schedule()`, y si `error` agregar a `relearn` con `due_after = spots_served + relearn_offset`; si era una tarjeta de la cola y ahora es `correct`, sacarla de la cola.

- [ ] **Step 1: Tests (fallan)** — ciclo completo con push/fold (sin tablas): crear sesión → `next` → la respuesta JSON **no contiene** `recommendation`/`reference`/`actions` → `answer` → feedback con `verdict` y `recommendation`; repetir `answer` → mismo feedback y la tarjeta no se reprograma dos veces; un error vuelve en 3–5 spots (forzar con semilla y verdict error); sesión solo "chart" sin tablas → 422; `review` sin vencidas → 409; payouts CRUD (builtin no borrable); rango: con una tabla, `next` devuelve `kind == "range"` cuando la sesión solo tiene `range`, y `answer {painted}` puntúa; resumen y frequent-errors.
- [ ] **Step 2: RED.** - [ ] **Step 3: Implementar.** - [ ] **Step 4: GREEN + suite + ruff.**
- [ ] **Step 5: Commit** — `feat(trainer): sessions, spaced selection and /api/trainer`.

---

### Task 8: UI del entrenador (manos)

**Files:**
- Create: `frontend/src/trainer/types.ts`, `api.ts`, `TrainerPage.tsx`, `SpotView.tsx`, `Feedback.tsx`, `SessionSidebar.tsx`, `TrainerPage.test.tsx`
- Modify: `frontend/src/App.tsx` (sección `trainer` disponible y renderizada), `frontend/src/ranges/RangeMatrix.tsx` (prop opcional `highlight?: number` que resalta una celda con un borde), `frontend/src/index.css`

**Interfaces:**
- Consumes: `/api/trainer/*` (Task 7), `RecommendationPanel`-like barras (reutilizar `ACTION_LABEL`), `RangeMatrix`, `handClassName`/`cards` utilities de `src/simulator/cards.ts`.
- Produces: `<TrainerPage initialFilters?: {positions?: string[], situations?: string[], formats?: string[], sources?: string[]} />` (lo usa el puente desde Leaks en Task 10).

Comportamiento:
- **Configuración** (arriba, plegable): fuentes (checkbox por fuente; deshabilitada con el `reason` de `/sources`), formatos, posiciones, situaciones, franjas de stack, modo (normal / solo repaso / solo errores frecuentes), dificultad (slider 0–100, default 50), estructura de premios (select: "Chip EV" + `/payouts`). Botón "Empezar" → `POST /sessions` y primer `next`.
- **Spot:** mesa compacta en texto (formato, jugadores, posición de Hero, situación en español, rival, stacks y ante si es push/fold), cartas de Hero grandes (reutilizar `CardView`), badge "Repaso" si `review`. Botones por `offered` con etiqueta de `ACTION_LABEL` (fold/call/raise/allin/3bet…). **Nada de la referencia se muestra antes de responder.**
- **Atajos:** `F` fold, `C` call/limp, `R` raise/allin/3bet (la primera agresiva ofrecida), `1–9` por índice, `Enter` = "Siguiente" cuando hay feedback. Ignorar atajos si el foco está en un input.
- **Feedback:** veredicto con color (correcto/aceptable/error), "Tu acción: X · Referencia: Y", pérdida (`-1,20bb` / `error de frecuencia 70%` + badge "Aproximado"), barras de la recomendación (acción, frecuencia, EV si hay), explicación y avisos de la recomendación, `RangeMatrix` con `layers = reference_layers` y `highlight = hand_index`. Botón "Siguiente".
- **Sidebar:** resumen de sesión (`GET /sessions/{id}` tras cada respuesta) y "Tus errores frecuentes" con botón "Entrenar solo estas" (crea sesión `mode: "frequent"`, `card_ids`).
- **Errores:** 409 "No hay spots para estos filtros" con botón "Limpiar filtros"; 422 al crear sesión mostrado como mensaje; "Preparando spot…" mientras `next` tarda.
- **Móvil:** barra de acciones fija abajo (`position: sticky; bottom: 0`) por debajo de 640 px.

- [ ] **Step 1: Tests (fallan)** — con `mockApi`: (a) empezar sesión y ver el spot sin ninguna frecuencia/EV en pantalla; (b) tecla `F` responde fold, aparece feedback con veredicto y barras; (c) `Enter` pide el siguiente; (d) fuente "tablas" deshabilitada con el motivo; (e) 409 muestra "No hay spots para estos filtros" y "Limpiar filtros"; (f) "Entrenar solo estas" crea sesión con `mode: "frequent"` y los `card_ids`.
- [ ] **Step 2: RED.** - [ ] **Step 3: Implementar.** - [ ] **Step 4: GREEN** (`npm test`, `typecheck`, `lint`).
- [ ] **Step 5: Commit** — `feat(ui): trainer page with shortcuts, feedback and session sidebar`.

---

### Task 9: UI de "Pintá tu rango" y estructuras de premios

**Files:**
- Create: `frontend/src/trainer/RangeDrill.tsx`, `frontend/src/trainer/PayoutsEditor.tsx`
- Modify: `frontend/src/trainer/TrainerPage.tsx`, `SpotView.tsx` (despachar `kind == "range"`), `TrainerPage.test.tsx`

**Interfaces:**
- Consumes: `paintCell` y la UI de pincel de `src/ranges/ChartEditor.tsx` (copiar solo el patrón; no importar el editor completo), `RangeMatrix`.
- Produces: `<RangeDrill spot onSubmit(painted: number[]) feedback? />`, `<PayoutsEditor onChange />`.

Comportamiento:
- `RangeDrill`: título del ejercicio, matriz vacía pintable (pincel 0/50/100%, arrastre), botones "Limpiar" y "Enviar" → `answer {painted}`. Feedback: precisión %, veredicto, matriz de diferencias (capas: verde = faltante, rojo = sobrante, usando tokens existentes `--action-call`/`--action-raise`), lista de las 10 clases con más peso ("Faltan: A5s (4 combos)…").
- `PayoutsEditor`: lista de estructuras (builtin marcadas, sin borrar), alta con nombre + premios separados por coma (validación numérica), borrar las propias.

- [ ] **Step 1: Tests (fallan)** — pintar dos celdas y enviar manda 169 valores con esas dos en 1; el feedback muestra la precisión; alta de estructura llama `POST /payouts` y la builtin no tiene botón borrar.
- [ ] **Step 2: RED.** - [ ] **Step 3: Implementar.** - [ ] **Step 4: GREEN.**
- [ ] **Step 5: Commit** — `feat(ui): paint-your-range drill and payout structures`.

---

### Task 10: UI de Leaks y puente al entrenador

**Files:**
- Create: `frontend/src/stats/LeaksPanel.tsx`, `frontend/src/stats/LeaksPanel.test.tsx`
- Modify: `frontend/src/stats/StatsPage.tsx` (subsección "Leaks" con los mismos filtros), `frontend/src/App.tsx` (callback para abrir el entrenador con filtros)

**Interfaces:**
- Consumes: `GET /api/leaks`, `GET /api/leaks/detail` (Task 3), `filterQuery` de `src/stats/filters.ts`, `TrainerPage initialFilters` (Task 8).
- Produces: `<LeaksPanel filters onTrain(f) />`.

Comportamiento:
- Tabla ordenada por impacto: spot ("BTN · RFI · cash 6 · 61-120bb"), por acción significativa "Observado 18% (IC 15–23%) · Esperado 45%", n, impacto (`2,4 bb/100` o `3,1 pts/100`), badges "Aproximado" y "Nash (chip EV)".
- Fila expandible → `GET /detail`: texto resumen, top clases, `RangeMatrix` del desvío (capas por signo con tokens existentes) y botón **"Entrenar este spot"** → `onTrain({positions:[pos], situations:[sit], formats:[fmt], sources: source==="nash" ? ["pushfold"] : ["chart"]})`; `App` cambia a la sección `trainer` con esos filtros.
- Secciones plegadas: "Muestra insuficiente" y "Sin desvíos".
- Avisos del backend arriba (sin manos / sin tablas).

- [ ] **Step 1: Tests (fallan)** — lista ordenada con los textos; expandir pide el detalle; "Entrenar este spot" llama `onTrain` con los filtros correctos; estado vacío muestra el aviso de importar.
- [ ] **Step 2: RED.** - [ ] **Step 3: Implementar.** - [ ] **Step 4: GREEN.**
- [ ] **Step 5: Commit** — `feat(ui): leaks panel in stats with a bridge to the trainer`.

---

### Task 11: README, verificación y cierre

- [ ] **Step 1: README** — sección "Entrenador y leak finder (fase 6)": fuentes, puntaje (EV exacto vs error de frecuencia aproximado), repetición espaciada, dificultad, estructuras de premios, "Pintá tu rango", leak finder (referencias, significancia, `POKER_LEAKS_MIN_SAMPLE`, impacto), limitaciones (postflop y spots del historial fuera de alcance; leaks de push/fold en chip EV). Agregar `POKER_LEAKS_MIN_SAMPLE` a la tabla de configuración. Quitar "(fase 6)" pendiente de la intro de historiales si corresponde.
- [ ] **Step 2: Suite completa** — `scripts\test.ps1` en el Developer Shell → "All requested suites passed."
- [ ] **Step 3: Verificación manual (controlador, navegador)** — sesión push/fold (atajos, feedback, repetición de un error), sesión desde tablas (con tablas cargadas en una carpeta de datos temporal), "Pintá tu rango", y Leaks con manos sintéticas importadas por la sala falsa en una DB temporal.
- [ ] **Step 4: Commit** — `docs: phase 6 trainer and leak finder`. Sin push (lo decide el usuario).
- [ ] **Step 5: Cierre de fase** — resumir lo hecho y lo pendiente; esperar confirmación (SPEC §8).
