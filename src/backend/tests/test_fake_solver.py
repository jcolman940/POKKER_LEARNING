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
        [
            sys.executable,
            str(FAKE),
            "--input_file",
            "cmds.txt",
            "--resource_dir",
            "x",
            "--mode",
            "holdem",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
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
