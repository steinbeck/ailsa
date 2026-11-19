"""Atom-by-atom ranking of LSD solutions (ailsa lsd rank --assigned)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from rdkit import Chem

from ailsa.cli.lsd import lsd
from ailsa.lsd import LSDRunner
from ailsa.prediction.models import PredictedShift, PredictionResult
from ailsa.ranking.assigned import observed_shifts, rank_assigned

# Butan-2-one: CH3-C(=O)-CH2-CH3. The two methyls are told apart only by their shifts.
BUTANONE_LSD = """\
MULT 1 C 3 3 ; 29.4 CH3
MULT 2 C 2 0 ; 209.3 C=O
MULT 3 C 3 2 ; 36.9 CH2
MULT 4 C 3 3 ; 7.9 CH3
MULT 5 O 2 0 ; carbonyl O
HSQC 1 1
HSQC 3 3
HSQC 4 4
BOND 2 5
DUPL 1
"""


class RolePredictor:
    """Predicts butanone's shifts from each carbon's neighbours, independent of numbering."""

    def predict_from_smiles(self, smiles: str) -> PredictionResult:
        mol = Chem.MolFromSmiles(smiles)
        preds = []
        for atom in mol.GetAtoms():
            if atom.GetSymbol() != "C":
                continue
            heavy = [n.GetSymbol() for n in atom.GetNeighbors()]
            if "O" in heavy:
                shift = 209.3
            elif atom.GetTotalNumHs() == 2:
                shift = 36.9
            elif any(n.GetSymbol() == "C" and n.GetDegree() == 3 for n in atom.GetNeighbors()):
                shift = 29.4  # methyl on the carbonyl carbon
            else:
                shift = 7.9
            preds.append(
                PredictedShift(atom_index=atom.GetIdx(), shift=shift, confidence=1.0, hose_code="",
                               radius_used=1, match_count=1, std_dev=0.0, min_shift=shift,
                               max_shift=shift)
            )
        return PredictionResult(smiles=smiles, predictions=preds, carbon_count=len(preds),
                                success_count=len(preds))


def test_observed_shifts_from_mult_comments() -> None:
    assert observed_shifts(BUTANONE_LSD) == {1: 29.4, 2: 209.3, 3: 36.9, 4: 7.9}


def test_shix_lines_take_precedence() -> None:
    text = BUTANONE_LSD + "SHIX 1 30.0\nSHIX 2 210.0\n"
    assert observed_shifts(text) == {1: 30.0, 2: 210.0}


def test_no_shifts_is_an_error(tmp_path: Path) -> None:
    lsd_file = tmp_path / "compound.lsd"
    lsd_file.write_text("MULT 1 C 3 3\nMULT 2 C 3 3\nBOND 1 2\n")
    with pytest.raises(ValueError, match="no observed 13C shifts"):
        rank_assigned([lsd_file], RolePredictor())


@pytest.mark.skipif(not LSDRunner.is_available(), reason="LSD not installed")
def test_correct_assignment_wins(tmp_path: Path) -> None:
    """With DUPL 1 LSD returns both methyl assignments; only the right one fits exactly."""
    lsd_file = tmp_path / "compound.lsd"
    lsd_file.write_text(BUTANONE_LSD)
    result = LSDRunner().run_file(lsd_file, output_dir=tmp_path)
    assert result.solution_count >= 2, result.stderr
    ranking = rank_assigned([lsd_file], RolePredictor())
    best = ranking.candidates[0]
    assert ranking.distinct == 1  # both solutions are butanone
    assert best.compared == 4 and best.mae == 0.0 and best.within_tolerance == 4
    assert not ranking.warnings

    out = CliRunner().invoke(lsd, ["rank", "--assigned", str(lsd_file), "--format", "json"])
    assert out.exit_code == 0, out.output
    data = json.loads(out.output)
    assert data["mode"] == "assigned" and data["candidates"][0]["compared"] == 4


def test_cli_needs_smiles_file_or_assigned() -> None:
    out = CliRunner().invoke(lsd, ["rank", "--shifts", "1,2"])
    assert out.exit_code == 1
    assert "--assigned" in out.output
