"""Identity verdicts saved as artefacts, hidden in blind runs (REC-19)."""

from __future__ import annotations

import json

from click.testing import CliRunner

from ailsa.cli.identify import identify
from ailsa.record.log import append_event, read_events
from ailsa.record.models import IdentityVerdict

FAKE = {
    "mode": "identity",
    "reported_name": None,
    "derived": {
        "matched": False,
        "canonical_smiles": "CCO",
        "inchi_key": "LFQSCWFLJHTTHZ-UHFFFAOYSA-N",
        "name": None,
    },
    "name_match": None,
    "verdict": "novel",
}


def _patch(monkeypatch) -> None:
    monkeypatch.setattr("ailsa.cli.identify.check_identity_result", lambda *a, **k: FAKE)


def _created(run_dir, blind: bool) -> None:
    append_event(
        run_dir,
        "run.created",
        {
            "dataset": {"label": "example", "blind": blind},
            "class": "public",
            "request": {},
            "prior_runs": {},
            "writer_host": "h",
        },
        actor={"kind": "tool", "name": "ailsa"},
    )


def test_verdict_saved(new_run, monkeypatch) -> None:
    _, run_dir = new_run
    _patch(monkeypatch)
    plain = CliRunner().invoke(identify, ["--smiles", "CCO", "--format", "json"])
    _created(run_dir, False)
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    res = CliRunner().invoke(identify, ["--smiles", "CCO", "--format", "json"])
    assert res.exit_code == 0
    assert res.stdout == plain.stdout
    model = IdentityVerdict.model_validate(
        json.loads((run_dir / "identity" / "1.json").read_text())
    )
    assert model.verdict == "novel" and model.hidden_in_blind is False
    ev = [e for e in read_events(run_dir)["events"] if e["type"] == "identity.derived"]
    assert len(ev) == 1
    assert ev[0]["payload"]["inchikey"] == FAKE["derived"]["inchi_key"]
    assert ev[0]["payload"]["hidden_in_blind"] is False


def test_blind_run_hidden(new_run, monkeypatch) -> None:
    _, run_dir = new_run
    _patch(monkeypatch)
    _created(run_dir, True)
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    CliRunner().invoke(identify, ["--smiles", "CC(C)O"])
    model = json.loads((run_dir / "identity" / "1.json").read_text())
    assert model["hidden_in_blind"] is True
    ev = [e for e in read_events(run_dir)["events"] if e["type"] == "identity.derived"]
    assert ev[0]["payload"]["hidden_in_blind"] is True


def test_record_failure_still_exits_zero(new_run, monkeypatch) -> None:
    _, run_dir = new_run
    _patch(monkeypatch)
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))

    def boom(*a, **k):
        raise OSError("no space")

    monkeypatch.setattr("ailsa.record.tooldata.record_identity", boom)
    res = CliRunner().invoke(identify, ["--smiles", "CCO", "--format", "json"])
    assert res.exit_code == 0
    assert json.loads(res.stdout)["verdict"] == "novel"
    assert "ailsa: record write failed: no space" in res.stderr


def test_outside_run_nothing_written(workspace, monkeypatch) -> None:
    _patch(monkeypatch)
    res = CliRunner().invoke(identify, ["--smiles", "CCO"])
    assert res.exit_code == 0
    assert "Verdict: novel" in res.stdout
