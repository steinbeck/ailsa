"""Typed contracts of the run record: event envelope, payloads, artefacts, manifest.

This is the only ``ailsa.record`` module that imports pydantic; hooks and the log writer
stay stdlib-only. The JSON Schemas under ``ailsa/data/schemas/run_*.json`` are generated
from these models (``python -m ailsa.record.models --write-schemas <dir>``) and guarded by
a drift test.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, create_model, model_validator

from ailsa.record.events import (
    ACTOR_KINDS,
    ALTERNATIVE_STATUSES,
    CONFIDENCE_LEVELS,
    FINAL_OUTCOMES,
    ID_PATTERNS,
    ITERATION_PURPOSES,
    MODEL_SOURCES,
    OUTCOMES_NEEDING_CANDIDATE,
    PEAK_ACTIONS,
    PEAK_CATEGORIES,
    PROCESSING_STATES,
    REQUIRED_PAYLOAD,
    RUN_CLASSES,
    RUN_STATES,
    SMILES_ABSENT_REASONS,
    SOLVER_OUTCOMES,
    WEB_TOOLS,
)

SHA_PATTERN = r"^[0-9a-f]{64}$"
UTC_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?Z$"

ActorKind = Literal[ACTOR_KINDS]  # type: ignore[valid-type]
SolverOutcome = Literal[SOLVER_OUTCOMES]  # type: ignore[valid-type]
SmilesAbsent = Literal[SMILES_ABSENT_REASONS]  # type: ignore[valid-type]
IterationPurpose = Literal[ITERATION_PURPOSES]  # type: ignore[valid-type]
FinalOutcome = Literal[FINAL_OUTCOMES]  # type: ignore[valid-type]
Confidence = Literal[CONFIDENCE_LEVELS]  # type: ignore[valid-type]
AlternativeStatus = Literal[ALTERNATIVE_STATUSES]  # type: ignore[valid-type]
RunClass = Literal[RUN_CLASSES]  # type: ignore[valid-type]
ProcessingState = Literal[PROCESSING_STATES]  # type: ignore[valid-type]
PeakAction = Literal[PEAK_ACTIONS]  # type: ignore[valid-type]
PeakCategory = Literal[PEAK_CATEGORIES]  # type: ignore[valid-type]
WebTools = Literal[WEB_TOOLS]  # type: ignore[valid-type]
ModelSource = Literal[MODEL_SOURCES]  # type: ignore[valid-type]
RunState = Literal[RUN_STATES]  # type: ignore[valid-type]


# --------------------------------------------------------------------------- envelope


class ArtefactRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str
    path: str
    sha256: str = Field(pattern=SHA_PATTERN)
    bytes: int = Field(ge=0)
    supersedes: str | None = None


class ActorModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: ActorKind
    name: str | None = None
    role: str | None = None
    agent_id: str | None = None
    model: str | None = None


class SpanModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    parent: str | None = None


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")

    v: Literal[1]
    seq: int = Field(ge=1)
    utc: str = Field(pattern=UTC_PATTERN)
    host: str
    run_id: str
    type: str
    actor: ActorModel
    span: SpanModel | None = None
    refs: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    artefacts: list[ArtefactRef] = Field(default_factory=list)
    post_run: bool = False
    after_finish: bool = False
    prev: str = Field(pattern=SHA_PATTERN)


# Field types fixed by the vocabulary; every other required key is ``Any``.
_TYPED_PAYLOAD: dict[str, dict[str, Any]] = {
    "solver.finished": {"outcome": SolverOutcome},
    "lsd.input.registered": {"purpose": IterationPurpose},
    "final.declared": {
        "outcome": FinalOutcome,
        "confidence": Confidence | None,
        "candidate": int | None,
    },
    "peak.decided": {
        "peaks": (list[str], Field(min_length=1)),
        "action": PeakAction,
        "category": PeakCategory | None,
    },
    "spectrum.processed": {"state": ProcessingState},
    "env.captured": {"web_tools": WebTools},
    "agent.model_reported": {"source": ModelSource},
    "run.created": {"class": RunClass},
}


def _build_payload_models() -> dict[str, type[BaseModel]]:
    out: dict[str, type[BaseModel]] = {}
    for etype, keys in REQUIRED_PAYLOAD.items():
        typed = _TYPED_PAYLOAD.get(etype, {})
        fields: dict[str, Any] = {}
        for key in keys:
            spec = typed.get(key, Any)
            if isinstance(spec, tuple):
                fields[key] = (spec[0], spec[1])
            else:
                fields[key] = (spec, ...)
        name = "Payload_" + etype.replace(".", "_")
        out[etype] = create_model(  # type: ignore[call-overload]
            name, __config__=ConfigDict(extra="allow"), **fields
        )
    return out


PAYLOAD_MODELS: dict[str, type[BaseModel]] = _build_payload_models()


def _err(exc: ValidationError, prefix: str = "") -> list[str]:
    out = []
    for e in exc.errors():
        loc = ".".join(str(p) for p in e["loc"])
        out.append(f"{prefix}{loc}: {e['msg']}")
    return out


def validate_event(ev: dict[str, Any]) -> list[str]:
    """Validate envelope and (for known types) payload. Returns error strings, never raises."""
    try:
        parsed = Event.model_validate(ev)
    except ValidationError as exc:
        return _err(exc)
    except Exception as exc:  # noqa: BLE001 - never raise
        return [f"envelope: {exc}"]
    model = PAYLOAD_MODELS.get(parsed.type)
    if model is None:
        return []
    try:
        model.model_validate(parsed.payload)
    except ValidationError as exc:
        return _err(exc)
    return []


# --------------------------------------------------------------------------- artefacts


class _Artefact(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


def _schema_field(name: str) -> Any:
    return Field(default=name, alias="schema")


class SourceFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    sha256: str


class NusInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fraction: float | None = None
    schedule_present: bool = False


class ExperimentEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    folder_alias: str | None = None
    kind: str | None = None
    nucleus: str | None = None
    nucleus_f1: str | None = None
    pulse_program: str | None = None
    processed: bool = False
    raw: bool = False
    edited: bool = False
    scans: int | None = None
    solvent: str | None = None
    sfo1_mhz: float | None = None
    sfo1_f1_mhz: float | None = None
    temperature_k: float | None = None
    sw_hz: float | None = None
    nus: NusInfo | None = None
    readable: bool = True
    reason: str | None = None
    source_files: list[SourceFile] = Field(default_factory=list)


class JcampFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    sha256: str
    headers: dict[str, Any] = Field(default_factory=dict)


class ExperimentInventory(_Artefact):
    schema_: Literal["ailsa.experiment-inventory"] = _schema_field("ailsa.experiment-inventory")
    schema_version: Literal["1"] = "1"
    dataset_fingerprint: str
    blind: bool
    experiments: list[ExperimentEntry] = Field(default_factory=list)
    jcamp_files: list[JcampFile] = Field(default_factory=list)
    unreadable: int = Field(default=0, ge=0)


class Quantisation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: Literal["log1p-noise"]
    zmax: float
    scale: float


class LevelFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: str
    shape: list[int]
    factor: float | None = None


class ProjectionFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    axis: str
    file: str


class SpectrumView(_Artefact):
    schema_: Literal["ailsa.spectrum-view"] = _schema_field("ailsa.spectrum-view")
    schema_version: Literal["1"] = "1"
    view_id: str
    experiment: str
    kind: Literal["1d", "2d"]
    nuclei: list[str]
    sf_mhz: list[float]
    ppm_start: list[float]
    ppm_end: list[float]
    points: list[int]
    noise_sigma: float | None = None
    quantisation: Quantisation | None = None
    levels: list[LevelFile] = Field(default_factory=list)
    projections: list[ProjectionFile] = Field(default_factory=list)
    sign_meaning: str | None = None
    state: ProcessingState
    qc_verdict: str | None = None
    source_sha256: dict[str, str] = Field(default_factory=dict)
    reader: str
    reader_version: str
    referencing: dict[str, Any] = Field(default_factory=dict)
    contour_levels_sigma: list[float] = Field(default_factory=list)


class PeakEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    ppm: float | None = None
    ppm_f2: float | None = None
    ppm_f1: float | None = None
    intensity: float | None = None
    snr: float | None = None
    sign: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class RejectedPeak(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ppm: float | None = None
    ppm_f2: float | None = None
    ppm_f1: float | None = None
    category: str | None = None
    reason: str | None = None


class PeakPick(_Artefact):
    schema_: Literal["ailsa.peak-pick"] = _schema_field("ailsa.peak-pick")
    schema_version: Literal["1"] = "1"
    pick_id: str
    experiment: str
    source_sha256: dict[str, str] = Field(default_factory=dict)
    picker: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    referencing: dict[str, Any] = Field(default_factory=dict)
    noise_sigma: float | None = None
    peaks: list[PeakEntry] = Field(default_factory=list)
    rejected: list[RejectedPeak] = Field(default_factory=list)
    rejected_available: bool = False


class PeakDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    peaks: list[str] = Field(min_length=1)
    action: PeakAction
    category: PeakCategory | None = None
    reason: str = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)
    target: str | None = None


class PeakDecisionTable(_Artefact):
    schema_: Literal["ailsa.peak-decisions"] = _schema_field("ailsa.peak-decisions")
    schema_version: Literal["1"] = "1"
    decisions: list[PeakDecision] = Field(min_length=1)


class AtomEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=ID_PATTERNS["atom"])
    element: str
    lsd_index: int | None = None
    shift: float | None = None
    multiplicity: str | None = None
    h_count: int | None = None
    hybridisation: str | None = None
    evidence: list[str] = Field(default_factory=list)
    sources: dict[str, str] = Field(default_factory=dict)


class CorrelationEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=ID_PATTERNS["correlation"])
    kind: str
    peaks: list[str] = Field(default_factory=list)
    atoms: list[str] = Field(default_factory=list)
    use: bool = True
    confidence: str | None = None
    reason: str | None = None


class AtomModel(_Artefact):
    schema_: Literal["ailsa.atom-model"] = _schema_field("ailsa.atom-model")
    schema_version: Literal["1"] = "1"
    atoms: list[AtomEntry] = Field(default_factory=list)
    correlations: list[CorrelationEntry] = Field(default_factory=list)


class ToolInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str | None = None
    version: str | None = None
    sha256: str | None = None


class FileInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    sha256: str
    bytes: int = Field(ge=0)


class SolverRun(_Artefact):
    schema_: Literal["ailsa.solver-run"] = _schema_field("ailsa.solver-run")
    schema_version: Literal["1"] = "1"
    iteration: str
    purpose: IterationPurpose
    parent: str | None = None
    host: str
    remote: bool = False
    provenance: Literal["run", "imported"]
    outcome: SolverOutcome
    count: int = Field(ge=0)
    partial_count: int | None = None
    limit: int | None = None
    elapsed_s: float | None = None
    timeout_s: int | None = None
    exit_code: int | None = None
    error_line: str | None = None
    lsd: ToolInfo | None = None
    outlsd: ToolInfo | None = None
    files: dict[str, FileInfo] = Field(default_factory=dict)
    smiles_absent_reason: SmilesAbsent | None = None
    scratch_dir: str | None = None


class ElimInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_eliminated: int | None = None
    max_bonds: int | None = None


class SolutionCorrelation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    carbon: int | None = None
    proton: int | None = None
    path_length: int | None = None
    j_coupling: int | None = None
    allowed_max: int | None = None
    exceeds_window: bool = False


class SolutionEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    solution: int
    solution_id: str
    correlations: list[SolutionCorrelation] = Field(default_factory=list)
    dropped_by_elim: list[int] = Field(default_factory=list)


class SolutionAnalysis(_Artefact):
    schema_: Literal["ailsa.solution-analysis"] = _schema_field("ailsa.solution-analysis")
    schema_version: Literal["1"] = "1"
    iteration: str
    lsd_sha256: str | None = None
    sol_sha256: str | None = None
    cap: int
    analysed: int
    total: int
    truncated: bool
    elim_active: bool = False
    elim: ElimInfo | None = None
    solutions: list[SolutionEntry] = Field(default_factory=list)


class AtomBasis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hose_code: str | None = None
    radius_used: int | None = None
    match_count: int | None = None
    std_dev: float | None = None
    min_shift: float | None = None
    max_shift: float | None = None
    confidence: str | None = None


class CandidateAtom(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lsd_atom: int
    observed: float | None = None
    predicted: float | None = None
    error: float | None = None
    basis: AtomBasis | None = None


class AtomMapEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    depiction_index: int
    lsd_atom: int
    element: str
    h_count: int | None = None


class CandidateCorrelation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    carbon: int | None = None
    proton: int | None = None
    path_length: int | None = None
    j_coupling: int | None = None


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=ID_PATTERNS["candidate"])
    rank: int = Field(ge=1)
    smiles: str
    inchikey: str | None = None
    mae: float | None = None
    within_tolerance: int | None = None
    compared: int | None = None
    carbons: int | None = None
    max_error: float | None = None
    worst_atom: int | None = None
    solutions: list[str] = Field(default_factory=list)
    mapping_status: Literal["ok", "unavailable", "not_applicable"]
    atom_map: list[AtomMapEntry] = Field(default_factory=list)
    atoms: list[CandidateAtom] = Field(default_factory=list)
    correlations: list[CandidateCorrelation] | None = None


class RankingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    iteration: str | None = None
    path: str
    lsd_sha256: str | None = None
    sol_sha256: str | None = None
    smiles_sha256: str | None = None


class PredictorInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backend: str
    database_sha256: str | None = None
    max_radius: int | None = None


class Ranking(_Artefact):
    schema_: Literal["ailsa.ranking"] = _schema_field("ailsa.ranking")
    schema_version: Literal["1"] = "1"
    ranking_id: str = Field(pattern=ID_PATTERNS["ranking"])
    method: Literal["assigned", "nearest-line"]
    tolerance: float
    inputs: list[RankingInput] = Field(default_factory=list)
    predictor: PredictorInfo
    total_solutions: int = Field(ge=0)
    distinct_structures: int = Field(ge=0)
    skipped: int = Field(default=0, ge=0)
    observed_shifts: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    correlations_cap: int | None = None
    candidates: list[Candidate] = Field(default_factory=list)


class IdentityVerdict(_Artefact):
    schema_: Literal["ailsa.identity"] = _schema_field("ailsa.identity")
    schema_version: Literal["1"] = "1"
    smiles: str
    canonical_smiles: str | None = None
    inchikey: str | None = None
    verdict: str
    derived_name: str | None = None
    reported_name: str | None = None
    name_match: str | None = None
    hidden_in_blind: bool = False
    candidate: str | None = None


class Alternative(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rank: int = Field(ge=1)
    status: AlternativeStatus


class FinalDeclaration(_Artefact):
    schema_: Literal["ailsa.final"] = _schema_field("ailsa.final")
    schema_version: Literal["1"] = "1"
    outcome: FinalOutcome
    termination_reason: str
    ranking_id: str | None = None
    ranking_sha256: str | None = None
    iterations: list[str] = Field(default_factory=list)
    candidate: int | None = Field(default=None, ge=1)
    candidate_id: str | None = None
    alternatives: list[Alternative] = Field(default_factory=list)
    confidence: Confidence | None = None
    caveats: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_candidate(self) -> FinalDeclaration:
        if self.outcome in OUTCOMES_NEEDING_CANDIDATE and self.candidate is None:
            raise ValueError(f"outcome {self.outcome!r} requires a candidate")
        if self.candidate is not None and not self.ranking_id:
            raise ValueError("a candidate requires ranking_id")
        return self


class ManifestStatus(BaseModel):
    model_config = ConfigDict(extra="allow")

    state: RunState
    inferred: bool = False
    label: str = ""
    reason: str | None = None
    heartbeat_utc: str | None = None
    started_utc: str | None = None
    last_event_utc: str | None = None
    ended_utc: str | None = None
    counts_as_clean: bool = False


class ManifestHarness(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = None
    hooks_recorded: bool = False
    hook_counts: dict[str, int] = Field(default_factory=dict)


class RunManifest(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    schema_: Literal["ailsa.run-manifest"] = _schema_field("ailsa.run-manifest")
    schema_version: Literal["1"] = "1"
    run_id: str
    writer_host: str | None = None
    foreign_host_events: int = 0
    dataset: dict[str, Any] = Field(default_factory=dict)
    class_: RunClass | None = Field(default=None, alias="class")
    request: dict[str, Any] = Field(default_factory=dict)
    environment: dict[str, Any] = Field(default_factory=dict)
    prior_runs: dict[str, Any] = Field(default_factory=dict)
    blind: bool = False
    not_blind_reason: str | None = None
    status: ManifestStatus
    harness: ManifestHarness = Field(default_factory=ManifestHarness)
    agents: dict[str, Any] = Field(default_factory=dict)
    experiments: dict[str, Any] = Field(default_factory=dict)
    views: dict[str, Any] = Field(default_factory=dict)
    picks: dict[str, Any] = Field(default_factory=dict)
    iterations: dict[str, Any] = Field(default_factory=dict)
    rankings: dict[str, Any] = Field(default_factory=dict)
    identity: list[Any] = Field(default_factory=list)
    final: dict[str, Any] = Field(default_factory=dict)
    notes: int = 0
    artefacts: dict[str, Any] = Field(default_factory=dict)
    integrity: dict[str, Any] = Field(default_factory=dict)
    spans: dict[str, Any] = Field(default_factory=dict)
    human_messages: int = 0
    assisted: bool | None = None
    warnings: list[str] = Field(default_factory=list)


ARTEFACT_MODELS: dict[str, type[BaseModel]] = {
    "event": Event,
    "manifest": RunManifest,
    "experiment_inventory": ExperimentInventory,
    "spectrum_view": SpectrumView,
    "peak_pick": PeakPick,
    "peak_decisions": PeakDecisionTable,
    "atom_model": AtomModel,
    "solver_run": SolverRun,
    "solution_analysis": SolutionAnalysis,
    "ranking": Ranking,
    "identity": IdentityVerdict,
    "final": FinalDeclaration,
}


def schema_text(model: type[BaseModel]) -> str:
    return json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"


def export_schemas(dest: Path) -> list[Path]:
    """Write ``run_<stem>.json`` for every record model into ``dest``."""
    dest.mkdir(parents=True, exist_ok=True)
    written = []
    for stem, model in ARTEFACT_MODELS.items():
        path = dest / f"run_{stem}.json"
        path.write_text(schema_text(model), encoding="utf-8")
        written.append(path)
    return written


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--write-schemas":
        for p in export_schemas(Path(sys.argv[2])):
            print(p)
    else:
        print("usage: python -m ailsa.record.models --write-schemas <dir>", file=sys.stderr)
        sys.exit(2)
