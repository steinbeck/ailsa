"""Reducer from the event log to the run manifest (standard library only).

The manifest is a pure function of the events, the integrity report and ``heartbeat.json``.
It can be rebuilt at any time; two rebuilds of an unchanged record give identical bytes.
The state of a run follows only from declarations (``final.declared``) and from end events,
never from files an agent wrote by hand (REC-09, REC-16, D-13).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from ailsa.record.events import HEARTBEAT, MANIFEST
from ailsa.record.fsutil import atomic_write_json
from ailsa.record.log import read_events

NO_HEARTBEAT_AFTER_S = 900

STATE_LABELS: dict[str, str] = {
    "running": "running",
    "result_declared": "result declared: {outcome}",
    "declaration_stale": "declared result is stale: a solver ran after the declaration",
    "stopped_before_result": "stopped before a result (inferred)",
    "no_heartbeat": "no heartbeat since {utc} (inferred stopped)",
}

END_EVENTS = ("run.finished", "session.ended", "run.attempt.ended")
HOOK_COUNT_TYPES = {
    "prompts": "prompt.submitted",
    "permission_waits": "human.waiting",
    "subagents": "agent.spawned",
    "messages": "agent.message",
    "compactions": "context.compacted",
    "turns": "agent.turn_ended",
    "session_stops": "session.ended",
}

Handler = Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], None]


def _parse(utc: str | None) -> datetime | None:
    if not utc:
        return None
    try:
        dt = datetime.fromisoformat(str(utc).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _exp(value: Any) -> str:
    text = str(value)
    return text if text.startswith("exp:") else f"exp:{text}"


def _payload(ev: dict[str, Any]) -> dict[str, Any]:
    p = ev.get("payload")
    return cast("dict[str, Any]", p) if isinstance(p, dict) else {}


def _int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _list(value: Any, what: str) -> list[Any]:
    """A list field of an event; absent is empty, any other type is an anomaly (raised)."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError(f"{what} is a {type(value).__name__}, not a list")
    return value


def _iteration(m: dict[str, Any], name: Any) -> dict[str, Any]:
    it: dict[str, Any] = m["iterations"].setdefault(
        str(name),
        {"purpose": None, "parent": None, "outcome": None, "count": None, "partial_count": None},
    )
    return it


# Handlers: (manifest, event, scratch) -> None


def _h_created(m: dict[str, Any], ev: dict[str, Any], s: dict[str, Any]) -> None:
    p = _payload(ev)
    dataset = p.get("dataset")
    if isinstance(dataset, str):
        dataset = {"label": dataset}
    m["dataset"] = dict(dataset) if isinstance(dataset, dict) else {}
    m["class"] = p.get("class")
    request = p.get("request")
    if isinstance(request, str):
        request = {"prompt": request}
    m["request"] = dict(request) if isinstance(request, dict) else {}
    m["prior_runs"] = p.get("prior_runs") if isinstance(p.get("prior_runs"), dict) else {}
    m["writer_host"] = p.get("writer_host")
    m["blind"] = bool(m["dataset"].get("blind", p.get("blind", False)))
    m["not_blind_reason"] = m["dataset"].get("not_blind_reason", p.get("not_blind_reason"))


def _h_env(m: dict[str, Any], ev: dict[str, Any], s: dict[str, Any]) -> None:
    m["environment"] = dict(_payload(ev))
    harness = _payload(ev).get("harness")
    if isinstance(harness, str):
        m["harness"]["name"] = harness


def _h_scan(m: dict[str, Any], ev: dict[str, Any], s: dict[str, Any]) -> None:
    for item in _list(_payload(ev).get("experiments"), "experiments"):
        if isinstance(item, dict):
            key = _exp(item.get("experiment", item.get("id", "?")))
            entry = m["experiments"].setdefault(key, {"used_by": []})
            entry.update({k: v for k, v in item.items() if k not in ("experiment", "id")})
        else:
            m["experiments"].setdefault(_exp(item), {"used_by": []})


def _h_processed(m: dict[str, Any], ev: dict[str, Any], s: dict[str, Any]) -> None:
    p = _payload(ev)
    m["views"][str(p.get("view_id"))] = {
        "experiment": p.get("experiment"),
        "state": p.get("state"),
        "status": p.get("status"),
    }


