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
