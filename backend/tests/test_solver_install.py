"""Installing TexasSolver from the app (served from a local test zip, never the real download)."""

from __future__ import annotations

import hashlib
import http.server
import io
import threading
import time
import zipfile
from pathlib import Path

import pytest

from app.config import get_settings
from app.solver import install
from app.solver.worker_registry import solver_available, stop_worker

EXE = install.EXE_RELATIVE


def _make_zip(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


@pytest.fixture
def served(tmp_path):
    """Serve a dict of {url path: bytes} from a local thread; yields (base_url, payloads)."""
    payloads: dict[str, bytes] = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = payloads.get(self.path)
            if body is None:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", payloads
    server.shutdown()
    server.server_close()


@pytest.fixture
def env(db_session):
    install.Installer.reset()
    yield get_settings()
    stop_worker()
    install.Installer.reset()


def _wait(inst, timeout=15.0):
    end = time.time() + timeout
    while time.time() < end:
        st = inst.status()
        if st.state in ("done", "error"):
            return st
        time.sleep(0.02)
    raise AssertionError(f"installer stuck: {inst.status()}")


def test_install_ok(env, served):
    base, payloads = served
    data = _make_zip({EXE: b"fake exe", "TexasSolver-v0.2.0-Windows/resources/x.txt": b"r"})
    payloads["/ts.zip"] = data
    inst = install.Installer.get()
    inst.start(f"{base}/ts.zip", hashlib.sha256(data).hexdigest().lower())
    st = _wait(inst)
    assert st.state == "done", st.error
    assert st.bytes == st.total == len(data)
    exe = env.data_dir / install.TOOLS_SUBDIR / EXE
    assert exe.read_bytes() == b"fake exe"
    assert install.detected_solver_path(env) == exe
    assert solver_available()
    assert not (env.data_dir / "tools" / ".tmp").exists()


def test_install_replaces_old_installation(env, served):
    base, payloads = served
    old = env.data_dir / install.TOOLS_SUBDIR / "old.txt"
    old.parent.mkdir(parents=True)
    old.write_text("old")
    data = _make_zip({EXE: b"new"})
    payloads["/ts.zip"] = data
    inst = install.Installer.get()
    inst.start(f"{base}/ts.zip", hashlib.sha256(data).hexdigest().upper())
    assert _wait(inst).state == "done"
    assert not old.exists()


def test_wrong_hash_is_error_and_installs_nothing(env, served):
    base, payloads = served
    payloads["/ts.zip"] = _make_zip({EXE: b"x"})
    inst = install.Installer.get()
    inst.start(f"{base}/ts.zip", "0" * 64)
    st = _wait(inst)
    assert st.state == "error"
    assert "hash distinto" in st.error
    assert not (env.data_dir / install.TOOLS_SUBDIR).exists()
    assert install.detected_solver_path(env) is None
    assert not solver_available()


def test_server_down_is_error(env):
    inst = install.Installer.get()
    inst.start("http://127.0.0.1:9/ts.zip", "0" * 64)
    st = _wait(inst)
    assert st.state == "error"
    assert st.error.startswith("No se pudo descargar TexasSolver")


def test_not_a_zip_is_error(env, served):
    base, payloads = served
    data = b"not a zip at all"
    payloads["/ts.zip"] = data
    inst = install.Installer.get()
    inst.start(f"{base}/ts.zip", hashlib.sha256(data).hexdigest())
    st = _wait(inst)
    assert st.state == "error"
    assert st.error.startswith("No se pudo descomprimir TexasSolver")


def test_zip_slip_is_rejected(env, served):
    base, payloads = served
    data = _make_zip({EXE: b"x", "../evil.txt": b"evil"})
    payloads["/ts.zip"] = data
    inst = install.Installer.get()
    inst.start(f"{base}/ts.zip", hashlib.sha256(data).hexdigest())
    st = _wait(inst)
    assert st.state == "error"
    assert st.error.startswith("No se pudo descomprimir TexasSolver")
    assert not (env.data_dir / "tools" / "evil.txt").exists()
    assert not (env.data_dir / "evil.txt").exists()
    assert not (env.data_dir / install.TOOLS_SUBDIR).exists()


def test_second_start_while_running_returns_current_state(env, served):
    base, payloads = served
    gate = threading.Event()
    data = _make_zip({EXE: b"x"})

    payloads["/ts.zip"] = data
    inst = install.Installer.get()
    orig = inst._run

    def slow_run(url, sha):
        gate.wait(5)
        orig(url, sha)

    inst._run = slow_run
    first = inst.start(f"{base}/ts.zip", hashlib.sha256(data).hexdigest())
    second = inst.start("http://127.0.0.1:9/other.zip", "0" * 64)
    assert first.state == "downloading"
    assert second.state == "downloading"
    gate.set()
    assert _wait(inst).state == "done"


def test_env_path_has_priority(env, tmp_path):
    custom = tmp_path / "custom_solver.exe"
    custom.write_bytes(b"x")
    installed = env.data_dir / install.TOOLS_SUBDIR / EXE
    installed.parent.mkdir(parents=True)
    installed.write_bytes(b"y")
    s = get_settings().model_copy(update={"solver_path": custom})
    assert install.detected_solver_path(s) == custom
    missing = s.model_copy(update={"solver_path": Path(tmp_path / "nope.exe")})
    assert install.detected_solver_path(missing) == installed


def test_api_endpoints(client, served, monkeypatch):
    base, payloads = served
    from app.solver import install as inst_mod

    inst_mod.Installer.reset()
    r = client.get("/api/solver/install")
    assert r.status_code == 200 and r.json()["state"] == "idle"
    data = _make_zip({EXE: b"x"})
    payloads["/ts.zip"] = data
    # The API uses the real URL/hash; patch the constants to the local server.
    monkeypatch.setattr(inst_mod, "TEXASSOLVER_URL", f"{base}/ts.zip")
    monkeypatch.setattr(inst_mod, "TEXASSOLVER_SHA256", hashlib.sha256(data).hexdigest())
    try:
        r = client.post("/api/solver/install")
        assert r.status_code == 202
        assert set(r.json()) == {"state", "bytes", "total", "error"}
        st = _wait(inst_mod.Installer.get())
        assert st.state == "done", st.error
        status = client.get("/api/solver/status").json()
        assert status["configured"] is True
        assert status["path"].endswith("console_solver.exe")
    finally:
        stop_worker()
        inst_mod.Installer.reset()


def test_failed_final_rename_keeps_old_install(env, served, monkeypatch):
    base, payloads = served
    target = env.data_dir / install.TOOLS_SUBDIR
    old_exe = target / EXE
    old_exe.parent.mkdir(parents=True)
    old_exe.write_bytes(b"old")
    data = _make_zip({EXE: b"new"})
    payloads["/ts.zip"] = data

    real_rename = Path.rename

    def flaky(self, dst):
        if self.name == "extract":
            raise OSError("boom")
        return real_rename(self, dst)

    monkeypatch.setattr(Path, "rename", flaky)
    inst = install.Installer.get()
    inst.start(f"{base}/ts.zip", hashlib.sha256(data).hexdigest())
    st = _wait(inst)
    assert st.state == "error"
    assert st.error.startswith("No se pudo instalar TexasSolver")
    assert old_exe.read_bytes() == b"old"
