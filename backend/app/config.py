"""Centralized application configuration.

Every setting can be overridden through environment variables prefixed with
``POKER_`` (e.g. ``POKER_DATABASE_URL``) or a ``.env`` file in the working directory.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_VERSION = "0.0.0"


def _env_resources_dir() -> Path:
    raw = os.environ.get("POKER_RESOURCES_DIR")
    return Path(raw) if raw else REPO_ROOT


def read_app_version() -> str:
    """Return the app version from the single source of truth (the root VERSION file)."""
    if env_version := os.environ.get("POKER_APP_VERSION"):
        return env_version.strip()
    version_file = _env_resources_dir() / "VERSION"
    if version_file.is_file():
        return version_file.read_text(encoding="utf-8").strip()
    return _DEFAULT_VERSION


def _default_data_dir() -> Path:
    return REPO_ROOT / "var"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POKER_", env_file=".env", extra="ignore")

    app_name: str = "Poker Study Tool"
    app_version: str = Field(default_factory=read_app_version)

    # Storage
    data_dir: Path = Field(default_factory=_default_data_dir)
    database_url: str | None = None
    auto_migrate: bool = True

    # Reference data shipped with the app (preflop ranges, precomputed spots, solver trees).
    # In the packaged app POKER_RESOURCES_DIR points at the bundled resources; the individual
    # overrides below are optional and take precedence over the derived locations.
    resources_dir: Path = REPO_ROOT
    ranges_dir: Path | None = None
    spots_dir: Path | None = None

    # Equity engine
    equity_iterations: int = 200_000
    equity_exact_limit: float = 3e7

    # Hand histories: names used as Hero when a file does not say who the hero is.
    hero_names: list[str] = []
    # Stats: below this sample size a metric is flagged as insufficient.
    stats_min_sample: int = 100
    leaks_min_sample: int = 50

    # Recommendation: tournaments at or below this effective stack use push/fold Nash.
    pushfold_max_bb: float = 15.0

    # External postflop solver (TexasSolver console binary, AGPL: never vendored).
    solver_path: Path | None = None
    solver_threads: int = Field(default_factory=lambda: os.cpu_count() or 4)
    solver_timeout_min: float = 30.0
    solver_trees_file: Path | None = None
    solver_library_file: Path | None = None

    # Multiway postflop heuristic thresholds (own heuristics, not solver output).
    heuristic_value_share: float = 0.65
    heuristic_raise_share: float = 0.80
    heuristic_semibluff_outs: int = 8
    heuristic_realization_oop: float = 0.85
    heuristic_realization_last: float = 0.95
    heuristic_margin: float = 0.03

    # Update channel (phase 7): e.g. a GitHub Releases API URL.
    update_feed_url: str | None = None

    # HTTP
    api_prefix: str = "/api"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @property
    def resolved_ranges_dir(self) -> Path:
        return self.ranges_dir or self.resources_dir / "data" / "ranges"

    @property
    def resolved_spots_dir(self) -> Path:
        return self.spots_dir or self.resources_dir / "data" / "spots"

    @property
    def resolved_solver_trees_file(self) -> Path:
        return self.solver_trees_file or self.resources_dir / "data" / "solver" / "trees.json"

    @property
    def resolved_solver_library_file(self) -> Path:
        return self.solver_library_file or self.resources_dir / "data" / "solver" / "library.json"

    @property
    def precomputed_dir(self) -> Path:
        return self.resources_dir / "data" / "precomputed"

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{(self.data_dir / 'poker.sqlite3').as_posix()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
