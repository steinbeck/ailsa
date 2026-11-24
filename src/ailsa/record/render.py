"""Markdown renderings of the run record (standard library only).

``CASE-PROGRESS.md`` and ``final_results.md`` are generated from the manifest and the event
log; nobody writes them by hand. Every agent-supplied string passes through ``md_escape``
(REC-22, D-10). Blind runs never show identity names or the text of human prompts.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from ailsa.record.fold import rebuild_manifest
from ailsa.record.fsutil import atomic_write_bytes, sha256_bytes
from ailsa.record.log import read_events

PROGRESS_FILE = "CASE-PROGRESS.md"
FINAL_FILE = "final_results.md"
BREAK_MARKER = "**Record changed or incomplete from here**"
NOT_RECORDED = (
    "Prompts, permission waits, subagents, messages between agents, compaction and heartbeat: "
    "not recorded by this harness"
)
STOPPED_LINE = "Stopped before a result (inferred)"

_SPECIAL = re.compile(r"([\\|`*_\[\]])")

DIARY_TEMPLATES: dict[str, str] = {
    "run.created": "Run created",
    "env.captured": "Environment recorded",
    "session.started": "Session started",
    "spectra.scanned": "Spectra scanned",
    "peaks.picked": "Peaks picked in experiment {experiment}: {count}",
    "peak.decided": "Peak decision: {action}",
    "lsd.input.registered": "Solver input {iteration} registered ({purpose})",
    "solver.started": "Solver round {iteration} started",
    "solver.finished": "Solver round {iteration}: {count} possible structures ({outcome})",
    "ranking.computed": "Ranking {ranking_id}: {candidate_count} candidates",
    "identity.derived": "Identity check: {verdict}",
    "final.declared": "Result declared: {outcome}",
    "final.withdrawn": "Result withdrawn",
    "agent.spawned": "Agent started: {agent_type}",
    "agent.stopped": "Agent stopped: {agent_type}",
    "agent.turn_ended": "Agent turn ended",
    "context.compacted": "Context compacted",
    "human.waiting": "Waiting for a human",
    "phase.started": "Phase started: {name}",
    "run.attempt.ended": "Attempt {attempt} ended: {reason}",
    "run.finished": "Run finished: {state}",
    "session.ended": "Session ended: {reason}",
    "warning.raised": "Warning {code}",
}


def md_escape(text: Any) -> str:
    """Escape agent text for Markdown, including table cells."""
    s = str(text)
    s = re.sub(r"\s*[\r\n]+\s*", " ", s)
    s = _SPECIAL.sub(r"\\\1", s)
    s = s.replace("<", "&lt;").replace(">", "&gt;")
    if s.startswith("#"):
        s = "\\" + s
    return s


class _Fields(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return "?"


def _describe(ev: dict[str, Any], first_prompt_seq: int | None) -> str:
    etype = str(ev.get("type"))
    p = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
    if etype == "prompt.submitted":
        return "Invocation prompt" if ev.get("seq") == first_prompt_seq else "Message from a human"
    if etype == "note.added":
        return f"Note from {md_escape(p.get('sender', '?'))}: {md_escape(p.get('text', ''))}"
    if etype == "agent.message":
        return f"Message {md_escape(p.get('from', '?'))} to {md_escape(p.get('to', '?'))}"
    template = DIARY_TEMPLATES.get(etype)
    if template is None:
        return md_escape(etype)
    fields = _Fields({k: md_escape(v) for k, v in p.items()})
    return template.format_map(fields)


def _who(ev: dict[str, Any]) -> str:
    actor = ev.get("actor") if isinstance(ev.get("actor"), dict) else {}
    name = actor.get("role") or actor.get("name") or actor.get("kind") or "?"
    return md_escape(name)


def render_progress(manifest: dict[str, Any], events: list[dict[str, Any]]) -> str:
    status = manifest.get("status", {})
    integrity = manifest.get("integrity", {})
    dataset = manifest.get("dataset") or {}
    lines = [
        f"# Run progress: {md_escape(manifest.get('run_id'))}",
        "",
        f"- Dataset: {md_escape(dataset.get('label', '?'))}",
        f"- Class: {md_escape(manifest.get('class'))}",
        f"- Status: {md_escape(status.get('label'))}",
    ]
    if integrity.get("clean", True):
        lines.append("- Record integrity: clean")
    else:
        lines.append(
            f"- Record integrity: changed or incomplete from event "
            f"{integrity.get('first_bad_seq')} ({md_escape(integrity.get('reason'))})"
        )
    harness = manifest.get("harness", {})
    if harness.get("hooks_recorded"):
        counts = harness.get("hook_counts", {})
        shown = ", ".join(f"{k.replace('_', ' ')} {counts[k]}" for k in counts)
        lines.append(f"- Hooks: {shown}")
    else:
        lines.append(f"- {NOT_RECORDED}")
    lines += ["", "| # | UTC | Who | What |", "|---|---|---|---|"]
    first_prompt = next((e.get("seq") for e in events if e.get("type") == "prompt.submitted"), None)
    marked = False
    for ev in events:
        if ev.get("_suspect") and not marked:
            lines.append(f"| | | | {BREAK_MARKER} |")
            marked = True
        lines.append(
            f"| {ev.get('seq')} | {md_escape(ev.get('utc'))} | {_who(ev)} | "
            f"{_describe(ev, first_prompt)} |"
        )
    return "\n".join(lines) + "\n"


def _bullets(title: str, items: list[Any]) -> list[str]:
    if not items:
        return []
    return ["", f"### {title}", ""] + [f"- {md_escape(i)}" for i in items]


def render_final(
    manifest: dict[str, Any],
    ranking: dict[str, Any] | None,
    declaration: dict[str, Any] | None,
    *,
    note: str | None = None,
) -> str:
    status = manifest.get("status", {})
    state = status.get("state")
    dataset = manifest.get("dataset") or {}
    lines = [
        f"# Final results: {md_escape(manifest.get('run_id'))}",
        "",
        f"Dataset: {md_escape(dataset.get('label', '?'))}",
        "",
        "## Result",
        "",
    ]
    if state not in ("result_declared", "declaration_stale"):
        if state in ("stopped_before_result", "no_heartbeat"):
            lines.append(STOPPED_LINE)
            lines += ["", f"Reason: {md_escape(status.get('reason') or status.get('label'))}"]
            lines += [
                "",
                "Files written by the agent without a declaration are unverified and not shown.",
            ]
        else:
            lines.append("Run in progress: no result declared yet")
        return "\n".join(lines) + "\n"

    final = manifest.get("final", {})
    decl = declaration or {}
    lines.append(f"Outcome: {md_escape(final.get('outcome'))}")
    if state == "declaration_stale":
        lines += [
            "",
            "**Warning: a solver ran after this declaration, so it may no longer hold.**",
        ]
    if note:
        lines += ["", f"**{md_escape(note)}**"]
    if decl.get("termination_reason"):
        lines += ["", f"Termination reason: {md_escape(decl['termination_reason'])}"]
    cands = (ranking or {}).get("candidates") or []
    chosen = next((c for c in cands if c.get("rank") == final.get("candidate")), None)
    if chosen:
        lines += [
            "",
            "### Chosen candidate",
            "",
            f"- Rank: {chosen.get('rank')}",
            f"- SMILES: `{str(chosen.get('smiles')).replace('`', '')}`",
            f"- MAE: {chosen.get('mae')}",
            f"- Shifts within tolerance: {chosen.get('within_tolerance')}",
        ]
    if final.get("confidence"):
        lines += ["", f"Confidence: {md_escape(final['confidence'])}"]
    lines += _bullets("Caveats", decl.get("caveats") or [])
    lines += _bullets("Open questions", decl.get("open_questions") or [])
    lines += _bullets("Next steps", decl.get("next_steps") or [])
    alts = decl.get("alternatives") or []
    if alts:
        lines += ["", "### Alternatives", ""]
        for alt in alts:
            lines.append(
                f"- Candidate {md_escape(alt.get('rank', alt.get('candidate')))}: "
                f"{md_escape(alt.get('status'))} ({md_escape(alt.get('reason', ''))})"
            )
    if decl.get("iterations"):
        lines += ["", "Iterations covered: " + ", ".join(md_escape(i) for i in decl["iterations"])]
    ids = [i for i in manifest.get("identity", []) if isinstance(i, dict)]
    if ids:
        lines += ["", "### Identity", ""]
        for item in ids:
            name = (
                "hidden in blind mode"
                if manifest.get("blind")
                else md_escape(item.get("derived_name") or "none")
            )
            lines.append(f"- Verdict: {md_escape(item.get('verdict'))}; derived name: {name}")
    if cands:
        lines += ["", "### Top candidates", "", "| Rank | SMILES | MAE | Within tolerance |"]
        lines.append("|---|---|---|---|")
        for c in cands[:10]:
            smiles = str(c.get("smiles")).replace("`", "").replace("|", "")
            lines.append(
                f"| {c.get('rank')} | `{smiles}` | {c.get('mae')} | {c.get('within_tolerance')} |"
            )
    return "\n".join(lines) + "\n"


def _load_artefact(
    run_dir: Path, manifest: dict[str, Any], art_id: str | None
) -> tuple[dict[str, Any] | None, str | None]:
    if not art_id:
        return None, None
    entry = manifest.get("artefacts", {}).get(art_id)
    if not entry or not entry.get("path"):
        return None, None
    base = run_dir.resolve()
    path = (run_dir / entry["path"]).resolve()
    if base not in path.parents:
        return None, f"{art_id} points outside the run folder"
    try:
        data = path.read_bytes()
    except OSError:
        return None, f"{art_id} file is missing"
    if entry.get("sha256") and sha256_bytes(data) != entry["sha256"]:
        kind = "ranking" if entry.get("kind") == "ranking" else "declaration"
        return None, f"{kind} file changed after it was recorded"
    try:
        obj = json.loads(data)
    except ValueError:
        return None, f"{art_id} is not valid JSON"
    return (obj if isinstance(obj, dict) else None), None


def render_run(run_dir: str | Path, now: str | datetime | None = None) -> list[Path]:
    path = Path(run_dir)
    manifest = rebuild_manifest(path, now=now)
    events = read_events(path)["events"]
    ranking_art = (manifest["rankings"].get(manifest["final"].get("ranking_id")) or {}).get(
        "artefact"
    )
    ranking, note1 = _load_artefact(path, manifest, ranking_art)
    declaration, note2 = _load_artefact(path, manifest, manifest["final"].get("artefact"))
    out_dir = path / "renderings"
    out_dir.mkdir(mode=0o700, exist_ok=True)
    progress = out_dir / PROGRESS_FILE
    final = out_dir / FINAL_FILE
    atomic_write_bytes(progress, render_progress(manifest, events).encode("utf-8"))
    text = render_final(manifest, ranking, declaration, note=note1 or note2)
    atomic_write_bytes(final, text.encode("utf-8"))
    return [progress, final]


__all__ = ["render_progress", "render_final", "render_run", "md_escape"]
