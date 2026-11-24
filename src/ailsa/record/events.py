"""Event vocabulary, enums, ID forms and run-folder file names (single source of names).

Standard library only. Later plans import from here and do not edit it.

Envelope (one JSON object per line in ``events.jsonl``):

- ``v``: schema version (1)
- ``seq``: gapless sequence number starting at 1
- ``utc``: ISO time with milliseconds and ``Z``
- ``host``: host alias of the writer
- ``run_id``: run folder name
- ``type``: one of the keys of ``REQUIRED_PAYLOAD``
- ``actor``: ``{kind, name, role, agent_id, model}``
- ``span``: ``{id, parent}`` or null
- ``refs``: list of IDs (see ``ID_PATTERNS``)
- ``payload``: object with at least the keys of ``REQUIRED_PAYLOAD[type]``
- ``artefacts``: list of ``{id, kind, path, sha256, bytes, supersedes}``; ``path`` is
  relative to the run folder
- ``post_run``: false in this phase
- ``after_finish``: true only for hook events written after ``run.finished``
- ``prev``: sha256 (hex) of the raw bytes of the previous line without the newline;
  genesis is ``sha256(run_id)``
"""

from __future__ import annotations

SCHEMA_VERSION = 1

TEXT_CAP = 4000
COMMAND_CAP = 2000
ARGV_ITEM_CAP = 300
DIFF_CAP = 20000

# Run-folder file and folder names
MARKER = ".ailsa-run"
EVENTS = "events.jsonl"
EVENTS_LOCK = "events.lock"
COUNTERS = ".counters.json"
FINISHED = "finished.json"
MANIFEST = "manifest.json"
HEARTBEAT = "heartbeat.json"
HOOKS_SETTINGS = "hooks.json"
HOOK_ERRORS = "hook-errors.log"
AGENT_DIR = "agent"
RECORD_DIRS = (
    "spectra",
    "peaks",
    "iterations",
    "rankings",
    "identity",
    "model",
    "final",
    "nus",
    "jcamp",
    "transcript",
    "renderings",
)

# Workspace file and folder names
INDEX = "runs.json"
WORKSPACE_LOCK = ".lock"
SESSIONS_DIR = ".sessions"

# Enums
ACTOR_KINDS = ("tool", "hook", "agent", "human", "launcher")
SOLVER_OUTCOMES = (
    "not_run",
    "blocked",
    "solutions",
    "no_solution",
    "limit_reached",
    "timeout",
    "error",
)
SMILES_ABSENT_REASONS = (
    "no_solution",
    "conversion_skipped_large",
    "conversion_failed",
    "timeout",
    "not_run",
    "blocked",
    "error",
)
ITERATION_PURPOSES = ("main", "family", "diagnostic", "control")
FINAL_OUTCOMES = (
    "proposal",
    "proposal_under_determined",
    "inconclusive",
    "no_structure_fits",
    "insufficient_data",
    "handed_to_human",
)
OUTCOMES_NEEDING_CANDIDATE = ("proposal", "proposal_under_determined")
OUTCOMES_NEEDING_RANKING = ("proposal", "proposal_under_determined", "inconclusive")
CONFIDENCE_LEVELS = ("high", "medium", "low")
ALTERNATIVE_STATUSES = ("not_excluded", "less_likely", "excluded")
RUN_CLASSES = ("public", "internal", "confidential")
PROCESSING_STATES = ("vendor", "rawproc", "nus-smile", "nus-vendor", "agent-script")
PEAK_ACTIONS = ("accept", "reject", "merge", "assign")
PEAK_CATEGORIES = (
    "solvent",
    "1J-leakage",
    "t1-noise",
    "impurity",
    "satellite",
    "artefact",
    "other",
)
WEB_TOOLS = ("enabled", "disabled", "unknown")
MODEL_SOURCES = ("harness", "transcript", "self-report", "launcher")
RUN_STATES = (
    "running",
    "result_declared",
    "declaration_stale",
    "stopped_before_result",
    "no_heartbeat",
)

