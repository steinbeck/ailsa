"""Deterministic fixture-record builder (invented tiny molecules, dataset label ``example``)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ailsa.record.events import AGENT_DIR, MARKER
from ailsa.record.fsutil import atomic_write_bytes, atomic_write_json, sha256_bytes
from ailsa.record.log import append_event

HOST = "testhost"
TOOL = {"kind": "tool", "name": "ailsa"}
HOOK = {"kind": "hook", "name": "claude-code"}
AGENT = {"kind": "agent", "name": "chemist", "role": "nmr-chemist"}

RANKING = {
    "schema": "ailsa.ranking",
    "schema_version": "1",
    "ranking_id": "rk01",
    "method": "nearest-line",
    "tolerance": 3.0,
    "total_solutions": 2,
    "distinct_structures": 2,
    "candidates": [
        {"id": "cand:rk01:1", "rank": 1, "smiles": "CCO", "mae": 0.8, "within_tolerance": 2},
        {"id": "cand:rk01:2", "rank": 2, "smiles": "CC(C)O", "mae": 2.1, "within_tolerance": 1},
    ],
}
DECLARATION = {
    "schema": "ailsa.final",
    "schema_version": "1",
    "outcome": "proposal",
    "termination_reason": "ranking has a clear best candidate",
    "ranking_id": "rk01",
    "candidate": 1,
    "alternatives": [{"candidate": 2, "status": "less_likely", "reason": "larger error"}],
    "confidence": "medium",
    "caveats": ["only one 2D experiment"],
    "open_questions": ["is the methyl group split?"],
    "next_steps": ["record an HMBC"],
}


def _dump(obj: Any) -> bytes:
    return (json.dumps(obj, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _write_art(run_dir: Path, kind: str, n: int, rel: str, obj: Any) -> dict[str, Any]:
    data = _dump(obj)
    target = run_dir / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(target, data)
    return {
        "id": f"art:{kind}:{n}",
        "kind": kind,
        "path": rel,
        "sha256": sha256_bytes(data),
        "bytes": len(data),
        "supersedes": None,
    }


def build_fixture_record(
    run_dir: Path,
    *,
    hooks: bool = True,
    declared: bool = True,
    stale: bool = False,
    hand_ranking: bool = False,
    withdraw: bool = False,
    base_utc: str = "2026-01-01T10:00:00.000Z",
) -> Path:
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / AGENT_DIR).mkdir(exist_ok=True)
    atomic_write_json(run_dir / MARKER, {"run_id": run_dir.name, "schema_version": 1})
    t0 = datetime.fromisoformat(base_utc.replace("Z", "+00:00"))
    step = [0]

    def add(type_: str, payload: dict[str, Any], actor: dict[str, Any] = TOOL, **kw: Any) -> None:
        utc = (t0 + timedelta(minutes=step[0])).isoformat(timespec="milliseconds")
        step[0] += 1
        append_event(
            run_dir, type_, payload, actor=actor, utc=utc.replace("+00:00", "Z"), host=HOST, **kw
        )

    add(
        "run.created",
        {
            "dataset": {"label": "example"},
            "class": "public",
            "request": {"prompt": "Elucidate the structure of the example data set."},
            "prior_runs": {},
            "writer_host": HOST,
        },
    )
    add(
        "env.captured",
        {
            "ailsa": "0.0",
            "skill": "test",
            "lsd": "3.5",
            "outlsd": "3.5",
            "database": "none",
            "predictor": "hose",
            "harness": "claude-code" if hooks else "headless",
            "mode": "interactive",
            "time_limit_s": 3600,
            "web_tools": "disabled",
            "host": HOST,
        },
    )
    if hooks:
        add("session.started", {"source": "startup", "model": "test-model"}, HOOK)
        add("prompt.submitted", {"text": "start", "chars": 5, "auto": True}, HOOK)
    add(
        "spectra.scanned",
        {
            "experiments": [
                {"experiment": "1", "kind": "13C"},
                {"experiment": "5", "kind": "HSQC"},
            ],
            "unreadable": [],
        },
    )
    add(
        "peaks.picked",
        {
            "pick_id": "pick:1:1",
            "experiment": "1",
            "picker": "ailsa",
            "parameters": {},
            "count": 3,
            "noise_sigma": 1.0,
        },
    )
    add("note.added", {"text": "three carbons seen", "sender": "chemist"}, AGENT)
    add(
        "lsd.input.registered",
        {
            "iteration": "it01",
            "parent": None,
            "purpose": "main",
            "lsd_sha256": "0" * 64,
            "path": "iterations/it01/input.lsd",
        },
    )
    add("solver.started", {"iteration": "it01", "host": HOST, "timeout_s": 60})
    add(
        "solver.finished",
        {
            "iteration": "it01",
            "outcome": "solutions",
            "count": 2,
            "elapsed_s": 1.5,
            "host": HOST,
            "provenance": {},
        },
    )
    if hand_ranking:
        (run_dir / AGENT_DIR / "ranking.json").write_text('{"top": "CCCO"}\n', encoding="utf-8")
        (run_dir / AGENT_DIR / "final_results.md").write_text("Result: CCCO\n", encoding="utf-8")
    else:
        art = _write_art(run_dir, "ranking", 1, "rankings/rk01.json", RANKING)
        add(
            "ranking.computed",
            {"ranking_id": "rk01", "method": "nearest-line", "inputs": [], "candidate_count": 2},
            artefacts=[art],
        )
        if declared:
            fin = _write_art(run_dir, "final", 1, "final/final-01.json", DECLARATION)
            add(
                "final.declared",
                {
                    "outcome": "proposal",
                    "ranking_id": "rk01",
                    "candidate": 1,
                    "confidence": "medium",
                },
                AGENT,
                artefacts=[fin],
            )
            if withdraw:
                add("final.withdrawn", {"reason": "changed my mind"}, AGENT)
    if stale:
        add(
            "solver.finished",
            {
                "iteration": "it02",
                "outcome": "solutions",
                "count": 1,
                "elapsed_s": 1.0,
                "host": HOST,
                "provenance": {},
            },
        )
    if hooks:
        add("agent.turn_ended", {"agent_id": "main"}, HOOK)
        add("session.ended", {"reason": "other"}, HOOK)
    else:
        add(
            "run.attempt.ended",
            {"attempt": 1, "exit_code": 0, "reason": "exited", "elapsed_s": 60},
        )
    return run_dir
