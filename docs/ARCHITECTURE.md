# Architecture

This document describes the technical architecture and design decisions behind AILSA.

## Table of Contents

- [Overview](#overview)
- [Module Structure](#module-structure)
- [Data Flow](#data-flow)
- [The CASE agent layer](#the-case-agent-layer)
- [Design Decisions](#design-decisions)
- [Key Classes](#key-classes)
- [Extension Points](#extension-points)

## Overview

AILSA is a layered Python library with two interfaces — the `ailsa` CLI (Click; every
subcommand supports `--format json`) and the Python API — and a CASE agent layer (a Claude
Code skill) that drives the CLI.

```
┌─────────────────────────────────────────────────────────────┐
│                      CASE agent layer                       │
│         (Claude Code skill: coordinator + specialist team)  │
├─────────────────────────────────┬───────────────────────────┤
│           CLI (click)           │        Python API         │
├───────────────────────────────────────────────────────────── ┤
│                      Core Library                           │
├──────────┬──────────┬───────────┬───────────┬──────────────┤
│ Readers  │Processing│ Analysis  │Dereplicat.│     LSD      │
├──────────┴──────────┴───────────┴───────────┴──────────────┤
│                      Data Models (Pydantic)                 │
└─────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Separation of Concerns**: Each module has a single responsibility
2. **Static Methods for Convenience**: Core operations are static for easy use
3. **Immutable Data Models**: All models are Pydantic dataclasses
4. **Explicit Error Handling**: Operations return result objects, not exceptions
5. **Agent-first output**: every CLI command can emit structured JSON for the agents

## Module Structure

```
src/ailsa/
├── __init__.py           # Public API exports
├── models/               # Pydantic data models
│   ├── spectrum.py       # Spectrum1D, Spectrum2D
│   ├── peaks.py          # Peak1D, Peak2D, PeakList1D, PeakList2D
│   └── nus.py            # NUS acquisition/schedule models
├── readers/              # NMR file readers
│   ├── bruker.py          # BrukerReader
│   ├── jcamp.py           # JCAMP-DX reader (1D + 2D NTUPLES)
│   └── _jcampdx_decode.py # vendored JCAMP-DX line decoder
├── processing/           # Signal processing and peak picking
│   ├── peak_picker.py        # AdaptivePeakPicker
│   ├── peak_picker_2d.py     # PeakPicker2D
│   ├── peak_validator.py     # PeakValidator
│   ├── dept_guided_picker.py # DEPTGuidedPicker
│   ├── hmbc_guided_picker.py # HMBCGuidedPicker
│   ├── edited_sign.py        # HSQC multiplicity-edited sign handling
│   └── jcamp_1d_bridge.py    # 1D peak-pick bridge for JCAMP-sourced spectra
├── analysis/             # Spectroscopic analysis
│   ├── hydrogen_budget.py    # HydrogenBudgetAnalyzer
│   ├── intensity_reporter.py # IntensityReporter
│   └── symmetry_analysis.py  # SymmetryAnalyzer
├── detection/            # Statistical detection (hybridisation, neighbours, HHB, grouping)
│   ├── detector.py
│   ├── grouping.py
│   └── models.py
├── dereplication/        # Formula-indexed compound database matching
│   ├── coconut.py        # CoconutLoader (streaming)
│   ├── nmrshiftdb.py     # NMRShiftDBLoader
│   ├── sherlock.py       # SherlockLoader / SherlockEntry
│   ├── matcher.py        # SpectrumMatcher
│   └── service.py        # DereplicationService
├── prediction/           # HOSE-code 13C shift prediction
│   ├── hose.py / hose_parser.py    # HOSE code generation/parsing
│   ├── predictor.py, resolver.py, lookup.py, db_lookup.py
│   ├── bond_pair_generator.py      # bond-pair statistics for detection
│   └── stats_generator.py          # HOSE statistics table generation
├── fragments/            # Bundled LSD fragment / ring-exclusion filter library
│   └── db.py, extractor.py, fingerprint.py, lsd_formatter.py, models.py, schema.py, searcher.py
├── ranking/              # Candidate solution ranking
│   ├── models.py
│   └── ranker.py
├── lsd/                  # LSD solver integration
│   ├── models.py          # LSDProblem, LSDAtom, etc.
│   ├── generator.py       # LSDInputGenerator
│   ├── runner.py          # LSDRunner, LSDResult
│   ├── parser.py          # LSDOutputParser
│   ├── analyzer.py        # J-coupling path analysis
│   ├── orchestrator.py    # multi-run (pyLSD) orchestration
│   └── filters/           # badlist/ring-exclusion filter files
├── nus/                  # Non-uniform-sampling 2D reconstruction pipeline
│   ├── params.py, schedule.py, platform_check.py, runner.py, bridge.py, postprocess.py, qc.py
│   └── backends/
├── nmrxiv/               # nmrXiv dataset fetching
│   ├── client.py
│   └── models.py
├── database/             # SQLite reference-database layer
│   └── finder.py, importer.py, manager.py, models.py, query.py, schema.py
├── identity.py           # Structure → identity derivation (`ailsa identify`)
├── visualization/        # NMR correlation diagram rendering
│   └── arrow_router.py, diagram_generator.py, layout_optimizer.py, models.py, svg_builder.py
├── webview/              # Read-only FastAPI run dashboard (optional [webview] extra)
│   ├── app.py, depiction.py, server.py, state.py
│   ├── routers/
│   └── static/
├── solvers/              # reserved for future solver integrations
├── data/                 # packaged schemas/fixtures
│   └── schemas/
└── cli/                  # `ailsa` Click CLI (every subcommand supports --format json)
    ├── main.py, __main__.py
    ├── read.py, pick.py, analyze.py, detect.py, dereplicate.py
    ├── predict.py, lsd.py, pylsd.py, fragment.py, identify.py
    ├── jcamp.py, nus.py, fetch.py, visualize.py, webview.py
    └── database.py
```

## Data Flow

### Reading → Peak Picking → Analysis

```
Bruker Files          BrukerReader         Processing          Analysis
    │                      │                   │                   │
    ▼                      ▼                   ▼                   ▼
┌────────┐  read_1d   ┌──────────┐  pick   ┌──────────┐  analyze ┌────────┐
│ pdata/ │ ─────────▶ │Spectrum1D│ ──────▶ │PeakList1D│ ───────▶ │Results │
└────────┘            └──────────┘         └──────────┘          └────────┘
    │                      │                   │
    │                      │                   │
    ▼                      ▼                   ▼
┌────────┐  read_2d   ┌──────────┐  pick   ┌──────────┐
│ pdata/ │ ─────────▶ │Spectrum2D│ ──────▶ │PeakList2D│
└────────┘            └──────────┘         └──────────┘
```

### Structure Elucidation Pipeline

```
HSQC + DEPT-135                    HMBC + 13C + HSQC
      │                                   │
      ▼                                   ▼
┌─────────────────┐              ┌─────────────────┐
│DEPTGuidedPicker │              │HMBCGuidedPicker │
└────────┬────────┘              └────────┬────────┘
         │                                │
         ▼                                ▼
    DEPTGuidedResult                HMBCGuidedResult
         │                                │
         └──────────┬─────────────────────┘
                    │
                    ▼
           ┌─────────────────┐
           │LSDInputGenerator│
           └────────┬────────┘
                    │
                    ▼
              ┌──────────┐
              │LSDProblem│
              └────┬─────┘
                   │
                   ▼
             ┌──────────┐
             │LSDRunner │
             └────┬─────┘
                  │
                  ▼
             ┌──────────┐
             │LSDResult │
             └──────────┘
```

In a CASE run the LSD-engineer agent writes the LSD file itself, iteration by iteration; the
CLI has no command that generates one from spectra (D-14) — `LSDInputGenerator` is a Python-API
building block the agent's own reasoning drives, not a `lsd generate` subcommand.

## The CASE agent layer

AILSA's CLI is a thin data-access layer; the intelligence that turns peak lists into a
structure lives one level up, in a Claude Code skill. That skill is **a designed agent team**:
specialists that coordinate with each other, not a single autonomous agent working alone.

- A **coordinator** (`/ailsa:case`) creates a task per elucidation stage and starts the
  specialist for it, monitors progress, detects unproductive loops, and sends advisories when
  one is found. It is the sole writer of `CASE-PROGRESS.md`, and escalates to `ailsa-diagnostic`
  when a specialist cannot make progress on its own.
- Four specialists do the elucidation work: `ailsa-nmr-chemist`, `ailsa-lsd-engineer`,
  `ailsa-solution-analyst` and `ailsa-devils-advocate`. `ailsa-diagnostic` joins only on
  escalation, for deep LSD-failure analysis.
- **The direct review loop:** the LSD engineer sends every new LSD file it writes directly to the
  devil's advocate, who approves it or blocks it with an issue list; the solver runs only after
  approval. This loop does not go through the coordinator.
- **Requests to the NMR chemist:** the LSD engineer can directly ask the NMR chemist for
  additional HMBC correlations or detection results mid-iteration, rather than waiting for the
  coordinator to relay the request.
- The NMR chemist's statistical detection (`ailsa detect …`: hybridisation, neighbours, HHB,
  grouping) draws on statistics tables in the reference database; it is one more source of
  evidence the chemist combines with direct spectral read-outs.
- Forming the team needs Claude Code's agent-team feature
  (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`); interactive sessions form it.

The published benchmark ran in a **restricted configuration**: without the agent team, because
unattended (`claude -p`) runs form none, and without statistical detection, because the compute
host's reference database lacked the current statistics tables. See
[How a benchmark run executes](BENCHMARK.md#how-a-benchmark-run-executes) for exactly what that
configuration measured.

## Design Decisions

### 1. Static Methods for Core Operations

**Decision**: Use static methods for primary operations like peak picking.

**Rationale**:
- Simpler API for users
- No need to instantiate objects for common tasks
- Consistent with library patterns (like `json.loads()`)

**Implementation**:
```python
class AdaptivePeakPicker:
    @staticmethod
    def pick_peaks(spectrum, threshold=0.05) -> PeakList1D:
        # Creates internal instance with defaults
        if AdaptivePeakPicker._default_instance is None:
            AdaptivePeakPicker._default_instance = AdaptivePeakPicker()
        return AdaptivePeakPicker._default_instance.pick_peaks_instance(...)
```

### 2. Pydantic v2 for Data Models

**Decision**: Use Pydantic dataclasses for all data structures.

**Rationale**:
- Automatic validation
- JSON serialization built-in
- Type hints enforced at runtime
- IDE support for autocomplete

**Example**:
```python
from pydantic import BaseModel

class Peak1D(BaseModel):
    position: float
    intensity: float
    assignment: str | None = None
```

### 3. Structured JSON Instead of Exceptions

**Decision**: Every CLI command returns a structured result; with `--format json`, agents get
that result as parseable JSON instead of formatted text.

**Rationale**:
- AI agents can handle structured errors
- No try/catch needed for expected failures
- Consistent interface across all operations

**Example** — `ailsa detect hhb C10H14O2 --format json`:
```python
{
    "formula": "C10H14O2",
    "threshold": 0.01,
    "allowed_pairs": [],
    "forbidden_pairs": [],
    "total_compounds": 325,
    "has_data": true,
    "has_heteroatoms": true,
    "warning": null
}
```

### 4. Guided Peak Picking Strategy

**Decision**: Use 1D spectra as ground truth to filter 2D peaks.

**Rationale**:
- Raw 2D peak picking produces many noise peaks
- DEPT-135 definitively shows all protonated carbons
- Cross-validation removes artifacts
- Improves LSD constraint quality dramatically

**Implementation**:
```python
class DEPTGuidedPicker:
    @staticmethod
    def pick_hsqc_peaks(hsqc, dept135):
        # 1. Pick DEPT peaks (ground truth)
        dept_peaks = AdaptivePeakPicker.pick_peaks(dept135)

        # 2. Iteratively lower HSQC threshold
        for threshold in [0.05, 0.025, 0.0125, ...]:
            hsqc_peaks = PeakPicker2D.pick_peaks(hsqc, threshold)

            # 3. Validate HSQC against DEPT
            if all_dept_carbons_matched(hsqc_peaks, dept_peaks):
                break

        # 4. Return filtered peaks
        return DEPTGuidedResult(peaks=validated_hsqc, ...)
```

The CLI itself only picks raw peaks — `ailsa pick hmbc --help` states it plainly: "Returns raw
cross-peaks without cross-validation filtering. The AI agent applies HMBC filtering logic using
skill knowledge." The guided classes above are Python-API building blocks; the CASE agent layer
is what actually invokes the cross-validation judgement during a run.

### 5. Streaming for Large Databases

**Decision**: Use streaming mode for COCONUT database.

**Rationale**:
- COCONUT is ~4.8 GB with ~895K entries
- Loading into memory is impractical
- Formula filtering allows streaming

**Implementation**:
```python
class CoconutLoader:
    def get_by_formula(self, formula: str):
        # Stream through file, only parse matching entries
        for entry in self._stream_by_formula(formula):
            yield entry

    def _stream_by_formula(self, formula):
        with open(self.path) as f:
            while block := self._read_next_block(f):
                if formula in block:
                    yield self._parse_block(block)
```

**Data provenance.** The pre-built reference database (`ailsa database download`) holds 928,443 compounds. The 13C shifts of the 895,099 COCONUT natural products are predicted, not measured; the 33,344 NMRShiftDB compounds carry experimental 13C shifts. COCONUT 13C shifts: from J.-M. Nuzillard, Zenodo, doi:[10.5281/zenodo.6561449](https://doi.org/10.5281/zenodo.6561449), CC BY 4.0.

### 6. Thin CLI, judgement in the agents

**Decision**: The CLI returns raw data and structured results; filtering, constraint choice and
plausibility judgement live in the agent skill, not in the Python package.

**Rationale**:
- A thin CLI is testable and scriptable in isolation
- Domain judgement (which correlation to trust, which constraint to add, when a solution is
  plausible) changes faster than the data-access code and belongs where it can be revised
  without touching the package
- Keeps the package dependency-light; the agent skill carries the strategy

**Example**: `ailsa pick hmbc` returns every raw cross-peak above the SNR floor; it does not
decide which are genuine 3J correlations versus artifacts — that filtering is the NMR chemist
agent's job, using the skill's HMBC-validation knowledge against HSQC/13C evidence. Likewise
`ailsa lsd run` solves whatever LSD file it is given; deciding what goes into that file — which
constraints are hard, which fragment to inject, when to escalate — is the LSD engineer's and
devil's advocate's judgement, not a CLI flag.

## Key Classes

### Data Models

| Class | Description |
|-------|-------------|
| `Spectrum1D` | 1D NMR spectrum with data, ppm scale, metadata |
| `Spectrum2D` | 2D NMR spectrum with F1/F2 axes |
| `Peak1D` | Single 1D peak (position, intensity) |
| `Peak2D` | Single 2D peak (f1_position, f2_position, intensity) |
| `PeakList1D` | Collection of 1D peaks with nucleus |
| `PeakList2D` | Collection of 2D peaks |

### Readers

| Class | Description |
|-------|-------------|
| `BrukerReader` | Read Bruker-format NMR data (1D and 2D) |

### Processing

| Class | Description |
|-------|-------------|
| `AdaptivePeakPicker` | FWHM-adaptive 1D peak picker |
| `PeakPicker2D` | Connected-region 2D peak picker |
| `DEPTGuidedPicker` | DEPT-guided HSQC peak picking |
| `HMBCGuidedPicker` | Reference-guided HMBC picking |
| `PeakValidator` | Cross-validate 2D vs 1D peaks |

### Analysis

| Class | Description |
|-------|-------------|
| `HydrogenBudgetAnalyzer` | Compare MF H count with observed |
| `IntensityReporter` | Report relative peak intensities |
| `SymmetryAnalyzer` | Detect molecular symmetry |

### Dereplication

| Class | Description |
|-------|-------------|
| `CoconutLoader` | Stream COCONUT SD file |
| `NMRShiftDBLoader` | Load NMRShiftDB SD file |
| `SpectrumMatcher` | Match observed vs reference |
| `DereplicationService` | High-level dereplication API |

### LSD Integration

| Class | Description |
|-------|-------------|
| `LSDProblem` | Complete LSD problem definition |
| `LSDAtom` | Atom definition for LSD |
| `LSDInputGenerator` | Generate LSD input files |
| `LSDRunner` | Execute LSD as subprocess |
| `LSDResult` | LSD execution results |

## Extension Points

### Adding New Readers

1. Create new class in `readers/`
2. Implement `read_1d()` and/or `read_2d()` methods
3. Return `Spectrum1D` or `Spectrum2D`
4. Export from `readers/__init__.py`

```python
# readers/varian.py
class VarianReader:
    @staticmethod
    def read_1d(path: str) -> Spectrum1D:
        # Implementation
        return Spectrum1D(...)
```

### Adding New Databases

1. Create loader class in `dereplication/`
2. Implement `get_by_formula()` method
3. Return entry objects (e.g. `NMRShiftDBEntry`)
4. Use with `DereplicationService`

```python
# dereplication/custom_db.py
class CustomDBLoader:
    def get_by_formula(self, formula: str) -> Generator[NMRShiftDBEntry]:
        # Implementation
        yield NMRShiftDBEntry(...)
```

### Adding CLI Commands

1. Create command in appropriate `cli/*.py` module
2. Use Click decorators
3. Support `--format json` output
4. Register in `src/ailsa/cli/`

```python
# cli/my_command.py
@click.command()
@click.argument("path")
@click.option("--format", type=click.Choice(["text", "json"]))
def my_command(path, format):
    """Description."""
    result = process(path)
    if format == "json":
        click.echo(json.dumps(result))
    else:
        click.echo(format_text(result))
```
