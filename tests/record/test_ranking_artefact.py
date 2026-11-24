"""REC-15, REC-01: rankings written by the tool, with atom map, prediction basis, path lengths."""

from __future__ import annotations

import json
from dataclasses import asdict, fields
from pathlib import Path

import pytest
from click.testing import CliRunner
from rdkit import Chem

from ailsa.cli.lsd import lsd
from ailsa.prediction.models import PredictedShift, PredictionResult
from ailsa.ranking.assigned import AssignedCandidate, rank_assigned
from ailsa.record.log import read_events
from ailsa.record.models import Ranking

# Ethanol, the only molecule used: C1 methyl, C2 methylene, O3 hydroxyl.
LSD_TEXT = """; tiny generic input
MULT 1 C 3 3 ; 18.3
MULT 2 C 3 2 ; 58.1
MULT 3 O 3 1
HMBC 1 2
HMBC 3 1
DUPL 1
"""
SOL_TEXT = """OUTLSD
3 1
1 C 4 3 0 0 0 2 1 0 0
1 C 4 2 0 0 0 1 1 3 1 0 0
1 O 2 1 0 0 0 2 1 0 0
0
"""


class StubPredictor:
    """Predicts 18.3 for a methyl and 58.1 for a methylene; no database needed."""

    _max_radius = 4

    def predict_from_smiles(self, smiles: str) -> PredictionResult:
        mol = Chem.MolFromSmiles(smiles)
        preds = []
        for atom in mol.GetAtoms():
            if atom.GetSymbol() != "C":
                continue
            shift = 18.3 if atom.GetTotalNumHs() == 3 else 58.1
            preds.append(
                PredictedShift(
                    atom_index=atom.GetIdx(),
                    shift=shift,
                    confidence=0.9,
                    hose_code=f"C-{atom.GetDegree()}",
                    radius_used=3,
                    match_count=7,
                    std_dev=0.4,
                    min_shift=shift - 1,
                    max_shift=shift + 1,
                )
            )
        return PredictionResult(
            smiles=smiles, predictions=preds, carbon_count=len(preds), success_count=len(preds)
        )


def _folder(tmp_path: Path, name: str = "elsewhere", lsd_text: str = LSD_TEXT) -> Path:
    d = tmp_path / name
    d.mkdir()
    (d / "compound.lsd").write_text(lsd_text)
    (d / "compound.sol").write_text(SOL_TEXT)
    (d / "solutions.smi").write_text("CCO\n")
    (d / "solncounter").write_text("1\n")
    return d


@pytest.fixture
def run_env(new_run, tmp_path, monkeypatch):
    _, run_dir = new_run
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    monkeypatch.setattr("ailsa.cli.lsd.resolve_c13_predictor", lambda **kw: StubPredictor())
    monkeypatch.chdir(tmp_path)
    return run_dir


def _import(folder: Path) -> None:
    res = CliRunner().invoke(lsd, ["import", str(folder)])
    assert res.exit_code == 0, res.output


def _rank(folder: Path, *extra: str):
    return CliRunner().invoke(
        lsd, ["rank", "--assigned", str(folder / "compound.lsd"), "--format", "json", *extra]
    )


def test_details_hold_atom_map_and_basis(tmp_path: Path) -> None:
    folder = _folder(tmp_path)
    result = rank_assigned([folder / "compound.lsd"], StubPredictor())
    cand = result.candidates[0]
    det = result.details[cand.inchikey]
    assert det["mapping_status"] == "ok"
    first = det["atom_map"][0]
    assert first == {"depiction_index": 0, "lsd_atom": 1, "element": "C", "h_count": 3}
    assert {m["lsd_atom"] for m in det["atom_map"]} == {1, 2, 3}
    assert det["basis"][2]["radius_used"] == 3 and det["basis"][2]["match_count"] == 7
    assert {f.name for f in fields(AssignedCandidate)} == set(asdict(cand))


def test_failed_sanity_check_means_unavailable(tmp_path: Path) -> None:
    wrong = LSD_TEXT.replace("MULT 2 C 3 2", "MULT 2 C 3 3")
    folder = _folder(tmp_path, lsd_text=wrong)
    result = rank_assigned([folder / "compound.lsd"], StubPredictor())
    det = result.details[result.candidates[0].inchikey]
    assert det["mapping_status"] == "unavailable" and det["atom_map"] == []


