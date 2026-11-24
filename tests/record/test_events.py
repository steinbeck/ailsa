"""Event envelope and payload models."""

from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from ailsa.record.events import REQUIRED_PAYLOAD
from ailsa.record.models import PAYLOAD_MODELS, ActorModel, validate_event

SHA = "a" * 64


def _event(etype: str, payload: dict) -> dict:
    return {
        "v": 1,
        "seq": 1,
        "utc": "2026-11-24T10:00:00.123Z",
        "host": "vitus",
        "run_id": "r1",
        "type": etype,
        "actor": {"kind": "tool", "name": "ailsa"},
        "span": None,
        "refs": [],
        "payload": payload,
        "artefacts": [],
        "post_run": False,
        "after_finish": False,
        "prev": SHA,
    }


SOLVER_OK = {
    "iteration": "it01",
    "outcome": "solutions",
    "count": 3,
    "elapsed_s": 1.5,
    "host": "vitus",
    "provenance": "run",
}


def test_payload_models_cover_required_keys() -> None:
    assert set(PAYLOAD_MODELS) == set(REQUIRED_PAYLOAD)
    for etype, keys in REQUIRED_PAYLOAD.items():
        required = {n for n, f in PAYLOAD_MODELS[etype].model_fields.items() if f.is_required()}
        assert required == set(keys), etype


def test_solver_finished_valid() -> None:
    assert validate_event(_event("solver.finished", SOLVER_OK)) == []


def test_bad_outcome_named() -> None:
    bad = dict(SOLVER_OK, outcome="maybe")
    errors = validate_event(_event("solver.finished", bad))
    assert errors and "outcome" in errors[0]


def test_short_prev_is_envelope_error() -> None:
    ev = _event("solver.finished", SOLVER_OK)
    ev["prev"] = "a" * 63
    errors = validate_event(ev)
    assert errors and "prev" in errors[0]


def test_unknown_type_tolerated() -> None:
    assert validate_event(_event("future.thing", {"x": 1})) == []


def test_envelope_forbids_extra() -> None:
    ev = copy.deepcopy(_event("future.thing", {}))
    ev["surprise"] = 1
    assert validate_event(ev)


def test_payload_allows_extra_keys() -> None:
    assert validate_event(_event("solver.finished", dict(SOLVER_OK, more=1))) == []


def test_actor_kind_restricted() -> None:
    with pytest.raises(ValidationError):
        ActorModel(kind="robot")


def test_run_created_class_vocabulary() -> None:
    base = {
        "dataset": {},
        "request": {},
        "prior_runs": {},
        "writer_host": "vitus",
    }
    assert validate_event(_event("run.created", dict(base, **{"class": "public"}))) == []
    assert validate_event(_event("run.created", dict(base, **{"class": "secret"})))


def test_peak_decided_needs_peaks() -> None:
    payload = {"peaks": [], "action": "accept", "category": None, "reason": "x"}
    assert validate_event(_event("peak.decided", payload))
