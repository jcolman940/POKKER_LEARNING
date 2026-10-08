"""Runs the TexasSolver console binary as a subprocess and follows its progress."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.solver.config_gen import RESULT_FILE

INPUT_FILE = "cmds.txt"
LOG_FILE = "tmp_log.txt"  # written by the solver itself
STDOUT_FILE = "stdout.txt"


@dataclass
class Progress:
    iteration: int = 0
    exploitability: float | None = None  # % of the pot
    elapsed_ms: int = 0


class SolverError(Exception):
    pass


class SolverStopped(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def solver_command(solver_path: Path, input_file: str) -> list[str]:
    if solver_path.suffix == ".py":
        prefix = [sys.executable, str(solver_path)]
    else:
        prefix = [str(solver_path)]
    resources = solver_path.parent / "resources"
    return [
        *prefix,
        "--input_file",
        input_file,
        "--resource_dir",
        str(resources),
        "--mode",
        "holdem",
    ]


def kill_tree(pid: int) -> None:
    """Kills a process and its children (the solver spawns worker threads/processes)."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True)
    else:
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _read_progress(log: Path, last: Progress) -> Progress:
    if not log.exists():
        return last
    for line in reversed(log.read_text(errors="replace").splitlines()):
        try:
            entry = json.loads(line)
        except ValueError:
            continue  # partially written line
        if not isinstance(entry, dict):
            continue
        return Progress(
            iteration=int(entry.get("iteration", 0)),
            exploitability=entry.get("exploitibility"),
            elapsed_ms=int(entry.get("time_ms", 0)),
        )
    return last


def _tail(path: Path, lines: int = 5) -> str:
    if not path.exists():
        return ""
    return "\n".join(path.read_text(errors="replace").strip().splitlines()[-lines:])


def run_solver(
    commands: str,
    workdir: Path,
    solver_path: Path,
    *,
    timeout_s: float,
    on_start: Callable[[int], None] | None = None,
    on_progress: Callable[[Progress], None] | None = None,
    should_stop: Callable[[], str | None] | None = None,
    poll_s: float = 0.5,
) -> tuple[dict, Progress]:
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / INPUT_FILE).write_text(commands)
    for name in (RESULT_FILE, LOG_FILE):
        (workdir / name).unlink(missing_ok=True)

    kwargs: dict = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    with (workdir / STDOUT_FILE).open("w") as out:
        proc = subprocess.Popen(
            solver_command(solver_path, INPUT_FILE),
            cwd=workdir,
            stdout=out,
            stderr=subprocess.STDOUT,
            **kwargs,
        )
        progress = Progress()
        started = time.monotonic()
        try:
            if on_start:
                on_start(proc.pid)
            while proc.poll() is None:
                time.sleep(poll_s)
                current = _read_progress(workdir / LOG_FILE, progress)
                if current != progress:
                    progress = current
                    if on_progress:
                        on_progress(progress)
                if proc.poll() is not None:
                    break  # finished during the last sleep: not a timeout/stop
                if should_stop and (reason := should_stop()):
                    raise SolverStopped(reason)
                if time.monotonic() - started > timeout_s:
                    raise SolverError(f"timeout: el solve superó {timeout_s / 60:g} min")
        except BaseException:
            try:
                kill_tree(proc.pid)
            finally:
                if proc.poll() is None:
                    proc.kill()
                proc.wait(timeout=30)
            raise

    progress = _read_progress(workdir / LOG_FILE, progress)
    if proc.returncode != 0:
        raise SolverError(
            f"El solver terminó con código {proc.returncode}: {_tail(workdir / STDOUT_FILE)}"
        )
    result = workdir / RESULT_FILE
    if not result.exists():
        raise SolverError(f"El solver no escribió el resultado: {_tail(workdir / STDOUT_FILE)}")
    try:
        return json.loads(result.read_text()), progress
    except ValueError as e:
        raise SolverError(f"Salida del solver ilegible: {e}") from e