def test_ranking_in_a_run_is_an_artefact(run_env, tmp_path) -> None:
    run_dir = run_env
    folder = _folder(tmp_path)
    _import(folder)
    res = _rank(folder)
    assert res.exit_code == 0, res.output
    data = json.loads(res.stdout)
    assert data["ranking_id"] == "rk01"
    assert "Recorded ranking rk01 (use: ailsa run finalize --ranking latest or --ranking rk01)" in (
        res.stderr
    )

    model = Ranking.model_validate(json.loads((run_dir / "rankings" / "rk01.json").read_text()))
    assert model.method == "assigned" and model.ranking_id == "rk01"
    assert model.inputs[0].iteration == "it01" and model.inputs[0].lsd_sha256
    assert model.inputs[0].sol_sha256
    assert model.warnings == [] and model.correlations_cap == 10
    assert model.predictor.backend == "StubPredictor" and model.predictor.max_radius == 4
    cand = model.candidates[0]
    assert cand.id == "cand:rk01:1" and cand.solutions == ["sol:it01:1"]
    assert cand.mapping_status == "ok" and len(cand.atom_map) == 3
    assert cand.atoms[0].basis is not None and cand.atoms[0].basis.radius_used == 3
    paths = {(c.kind, c.carbon, c.proton): c.path_length for c in cand.correlations or []}
    assert paths == {("HMBC", 1, 2): 1, ("HMBC", 3, 1): 2}

    events = read_events(run_dir)["events"]
    ev = next(e for e in events if e["type"] == "ranking.computed")
    assert ev["payload"]["ranking_id"] == "rk01" and ev["payload"]["method"] == "assigned"
    assert ev["payload"]["candidate_count"] == 1
    art = ev["artefacts"][0]
    assert art["kind"] == "ranking" and art["sha256"] == ev["payload"]["sha256"]


def test_stdout_outside_a_run_has_no_ranking_id(tmp_path, workspace, monkeypatch) -> None:
    monkeypatch.setattr("ailsa.cli.lsd.resolve_c13_predictor", lambda **kw: StubPredictor())
    monkeypatch.chdir(tmp_path)
    folder = _folder(tmp_path)
    res = _rank(folder)
    assert res.exit_code == 0, res.output
    assert "ranking_id" not in json.loads(res.stdout)
    assert not (tmp_path / "rankings").exists()


def test_unregistered_input_is_flagged(run_env, tmp_path) -> None:
    folder = _folder(tmp_path)
    res = _rank(folder)
    assert res.exit_code == 0, res.output
    model = Ranking.model_validate(json.loads((run_env / "rankings" / "rk01.json").read_text()))
    assert model.inputs[0].iteration is None
    assert "input not registered by ailsa lsd run" in model.warnings
    assert model.candidates[0].solutions == []


def test_changed_solutions_file_is_flagged(run_env, tmp_path) -> None:
    folder = _folder(tmp_path)
    _import(folder)
    (folder / "compound.sol").write_text(SOL_TEXT + "\n")
    res = _rank(folder)
    assert res.exit_code == 0, res.output
    model = Ranking.model_validate(json.loads((run_env / "rankings" / "rk01.json").read_text()))
    assert model.inputs[0].iteration == "it01"
    assert "solutions file differs from the recorded solver output" in model.warnings


def test_nearest_line_uses_the_same_schema(run_env, tmp_path) -> None:
    folder = _folder(tmp_path)
    _import(folder)
    res = CliRunner().invoke(
        lsd, ["rank", str(folder / "solutions.smi"), "--shifts", "18.3,58.1", "--format", "json"]
    )
    assert res.exit_code == 0, res.output
    assert json.loads(res.stdout)["ranking_id"] == "rk01"
    model = Ranking.model_validate(json.loads((run_env / "rankings" / "rk01.json").read_text()))
    assert model.method == "nearest-line"
    assert model.inputs[0].iteration == "it01" and model.inputs[0].smiles_sha256
    cand = model.candidates[0]
    assert cand.mapping_status == "not_applicable" and cand.atom_map == []
    assert cand.correlations is None and cand.solutions == ["sol:it01:1"]
