"""Cross-package checks: run with the backend environment (see scripts/test.sh)."""

import json
from pathlib import Path

import pokercore

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_native_core_importable():
    assert pokercore.version()


def test_frontend_package_version_matches_root_version():
    root_version = (REPO_ROOT / "VERSION").read_text().strip()
    pkg = json.loads((REPO_ROOT / "src" / "frontend" / "package.json").read_text())
    assert pkg["version"] == root_version