def _h_picked(m: dict[str, Any], ev: dict[str, Any], s: dict[str, Any]) -> None:
    p = _payload(ev)
    pid = str(p.get("pick_id"))
    m["picks"][pid] = {
        "experiment": p.get("experiment"),
        "picker": p.get("picker"),
        "count": p.get("count"),
        "noise_sigma": p.get("noise_sigma"),
        "seq": ev.get("seq"),
    }
    entry = m["experiments"].setdefault(_exp(p.get("experiment")), {"used_by": []})
    if pid not in entry["used_by"]:
        entry["used_by"].append(pid)


def _h_lsd_input(m: dict[str, Any], ev: dict[str, Any], s: dict[str, Any]) -> None:
    p = _payload(ev)
    it = _iteration(m, p.get("iteration"))
    it["purpose"] = p.get("purpose")
    it["parent"] = p.get("parent")
    it["path"] = p.get("path")
    s["last_input_seq"] = _int(ev.get("seq"))


def _h_solver_started(m: dict[str, Any], ev: dict[str, Any], s: dict[str, Any]) -> None:
    p = _payload(ev)
    s["open_solver"][str(p.get("iteration"))] = ev.get("utc")


def _h_solver_finished(m: dict[str, Any], ev: dict[str, Any], s: dict[str, Any]) -> None:
    p = _payload(ev)
    name = str(p.get("iteration"))
    it = _iteration(m, name)
    it["outcome"] = p.get("outcome")
    it["count"] = p.get("count")
    it["partial_count"] = p.get("partial_count")
    start = s["open_solver"].pop(name, None)
    m["spans"]["solver"].append(_span(name, start, ev.get("utc")))
    s["last_solver_seq"] = _int(ev.get("seq"))


def _h_ranking(m: dict[str, Any], ev: dict[str, Any], s: dict[str, Any]) -> None:
    p = _payload(ev)
    entry: dict[str, Any] = {
        "method": p.get("method"),
        "candidate_count": p.get("candidate_count"),
        "seq": ev.get("seq"),
        "artefact": None,
    }
    for art in ev.get("artefacts") or []:
        if isinstance(art, dict) and art.get("kind") == "ranking":
            entry["artefact"] = art.get("id")
    m["rankings"][str(p.get("ranking_id"))] = entry


def _h_identity(m: dict[str, Any], ev: dict[str, Any], s: dict[str, Any]) -> None:
    m["identity"].append(dict(_payload(ev)))


def _h_declared(m: dict[str, Any], ev: dict[str, Any], s: dict[str, Any]) -> None:
    p = _payload(ev)
    art = None
    for a in ev.get("artefacts") or []:
        if isinstance(a, dict) and a.get("kind") == "final":
            art = a.get("id")
    s["final"] = {
        "declared_seq": ev.get("seq"),
        "outcome": p.get("outcome"),
        "candidate": p.get("candidate"),
        "ranking_id": p.get("ranking_id"),
        "confidence": p.get("confidence"),
        "artefact": art,
        "withdrawn": False,
    }


def _h_withdrawn(m: dict[str, Any], ev: dict[str, Any], s: dict[str, Any]) -> None:
    if s["final"] is not None:
        s["final"]["withdrawn"] = True


def _h_note(m: dict[str, Any], ev: dict[str, Any], s: dict[str, Any]) -> None:
    m["notes"] += 1


def _h_warning(m: dict[str, Any], ev: dict[str, Any], s: dict[str, Any]) -> None:
    p = _payload(ev)
    m["warnings"].append(f"{p.get('code')}: {p.get('message')}")


def _h_prompt(m: dict[str, Any], ev: dict[str, Any], s: dict[str, Any]) -> None:
    s["prompts"] += 1
    if s["prompts"] == 1:
        s["first_prompt"] = _payload(ev).get("text")
    elif not _payload(ev).get("auto"):
        m["human_messages"] += 1


def _h_spawned(m: dict[str, Any], ev: dict[str, Any], s: dict[str, Any]) -> None:
    p = _payload(ev)
    aid = str(p.get("agent_id"))
    m["agents"].setdefault(aid, {"reports": []})["agent_type"] = p.get("agent_type")
    s["open_agent"][aid] = ev.get("utc")


def _h_stopped(m: dict[str, Any], ev: dict[str, Any], s: dict[str, Any]) -> None:
    aid = str(_payload(ev).get("agent_id"))
    start = s["open_agent"].pop(aid, None)
    m["spans"]["agent"].append(_span(aid, start, ev.get("utc")))


