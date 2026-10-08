import sqlalchemy as sa

from app.config import REPO_ROOT, read_app_version


def test_version_matches_root_version_file(client):
    resp = client.get("/api/version")
    assert resp.status_code == 200
    body = resp.json()
    assert body["app"] == (REPO_ROOT / "VERSION").read_text().strip()
    assert body["core"]


def test_version_env_override(monkeypatch):
    monkeypatch.setenv("POKER_APP_VERSION", "9.9.9")
    assert read_app_version() == "9.9.9"


def test_health_ok(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": True}


def test_migrations_create_schema(client, tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'poker.sqlite3'}")
    tables = sa.inspect(engine).get_table_names()
    engine.dispose()
    assert "app_meta" in tables
    assert "alembic_version" in tables
