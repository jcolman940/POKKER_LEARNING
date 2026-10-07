from pathlib import Path

import pytest

from app.solver.runner import Progress, SolverError, SolverStopped, run_solver, solver_command

FIXTURES = Path(__file__).parent / "fixtures" / "solver"
FAKE = Path(__file__).parent / "fake_solver.py"
COMMANDS = "set_pot 2000\ndump_result result.json\n"


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setenv("FAKE_SOLVER_FIXTURE", str(FIXTURES / "river_out.json"))
    monkeypatch.setenv("FAKE_SOLVER_DELAY", "0.01")

    def set_mode(mode):
        monkeypatch.setenv("FAKE_SOLVER_MODE", mode)

    return set_mode


def test_command_for_python_script_uses_interpreter():
    cmd = solver_command(FAKE, "cmds.txt")
    assert cmd[1] == str(FAKE)
    assert cmd[2:4] == ["--input_file", "cmds.txt"]
    assert cmd[-2:] == ["--mode", "holdem"]


def test_ok_returns_raw_output_and_progress(tmp_path, fake):
    fake("ok")
    seen: list[Progress] = []
    pids: list[int] = []
    raw, last = run_solver(
        COMMANDS,
        tmp_path,
        FAKE,
        timeout_s=30,
        on_start=pids.append,
        on_progress=seen.append,
        poll_s=0.01,
    )
    assert raw["player"] == 1
    assert last.iteration == 30
    assert last.exploitability == pytest.approx(10 / 3)
    assert pids and seen
    assert (tmp_path / "cmds.txt").read_text() == COMMANDS


def test_failure_reports_last_output_lines(tmp_path, fake):
    fake("fail")
    with pytest.raises(SolverError, match="len not valid"):
        run_solver(COMMANDS, tmp_path, FAKE, timeout_s=30, poll_s=0.01)


def test_missing_output(tmp_path, fake):
    fake("no_output")
    with pytest.raises(SolverError, match="no escribió"):
        run_solver(COMMANDS, tmp_path, FAKE, timeout_s=30, poll_s=0.01)


def test_garbage_output(tmp_path, fake):
    fake("garbage")
    with pytest.raises(SolverError, match="ilegible"):
        run_solver(COMMANDS, tmp_path, FAKE, timeout_s=30, poll_s=0.01)


def test_timeout_kills_the_process(tmp_path, fake):
    fake("hang")
    with pytest.raises(SolverError, match="timeout"):
        run_solver(COMMANDS, tmp_path, FAKE, timeout_s=0.5, poll_s=0.05)


def test_should_stop(tmp_path, fake):
    fake("hang")
    with pytest.raises(SolverStopped) as exc:
        run_solver(
            COMMANDS, tmp_path, FAKE, timeout_s=30, poll_s=0.05, should_stop=lambda: "cancelled"
        )
    assert exc.value.reason == "cancelled"
