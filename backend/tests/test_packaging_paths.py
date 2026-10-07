import shutil

import numpy as np
import pytest

from app.config import REPO_ROOT, get_settings, read_app_version


def _clear_caches():
    from app.recommend.preflop_equity import preflop_equity
    from app.solver.trees import _bundled

    get_settings.cache_clear()
    _bundled.cache_clear()
    preflop_equity.cache_clear()


@pytest.fixture(autouse=True)
def _caches(monkeypatch):
    monkeypatch.delenv("POKER_RESOURCES_DIR", raising=False)
    monkeypatch.delenv("POKER_APP_VERSION", raising=False)
    _clear_caches()
    yield
    monkeypatch.undo()
    _clear_caches()


@pytest.fixture
def resources(tmp_path, monkeypatch):
    res = tmp_path / "res"
    (res / "data" / "solver").mkdir(parents=True)
    (res / "data" / "precomputed").mkdir(parents=True)
    (res / "VERSION").write_text("9.9.9\n", encoding="utf-8")
    shutil.copy(REPO_ROOT / "data" / "solver" / "trees.json", res / "data" / "solver")
    shutil.copy(REPO_ROOT / "data" / "solver" / "library.json", res / "data" / "solver")
    shutil.copy(
        REPO_ROOT / "data" / "precomputed" / "preflop_equity_169.npy", res / "data" / "precomputed"
    )
    monkeypatch.setenv("POKER_RESOURCES_DIR", str(res))
    _clear_caches()
    return res


def test_defaults_point_to_repo():
    s = get_settings()
    assert s.resources_dir == REPO_ROOT
    assert s.resolved_ranges_dir == REPO_ROOT / "data" / "ranges"
    assert s.resolved_spots_dir == REPO_ROOT / "data" / "spots"
    assert s.resolved_solver_trees_file == REPO_ROOT / "data" / "solver" / "trees.json"
    assert s.resolved_solver_library_file == REPO_ROOT / "data" / "solver" / "library.json"
    assert s.precomputed_dir == REPO_ROOT / "data" / "precomputed"
    assert read_app_version() == (REPO_ROOT / "VERSION").read_text().strip()


def test_resources_dir_overrides_everything(resources):
    s = get_settings()
    assert s.resources_dir == resources
    assert s.app_version == "9.9.9"
    assert read_app_version() == "9.9.9"
    assert s.resolved_ranges_dir == resources / "data" / "ranges"
    assert s.resolved_spots_dir == resources / "data" / "spots"
    assert s.resolved_solver_trees_file == resources / "data" / "solver" / "trees.json"
    assert s.resolved_solver_library_file == resources / "data" / "solver" / "library.json"
    assert s.precomputed_dir == resources / "data" / "precomputed"


def test_app_version_env_still_wins(resources, monkeypatch):
    monkeypatch.setenv("POKER_APP_VERSION", "1.2.3")
    assert read_app_version() == "1.2.3"


def test_explicit_file_override_is_kept(resources, monkeypatch, tmp_path):
    custom = tmp_path / "t.json"
    monkeypatch.setenv("POKER_SOLVER_TREES_FILE", str(custom))
    _clear_caches()
    assert get_settings().resolved_solver_trees_file == custom


def test_presets_load_from_resources_dir(resources):
    from app.solver.trees import load_presets

    (resources / "data" / "solver" / "trees.json").write_text(
        (REPO_ROOT / "data" / "solver" / "trees.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    assert load_presets()  # reads resources/data/solver/trees.json
    (resources / "data" / "solver" / "trees.json").unlink()
    with pytest.raises(FileNotFoundError):
        load_presets()


def test_equity_matrix_loads_from_resources_dir(resources):
    from app.recommend import preflop_equity as pe

    assert pe.matrix_path() == resources / "data" / "precomputed" / "preflop_equity_169.npy"
    marker = np.load(pe.matrix_path()).astype(float)
    assert pe.preflop_equity().equity.shape == marker.shape
    (resources / "data" / "precomputed" / "preflop_equity_169.npy").unlink()
    pe.preflop_equity.cache_clear()
    with pytest.raises(FileNotFoundError):
        pe.preflop_equity()


def test_matrix_path_default_is_repo():
    from app.recommend.preflop_equity import matrix_path

    assert matrix_path() == REPO_ROOT / "data" / "precomputed" / "preflop_equity_169.npy"


def test_backend_root_uses_meipass(monkeypatch):
    import importlib.util
    import sys

    import app.db.session as session

    monkeypatch.setattr(sys, "_MEIPASS", "C:/bundle", raising=False)
    # Execute a private copy of the module: reloading the real one would orphan the
    # lru_cache'd engine/session factories other modules already imported.
    spec = importlib.util.spec_from_file_location("_session_probe", session.__file__)
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    assert str(probe.BACKEND_ROOT).replace("\\", "/") == "C:/bundle"
