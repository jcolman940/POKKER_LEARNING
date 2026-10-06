"""Regenerates data/precomputed/preflop_equity_169.npy (heads-up class vs class equity).

Run from the backend environment:
    cd backend && uv run python ../scripts/gen_preflop_equity.py [trials_per_pair]
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
import pokercore

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "precomputed"
SEED = 20261006


def main() -> None:
    trials = int(sys.argv[1]) if len(sys.argv) > 1 else 100_000
    start = time.perf_counter()
    flat = pokercore.preflop_equity_matrix(trials, SEED)
    matrix = np.asarray(flat, dtype=np.float32).reshape(169, 169)
    elapsed = time.perf_counter() - start

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    np.save(OUT_DIR / "preflop_equity_169.npy", matrix)
    meta = {
        "description": "Heads-up preflop all-in equity, class (row) vs class (column), "
        "ties as half. Classes in 13x13 grid order (pokercore.hand_class_names()).",
        "method": "Monte Carlo over compatible combo pairs (exact card removal)",
        "trials_per_pair": trials,
        "seed": SEED,
        "max_standard_error": 0.5 / trials**0.5,
        "core_version": pokercore.version(),
        "classes": pokercore.hand_class_names(),
    }
    (OUT_DIR / "preflop_equity_169.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"done in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
