import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("POKER_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("POKER_DATABASE_URL", raising=False)
    monkeypatch.delenv("POKER_SOLVER_PATH", raising=False)

    from app.config import get_settings
    from app.db.session import _session_factory, get_engine

    get_settings.cache_clear()
    get_engine.cache_clear()
    _session_factory.cache_clear()

    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c

    get_engine().dispose()
    get_settings.cache_clear()
    get_engine.cache_clear()
    _session_factory.cache_clear()


@pytest.fixture
def fake_room():
    from app.parsers import register, unregister
    from tests.fake_parser import FakeParser

    register(FakeParser())
    yield
    unregister("fake")


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
