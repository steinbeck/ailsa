"""Committed JSON Schemas match the models; artefact model behaviour."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

from ailsa.record.models import (
    ARTEFACT_MODELS,
    FinalDeclaration,
    Ranking,
    SolverRun,
    export_schemas,
)

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "src" / "ailsa" / "data" / "schemas"
SHA = "b" * 64


def test_schema_drift(tmp_path: Path) -> None:
    written = export_schemas(tmp_path)
    assert len(written) == 12
    for path in written:
        committed = SCHEMA_DIR / path.name
        assert committed.is_file(), path.name
        assert committed.read_bytes() == path.read_bytes(), f"{path.name} drifted"


def test_final_declaration_rules() -> None:
    with pytest.raises(ValidationError):
        FinalDeclaration(outcome="proposal", termination_reason="x")
    ok = FinalDeclaration(
        outcome="proposal", termination_reason="x", candidate=1, ranking_id="rk01"
    )
    assert ok.candidate == 1
    FinalDeclaration(outcome="no_structure_fits", termination_reason="x")
    FinalDeclaration(outcome="inconclusive", termination_reason="x")
    with pytest.raises(ValidationError):
        FinalDeclaration(outcome="proposal", termination_reason="x", candidate=0, ranking_id="rk01")
    with pytest.raises(ValidationError):
        FinalDeclaration(outcome="unknown", termination_reason="x")
    with pytest.raises(ValidationError):
        FinalDeclaration(
            outcome="inconclusive",
            termination_reason="x",
            alternatives=[{"rank": 0, "status": "excluded"}],
        )
    with pytest.raises(ValidationError):
        FinalDeclaration(
            outcome="inconclusive",
            termination_reason="x",
            alternatives=[{"rank": 1, "status": "maybe"}],
        )


def test_artefact_models_forbid_extra() -> None:
    with pytest.raises(ValidationError):
        FinalDeclaration(outcome="inconclusive", termination_reason="x", bogus=1)


RANKING = {
    "schema": "ailsa.ranking",
    "schema_version": "1",
    "ranking_id": "rk01",
    "method": "assigned",
    "tolerance": 5.0,
    "inputs": [{"iteration": "it01", "path": "iterations/it01/x.sol"}],
    "predictor": {"backend": "hose", "database_sha256": None, "max_radius": 4},
    "total_solutions": 2,
    "distinct_structures": 1,
    "skipped": 0,
    "observed_shifts": {"1": 120.5},
    "warnings": [],
    "correlations_cap": 100,
    "candidates": [
        {
            "id": "cand:rk01:1",
            "rank": 1,
            "smiles": "CCO",
            "mapping_status": "ok",
            "atom_map": [{"depiction_index": 0, "lsd_atom": 1, "element": "C", "h_count": 3}],
            "atoms": [
                {
                    "lsd_atom": 1,
                    "observed": 18.0,
                    "predicted": 17.5,
                    "error": 0.5,
                    "basis": {"hose_code": "C-4;C(//)", "radius_used": 2, "match_count": 5},
                }
            ],
            "correlations": None,
        }
    ],
}

SOLVER = {
    "schema": "ailsa.solver-run",
    "schema_version": "1",
    "iteration": "it01",
    "purpose": "main",
    "host": "vitus",
    "provenance": "run",
    "outcome": "timeout",
    "count": 0,
    "partial_count": 12,
}


def test_ranking_sample() -> None:
    r = Ranking.model_validate(RANKING)
    assert r.candidates[0].mapping_status == "ok"
    unavailable = json.loads(json.dumps(RANKING))
    cand = unavailable["candidates"][0]
    cand["mapping_status"] = "unavailable"
    cand["atom_map"] = []
    Ranking.model_validate(unavailable)


def test_solver_samples() -> None:
    assert SolverRun.model_validate(SOLVER).partial_count == 12
    conv = dict(SOLVER, outcome="solutions", count=4, smiles_absent_reason="conversion_failed")
    SolverRun.model_validate(conv)


def _schema(stem: str) -> dict:
    return json.loads((SCHEMA_DIR / f"run_{stem}.json").read_text(encoding="utf-8"))


def test_samples_against_committed_schema() -> None:
    final = {
        "schema": "ailsa.final",
        "schema_version": "1",
        "outcome": "no_structure_fits",
        "termination_reason": "x",
    }
    for stem, sample in (("ranking", RANKING), ("solver_run", SOLVER), ("final", final)):
        jsonschema.Draft202012Validator(_schema(stem)).validate(sample)
    bad = dict(SOLVER, outcome="maybe")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema("solver_run")).validate(bad)


def test_every_model_has_versioned_schema_field() -> None:
    for stem, model in ARTEFACT_MODELS.items():
        if stem == "event":
            continue
        assert "schema_version" in model.model_fields, stem
