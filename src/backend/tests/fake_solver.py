"""Stand-in for TexasSolver's console_solver.exe, driven by environment variables.

FAKE_SOLVER_MODE: ok | fail | hang | garbage | no_output
FAKE_SOLVER_FIXTURE: JSON copied to the `dump_result` path in `ok` mode
FAKE_SOLVER_DELAY: seconds between progress lines (default 0.05)
"""

import itertools
import json
import os
import shutil
import sys
import time
from pathlib import Path


def main(argv: list[str]) -> int:
    args = dict(zip(argv[1::2], argv[2::2], strict=False))
    commands = Path(args["--input_file"]).read_text().splitlines()
    out = next(line.split(" ", 1)[1] for line in commands if line.startswith("dump_result "))
    mode = os.environ.get("FAKE_SOLVER_MODE", "ok")
    delay = float(os.environ.get("FAKE_SOLVER_DELAY", "0.05"))

    if mode == "fail":
        print("terminate called after throwing an instance of 'std::runtime_error'")
        print("  what():   range str AcKc len not valid ")
        return 3

    steps = itertools.count(1) if mode == "hang" else range(1, 4)
    with Path("tmp_log.txt").open("w") as log:
        for i in steps:
            entry = {"exploitibility": 10.0 / i, "iteration": i * 10, "time_ms": i * 100}
            log.write(json.dumps(entry) + "\n")
            log.flush()
            time.sleep(delay)

    if mode == "garbage":
        Path(out).write_text("{not json")
    elif mode == "ok":
        shutil.copy(os.environ["FAKE_SOLVER_FIXTURE"], out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
