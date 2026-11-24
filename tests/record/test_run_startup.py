"""`ailsa run note` is cheap: well under a second and no heavy libraries (REC-04)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from ailsa.record.events import AGENT_DIR, MARKER
from ailsa.record.fsutil import atomic_write_json

HEAVY = ["pydantic", "numpy", "rdkit", "scipy", "nmrglue"]

_CODE = (
    "import sys, json\n"
    "from ailsa.cli.run import run\n"
    "try:\n"
    "    run(['note', 'x'])\n"
    "except SystemExit:\n"
    "    pass\n"
    f"print(json.dumps(sorted(m for m in {HEAVY!r} if m in sys.modules)))\n"
)


def _make_run(workspace: Path) -> Path:
    run_dir = workspace / "2026-01-01T1000Z_example_st01"
    run_dir.mkdir(parents=True)
    (run_dir / AGENT_DIR).mkdir()
    atomic_write_json(run_dir / MARKER, {"run_id": run_dir.name, "schema_version": 1})
    return run_dir


def test_note_loads_no_heavy_modules(workspace: Path) -> None:
    run_dir = _make_run(workspace)
    env = {**os.environ, "AILSA_RUN_DIR": str(run_dir), "AILSA_WORKSPACE": str(workspace)}
    proc = subprocess.run(
        [sys.executable, "-c", _CODE], capture_output=True, text=True, env=env, timeout=60
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout.strip().splitlines()[-1]) == []
    assert (run_dir / "events.jsonl").is_file()


def test_note_minimum_wall_time_below_one_second(workspace: Path) -> None:
    run_dir = _make_run(workspace)
    env = {**os.environ, "AILSA_RUN_DIR": str(run_dir), "AILSA_WORKSPACE": str(workspace)}
    times = []
    for _ in range(3):
        start = time.monotonic()
        proc = subprocess.run(
            [sys.executable, "-m", "ailsa.cli", "run", "note", "x"],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )
        times.append(time.monotonic() - start)
        assert proc.returncode == 0, proc.stderr
    assert min(times) < 1.0, times
