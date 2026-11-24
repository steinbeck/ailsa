"""`ailsa run finalize` and `ailsa run close`: strict declarations (REC-16, REC-23, D-08)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from ailsa.cli.run import run
from ailsa.record.artefacts import register_artefact
from ailsa.record.finalize import resolve_ranking, unregistered_files
from ailsa.record.fsutil import sha256_bytes
from ailsa.record.log import append_event, read_events

from ._fixture_record import RANKING, build_fixture_record

TOOL = {"kind": "tool", "name": "ailsa"}
LSD_SHA = "a" * 64


def _invoke(args: list[str]) -> Any:
    return CliRunner().invoke(run, args)


def _events(run_dir: Path) -> list[dict[str, Any]]:
    return read_events(run_dir)["events"]


def _types(run_dir: Path) -> list[str]:
    return [e["type"] for e in _events(run_dir)]


def _solve(run_dir: Path, iteration: str = "it01", sha: str = LSD_SHA) -> None:
    append_event(
        run_dir,
        "lsd.input.registered",
        {"iteration": iteration, "purpose": "main", "lsd_sha256": sha},
        actor=TOOL,
    )
    append_event(
        run_dir,
        "solver.finished",
        {"iteration": iteration, "outcome": "solutions", "count": 2},
        actor=TOOL,
    )


def _rank(
    run_dir: Path, n: int = 1, *, inputs: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    rk = f"rk{n:02d}"
    data = {**RANKING, "ranking_id": rk}
    blob = (json.dumps(data, sort_keys=True, indent=2) + "\n").encode()
    if inputs is None:
        inputs = [{"iteration": "it01", "lsd_sha256": LSD_SHA, "sol_sha256": "b" * 64}]
    return register_artefact(
        run_dir,
        kind="ranking",
        rel_path=f"rankings/{rk}.json",
        data=blob,
        event_type="ranking.computed",
        payload={
            "ranking_id": rk,
            "method": "nearest-line",
            "inputs": inputs,
            "candidate_count": 2,
            "sha256": sha256_bytes(blob),
        },
        actor=TOOL,
        refs=[rk],
    )


@pytest.fixture
def active(new_run, monkeypatch) -> Path:
    _, run_dir = new_run
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    append_event(
        run_dir,
        "run.created",
        {"dataset": {"label": "example"}, "class": "public", "request": {}},
        actor=TOOL,
    )
    _solve(run_dir)
    _rank(run_dir)
    return run_dir


FULL = [
    "finalize",
    "--outcome",
    "proposal",
    "--ranking",
    "latest",
    "--candidate",
    "1",
    "--confidence",
    "medium",
    "--caveat",
    "one HMBC decides",
    "--open-question",
    "q",
    "--next-step",
    "n",
    "--alternative",
    "2:less_likely",
    "--termination-reason",
    "10 or fewer solutions",
]


def test_happy_path(active: Path) -> None:
    res = _invoke(FULL)
    assert res.exit_code == 0, res.output
    assert "final_results.md" in res.stdout and "CASE-PROGRESS.md" in res.stdout
    decl = json.loads((active / "final" / "declaration.1.json").read_text())
    assert decl["candidate_id"] == "cand:rk01:1"
    assert decl["iterations"] == ["it01"]
    assert decl["ranking_sha256"]
    assert decl["alternatives"] == [{"rank": 2, "status": "less_likely"}]
    assert "final.declared" in _types(active)
    assert (active / "renderings" / "final_results.md").is_file()
    assert "run.finished" not in _types(active)
    status = _invoke(["status"])
    assert "result declared: proposal" in status.stdout


def test_no_run_is_refused(workspace: Path) -> None:
    res = _invoke(FULL)
    assert res.exit_code == 1
    assert "start one with ailsa run init" in res.stderr


def test_proposal_without_candidate(active: Path) -> None:
    before = len(_events(active))
    res = _invoke(["finalize", "--outcome", "proposal"])
    assert res.exit_code == 1 and "--candidate" in res.stderr
    assert len(_events(active)) == before


def test_candidate_beyond_ranking(active: Path) -> None:
    res = _invoke(["finalize", "--outcome", "proposal", "--candidate", "9"])
    assert res.exit_code == 1 and "not in ranking" in res.stderr


def test_hand_made_ranking_refused(active: Path) -> None:
    (active / "agent" / "ranking.json").write_text('{"top": "CCCO"}\n')
    for ref in ("agent/ranking.json", "rk77", "../x"):
        res = _invoke(["finalize", "--outcome", "inconclusive", "--ranking", ref])
        assert res.exit_code == 1, ref
        assert "this ranking was not written by ailsa lsd rank" in res.stderr


def test_changed_ranking_file(active: Path) -> None:
    path = active / "rankings" / "rk01.json"
    path.write_text(path.read_text().replace("CCO", "CCC"))
    res = _invoke(["finalize", "--outcome", "inconclusive"])
    assert res.exit_code == 1 and "ranking file changed after it was recorded" in res.stderr


def test_stale_by_later_solve(active: Path) -> None:
    append_event(
        active, "solver.finished", {"iteration": "it01", "outcome": "solutions"}, actor=TOOL
    )
    res = _invoke(FULL)
    assert res.exit_code == 1 and "ranking is stale: re-run ailsa lsd rank" in res.stderr


def test_stale_by_changed_input(active: Path) -> None:
    append_event(
        active,
        "lsd.input.registered",
        {"iteration": "it01", "purpose": "main", "lsd_sha256": "c" * 64},
        actor=TOOL,
    )
    res = _invoke(["finalize", "--outcome", "inconclusive"])
    assert res.exit_code == 1 and "stale" in res.stderr


def test_unregistered_input_iteration(new_run, monkeypatch) -> None:
    _, run_dir = new_run
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    _rank(run_dir, inputs=[{"iteration": None, "lsd_sha256": None}])
    res = _invoke(["finalize", "--outcome", "inconclusive"])
    assert res.exit_code == 1 and "not a registered iteration" in res.stderr


def test_unknown_outcome(active: Path) -> None:
    assert _invoke(["finalize", "--outcome", "maybe"]).exit_code == 2


def test_inconclusive_needs_ranking_not_candidate(active: Path) -> None:
    res = _invoke(["finalize", "--outcome", "inconclusive"])
    assert res.exit_code == 0, res.output


def test_inconclusive_without_any_ranking(new_run, monkeypatch) -> None:
    _, run_dir = new_run
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    res = _invoke(["finalize", "--outcome", "inconclusive"])
    assert res.exit_code == 1 and "no ranking" in res.stderr


@pytest.mark.parametrize("outcome", ["no_structure_fits", "insufficient_data", "handed_to_human"])
def test_outcomes_without_candidate_accepted(new_run, monkeypatch, outcome: str) -> None:
    _, run_dir = new_run
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    res = _invoke(["finalize", "--outcome", outcome])
    assert res.exit_code == 0, res.output
    assert "result declared" in _invoke(["status"]).stdout


def test_explicit_ranking_must_still_be_valid(new_run, monkeypatch) -> None:
    _, run_dir = new_run
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    res = _invoke(["finalize", "--outcome", "no_structure_fits", "--ranking", "rk01"])
    assert res.exit_code == 1


def test_hand_formatted_run_stops_before_result(workspace: Path, monkeypatch) -> None:
    run_dir = workspace / "2026-01-01T1000Z_example_hd01"
    build_fixture_record(run_dir, hand_ranking=True)
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    args = ["finalize", "--outcome", "proposal", "--candidate", "1"]
    res = _invoke([*args, "--ranking", "agent/ranking.json"])
    assert res.exit_code == 1
    _invoke(["render"])
    text = (run_dir / "renderings" / "final_results.md").read_text()
    assert "Stopped before a result (inferred)" in text
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["status"]["state"] == "stopped_before_result"


def test_later_solve_makes_declaration_stale(active: Path) -> None:
    assert _invoke(FULL).exit_code == 0
    _solve(active, "it02", "d" * 64)
    assert "stale" in _invoke(["status"]).stdout.lower() or "declaration_stale" in _invoke(
        ["status"]
    ).stdout


def test_withdraw(active: Path) -> None:
    assert _invoke(FULL).exit_code == 0
    res = _invoke(["finalize", "--withdraw", "--reason", "wrong multiplicity"])
    assert res.exit_code == 0, res.output
    withdrawn = [e for e in _events(active) if e["type"] == "final.withdrawn"]
    assert withdrawn and withdrawn[0]["payload"]["reason"] == "wrong multiplicity"


def test_withdraw_without_declaration(active: Path) -> None:
    assert _invoke(["finalize", "--withdraw"]).exit_code == 1


def test_second_declaration_supersedes(active: Path) -> None:
    assert _invoke(FULL).exit_code == 0
    assert _invoke(FULL).exit_code == 0
    assert (active / "final" / "declaration.2.json").is_file()
    decls = [e for e in _events(active) if e["type"] == "final.declared"]
    assert decls[-1]["artefacts"][0]["supersedes"] == decls[0]["artefacts"][0]["id"]


def test_unregistered_file_is_a_warning(active: Path) -> None:
    (active / "notes.txt").write_text("hello")
    (active / "agent" / "fine.txt").write_text("ok")
    assert unregistered_files(active, _events(active)) == ["notes.txt"]
    res = _invoke(FULL)
    assert res.exit_code == 0, res.output
    assert "unverified file notes.txt" in res.stdout
    warned = [e for e in _events(active) if e["type"] == "warning.raised"]
    assert any(e["payload"]["code"] == "unregistered_file" for e in warned)
    _invoke(["finalize", "--outcome", "inconclusive"])
    again = [
        e
        for e in _events(active)
        if e["type"] == "warning.raised" and e["payload"]["code"] == "unregistered_file"
    ]
    assert len(again) == 1


def test_symlink_is_not_followed(active: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("x")
    (active / "link").symlink_to(outside)
    assert "link/secret.txt" not in unregistered_files(active, _events(active))


def test_transcripts_copied_by_finalize(active: Path, tmp_path: Path, monkeypatch) -> None:
    sid = "11111111-2222-3333-4444-555555555555"
    projects = tmp_path / "projects" / "p"
    projects.mkdir(parents=True)
    line = {"type": "assistant", "message": {"model": "claude-x"}, "requestedModel": "x"}
    (projects / f"{sid}.jsonl").write_text(json.dumps(line) + "\n")
    monkeypatch.setenv("AILSA_CLAUDE_PROJECTS", str(tmp_path / "projects"))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", sid)
    assert _invoke(FULL).exit_code == 0
    copied = [e for e in _events(active) if e["type"] == "transcript.copied"]
    assert copied and copied[0]["payload"]["via"] == "finalize"
    assert (active / "transcript" / f"{sid}.jsonl").is_file()
    assert any(
        e["type"] == "agent.model_reported" and e["payload"]["source"] == "transcript"
        for e in _events(active)
    )


def test_finished_run_refused(active: Path) -> None:
    assert _invoke(["close"]).exit_code == 0
    res = _invoke(FULL)
    assert res.exit_code == 1 and "run finished" in res.stderr


def test_close_records_state_and_head(active: Path, workspace: Path) -> None:
    assert _invoke(FULL).exit_code == 0
    res = _invoke(["close", "--reason", "done"])
    assert res.exit_code == 0, res.output
    finished = json.loads((active / "finished.json").read_text())
    from ailsa.record.runinit import read_index

    entries = [e for e in read_index(workspace) if e.get("head")]
    assert entries and entries[0]["head"] == finished["head"]
    last = _events(active)[-1]
    assert last["type"] == "run.finished" and last["payload"]["state"] == "result_declared"
    assert _invoke(["close"]).exit_code == 1


def test_resolve_ranking_latest_and_named(active: Path) -> None:
    _rank(active, 2)
    ev = _events(active)
    assert resolve_ranking(ev, active, "latest")["payload"]["ranking_id"] == "rk02"
    assert resolve_ranking(ev, active, "rk01")["payload"]["ranking_id"] == "rk01"
    assert resolve_ranking(ev, active, None) is None
