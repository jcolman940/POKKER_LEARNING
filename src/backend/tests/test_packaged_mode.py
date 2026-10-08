import pytest
from fastapi.testclient import TestClient

from app import packaged
from app.config import get_settings
from app.db.models import AppMeta, SolverJob
from app.packaged import Heartbeat, Watchdog
from app.solver.queue import PAUSED_KEY

TOKEN = "t"


def _reset_caches():
    from app.db.session import _session_factory, get_engine

    get_settings.cache_clear()
    get_engine.cache_clear()
    _session_factory.cache_clear()


@pytest.fixture
def web_dir(tmp_path):
    web = tmp_path / "web"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text("<html>INDEX</html>", encoding="utf-8")
    (web / "assets" / "a.js").write_text("console.log('a')", encoding="utf-8")
    return web


@pytest.fixture
def shutdown_calls():
    calls = []
    packaged.set_shutdown_callback(lambda: calls.append(1))
    yield calls
    packaged.set_shutdown_callback(None)


@pytest.fixture
def pclient(tmp_path, monkeypatch, web_dir, shutdown_calls):
    monkeypatch.setenv("POKER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("POKER_DATABASE_URL", raising=False)
    monkeypatch.delenv("POKER_SOLVER_PATH", raising=False)
    monkeypatch.setenv("POKER_LAUNCH_TOKEN", TOKEN)
    monkeypatch.setenv("POKER_WEB_DIR", str(web_dir))
    monkeypatch.setenv("POKER_PORT", "47900")
    _reset_caches()
    from app.db.session import get_engine
    from app.main import create_app

    with TestClient(create_app(), base_url="http://127.0.0.1:47900") as c:
        yield c
    get_engine().dispose()
    _reset_caches()


def _add_job(session, status):
    session.add(
        SolverJob(
            spot_hash="h",
            spot={},
            label="x",
            origin="batch",
            priority=1,
            status=status,
        )
    )
    session.commit()


# --- static web ---------------------------------------------------------------------------


def test_root_and_client_routes_serve_index(pclient):
    assert "INDEX" in pclient.get("/").text
    r = pclient.get("/simulador")
    assert r.status_code == 200 and "INDEX" in r.text


def test_assets_are_served(pclient):
    r = pclient.get("/assets/a.js")
    assert r.status_code == 200 and "console.log" in r.text


def test_missing_asset_is_404_not_index(pclient):
    assert pclient.get("/assets/missing.js").status_code == 404


def test_api_still_json_and_flags_packaged(pclient):
    r = pclient.get("/api/version")
    assert r.status_code == 200
    assert r.json()["packaged"] is True


def test_unknown_api_route_is_json_404(pclient):
    r = pclient.get("/api/nada")
    assert r.status_code == 404
    assert "INDEX" not in r.text
    assert r.headers["content-type"].startswith("application/json")


# --- host check ---------------------------------------------------------------------------


def test_foreign_host_rejected(pclient):
    r = pclient.get("/api/version", headers={"Host": "evil.com"})
    assert r.status_code == 400
    assert r.json() == {"detail": "Host no permitido"}


def test_loopback_hosts_allowed(pclient):
    for host in ("127.0.0.1:47900", "localhost:47900", "127.0.0.1", "localhost"):
        assert pclient.get("/api/version", headers={"Host": host}).status_code == 200


# --- control endpoints --------------------------------------------------------------------


def test_ping_204_and_status_age(pclient):
    assert pclient.get("/api/app/status").json()["heartbeat_age_s"] is None
    assert pclient.post("/api/app/ping").status_code == 204
    body = pclient.get("/api/app/status").json()
    assert body["packaged"] is True
    assert body["heartbeat_age_s"] is not None and body["heartbeat_age_s"] < 5


def test_shutdown_requires_token(pclient, shutdown_calls):
    assert pclient.post("/api/app/shutdown").status_code == 403
    assert pclient.post("/api/app/shutdown", headers={"X-Pokker-Token": "bad"}).status_code == 403
    assert shutdown_calls == []
    r = pclient.post("/api/app/shutdown", headers={"X-Pokker-Token": TOKEN})
    assert r.status_code == 202
    assert shutdown_calls == [1]


def test_status_reflects_solver_queue(pclient, monkeypatch):
    from app.db.session import _session_factory

    monkeypatch.setattr("app.solver.worker_registry.worker_running", lambda: True)
    base = pclient.get("/api/app/status").json()
    assert base["solver_busy"] is False and base["solver_pending"] == 0
    with _session_factory()() as s:
        _add_job(s, "running")
        _add_job(s, "queued")
        _add_job(s, "queued")
    body = pclient.get("/api/app/status").json()
    assert body["solver_busy"] is True and body["solver_pending"] == 2
    with _session_factory()() as s:
        s.merge(AppMeta(key=PAUSED_KEY, value="1"))
        s.commit()
    assert pclient.get("/api/app/status").json()["solver_pending"] == 0


def test_worker_not_running_without_solver(pclient):
    from app.solver import worker_registry

    assert worker_registry.worker_running() is False


def test_status_reports_no_work_when_the_worker_is_not_running(pclient):
    from app.db.session import _session_factory

    with _session_factory()() as s:
        _add_job(s, "running")
        _add_job(s, "queued")
    body = pclient.get("/api/app/status").json()
    assert body["solver_busy"] is False and body["solver_pending"] == 0


# --- CSRF guard ---------------------------------------------------------------------------


def test_cross_origin_post_rejected(pclient):
    r = pclient.post("/api/app/ping", headers={"Origin": "http://evil.com"})
    assert r.status_code == 403
    r = pclient.post("/api/app/ping", headers={"Origin": "http://127.0.0.1:47901"})
    assert r.status_code == 403
    r = pclient.post("/api/app/ping", headers={"Sec-Fetch-Site": "cross-site"})
    assert r.status_code == 403


def test_same_origin_and_originless_posts_allowed(pclient):
    for origin in ("http://127.0.0.1:47900", "http://localhost:47900"):
        r = pclient.post(
            "/api/app/ping", headers={"Origin": origin, "Sec-Fetch-Site": "same-origin"}
        )
        assert r.status_code == 204, origin
    assert pclient.post("/api/app/ping").status_code == 204


def test_cross_origin_get_is_not_blocked(pclient):
    r = pclient.get("/api/version", headers={"Origin": "http://evil.com"})
    assert r.status_code == 200


def test_dev_mode_has_no_csrf_guard(client):
    r = client.post("/api/ranges/parse", json={"text": "AA"}, headers={"Origin": "http://evil.com"})
    assert r.status_code != 403


# --- watchdog -----------------------------------------------------------------------------


class _Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def _watchdog(busy=False, timeout=10.0):
    clock = _Clock()
    hb = Heartbeat(clock=clock)
    fired = []
    wd = Watchdog(hb, timeout, lambda: busy, check_every=0.01, on_timeout=lambda: fired.append(1))
    return clock, hb, wd, fired


def test_watchdog_does_not_fire_before_first_beat():
    clock, _hb, wd, fired = _watchdog()
    clock.t += 10_000
    assert wd.check() is False and fired == []


def test_watchdog_does_not_fire_while_beating():
    clock, hb, wd, fired = _watchdog()
    hb.beat()
    clock.t += 5
    assert wd.check() is False and fired == []


def test_watchdog_does_not_fire_with_solver_busy():
    clock, hb, wd, fired = _watchdog(busy=True)
    hb.beat()
    clock.t += 1000
    assert wd.check() is False and fired == []


def test_watchdog_fires_after_timeout_without_work():
    clock, hb, wd, fired = _watchdog()
    hb.beat()
    clock.t += 11
    assert wd.check() is True and fired == [1]


def test_default_heartbeat_timeout_is_three_minutes(monkeypatch):
    monkeypatch.delenv("POKER_HEARTBEAT_TIMEOUT_S", raising=False)
    from app.config import Settings

    assert Settings().heartbeat_timeout_s == 180


def _gap_watchdog(timeout=10.0, check_every=5.0):
    clock = _Clock()
    hb = Heartbeat(clock=clock)
    fired = []
    wd = Watchdog(
        hb, timeout, lambda: False, check_every=check_every, on_timeout=lambda: fired.append(1)
    )
    return clock, hb, wd, fired


def test_watchdog_treats_a_suspend_gap_as_a_fresh_beat():
    clock, hb, wd, fired = _gap_watchdog()
    hb.beat()
    assert wd.check() is False
    clock.t += 3600  # the PC slept: way more than 3 x check_every since the last check
    assert wd.check() is False and fired == []
    assert hb.age() == 0
    # Regular checks afterwards: the timeout counts again from the wake-up.
    for _ in range(2):
        clock.t += 5
        assert wd.check() is False
    clock.t += 5
    assert wd.check() is True and fired == [1]


def test_watchdog_without_gap_still_fires_on_regular_checks():
    clock, hb, wd, fired = _gap_watchdog()
    hb.beat()
    for _ in range(2):
        clock.t += 5
        assert wd.check() is False
    clock.t += 5
    assert wd.check() is True and fired == [1]


def test_watchdog_logs_shutdown_as_warning(caplog):
    clock, hb, wd, fired = _gap_watchdog()
    hb.beat()
    clock.t += 11
    with caplog.at_level("WARNING", logger="app.packaged"):
        assert wd.check() is True
    assert any(
        r.levelname == "WARNING" and "No heartbeat" in r.getMessage() for r in caplog.records
    )


def test_watchdog_thread_fires_and_stops():
    import time

    hb = Heartbeat()
    hb.beat()
    fired = []
    wd = Watchdog(hb, 0.05, lambda: False, check_every=0.01, on_timeout=lambda: fired.append(1))
    wd.start()
    deadline = time.monotonic() + 3
    while not fired and time.monotonic() < deadline:
        time.sleep(0.01)
    wd.stop()
    assert fired == [1]


def test_request_shutdown_uses_registered_callback(shutdown_calls):
    packaged.request_shutdown()
    assert shutdown_calls == [1]


def test_lifespan_watchdog_shuts_down_idle_app(tmp_path, monkeypatch, shutdown_calls):
    import time

    monkeypatch.setenv("POKER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("POKER_DATABASE_URL", raising=False)
    monkeypatch.delenv("POKER_SOLVER_PATH", raising=False)
    monkeypatch.setenv("POKER_LAUNCH_TOKEN", TOKEN)
    monkeypatch.setenv("POKER_HEARTBEAT_TIMEOUT_S", "0.05")
    monkeypatch.delenv("POKER_WEB_DIR", raising=False)
    _reset_caches()
    from app.db.session import get_engine
    from app.main import create_app

    app = create_app()
    app.state.watchdog_check_every = 0.01
    with TestClient(app, base_url="http://127.0.0.1:47900") as c:
        c.post("/api/app/ping")
        deadline = time.monotonic() + 3
        while not shutdown_calls and time.monotonic() < deadline:
            time.sleep(0.01)
    get_engine().dispose()
    _reset_caches()
    assert shutdown_calls


def test_lifespan_watchdog_ignores_queued_jobs_without_solver(
    tmp_path, monkeypatch, shutdown_calls
):
    import time

    monkeypatch.setenv("POKER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("POKER_DATABASE_URL", raising=False)
    monkeypatch.delenv("POKER_SOLVER_PATH", raising=False)
    monkeypatch.setenv("POKER_LAUNCH_TOKEN", TOKEN)
    monkeypatch.setenv("POKER_HEARTBEAT_TIMEOUT_S", "0.05")
    monkeypatch.delenv("POKER_WEB_DIR", raising=False)
    _reset_caches()
    from app.db.session import _session_factory, get_engine
    from app.main import create_app

    app = create_app()
    app.state.watchdog_check_every = 0.01
    with TestClient(app, base_url="http://127.0.0.1:47900") as c:
        with _session_factory()() as s:
            _add_job(s, "queued")  # can never run: there is no solver
        c.post("/api/app/ping")
        deadline = time.monotonic() + 3
        while not shutdown_calls and time.monotonic() < deadline:
            time.sleep(0.01)
        assert c.get("/api/app/status").json()["solver_pending"] == 0
    get_engine().dispose()
    _reset_caches()
    assert shutdown_calls


# --- development mode regression ----------------------------------------------------------


def test_dev_mode_has_no_control_routes_nor_host_check(client):
    assert client.post("/api/app/ping").status_code == 404
    assert client.get("/api/app/status").status_code == 404
    r = client.get("/api/version", headers={"Host": "evil.com"})
    assert r.status_code == 200
    assert r.json()["packaged"] is False


# --- server entry point -------------------------------------------------------------------


def test_server_main_rejects_non_loopback_host(monkeypatch):
    monkeypatch.setenv("POKER_HOST", "0.0.0.0")
    get_settings.cache_clear()
    from app import server_main

    try:
        assert server_main.main() == 2
    finally:
        get_settings.cache_clear()


def test_server_logging_sends_app_info_to_the_stream():
    import io
    import logging

    from app import server_main

    stream = io.StringIO()
    app_logger = logging.getLogger("app")
    level = app_logger.level
    handler = server_main.configure_logging(stream)
    try:
        logging.getLogger("app.packaged").info("hola desde app")
        logging.getLogger("uvicorn.access").warning("GET / 200")
        logging.getLogger("uvicorn.error").info("Started server process")
    finally:
        logging.getLogger().removeHandler(handler)
        app_logger.setLevel(level)
    out = stream.getvalue()
    assert "hola desde app" in out
    assert "GET / 200" in out  # WARNING and above from anyone still reach the log
    assert "Started server process" not in out
