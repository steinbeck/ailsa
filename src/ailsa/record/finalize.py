"""How a run ends: ``ailsa run finalize`` and ``ailsa run close`` (REC-16, REC-22, REC-23, REC-27).

A result is declared, never inferred. A declaration of an outcome that needs a ranking is only
accepted against a ranking that ``ailsa lsd rank`` wrote (a ``ranking.computed`` event whose
sha256 still equals the file on disk), whose inputs are registered, and that no later solve has
made stale. Anything else leaves the run in ``stopped_before_result``.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from ailsa.record.artefacts import artefact_index, find_artefacts, register_artefact
from ailsa.record.events import (
    ALTERNATIVE_STATUSES,
    CONFIDENCE_LEVELS,
    FINAL_OUTCOMES,
    FINISHED,
    OUTCOMES_NEEDING_CANDIDATE,
    OUTCOMES_NEEDING_RANKING,
    TEXT_CAP,
    candidate_id,
)
from ailsa.record.fsutil import sha256_file
from ailsa.record.log import RecordWriteRefused, append_event, read_events

NOT_BY_TOOL = "this ranking was not written by ailsa lsd rank"
FINISHED_MESSAGE = (
    "run finished: post-run material goes to the verification store, not the run folder"
)
NO_RUN_MESSAGE = "finalize needs an active run: start one with ailsa run init"

_RANKING_REF = re.compile(r"^rk\d{2,}$")
_FREE_DIRS = frozenset({"agent", "transcript", "renderings"})
_RECORD_FILES = frozenset(
    {
        "events.jsonl",
        "events.lock",
        ".counters.json",
        "finished.json",
        "manifest.json",
        "heartbeat.json",
        "hooks.json",
        "hook-errors.log",
        ".ailsa-run",
    }
)
_KNOWN_PATHS = frozenset({"spectra/export.log"})
_TOOL = {"kind": "tool", "name": "ailsa run finalize"}


class FinalizeRefused(Exception):
    """The declaration is refused; the message says what to do."""


def _payload(ev: dict[str, Any]) -> dict[str, Any]:
    p = ev.get("payload")
    return p if isinstance(p, dict) else {}


def resolve_ranking(
    events: list[dict[str, Any]], run_dir: str | os.PathLike[str], ref: str | None
) -> dict[str, Any] | None:
    """The ``ranking.computed`` event named by ``ref`` ("latest" or "rkNN")."""
    computed = [e for e in events if e.get("type") == "ranking.computed"]
    if ref is None:
        return None
    if ref == "latest":
        if not computed:
            raise FinalizeRefused(
                "there is no ranking in this run: run ailsa lsd rank on the solutions first"
            )
        return computed[-1]
    if not _RANKING_REF.match(ref):
        raise FinalizeRefused(NOT_BY_TOOL)
    for ev in reversed(computed):
        if _payload(ev).get("ranking_id") == ref:
            found: dict[str, Any] = ev
            return found
    raise FinalizeRefused(NOT_BY_TOOL)


def _ranking_artefact(ev: dict[str, Any]) -> dict[str, Any]:
    for art in ev.get("artefacts") or []:
        if isinstance(art, dict) and art.get("kind") == "ranking":
            return art
    raise FinalizeRefused(NOT_BY_TOOL)


def check_ranking(
    events: list[dict[str, Any]], run_dir: str | os.PathLike[str], ranking_event: dict[str, Any]
) -> dict[str, Any]:
    """Validate the ranking against the file and the later events; return its parsed content."""
    run = Path(run_dir)
    payload = _payload(ranking_event)
    art = _ranking_artefact(ranking_event)
    target = run / str(art.get("path"))
    if not target.is_file() or target.is_symlink():
        raise FinalizeRefused("ranking file is missing: run ailsa lsd rank again")
    digest = sha256_file(target)
    expected = {str(x) for x in (payload.get("sha256"), art.get("sha256")) if x}
    if not expected or any(digest != x for x in expected):
        raise FinalizeRefused(
            "ranking file changed after it was recorded: run ailsa lsd rank again"
        )
    inputs = [i for i in payload.get("inputs") or [] if isinstance(i, dict)]
    if not inputs:
        raise FinalizeRefused(
            "the ranking covers no registered solver input: run ailsa lsd import, "
            "then ailsa lsd rank"
        )
    seq = int(ranking_event.get("seq") or 0)
    for item in inputs:
        iteration = item.get("iteration")
        if not iteration:
            raise FinalizeRefused(
                "a ranking input is not a registered iteration: run ailsa lsd import, "
                "then ailsa lsd rank"
            )
        latest_sha: str | None = None
        for ev in events:
            pl = _payload(ev)
            if ev.get("type") == "lsd.input.registered" and pl.get("iteration") == iteration:
                latest_sha = pl.get("lsd_sha256")
            if (
                ev.get("type") == "solver.finished"
                and _payload(ev).get("iteration") == iteration
                and int(ev.get("seq") or 0) > seq
            ):
                raise FinalizeRefused("ranking is stale: re-run ailsa lsd rank")
        if latest_sha is not None and item.get("lsd_sha256") and latest_sha != item["lsd_sha256"]:
            raise FinalizeRefused("ranking is stale: re-run ailsa lsd rank")
    try:
        parsed = json.loads(target.read_text(encoding="utf-8"))
    except ValueError:
        raise FinalizeRefused("ranking file is not valid JSON: run ailsa lsd rank again") from None
    return parsed if isinstance(parsed, dict) else {}


def unregistered_files(run_dir: str | os.PathLike[str], events: list[dict[str, Any]]) -> list[str]:
    """Files in the run folder outside agent/, transcript/, renderings/ that no event registered."""
    run = Path(run_dir)
    registered = {str(a.get("path")) for a in artefact_index(events).values()}
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(run, followlinks=False):
        here = Path(dirpath)
        rel_dir = here.relative_to(run)
        if rel_dir == Path("."):
            dirnames[:] = sorted(d for d in dirnames if d not in _FREE_DIRS)
        else:
            dirnames[:] = sorted(dirnames)
        for name in sorted(filenames):
            rel = (rel_dir / name).as_posix()
            if rel_dir == Path(".") and name in _RECORD_FILES:
                continue
            if rel in registered or rel in _KNOWN_PATHS:
                continue
            if name.startswith(".") and name.endswith(".tmp"):
                continue
            found.append(rel)
    return sorted(found)


def parse_alternative(text: str, top: int | None) -> dict[str, Any]:
    rank_text, _, status = text.partition(":")
    try:
        rank = int(rank_text)
    except ValueError:
        raise FinalizeRefused(f"--alternative wants RANK:STATUS, got {text!r}") from None
    if status not in ALTERNATIVE_STATUSES:
        raise FinalizeRefused(
            f"alternative status must be one of {', '.join(ALTERNATIVE_STATUSES)}, got {status!r}"
        )
    if rank < 1 or (top is not None and rank > top):
        raise FinalizeRefused(f"alternative {rank} is not a candidate of the ranking")
    return {"rank": rank, "status": status}


def _warn_unregistered(run: Path, events: list[dict[str, Any]]) -> list[str]:
    files = unregistered_files(run, events)
    known = {
        _payload(e).get("message")
        for e in events
        if e.get("type") == "warning.raised" and _payload(e).get("code") == "unregistered_file"
    }
    for rel in files:
        message = f"unverified file outside the working folder: {rel}"
        if message in known:
            continue
        append_event(
            run,
            "warning.raised",
            {"code": "unregistered_file", "message": message},
            actor=_TOOL,
        )
    return files


def _copy_transcripts(run: Path, session_id: str | None) -> list[str]:
    from ailsa.record.transcript import copy_transcripts, record_transcript_models

    problems: list[str] = []
    try:
        copied = copy_transcripts(run, None, session_id, via="finalize")
        files = [run / "transcript" / str(c["name"]) for c in copied]
        if files:
            record_transcript_models(run, files)
    except Exception as exc:  # noqa: BLE001 - a transcript problem never blocks a declaration
        problems.append(f"transcript copy failed: {type(exc).__name__}: {exc}")
        try:
            append_event(
                run,
                "warning.raised",
                {"code": "transcript_copy_failed", "message": problems[-1]},
                actor=_TOOL,
            )
        except Exception:  # noqa: BLE001
            pass
    return problems


def finalize_run(
    run_dir: str | os.PathLike[str],
    *,
    outcome: str | None,
    ranking_ref: str | None = None,
    candidate: int | None = None,
    confidence: str | None = None,
    termination_reason: str = "agent finished",
    caveats: list[str] | None = None,
    open_questions: list[str] | None = None,
    next_steps: list[str] | None = None,
    alternatives: list[str] | None = None,
    withdraw: bool = False,
    reason: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Validate and record the declaration (or its withdrawal) and write the renderings."""
    from ailsa.record.models import FinalDeclaration
    from ailsa.record.render import render_run

    run = Path(run_dir)
    if (run / FINISHED).exists():
        raise FinalizeRefused(FINISHED_MESSAGE)
    events = read_events(run)["events"]
    role = os.environ.get("AILSA_AGENT_ROLE") or "agent"
    actor = {"kind": "agent", "name": role, "role": role}

    if withdraw:
        if not any(e.get("type") == "final.declared" for e in events):
            raise FinalizeRefused("there is no declaration to withdraw")
        append_event(
            run,
            "final.withdrawn",
            {"reason": (reason or "withdrawn")[:TEXT_CAP]},
            actor=actor,
            fsync=True,
        )
        return {"withdrawn": True, "files": [str(p) for p in render_run(run)], "unverified": []}

    if outcome not in FINAL_OUTCOMES:
        raise FinalizeRefused(
            f"unknown outcome {outcome!r}; choose one of {', '.join(FINAL_OUTCOMES)}"
        )
    if confidence is not None and confidence not in CONFIDENCE_LEVELS:
        raise FinalizeRefused(f"confidence must be one of {', '.join(CONFIDENCE_LEVELS)}")
    if outcome in OUTCOMES_NEEDING_CANDIDATE and candidate is None:
        raise FinalizeRefused(
            f"outcome {outcome} needs a candidate: pass --candidate RANK from the ranking"
        )
    needs_ranking = outcome in OUTCOMES_NEEDING_RANKING
    ref = ranking_ref if ranking_ref is not None else ("latest" if needs_ranking else None)
    if candidate is not None and ref is None:
        ref = "latest"

    ranking_event = resolve_ranking(events, run, ref)
    ranking: dict[str, Any] = {}
    ranking_id: str | None = None
    ranking_sha: str | None = None
    iterations: list[str] = []
    chosen_id: str | None = None
    top: int | None = None
    if ranking_event is not None:
        ranking = check_ranking(events, run, ranking_event)
        pl = _payload(ranking_event)
        ranking_id = str(pl.get("ranking_id"))
        ranking_sha = str(_ranking_artefact(ranking_event).get("sha256") or pl.get("sha256"))
        for item in pl.get("inputs") or []:
            it = item.get("iteration") if isinstance(item, dict) else None
            if it and it not in iterations:
                iterations.append(str(it))
        cands = [c for c in ranking.get("candidates") or [] if isinstance(c, dict)]
        top = max([int(c.get("rank") or 0) for c in cands], default=0) or None
        if candidate is not None:
            match = next((c for c in cands if c.get("rank") == candidate), None)
            if match is None:
                raise FinalizeRefused(
                    f"candidate {candidate} is not in ranking {ranking_id} "
                    f"({len(cands)} candidates)"
                )
            chosen_id = str(match.get("id") or candidate_id(ranking_id, candidate))

    alts = [parse_alternative(a, top) for a in alternatives or []]
    try:
        declaration = FinalDeclaration.model_validate(
            {
                "schema": "ailsa.final",
                "schema_version": "1",
                "outcome": outcome,
                "termination_reason": termination_reason[:TEXT_CAP],
                "ranking_id": ranking_id,
                "ranking_sha256": ranking_sha,
                "iterations": iterations,
                "candidate": candidate,
                "candidate_id": chosen_id,
                "alternatives": alts,
                "confidence": confidence,
                "caveats": [c[:TEXT_CAP] for c in caveats or []],
                "open_questions": [c[:TEXT_CAP] for c in open_questions or []],
                "next_steps": [c[:TEXT_CAP] for c in next_steps or []],
            }
        )
    except ValueError as exc:
        raise FinalizeRefused(f"declaration is not valid: {exc}") from None

    files = _warn_unregistered(run, events)

    previous = find_artefacts(events, "final")
    n = len(previous) + 1
    blob = (
        json.dumps(declaration.model_dump(mode="json", by_alias=True), sort_keys=True, indent=2)
        + "\n"
    ).encode("utf-8")
    try:
        register_artefact(
            run,
            kind="final",
            rel_path=f"final/declaration.{n}.json",
            data=blob,
            event_type="final.declared",
            payload={
                "outcome": outcome,
                "ranking_id": ranking_id,
                "candidate": candidate,
                "candidate_id": chosen_id,
                "confidence": confidence,
                "iterations": iterations,
                "termination_reason": termination_reason[:TEXT_CAP],
            },
            actor=actor,
            refs=[x for x in (ranking_id, chosen_id) if x],
            supersedes=previous[-1]["id"] if previous else None,
            fsync=True,
        )
    except RecordWriteRefused:
        raise FinalizeRefused(FINISHED_MESSAGE) from None

    problems = _copy_transcripts(run, session_id)
    paths = [str(p) for p in render_run(run)]
    return {
        "withdrawn": False,
        "outcome": outcome,
        "ranking_id": ranking_id,
        "candidate_id": chosen_id,
        "iterations": iterations,
        "files": paths,
        "unverified": files,
        "warnings": problems,
    }
