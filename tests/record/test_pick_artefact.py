"""Peak-pick artefacts: source hashes, parameters, peak IDs, unchanged stdout (REC-17, REC-07)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from click.testing import CliRunner

from ailsa.cli.pick import pick
from ailsa.record.log import read_events
from ailsa.record.models import PeakPick
from ailsa.record.tooldata import experiment_of

from .test_spectra_export import make_1d, make_2d


def _make_2d_with_peaks(root: Path, expno: str) -> Path:
    exp = make_2d(root, expno)
    data = np.zeros((512, 1024))
    for r, c in ((100, 200), (250, 600), (400, 900)):
        data[r - 1 : r + 2, c - 1 : c + 2] = 5000.0
    data.astype("<i4").tofile(exp / "pdata" / "1" / "2rr")
    return exp


def _run_json(args: list[str]) -> dict:
    res = CliRunner().invoke(pick, args)
    assert res.exit_code == 0, res.output
    return json.loads(res.stdout)


def test_experiment_of(tmp_path: Path) -> None:
    exp = make_1d(tmp_path / "ds", "5")
    assert experiment_of(exp / "pdata" / "1") == ("5", exp.resolve())
    assert experiment_of(exp) == ("5", exp.resolve())


def test_pick_1d_in_run(new_run, monkeypatch, tmp_path: Path) -> None:
    _, run_dir = new_run
    exp = make_1d(tmp_path / "ds", "5")
    outside = _run_json(["1d", str(exp), "--format", "json"])
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    inside = _run_json(["1d", str(exp), "--format", "json", "-s", "4"])
    assert inside.pop("pick_id") == "pick:5:1"
    assert "pick_id" not in outside
    art = json.loads((run_dir / "peaks" / "5.1.json").read_text())
    model = PeakPick.model_validate(art)
    assert model.experiment == "exp:5" and model.picker == "AdaptivePeakPicker"
    assert model.parameters["snr_floor"] == 4.0
    assert "pdata/1/1r" in model.source_sha256 and "acqus" in model.source_sha256
    assert model.referencing["SF"] == 100.6
    assert model.rejected == [] and model.rejected_available is False
    assert [p.id for p in model.peaks] == [f"pk:5:1:{i}" for i in range(1, len(model.peaks) + 1)]
    assert len(model.peaks) >= 1
    events = read_events(run_dir)["events"]
    picked = [e for e in events if e["type"] == "peaks.picked"]
    assert len(picked) == 1
    assert picked[0]["payload"]["pick_id"] == "pick:5:1"
    assert picked[0]["payload"]["count"] == len(model.peaks)


def test_pick_uses_the_inventory_alias_not_the_folder_name(
    new_run, monkeypatch, tmp_path: Path
) -> None:
    """WR-08: a non-numeric folder name never reaches ids or paths; the inventory label does."""
    from ailsa.record.inventory import build_inventory

    _, run_dir = new_run
    ds = tmp_path / "ds"
    make_1d(ds, "1")
    exp = make_1d(ds, "my sample: 1H")
    labels = [e["id"] for e in build_inventory(ds, blind=True, fingerprint="")["experiments"]]
    assert labels == ["exp:1", "exp:x1"]
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    assert _run_json(["1d", str(exp), "--format", "json"])["pick_id"] == "pick:x1:1"
    assert (run_dir / "peaks" / "x1.1.json").is_file()
    raw = (run_dir / "events.jsonl").read_text()
    assert "my sample" not in raw
    model = PeakPick.model_validate(json.loads((run_dir / "peaks" / "x1.1.json").read_text()))
    assert model.experiment == "exp:x1"


def test_second_pick_gets_next_number(new_run, monkeypatch, tmp_path: Path) -> None:
    _, run_dir = new_run
    exp = make_1d(tmp_path / "ds", "5")
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    _run_json(["1d", str(exp), "--format", "json"])
    assert _run_json(["1d", str(exp), "--format", "json"])["pick_id"] == "pick:5:2"
    assert (run_dir / "peaks" / "5.2.json").is_file()


@pytest.mark.parametrize("sub", ["hsqc", "hmbc", "2d"])
def test_pick_2d_in_run(sub: str, new_run, monkeypatch, tmp_path: Path) -> None:
    _, run_dir = new_run
    exp = _make_2d_with_peaks(tmp_path / "ds", "2")
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    data = _run_json([sub, str(exp), "--format", "json", "-t", "0.05"])
    assert data["pick_id"] == "pick:2:1"
    model = PeakPick.model_validate(json.loads((run_dir / "peaks" / "2.1.json").read_text()))
    assert model.peaks
    assert all(p.ppm_f2 is not None and p.ppm_f1 is not None for p in model.peaks)
    assert "pdata/1/2rr" in model.source_sha256
    assert model.referencing["f2"]["SF"] == 400.1


def test_outside_run_nothing_written(workspace, tmp_path: Path) -> None:
    exp = make_1d(tmp_path / "ds", "5")
    res = CliRunner().invoke(pick, ["1d", str(exp), "--format", "json"])
    assert res.exit_code == 0
    assert "pick_id" not in json.loads(res.stdout)
    assert not list(workspace.rglob("peaks")) if workspace.exists() else True


def test_text_output_unchanged_in_run(new_run, monkeypatch, tmp_path: Path) -> None:
    _, run_dir = new_run
    exp = make_1d(tmp_path / "ds", "5")
    before = CliRunner().invoke(pick, ["1d", str(exp)]).stdout
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    after = CliRunner().invoke(pick, ["1d", str(exp)]).stdout
    assert before == after


def test_record_failure_keeps_output(new_run, monkeypatch, tmp_path: Path) -> None:
    _, run_dir = new_run
    exp = make_1d(tmp_path / "ds", "5")
    expected = CliRunner().invoke(pick, ["1d", str(exp), "--format", "json"]).stdout
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr("ailsa.record.tooldata.record_pick", boom)
    res = CliRunner().invoke(pick, ["1d", str(exp), "--format", "json"])
    assert res.exit_code == 0
    assert res.stdout == expected
    assert "ailsa: record write failed: disk full" in res.stderr
