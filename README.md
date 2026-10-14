# AILSA

**AI + LSD + Agents — AI-agent computer-assisted structure elucidation for organic natural products**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

AILSA determines the structure of an unknown organic natural product from its NMR
spectra. At its core is **[LSD](https://nuzillard.github.io/LSD/) — Jean-Marc
Nuzillard's structure generator** — which enumerates every molecular graph consistent
with the spectroscopic constraints without leaning on a chemical-shift database (see
[Built on LSD](#built-on-lsd-and-established-tools) below). Driving it is a
**coordinator leading a team of specialist AI agents** that runs the full
Computer-Assisted Structure Elucidation (CASE) workflow autonomously — picking peaks,
extracting constraints, running LSD, ranking candidates, and critiquing its own work —
the way a group of human spectroscopists would, but unattended.

The agent team is AILSA's own contribution; LSD does the structure generation
underneath it. Everything the agents do is also available directly through the
`ailsa` command-line toolkit, a thin integration layer around LSD and the other
established packages it relies on (RDKit, nmrglue).

---

## Table of Contents

- [Built on LSD and Established Tools](#built-on-lsd-and-established-tools)
- [The CASE Agent Team](#the-case-agent-team)
- [Running a CASE Elucidation](#running-a-case-elucidation)
- [The `ailsa` CLI](#the-ailsa-cli)
- [Evaluation](#evaluation)
- [Installation](#installation)
- [Scientific Background](#scientific-background)
- [Architecture](#architecture)
- [Supported Data](#supported-data)
- [Development](#development)
- [License & Citation](#license--citation)

---

## Built on LSD and Established Tools

The hard combinatorial heart of structure elucidation — enumerating every molecular graph
consistent with the spectroscopic constraints — is done by **[LSD (Logic for Structure
Determination)](https://nuzillard.github.io/LSD/), created and maintained by Jean-Marc
Nuzillard** (Université de Reims Champagne-Ardenne, CNRS). LSD is the product of decades of
rigorous work, it builds structures purely from 2D-NMR connectivity without leaning on a
chemical-shift database, and it is the foundation without which AILSA simply would not
exist. **If you use AILSA in research, cite LSD** — see [Citation](#license--citation).

AILSA does not replace LSD or the other packages it relies on. It wraps and coordinates
them:

| Foundation | By | Its role in AILSA |
|------------|-----|---------------------|
| **LSD** | Jean-Marc Nuzillard | The structure generator — the core solver |
| **RDKit** | RDKit contributors | Cheminformatics: molecules, SMILES/InChI, substructure search |
| **nmrglue** | J. J. Helmus et al. | Reading Bruker NMR data |
| **HOSE codes** | W. Bremser (1978) | 13C shift-prediction descriptors |
| **COCONUT**, **NMRShiftDB** | their respective communities (COCONUT 13C shifts: ACD/Labs predictions from J.-M. Nuzillard) | Reference data for dereplication and prediction |

The `ailsa` command-line tools are the wrappers through which these packages are driven.
**What is genuinely new here — our own contribution — is the [CASE agent team](#the-case-agent-team)**
that operates all of them end to end, unattended.

---

## The CASE Agent Team

Structure elucidation is not a single algorithm — it is an iterative, judgement-heavy
process where evidence from several spectra has to be weighed, constraints have to be
built carefully, and wrong turns have to be caught before they waste a solver run. AILSA
is designed as a **team of specialists that coordinate with each other**, rather than as
one monolithic prompt or a coordinator that only ever talks to one specialist at a time.

When you start a run, the coordinator (`/ailsa:case`) starts four specialists:

| Agent | Role |
|-------|------|
| 🧪 **NMR Chemist** (`ailsa-nmr-chemist`) | Peak picking, multiplicity assignment, statistical detection (hybridisation, neighbours), spectral-quality assessment. Establishes the chemistry-first evidence hierarchy. |
| 🔧 **LSD Engineer** (`ailsa-lsd-engineer`) | Builds LSD constraint files, runs the solver, manages the constraint inventory across iterations, adds HMBC correlations incrementally, converts solutions to structures. |
| 📊 **Solution Analyst** (`ailsa-solution-analyst`) | Ranks candidate structures by 13C-shift prediction, derives and verifies identity, assesses chemical plausibility, and reports the final result. |
| 😈 **Devil's Advocate** (`ailsa-devils-advocate`) | Quality gate. Validates **every** LSD file before the solver runs, checks that constraints persist across iterations, and flags loss or over-constraint — the primary defence against silent failure modes. |

Two of those specialists talk to each other directly, without going through the
coordinator. The LSD Engineer and the Devil's Advocate run a **direct review loop** on
every LSD file: the LSD Engineer marks a new file "ready for validation", the Devil's
Advocate approves it or blocks it with an issue list, and the solver runs only after
approval. The LSD Engineer can also **ask the NMR chemist** directly for additional HMBC
correlations or detection results, without routing the request through the coordinator.

A fifth agent, the **Diagnostic specialist** (`ailsa-diagnostic`), is held in reserve and
called only when a run gets stuck (zero solutions or a solution explosion) and basic
intervention has failed.

The team needs Claude Code's agent-team feature (see [Installation](#installation)); the
benchmark figures quoted under [Evaluation](#evaluation) were measured in a restricted
configuration without it — see that section for what changes and why.

### How a run unfolds

```
                    ┌────────────────────────────────┐
                    │   Coordinator   /ailsa:case      │
                    │   tasks · advisories ·           │
                    │   writes CASE-PROGRESS.md        │
                    └─────┬───────┬───────┬───────┬────┘
                          │       │       │       │
                 ┌────────▼──┐ ┌──▼──────────┐ ┌──▼───────────┐ ┌───▼─────────────┐
                 │NMR Chemist│ │LSD Engineer │ │Devil's Advocate│ │Solution Analyst │
                 └───────────┘ └──────┬──────┘ └───────▲────────┘ └─────────────────┘
                                      │                │
                                      └──◄───────────►─┘   direct review loop
                                        every LSD file; solver runs only after approval

                 NMR Chemist ◄────────── requests ─────────── LSD Engineer
                           (additional HMBC correlations or detection results)
```

The coordinator monitors progress, detects unproductive loops, intervenes with
**advisory** constraints (telling the team *what* is wrong, not *how* to fix it, so the
specialists keep their autonomy), escalates to the Diagnostic specialist after repeated
intervention cycles fail, and is the sole writer of the progress log
(`CASE-PROGRESS.md`). It never does dereplication and never short-cuts the elucidation —
a CASE run always starts from the raw spectra.

The agents live in [`.claude/`](https://github.com/steinbeck/ailsa/tree/master/.claude)
(`agents/ailsa-*.md` and `commands/ailsa/`) and are loaded as Claude Code skills.

---

## Running a CASE Elucidation

The team runs inside [Claude Code](https://claude.com/claude-code). The fastest path on a
fresh machine is the CASE-host bootstrap, which provisions Python + dependencies, the LSD
solver, the reference database, **and** the CASE commands and team agents:

```bash
git clone https://github.com/steinbeck/ailsa.git
cd ailsa
./scripts/bootstrap_case_host.sh
```

See **[docs/SERVER_BOOTSTRAP.md](https://github.com/steinbeck/ailsa/blob/master/docs/SERVER_BOOTSTRAP.md)**
for a headless/compute-host walkthrough.

Then, from a directory holding your Bruker NMR data, start Claude Code and run:

```
/ailsa:case
```

The coordinator picks up the spectra in the current directory, asks for the molecular
formula if it cannot infer one, assembles the team, and runs to completion. Other
commands in the same family:

| Command | Purpose |
|---------|---------|
| `/ailsa:case` | Full autonomous CASE elucidation (the agent team) |
| `/ailsa:dereplicate` | Match a 13C spectrum against the reference database |
| `/ailsa:predict` | Predict 13C shifts for a candidate SMILES |
| `/ailsa:sanitise` | Strip identifiers from a dataset for blind evaluation |
| `/ailsa:status` | Check environment readiness (LSD, database, install) |

---

## The `ailsa` CLI

Everything the agents do is available directly through the `ailsa` command. These commands
are thin wrappers that orchestrate the [foundational packages above](#built-on-lsd-and-established-tools)
— LSD, RDKit, nmrglue and the rest — behind one consistent interface; the science lives in
those packages, not here. Every subcommand supports `--format json` for scripting. The
command groups:

| Group | What it does |
|-------|--------------|
| `ailsa read` | Read 1D / 2D Bruker spectra |
| `ailsa pick` | Raw peak picking (1D, 2D, HSQC, HMBC); DEPT- and HMBC-guided filtering is done by the agents |
| `ailsa analyze` | Symmetry detection and structural analysis |
| `ailsa detect` | Statistical detection (hybridisation, neighbours) |
| `ailsa dereplicate` | Match a spectrum against the reference database |
| `ailsa identify` | Derive a deterministic identity (SMILES → InChIKey + DB name) |
| `ailsa predict` | Predict 13C shifts from structure (HOSE codes) |
| `ailsa lsd` | Check the solver, run it, rank and analyse solutions |
| `ailsa pylsd` | Multi-run LSD orchestration for 4J-HMBC handling |
| `ailsa fragment` | Fragment-library build / search |
| `ailsa visualize` | NMR correlation diagrams |
| `ailsa fetch` | Fetch datasets from external repositories |
| `ailsa jcamp` | Read 2D spectra from JCAMP-DX files (binary-free ingestion path) |
| `ailsa nus` | Reconstruct non-uniformly-sampled 2D spectra (NMRPipe + SMILE) |
| `ailsa webview` | Local dashboard for watching a CASE run |
| `ailsa database` | Download and inspect the reference database |

A few representative invocations:

```bash
# Inspect a carbon spectrum
ailsa read 1d data/Ibuprofen/2

# Raw HSQC peak picking (the agent applies DEPT-guided filtering on top)
ailsa pick hsqc data/Ibuprofen/6

# Raw HMBC peak picking (the agent applies cross-validation filtering on top)
ailsa pick hmbc data/Ibuprofen/7

# Dereplicate against the reference database
ailsa dereplicate c13 data/Ibuprofen/2 C13H18O2

# The per-run LSD constraint file (compound.lsd) is built by the LSD-engineer
# agent from the picked peaks and detection results -- there is no CLI command
# that builds it from scratch.
ailsa lsd run ibuprofen.lsd
ailsa lsd rank solutions.smi --spectrum data/Ibuprofen/2 --top 10

# Predict 13C shifts for a candidate
ailsa predict c13 "CC(C)Cc1ccc(cc1)C(C)C(=O)O"
```

A Python API mirrors the CLI for custom workflows — see
[docs/USER_GUIDE.md](https://github.com/steinbeck/ailsa/blob/master/docs/USER_GUIDE.md).

---

## Evaluation

AILSA is measured **blind**: the coordinator gets a directory of Bruker spectra and a
molecular formula, never the compound's name or structure, and dereplication is
forbidden. Grading is done afterwards by an independent script that re-derives every
candidate's InChIKey with RDKit — a run's own claim about its result is never used.

On all **256 runnable datasets from [nmrXiv](https://nmrxiv.org)** (8–39 heavy atoms,
median 24), every one run on the current model:

| | |
|---|---|
| Correct structure ranked **first** | **177 / 256 — 69.1 %** |
| Correct structure **within the top 10** | **189 / 256 — 73.8 %** |

Runs that hit the time limit of about three hours without a report (25) count as failures here; of the
231 runs that did report, 76.6 % have the correct structure first and 81.8 % in the top
10. Molecules up to 15 heavy atoms were all solved; above 25 heavy atoms it is about half.

These figures were measured in a restricted configuration: without the agent team,
because Claude Code forms no team in unattended `claude -p` runs and the specialists
therefore ran one at a time under the coordinator, and without statistical detection,
because the reference database on the compute host had an outdated schema. Prediction,
ranking and identity derivation worked normally. What the full configuration — with the
team and with statistical detection — achieves is a separate, not-yet-answered question.
See
[docs/BENCHMARK.md#how-a-benchmark-run-executes](https://github.com/steinbeck/ailsa/blob/master/docs/BENCHMARK.md#how-a-benchmark-run-executes)
for the detail.

The top-10 figure is the one that matters in practice: ten candidates is the shortlist
size a DP4/GIAO shift calculation is run on, so a result in that band is one a
spectroscopist can finish. Matching is on constitution only — **stereochemistry is not
tested**.

102 datasets have been run on two model generations. With each dataset as its own
control, the current system solves 67 at rank 1 against 40, winning 30 and losing 3
(exact McNemar, p = 1.4 · 10⁻⁶).

**[docs/BENCHMARK.md](https://github.com/steinbeck/ailsa/blob/master/docs/BENCHMARK.md)**
has the full picture: how blindness is enforced, what the audits found, results by size
and by arm, what the numbers do *not* say, a measurement error that had flattered this
comparison and how correcting it shrank the claimed gap, and the complete table of all
258 datasets with their metadata and per-model result.

---

## Installation

To install AILSA, simply ask your AI to look at this repo and do the installation for you.
Alternatively, you can follow the instructions below.

### CLI only

```bash
pip install ailsa
```

To install the development head instead of the latest release:

```bash
pip install "ailsa @ git+https://github.com/steinbeck/ailsa.git"
```

> **macOS / zsh:** the quotes are required because zsh expands square brackets.

### Development

```bash
git clone https://github.com/steinbeck/ailsa.git
cd ailsa
pip install -e ".[dev]"
```

### 13C prediction support

13C prediction needs the `hose-code-generator` package, which has a broken test
dependency on modern Python. Install it without that dependency:

```bash
pip install git+https://github.com/Ratsemaat/HOSE_code_generator.git --no-deps
pip install rdkit
```

### LSD solver

The [LSD solver](https://nuzillard.github.io/LSD/) by Jean-Marc Nuzillard does the actual
structure generation. Download it, extract it, and add its `bin/` directory to `PATH`.
Verify with:

```bash
ailsa lsd check     # must report both LSD and outlsd on PATH
```

### Reference database

Dereplication, 13C prediction, and CASE ranking all share one pre-built SQLite database:
**928,443 compounds** (COCONUT + NMRShiftDB) and **7.9 M HOSE-code statistics**
(~830 MB download → ~2.8 GB uncompressed).

The 13C shifts of the 895,099 COCONUT natural products are predicted, not measured (ACD/Labs C+H NMR Predictors and DB 2020.1.0); the 33,344 NMRShiftDB compounds carry experimental 13C shifts. COCONUT 13C shifts: ACD/Labs predictions from J.-M. Nuzillard, Zenodo, doi:[10.5281/zenodo.6561449](https://doi.org/10.5281/zenodo.6561449), CC BY 4.0.

```bash
ailsa database download
ailsa database info
```

Both commands auto-resolve the database; the default location is
`data/reference/ailsa-derep.db`. DOI:
[10.6084/m9.figshare.31073554](https://doi.org/10.6084/m9.figshare.31073554). See
[docs/INSTALLATION.md](https://github.com/steinbeck/ailsa/blob/master/docs/INSTALLATION.md#reference-database)
for detail.

### NMRPipe + SMILE (NUS reconstruction)

Automatic reconstruction of non-uniformly-sampled (NUS) 2D spectra (`ailsa nus reconstruct`
/ `pipeline`) uses NMRPipe with the SMILE plugin as its backend. Install NMRPipe (native
`mac11_arm64`/Linux build) **and** the separate SMILE companion plugin
(`plugin.smile.tZ`) from https://www.ibbr.umd.edu/nmrpipe/install, source its environment
script, and add its `bin/` directory to `PATH`. Verify with:

```bash
ailsa nus check     # must report the backend "available"
```

See [docs/NUS-PORTABILITY.md](https://github.com/steinbeck/ailsa/blob/master/docs/NUS-PORTABILITY.md)
for the full per-platform matrix (macOS Apple Silicon native / Linux native / Windows
WSL2 gap).

---

## Scientific Background

CASE follows a systematic pipeline:

```
NMR Spectra → Peak Picking → Constraint Extraction → Solver → Candidate Structures → Ranking
```

Two design choices matter most for getting correct answers:

### Guided peak picking

Raw 2D peak picking produces many noise peaks and artefacts. The NMR-chemist agent uses
DEPT-135 as ground truth (it definitively shows all protonated carbons), lowers the HSQC
threshold until every DEPT carbon is matched, and filters HMBC peaks to require a
matching carbon (from 13C) **and** proton (from HSQC). This removes the false
correlations that would otherwise generate thousands of incorrect structures.

| Constraint source | Typical LSD solutions |
|-------------------|-----------------------|
| Manual HMBC (~16 correlations) | 900+ structures |
| Guided HMBC (28–30 correlations) | 1–10 structures |

### Molecular symmetry

Equivalent carbons appear as single signals, so the observed carbon count is often below
the formula count (e.g. a para-disubstituted benzene shows two pairs of equivalent
carbons). AILSA detects this by comparing the formula's hydrogen budget with the
observed C–H count and by analysing relative peak intensities, then encodes it as solver
constraints rather than guessing.

---

## Architecture

```
ailsa/
├── src/ailsa/
│   ├── models/          # Pydantic v2 data models (Spectrum1D/2D, Peak1D, …)
│   ├── readers/         # NMR file readers (BrukerReader)
│   ├── processing/      # peak picking, signal processing
│   ├── detection/       # statistical detection (hybridisation, neighbours)
│   ├── analysis/        # symmetry / signal-grouping analysis
│   ├── dereplication/   # formula-indexed compound DB matching
│   ├── prediction/      # HOSE-code 13C shift prediction
│   ├── ranking/         # candidate solution ranking
│   ├── lsd/             # LSD solver integration + bundled fragment filters
│   ├── fragments/       # fragment-library build / search / LSD injection
│   ├── solvers/         # solver back-ends behind one interface
│   ├── nus/             # non-uniform-sampling reconstruction + QC gate
│   ├── nmrxiv/          # nmrXiv dataset fetching
│   ├── database/        # reference-database access
│   ├── data/            # bundled schemas (constraint-inventory JSON, …)
│   ├── webview/         # local run dashboard
│   ├── visualization/   # NMR correlation diagrams
│   ├── identity.py      # deterministic identity derivation (ailsa identify)
│   └── cli/             # the `ailsa` Click CLI
├── .claude/             # CASE orchestrator command + team agents (skills)
├── tests/               # pytest suite
├── data/                # local test NMR datasets (Bruker format)
└── docs/                # documentation
```

### Design principles

1. **Structured results** — every operation returns a result object with a success flag
   and detailed data, rather than raising on the common error paths.
2. **Pydantic models** — all data structures use Pydantic v2 for validation and
   serialisation.
3. **HOSE codes use molecules without explicit hydrogens** — a hard invariant shared
   between database generation and prediction; mixing the two causes prediction
   mismatches (see [CLAUDE.md](https://github.com/steinbeck/ailsa/blob/master/CLAUDE.md)).

Developer notes (commands, invariants) are in
[CLAUDE.md](https://github.com/steinbeck/ailsa/blob/master/CLAUDE.md); the CASE workflow
itself is defined in `.claude/commands/ailsa/case.md` and `.claude/agents/ailsa-*.md`.

---

## Supported Data

**Input:** Bruker TopSpin 1D and 2D spectra (processed data from `pdata/1/`); 2D spectra
from **JCAMP-DX** files via `ailsa jcamp`, which needs no vendor binaries; **non-uniformly
sampled** 2D data, reconstructed by `ailsa nus` through NMRPipe + SMILE; SD files for
reference databases.

| Experiment | Detection | Notes |
|------------|-----------|-------|
| 1H | Nucleus | Proton spectrum |
| 13C | Nucleus | Carbon spectrum |
| DEPT-135 | Pulse program | CH/CH3 up, CH2 down |
| DEPT-90 | Pulse program | CH only |
| COSY | Pulse program | H–H correlations |
| HSQC | Pulse program (inv4) | Direct C–H |
| HMBC | Pulse program (inv4·lr) | Long-range C–H |

---

## Development

```bash
pytest                    # run tests
pytest --cov=ailsa         # with coverage
mypy src/ailsa             # type checking (strict)
ruff check src tests      # linting
hatch build               # build the package
```

---

## License & Citation

MIT License — see [LICENSE](https://github.com/steinbeck/ailsa/blob/master/LICENSE).

### Cite LSD first

AILSA is worthless without the LSD structure generator. **Any work using AILSA must
cite LSD.** See the [LSD website](https://nuzillard.github.io/LSD/) for the author's
current preferred citation; a key reference is:

> B. Plainchont, V. P. Emerenciano, J.-M. Nuzillard. *Recent advances in the structure
> elucidation of small organic molecules by the LSD software.* Magn. Reson. Chem. **2013**,
> 51, 447–453. See also J.-M. Nuzillard, *Tutorial for the structure elucidation of small
> molecules by means of the LSD software*, Magn. Reson. Chem. **2018**
> ([doi:10.1002/mrc.4612](https://doi.org/10.1002/mrc.4612)).

**Acknowledgments:** LSD by Jean-Marc Nuzillard (Université de Reims Champagne-Ardenne) ·
RDKit · nmrglue for NMR file parsing · HOSE codes (W. Bremser, *Anal. Chim. Acta* **1978**,
103, 355–365) · COCONUT and NMRShiftDB for reference data (COCONUT 13C shifts: ACD/Labs predictions from J.-M. Nuzillard, Zenodo, doi:[10.5281/zenodo.6561449](https://doi.org/10.5281/zenodo.6561449), CC BY 4.0).

If you use AILSA itself, please also cite it (alongside LSD):

```bibtex
@software{ailsa,
  author = {Steinbeck, Christoph},
  title  = {AILSA: AI + LSD + Agents — AI-agent computer-assisted structure elucidation from NMR},
  url    = {https://github.com/steinbeck/ailsa},
  year   = {2026}
}
```