def _h_model_reported(m: dict[str, Any], ev: dict[str, Any], s: dict[str, Any]) -> None:
    p = _payload(ev)
    key = str(p.get("agent") or "main")
    entry = m["agents"].setdefault(key, {"reports": []})
    entry["reports"].append(
        {"requested": p.get("requested"), "actual": p.get("actual"), "source": p.get("source")}
    )
    entry["requested"] = p.get("requested")
    entry["actual"] = p.get("actual")
    entry["source"] = p.get("source")


def _h_phase(m: dict[str, Any], ev: dict[str, Any], s: dict[str, Any]) -> None:
    if s["open_phase"] is not None:
        name, start = s["open_phase"]
        m["spans"]["phase"].append(_span(name, start, ev.get("utc")))
    s["open_phase"] = (str(_payload(ev).get("name")), ev.get("utc"))


HANDLERS: dict[str, Handler] = {
    "run.created": _h_created,
    "env.captured": _h_env,
    "spectra.scanned": _h_scan,
    "spectrum.processed": _h_processed,
    "peaks.picked": _h_picked,
    "lsd.input.registered": _h_lsd_input,
    "solver.started": _h_solver_started,
    "solver.finished": _h_solver_finished,
    "ranking.computed": _h_ranking,
    "identity.derived": _h_identity,
    "final.declared": _h_declared,
    "final.withdrawn": _h_withdrawn,
    "note.added": _h_note,
    "warning.raised": _h_warning,
    "prompt.submitted": _h_prompt,
    "agent.spawned": _h_spawned,
    "agent.stopped": _h_stopped,
    "agent.model_reported": _h_model_reported,
    "phase.started": _h_phase,
}


def _span(name: str, start: str | None, end: str | None) -> dict[str, Any]:
    a, b = _parse(start), _parse(end)
    duration = round((b - a).total_seconds(), 3) if a and b else None
    return {"name": name, "start": start, "end": end, "duration_s": duration}


def _index_artefacts(m: dict[str, Any], ev: dict[str, Any]) -> None:
    for art in _list(ev.get("artefacts"), "artefacts"):
        if not isinstance(art, dict) or "id" not in art:
            continue
        m["artefacts"][str(art["id"])] = {
            "kind": art.get("kind"),
            "path": art.get("path"),
            "sha256": art.get("sha256"),
            "bytes": art.get("bytes"),
            "seq": ev.get("seq"),
            "superseded_by": None,
        }
        old = art.get("supersedes")
        if old and str(old) in m["artefacts"]:
            m["artefacts"][str(old)]["superseded_by"] = art["id"]


def _as_dt(now: str | datetime | None) -> datetime:
    if isinstance(now, datetime):
        return now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    return _parse(now) or datetime.now(timezone.utc)


