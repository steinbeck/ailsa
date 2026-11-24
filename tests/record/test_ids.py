"""ID helpers and event vocabulary."""

from __future__ import annotations

import re

from ailsa.record import events as ev


def test_id_forms() -> None:
    assert ev.exp_id("5") == "exp:5"
    assert ev.pick_id("5", 2) == "pick:5:2"
    assert ev.peak_id("5", 2, 17) == "pk:5:2:17"
    assert ev.iteration_id(3) == "it03"
    assert ev.iteration_id(3, "methyl") == "it03.methyl"
    assert ev.solution_id("it03", 12) == "sol:it03:12"
    assert ev.ranking_id(4) == "rk04"
    assert ev.candidate_id("rk04", 1) == "cand:rk04:1"
    assert ev.artefact_id("ranking", 4) == "art:ranking:4"
    assert ev.view_id("5", "rawproc") == "view:5:rawproc"
    assert ev.atom_id(3) == "at:3"
    assert ev.correlation_id("hmbc", 2) == "cor:hmbc:2"
    assert ev.constraint_id(1) == "con:1"
    assert ev.decision_id(1) == "dec:1"
    assert ev.hypothesis_id(1) == "hyp:1"


def test_id_patterns_match_helpers() -> None:
    samples = {
        "exp": ev.exp_id("5"),
        "pick": ev.pick_id("5", 2),
        "peak": ev.peak_id("5", 2, 17),
        "iteration": ev.iteration_id(3, "methyl"),
        "solution": ev.solution_id("it03", 12),
        "ranking": ev.ranking_id(4),
        "candidate": ev.candidate_id("rk04", 1),
        "artefact": ev.artefact_id("ranking", 4),
        "view": ev.view_id("5", "rawproc"),
        "structure": ev.structure_id("XMGQYMWWDOXHJM-UHFFFAOYSA-N"),
        "atom": ev.atom_id(3),
        "correlation": ev.correlation_id("hmbc", 2),
        "constraint": ev.constraint_id(1),
        "decision": ev.decision_id(1),
        "hypothesis": ev.hypothesis_id(1),
    }
    assert set(samples) == set(ev.ID_PATTERNS)
    for form, value in samples.items():
        assert re.match(ev.ID_PATTERNS[form], value), form


def test_vocabulary_size_and_hooks() -> None:
    assert len(ev.REQUIRED_PAYLOAD) == 58
    assert ev.HOOK_TYPES <= set(ev.REQUIRED_PAYLOAD)
    assert "final.declared" in ev.REQUIRED_PAYLOAD
