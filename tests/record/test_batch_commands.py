"""Batch recording commands: peaks decide, model import (REC-04, REC-17)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from ailsa.cli.model import model
from ailsa.cli.peaks import peaks
from ailsa.record.artefacts import register_artefact
from ailsa.record.log import read_events

ACTOR = {"kind": "tool", "name": "test"}


@pytest.fixture
def run_with_pick(new_run, monkeypatch) -> Path:
    _, run_dir = new_run
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    pick = {
        "schema": "ailsa.peak-pick",
        "schema_version": "1",
        "pick_id": "pick:5:1",
        "peaks": [{"id": f"pk:5:1:{i}", "ppm": 10.0 * i} for i in range(1, 5)],
    }
    register_artefact(
        run_dir,
        kind="peak-pick",
        rel_path="peaks/5.1.json",
        data=json.dumps(pick).encode(),
        event_type="peaks.picked",
        payload={
            "pick_id": "pick:5:1",
            "experiment": "exp:5",
            "picker": "x",
            "parameters": {},
            "count": 4,
            "noise_sigma": None,
        },
        actor=ACTOR,
    )
    return run_dir


def _write(tmp_path: Path, name: str, obj) -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(obj))
    return p


def _decisions() -> list[dict]:
    return [
        {"peaks": ["pk:5:1:1"], "action": "accept", "reason": "clear signal"},
        {
            "peaks": ["pk:5:1:2"],
            "action": "reject",
            "category": "solvent",
            "reason": "CDCl3 triplet",
        },
        {"peaks": ["pk:5:1:3"], "action": "merge", "reason": "same carbon", "target": "pk:5:1:4"},
    ]


def _events(run_dir: Path, type_: str) -> list[dict]:
    return [e for e in read_events(run_dir)["events"] if e["type"] == type_]


def test_decide_records_batch(run_with_pick, tmp_path: Path) -> None:
    table = _write(tmp_path, "t.json", {"decisions": _decisions()})
    res = CliRunner().invoke(peaks, ["decide", "--from", str(table), "--format", "json"])
    assert res.exit_code == 0, res.output
    assert json.loads(res.stdout) == {"recorded": 3, "artefact": "art:peak-decisions:1"}
    evs = _events(run_with_pick, "peak.decided")
    assert [e["seq"] - evs[0]["seq"] for e in evs] == [0, 1, 2]
    assert evs[1]["payload"]["category"] == "solvent"
    assert evs[1]["payload"]["reason"] == "CDCl3 triplet"
    assert (run_with_pick / "peaks" / "decisions.1.json").is_file()


def test_decide_bare_list(run_with_pick, tmp_path: Path) -> None:
    table = _write(tmp_path, "t.json", _decisions())
    res = CliRunner().invoke(peaks, ["decide", "--from", str(table)])
    assert res.exit_code == 0, res.output
    assert len(_events(run_with_pick, "peak.decided")) == 3


def test_decide_invalid_writes_nothing(run_with_pick, tmp_path: Path) -> None:
    rows = [
        {"peaks": ["pk:9:9:9"], "action": "accept", "reason": "r"},
        {"peaks": ["pk:5:1:1"], "action": "bogus", "reason": "r"},
        {"peaks": ["pk:5:1:1"], "action": "reject", "reason": "r"},
        {"peaks": ["pk:5:1:1"], "action": "accept", "reason": ""},
    ]
    table = _write(tmp_path, "t.json", rows)
    res = CliRunner().invoke(peaks, ["decide", "--from", str(table)])
    assert res.exit_code == 1
    for n in (1, 2, 3, 4):
        assert f"row {n}" in res.output
    assert _events(run_with_pick, "peak.decided") == []
    assert not (run_with_pick / "peaks" / "decisions.1.json").exists()


def test_decide_dry_run(run_with_pick, tmp_path: Path) -> None:
    table = _write(tmp_path, "t.json", _decisions())
    res = CliRunner().invoke(peaks, ["decide", "--from", str(table), "--dry-run"])
    assert res.exit_code == 0
    assert "3" in res.output
    assert _events(run_with_pick, "peak.decided") == []


def test_decide_without_run(workspace, tmp_path: Path) -> None:
    table = _write(tmp_path, "t.json", _decisions())
    res = CliRunner().invoke(peaks, ["decide", "--from", str(table)])
    assert res.exit_code == 1
    assert "peaks decide needs an active run (start one with ailsa run init)" in res.output


def test_decide_refuses_huge_table(run_with_pick, tmp_path: Path) -> None:
    rows = [{"peaks": ["pk:5:1:1"], "action": "accept", "reason": "r"}] * 10_001
    table = _write(tmp_path, "t.json", rows)
    res = CliRunner().invoke(peaks, ["decide", "--from", str(table)])
    assert res.exit_code == 1
    assert "10000" in res.output


def test_decide_refuses_tampered_pick(run_with_pick, tmp_path: Path) -> None:
    (run_with_pick / "peaks" / "5.1.json").write_text("{}")
    table = _write(tmp_path, "t.json", _decisions())
    res = CliRunner().invoke(peaks, ["decide", "--from", str(table)])
    assert res.exit_code == 1
    assert "sha256" in res.output


def _model(**over) -> dict:
    base = {
        "atoms": [
            {"id": "at:1", "element": "C", "evidence": ["pk:5:1:1"]},
            {"id": "at:2", "element": "C"},
            {"id": "at:3", "element": "O"},
        ],
        "correlations": [
            {"id": "cor:hmbc:1", "kind": "hmbc", "peaks": ["pk:5:1:2"], "atoms": ["at:1", "at:2"]},
            {"id": "cor:hmbc:2", "kind": "hmbc", "peaks": ["pk:5:1:3"], "atoms": ["at:2", "at:3"]},
        ],
    }
    base.update(over)
    return base


def test_model_import_and_supersede(run_with_pick, tmp_path: Path) -> None:
    f = _write(tmp_path, "m.json", _model())
    res = CliRunner().invoke(model, ["import", str(f), "--format", "json"])
    assert res.exit_code == 0, res.output
    assert json.loads(res.stdout) == {
        "atoms": 3,
        "correlations": 2,
        "artefact": "art:atom-model:1",
        "supersedes": None,
    }
    res = CliRunner().invoke(model, ["import", str(f), "--format", "json"])
    assert json.loads(res.stdout)["artefact"] == "art:atom-model:2"
    assert json.loads(res.stdout)["supersedes"] == "art:atom-model:1"
    ev = _events(run_with_pick, "model.imported")
    assert ev[0]["payload"]["atoms"] == 3 and ev[0]["payload"]["correlations"] == 2
    assert (run_with_pick / "model" / "atoms.2.json").is_file()


def test_model_import_invalid(run_with_pick, tmp_path: Path) -> None:
    bad = _model(
        atoms=[
            {"id": "at:1", "element": "C"},
            {"id": "at:1", "element": "Xx"},
            {"id": "at:2", "element": "C", "evidence": ["pk:7:7:7"]},
        ],
        correlations=[{"id": "cor:hmbc:1", "kind": "hmbc", "atoms": ["at:9"]}],
    )
    f = _write(tmp_path, "m.json", bad)
    res = CliRunner().invoke(model, ["import", str(f)])
    assert res.exit_code == 1
    for word in ("duplicate", "Xx", "at:9", "pk:7:7:7"):
        assert word in res.output
    assert _events(run_with_pick, "model.imported") == []
    assert not (run_with_pick / "model" / "atoms.1.json").exists()


def test_model_import_without_run(workspace, tmp_path: Path) -> None:
    f = _write(tmp_path, "m.json", _model())
    res = CliRunner().invoke(model, ["import", str(f)])
    assert res.exit_code == 1
    assert "model import needs an active run (start one with ailsa run init)" in res.output


def test_model_import_dry_run(run_with_pick, tmp_path: Path) -> None:
    f = _write(tmp_path, "m.json", _model())
    res = CliRunner().invoke(model, ["import", str(f), "--dry-run"])
    assert res.exit_code == 0
    assert _events(run_with_pick, "model.imported") == []