def fold(
    events: list[dict[str, Any]],
    integrity: dict[str, Any],
    *,
    heartbeat: dict[str, Any] | None = None,
    now: str | datetime | None = None,
) -> dict[str, Any]:
    events = [ev for ev in events if isinstance(ev, dict)]
    m: dict[str, Any] = {
        "schema": "ailsa.run-manifest",
        "schema_version": "1",
        "run_id": events[0].get("run_id") if events else None,
        "writer_host": None,
        "foreign_host_events": 0,
        "dataset": {},
        "class": None,
        "request": {},
        "environment": {},
        "prior_runs": {},
        "blind": False,
        "not_blind_reason": None,
        "status": {},
        "harness": {"name": None, "hooks_recorded": False, "hook_counts": {}},
        "agents": {},
        "experiments": {},
        "views": {},
        "picks": {},
        "iterations": {},
        "rankings": {},
        "identity": [],
        "final": {},
        "notes": 0,
        "artefacts": {},
        "integrity": dict(integrity),
        "spans": {"solver": [], "agent": [], "phase": []},
        "human_messages": 0,
        "assisted": None,
        "warnings": [],
    }
    s: dict[str, Any] = {
        "final": None,
        "prompts": 0,
        "first_prompt": None,
        "open_solver": {},
        "open_agent": {},
        "open_phase": None,
        "last_input_seq": 0,
        "last_solver_seq": 0,
    }
    counts = {name: 0 for name in HOOK_COUNT_TYPES}
    by_type = {t: n for n, t in HOOK_COUNT_TYPES.items()}
    end_ev: dict[str, Any] | None = None
    hooks = False
    # Hook events written after run.finished (after_finish) belong to the session after the
    # run: they never count as human messages, hook counts or the run's end. Decided by
    # position, because records written before the flag was fixed stamp it on every hook event.
    finished_seen = False

    for ev in events:
        raw_type = ev.get("type")
        etype = raw_type if isinstance(raw_type, str) else None
        post_finish = finished_seen
        raw_actor = ev.get("actor")
        actor: dict[str, Any] = raw_actor if isinstance(raw_actor, dict) else {}
        if actor.get("kind") == "hook":
            hooks = True
        if etype in by_type and not post_finish:
            counts[by_type[str(etype)]] += 1
        if etype in END_EVENTS and not post_finish:
            end_ev = ev
        if etype == "run.finished":
            finished_seen = True
        try:
            _index_artefacts(m, ev)
            handler = HANDLERS.get(etype or "")
            if handler is not None and not (post_finish and etype == "prompt.submitted"):
                handler(m, ev, s)
        except (TypeError, ValueError, AttributeError, KeyError) as exc:
            # D-09: a record of unexpected shape is shown with a warning, never a crash.
            m["warnings"].append(
                f"record_anomaly: event {ev.get('seq')} ({etype}) not fully read: "
                f"{type(exc).__name__}: {exc}"[:300]
            )

    writer = m["writer_host"]
    if writer:
        m["foreign_host_events"] = sum(1 for ev in events if ev.get("host") != writer)
    if not m["request"].get("prompt") and s["first_prompt"]:
        m["request"]["prompt"] = s["first_prompt"]
    m["harness"]["hooks_recorded"] = hooks
    m["harness"]["hook_counts"] = counts
    m["assisted"] = None if m["human_messages"] > 0 else False
    if s["open_phase"] is not None and events:
        name, start = s["open_phase"]
        m["spans"]["phase"].append(_span(name, start, events[-1].get("utc")))

    final = s["final"]
    declared_seq = final["declared_seq"] if final else None
    valid = bool(final) and not final["withdrawn"]
    later = max(s["last_input_seq"], s["last_solver_seq"])
    stale = valid and later > _int(declared_seq)
    m["final"] = {
        "declared_seq": declared_seq,
        "outcome": final["outcome"] if final else None,
        "candidate": final["candidate"] if final else None,
        "ranking_id": final["ranking_id"] if final else None,
        "confidence": final["confidence"] if final else None,
        "artefact": final["artefact"] if final else None,
        "stale": stale,
        "withdrawn": final["withdrawn"] if final else False,
        "valid": valid,
    }

    last_event_utc = events[-1].get("utc") if events else None
    hb_utc = heartbeat.get("utc") if isinstance(heartbeat, dict) else None
    last_activity = max([str(u) for u in (last_event_utc, hb_utc) if u], default=None)
    inferred = False
    reason: str | None = None
    if valid and not stale:
        state = "result_declared"
        label = STATE_LABELS[state].format(outcome=final["outcome"] if final else "")
    elif valid and stale:
        state = "declaration_stale"
        label = STATE_LABELS[state]
    elif end_ev is not None:
        state = "stopped_before_result"
        label = STATE_LABELS[state]
        inferred = True
        reason = (
            "the declaration was withdrawn"
            if final and final["withdrawn"]
            else "the run ended without a valid declaration"
        )
    else:
        a = _parse(last_activity)
        idle = (_as_dt(now) - a).total_seconds() if a else 0
        if a and idle > NO_HEARTBEAT_AFTER_S:
            state = "no_heartbeat"
            label = STATE_LABELS[state].format(utc=last_activity)
            inferred = True
            reason = "no event or heartbeat for more than 15 minutes"
        else:
            state = "running"
            label = STATE_LABELS[state]
    m["status"] = {
        "state": state,
        "inferred": inferred,
        "label": label,
        "reason": reason,
        "heartbeat_utc": hb_utc,
        "started_utc": events[0].get("utc") if events else None,
        "last_event_utc": last_event_utc,
        "ended_utc": end_ev.get("utc") if end_ev else None,
        "counts_as_clean": bool(integrity.get("clean")) and state == "result_declared",
    }
    return m


def _read_heartbeat(run_dir: Path) -> dict[str, Any] | None:
    try:
        data = json.loads((run_dir / HEARTBEAT).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def rebuild_manifest(
    run_dir: str | Path, now: str | datetime | None = None
) -> dict[str, Any]:
    path = Path(run_dir)
    result = read_events(path)
    manifest = fold(
        result["events"], result["integrity"], heartbeat=_read_heartbeat(path), now=now
    )
    atomic_write_json(path / MANIFEST, manifest)
    return manifest