REQUIRED_PAYLOAD: dict[str, tuple[str, ...]] = {
    # Lifecycle
    "run.created": ("dataset", "class", "request", "prior_runs", "writer_host"),
    "run.bound": ("session_id", "harness", "via"),
    "run.attempt.started": ("attempt", "harness", "time_limit_s"),
    "run.attempt.ended": ("attempt", "exit_code", "reason", "elapsed_s"),
    "run.paused": ("cause", "detail"),
    "run.finished": ("state", "reason"),
    "env.captured": (
        "ailsa",
        "skill",
        "lsd",
        "outlsd",
        "database",
        "predictor",
        "harness",
        "mode",
        "time_limit_s",
        "web_tools",
        "host",
    ),
    "log.recovered": ("discarded_bytes", "partial_sha256"),
    "warning.raised": ("code", "message"),
    # Hooks and agents
    "session.started": ("source", "model"),
    "prompt.submitted": ("text", "chars", "auto"),
    "human.waiting": ("notification_type", "message"),
    "agent.spawned": ("agent_id", "agent_type"),
    "agent.stopped": ("agent_id", "agent_type"),
    "agent.message": ("from", "to", "kind", "text"),
    "agent.model_reported": ("agent", "requested", "actual", "source"),
    "agent.turn_ended": ("agent_id",),
    "context.compacted": ("trigger", "stage"),
    "session.ended": ("reason",),
    "model.switched": ("from_model", "to_model"),
    "transcript.copied": ("files", "via"),
    "tool.shell": ("command", "response_bytes", "response_sha256"),
    "note.added": ("text", "sender"),
    "phase.started": ("name",),
    # Spectra, peaks, model
    "spectra.scanned": ("experiments", "unreadable"),
    "spectrum.processed": ("experiment", "view_id", "state", "status"),
    "peaks.picked": ("pick_id", "experiment", "picker", "parameters", "count", "noise_sigma"),
    "peak.decided": ("peaks", "action", "category", "reason"),
    "model.imported": ("atoms", "correlations"),
    # Tools and solver
    "tool.invoked": ("argv", "exit_code", "duration_s"),
    "lsd.input.registered": ("iteration", "parent", "purpose", "lsd_sha256", "path"),
    "solver.started": ("iteration", "host", "timeout_s"),
    "solver.finished": ("iteration", "outcome", "count", "elapsed_s", "host", "provenance"),
    "solutions.converted": ("iteration", "count", "status"),
    "solutions.analysed": ("iteration", "analysed", "cap", "truncated"),
    "validation.result": ("validator", "verdict", "checks"),
    "ranking.computed": ("ranking_id", "method", "inputs", "candidate_count"),
    "identity.derived": ("smiles", "inchikey", "verdict"),
    "final.declared": ("outcome", "ranking_id", "candidate", "confidence"),
    "final.withdrawn": ("reason",),
    # Declared for later writers (typed now so no migration is needed)
    "decision.recorded": ("subject", "choice", "reason"),
    "hypothesis.opened": ("hypothesis", "description"),
    "hypothesis.closed": ("hypothesis", "outcome"),
    "atom.set": ("atom",),
    "correlation.set": ("correlation", "kind"),
    "constraint.set": ("constraint", "lsd"),
    "loop.detected": ("pattern",),
    "intervention.sent": ("text",),
    "escalation": ("reason",),
    "diagnostic.reported": ("root_cause",),
    "assessment.recorded": ("candidate", "plausibility", "confidence"),
    "gate.result": ("gate", "verdict"),
    "referencing.set": ("experiment", "offset_ppm"),
    "qc.override": ("experiment", "reason"),
    "spectrum.qc": ("experiment", "verdict"),
    "detection.queried": ("query",),
    "report.rendered": ("files",),
    "annotation.added": ("author", "kind", "text"),
}

HOOK_TYPES = frozenset(
    {
        "session.started",
        "prompt.submitted",
        "human.waiting",
        "agent.spawned",
        "agent.stopped",
        "agent.message",
        "agent.model_reported",
        "agent.turn_ended",
        "context.compacted",
        "session.ended",
        "model.switched",
        "transcript.copied",
        "tool.shell",
        "run.paused",
    }
)


# ID helpers
def exp_id(exp: str | int) -> str:
    return f"exp:{exp}"


def pick_id(exp: str | int, n: int) -> str:
    return f"pick:{exp}:{n}"


def peak_id(exp: str | int, pick: int, n: int) -> str:
    return f"pk:{exp}:{pick}:{n}"


def iteration_id(n: int, family: str | None = None) -> str:
    base = f"it{n:02d}"
    return f"{base}.{family}" if family else base


def solution_id(iteration: str, n: int) -> str:
    return f"sol:{iteration}:{n}"


def ranking_id(n: int) -> str:
    return f"rk{n:02d}"


def candidate_id(ranking: str, n: int) -> str:
    return f"cand:{ranking}:{n}"


def artefact_id(kind: str, n: int) -> str:
    return f"art:{kind}:{n}"


def view_id(exp: str | int, state: str) -> str:
    return f"view:{exp}:{state}"


def structure_id(inchikey: str) -> str:
    return f"str:{inchikey}"


def atom_id(n: int) -> str:
    return f"at:{n}"


def correlation_id(kind: str, n: int) -> str:
    return f"cor:{kind}:{n}"


def constraint_id(n: int) -> str:
    return f"con:{n}"


def decision_id(n: int) -> str:
    return f"dec:{n}"


def hypothesis_id(n: int) -> str:
    return f"hyp:{n}"


ID_PATTERNS: dict[str, str] = {
    "exp": r"^exp:[^:\s]+$",
    "pick": r"^pick:[^:\s]+:\d+$",
    "peak": r"^pk:[^:\s]+:\d+:\d+$",
    "iteration": r"^it\d{2,}(\.[A-Za-z0-9_-]+)?$",
    "solution": r"^sol:it\d{2,}(\.[A-Za-z0-9_-]+)?:\d+$",
    "ranking": r"^rk\d{2,}$",
    "candidate": r"^cand:rk\d{2,}:\d+$",
    "artefact": r"^art:[A-Za-z0-9_-]+:\d+$",
    "view": r"^view:[^:\s]+:[A-Za-z0-9_-]+$",
    "structure": r"^str:[A-Z]{14}-[A-Z]{10}-[A-Z]$",
    "atom": r"^at:\d+$",
    "correlation": r"^cor:[A-Za-z0-9_-]+:\d+$",
    "constraint": r"^con:\d+$",
    "decision": r"^dec:\d+$",
    "hypothesis": r"^hyp:\d+$",
}
