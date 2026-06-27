"""
Batch scraper — runs scraper.py up to TOTAL_RUNS times with a cooldown between each run.
Progress is saved to batch_progress.json so the script can be resumed after a restart.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

TOTAL_RUNS = 18
COOLDOWN_SECONDS = 10
PROGRESS_FILE = Path(__file__).parent / "batch_progress.json"


def load_progress() -> int:
    if PROGRESS_FILE.exists():
        try:
            data = json.loads(PROGRESS_FILE.read_text())
            return int(data.get("completed", 0))
        except (json.JSONDecodeError, ValueError):
            pass
    return 0


def save_progress(completed: int) -> None:
    PROGRESS_FILE.write_text(json.dumps({"completed": completed}, indent=2))


def main() -> None:
    completed = load_progress()

    if completed >= TOTAL_RUNS:
        print(f"Already completed {completed}/{TOTAL_RUNS} runs. Nothing to do.")
        return

    print(f"Resuming from run {completed + 1}/{TOTAL_RUNS}")

    while completed < TOTAL_RUNS:
        run_number = completed + 1
        print(f"\n[{run_number}/{TOTAL_RUNS}] Starting scraper...", flush=True)

        result = subprocess.run(
            [sys.executable, "scraper.py"],
            cwd=Path(__file__).parent,
        )

        if result.returncode != 0:
            print(f"  scraper.py exited with code {result.returncode} — skipping this run.")

        completed += 1
        save_progress(completed)
        print(f"  Done. Completed: {completed}/{TOTAL_RUNS}", flush=True)

        if completed < TOTAL_RUNS:
            print(f"  Cooling down for {COOLDOWN_SECONDS}s...", flush=True)
            time.sleep(COOLDOWN_SECONDS)

    print(f"\nAll {TOTAL_RUNS} runs complete.")
    PROGRESS_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
