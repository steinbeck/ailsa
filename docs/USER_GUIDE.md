# User Guide

This guide documents AILSA's two interfaces: the `ailsa` command line and the Python API. The
CASE agents (a Claude Code skill, see the README) drive the same CLI.

## Table of Contents

- [Overview](#overview)
- [Command-Line Interface](#command-line-interface)
- [Python API](#python-api)
- [Workflow Examples](#workflow-examples)
- [Best Practices](#best-practices)

## Overview

AILSA provides two interfaces:

1. **CLI** (`ailsa` command): Best for quick analysis and scripting
2. **Python API** (`import ailsa`): Best for custom workflows and integration

Both interfaces share the same underlying functionality.

## Command-Line Interface

### Global Options

```bash
ailsa [OPTIONS] COMMAND [ARGS]...

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.
```

### Command Groups

| Group | Description |
|-------|-------------|
| `ailsa read` | Read NMR spectra. |
| `ailsa pick` | Peak picking from spectra. |
| `ailsa analyze` | Analysis tools for structure elucidation. |
| `ailsa dereplicate` | Dereplication against reference databases. |
| `ailsa identify` | Derive a deterministic structural identity and gate a reported name. |
| `ailsa predict` | Predict NMR chemical shifts from structure. |
| `ailsa detect` | Statistical detection of structural constraints from shifts. |
| `ailsa lsd` | LSD structure elucidation. |
| `ailsa visualize` | Visualization tools for NMR correlation diagrams. |
| `ailsa fetch` | Fetch NMR data from external repositories. |
| `ailsa database` | Database management commands. |
| `ailsa fragment` | Fragment library management and search. |
| `ailsa webview` | Webview dashboard server commands. |
| `ailsa nus` | NUS (Non-Uniform Sampling) 2D reconstruction commands. |
| `ailsa jcamp` | Ingest JCAMP-DX spectra: read -> pick -> QC -> write in one invocation. |
| `ailsa pylsd` | PyLSD multi-run orchestration for 4J HMBC handling. |

---

### Fetching Data from External Sources

#### Fetch from NMRXiv

Download NMR datasets from NMRXiv repository.

```bash
ailsa fetch nmrxiv IDENTIFIER [OPTIONS]

Arguments:
  IDENTIFIER  NMRXiv DOI, project ID, or URL

Options:
  -o, --output PATH      Output directory (default: current)
  --study TEXT           Download specific study only
  --all                  Download all studies (even if DOI specifies one)
  --format [text|json]   Output format
  --quiet                Suppress progress output
```

**Identifier formats:**
- DOI: `10.57992/NMRXIV.P10.S69` or `10.57992/NMRXIV.P10`
- Project ID: `P10`
- URL: `https://nmrxiv.org/P10`

**Examples:**
```bash
# Download by DOI (specific study)
ailsa fetch nmrxiv 10.57992/NMRXIV.P10.S69 --output ./data/

# Download entire project
ailsa fetch nmrxiv P10 --output ./data/

# Download specific study from project
ailsa fetch nmrxiv P10 --study S69 --output ./data/

# JSON output for scripting
ailsa fetch nmrxiv P10 --format json
```

**Output structure:**
```
output_dir/
└── P10/
    └── S69/
        ├── 1H/
        │   ├── acqus
        │   ├── fid
        │   └── ...
        ├── 13C/
        └── HSQC/
```

Downloaded data preserves Bruker folder structure and can be directly used with `ailsa read` commands.

---

### Reading Spectra

#### Read 1D Spectrum

```bash
ailsa read 1d PATH [OPTIONS]

Arguments:
  PATH  Path to Bruker 1D experiment directory

Options:
  --format [text|json]  Output format (default: text)
```

**Examples:**
```bash
# Basic usage
ailsa read 1d data/Ibuprofen/2

# JSON output for scripting
ailsa read 1d data/Ibuprofen/2 --format json
```

**Output:**
```
Spectrum: 13C
Frequency: 125.76 MHz
Solvent: CDCl3
Points: 32768
PPM range: -10.00 to 230.00
```

#### Read 2D Spectrum

```bash
ailsa read 2d PATH [OPTIONS]

Arguments:
  PATH  Path to Bruker 2D experiment directory

Options:
  --format [text|json]  Output format (default: text)
```

**Examples:**
```bash
ailsa read 2d data/Ibuprofen/6
ailsa read 2d data/Ibuprofen/7 --format json
```

---

### Peak Picking

#### Pick 1D Peaks

```bash
ailsa pick 1d PATH [OPTIONS]

Arguments:
  PATH  Path to Bruker 1D experiment directory

Options:
  -t, --threshold FLOAT  Peak threshold (auto if not set)
  -s, --snr-floor FLOAT  SNR floor multiplier k (default: 5.0 signal/noise; use 3.0 for exploratory re-pick)
  --format [text|json]   Output format
```

Automatically detects negative peaks in spectra that contain them (e.g. DEPT-135, where CH2
peaks are negative).

**Example:**
```bash
ailsa pick 1d data/Ibuprofen/2 --threshold 0.03
```

#### Pick 2D Peaks

```bash
ailsa pick 2d PATH [OPTIONS]

Arguments:
  PATH  Path to Bruker 2D experiment directory

Options:
  -t, --threshold FLOAT  Peak threshold (default: 0.05)
  --format [text|json]   Output format
```

#### HSQC Picking

```bash
ailsa pick hsqc PATH [OPTIONS]

Arguments:
  PATH  Path to HSQC experiment

Options:
  -t, --threshold FLOAT  Peak threshold (default: 0.05)
  --format [text|json]   Output format
```

Returns raw cross-peaks above threshold, without DEPT-guided filtering. In a CASE run, the
NMR-chemist agent applies DEPT-guided filtering using skill knowledge on top of this raw pick.
From Python, the same filtering is available directly as `DEPTGuidedPicker` (see
[Python API](#python-api)).

**Example:**
```bash
ailsa pick hsqc data/Ibuprofen/6 --threshold 0.05
```

**Output:**
```
HSQC Peaks (threshold 0.05)
----------------------------
Peaks found: 10

Peaks:
  45.12 ppm (C) / 1.84 ppm (H)
  ...
```

#### HMBC Picking

```bash
ailsa pick hmbc PATH [OPTIONS]

Arguments:
  PATH  Path to HMBC experiment

Options:
  -t, --threshold FLOAT   Fraction-of-max peak threshold (legacy mode; SNR mode if not set)
  -s, --snr-floor FLOAT   SNR floor multiplier k (default: 5.0)
  --format [text|json]    Output format
```

Returns raw cross-peaks, without cross-validation filtering. In a CASE run, the NMR-chemist
agent applies HMBC filtering using skill knowledge on top of this raw pick. From Python, the
same filtering is available directly as `HMBCGuidedPicker` (see [Python API](#python-api)).

**Example:**
```bash
ailsa pick hmbc data/Ibuprofen/7
```

---

### Analysis

#### Symmetry Analysis

```bash
ailsa analyze symmetry FORMULA C13_PATH [OPTIONS]

Arguments:
  FORMULA   Molecular formula (e.g., C13H18O2)
  C13_PATH  Path to the 13C Bruker experiment

Options:
  -t, --threshold FLOAT  Peak threshold (auto if not set)
  --format [text|json]   Output format
```

Compares observed 13C peaks with the expected carbon count from the formula. Returns the raw
comparison; the AI agent interprets the difference using symmetry-detection knowledge.

**Example:**
```bash
ailsa analyze symmetry C13H18O2 data/Ibuprofen/2
```

**Output:**
```
Symmetry Analysis for C13H18O2
==============================
Expected carbons: 13
Observed signals: 10
Missing carbons: 3
Has symmetry: Yes

Hydrogen Budget:
  Expected H: 18
  Accounted H: 15
  Missing H: 3

Potential equivalents (high intensity):
  127.5 ppm (CH) - relative intensity: 1.8
  129.3 ppm (CH) - relative intensity: 1.9
```

---

### Dereplication

```bash
ailsa dereplicate c13 C13_PATH FORMULA [OPTIONS]

Arguments:
  C13_PATH  Path to the 13C Bruker experiment
  FORMULA   Molecular formula (e.g., C13H18O2)

Options:
  -d, --database PATH    Path to database (.db) or SD file (.sd/.sdf); auto-detects SQLite database first
  -n, --top INTEGER      Number of top matches to show
  -t, --threshold FLOAT  Match threshold (0-1). Default: 0.7
  --format [text|json]   Output format
```

**Reference data.** `ailsa dereplicate c13` and `ailsa predict c13` use the pre-built reference database when it is installed (`ailsa database download`, see INSTALLATION.md): 928,443 compounds. The 13C shifts of the 895,099 COCONUT natural products are predicted, not measured; the 33,344 NMRShiftDB compounds carry experimental 13C shifts. COCONUT 13C shifts: from J.-M. Nuzillard, Zenodo, doi:[10.5281/zenodo.6561449](https://doi.org/10.5281/zenodo.6561449), CC BY 4.0.

**Examples:**
```bash
# Auto-discover database (SQLite preferred, falls back to SD files)
ailsa dereplicate c13 data/Ibuprofen/2 C13H18O2

# Use specific database
ailsa dereplicate c13 data/Ibuprofen/2 C13H18O2 --database data/reference/nmrshiftdb2withsignals.sd

# More results
ailsa dereplicate c13 data/Ibuprofen/2 C13H18O2 --top 10
```

---

### LSD Integration

#### Check LSD Availability

```bash
ailsa lsd check
```

Checks whether `LSD` and `outlsd` are installed and available on PATH.

#### LSD Input Files

There is no CLI command that writes an LSD input file from a data directory. In a CASE run,
the LSD-engineer agent builds the input file from the picked peaks and constraints. From
Python, `LSDInputGenerator` builds the same input (see [Python API](#python-api)).

#### Run LSD Solver

```bash
ailsa lsd run INPUT_FILE [OPTIONS]

Arguments:
  INPUT_FILE  Path to the LSD input file

Options:
  --timeout INTEGER      Timeout in seconds
  -o, --output-dir PATH  Directory for solution files
  --format [text|json]   Output format
```

#### Rank LSD Solutions

```bash
ailsa lsd rank SMILES_FILE [OPTIONS]

Arguments:
  SMILES_FILE  File containing SMILES strings (one per line), typically outlsd output

Options:
  -s, --spectrum PATH    Path to Bruker 13C spectrum directory for experimental shifts
  --shifts TEXT          Comma-separated list of experimental 13C shifts in ppm
  -n, --top INTEGER      Number of top results to show
  -t, --tolerance FLOAT  Tolerance in ppm for shift matching
  --db PATH              Path to SQLite HOSE database (auto-detected if not set)
  --table PATH           Path to HOSE lookup table (auto-detected if not set)
  --max-radius INTEGER   Maximum HOSE radius (default 6; must match predict c13 for identical predictions)
  --format [text|json]   Output format
```

**Examples:**
```bash
# Rank using curated shift list (RECOMMENDED)
# Use the peak list that was refined during the CASE workflow
ailsa lsd rank outlsd.out --shifts "180.5,140.8,137.0,129.4,127.1,45.1,40.4,30.2,22.4,18.2"

# Rank using experimental 13C spectrum (re-picks peaks from scratch)
ailsa lsd rank solutions.smi --spectrum data/Ibuprofen/2 --top 5

# With custom tolerance
ailsa lsd rank outlsd.out --shifts "180.5,140.8,137.0,129.4,127.1" --tolerance 2.0
```

> **Best Practice**: Use `--shifts` with your curated peak list rather than `--spectrum`.
> During the CASE workflow, peaks may have been validated against DEPT, adjusted for
> overlapping signals, or manually curated. Using `--spectrum` would discard this
> curation and re-pick peaks from scratch, potentially reintroducing noise or
> missing validated peaks.

**Output:**
```
Ranking 50 LSD solutions
  Successfully ranked: 48
  Skipped (no SMILES): 2
  Experimental peaks: 10
  Tolerance: 3.0 ppm

Top 5 solutions:
----------------------------------------------------------------------
  1. Solution 3: MAE=1.85 ppm, matched=10/13
     CC(C)Cc1ccc(cc1)C(C)C(=O)O
  2. Solution 7: MAE=2.34 ppm, matched=10/13
     CC(C)Cc1ccc(C(C)C(=O)O)cc1
  ...
```

---

### 13C Shift Prediction

#### Predict Shifts from SMILES

```bash
ailsa predict c13 SMILES [OPTIONS]

Arguments:
  SMILES  SMILES string of the molecule

Options:
  -d, --db PATH             Path to SQLite database with HOSE stats (preferred over JSON table)
  -t, --table PATH          Path to HOSE lookup table (JSON); database is preferred if available
  -r, --max-radius INTEGER  Maximum HOSE radius (default: 6)
  --format [text|json]      Output format
```

**Example:**
```bash
ailsa predict c13 "CC(C)Cc1ccc(cc1)C(C)C(=O)O"
```

#### Build Lookup Table

```bash
ailsa predict build-table SD_PATH [OPTIONS]

Arguments:
  SD_PATH  Path to an SD file with 13C chemical shifts (COCONUT or nmrshiftdb2)

Options:
  -o, --output PATH               Output file path (default: data/reference/hose_lookup.json.gz)
  -s, --source [coconut|nmrshiftdb|auto]  Source format (auto-detects by default)
  -r, --max-radius INTEGER        Maximum HOSE radius (default: 6)
  -l, --limit INTEGER             Limit number of molecules to process (for testing)
  -w, --workers INTEGER           Number of parallel workers (default: CPU count)
  --no-compress                   Don't compress output file
```

**Example:**
```bash
ailsa predict build-table data/reference/nmrshiftdb2withsignals.sd
```

---

## Python API

### Reading Spectra

```python
from ailsa import BrukerReader

# Read 1D spectrum
spectrum_1d = BrukerReader.read_1d("data/Ibuprofen/2")
print(f"Nucleus: {spectrum_1d.nucleus}")
print(f"Frequency: {spectrum_1d.frequency} MHz")
print(f"Points: {len(spectrum_1d.data)}")
print(f"PPM range: {spectrum_1d.ppm_scale.min():.1f} - {spectrum_1d.ppm_scale.max():.1f}")

# Read 2D spectrum
spectrum_2d = BrukerReader.read_2d("data/Ibuprofen/6")
print(f"Experiment: {spectrum_2d.experiment_type}")
print(f"Shape: {spectrum_2d.data.shape}")
```

### Peak Picking

```python
from ailsa import BrukerReader, AdaptivePeakPicker

# Basic 1D peak picking
spectrum = BrukerReader.read_1d("data/Ibuprofen/2")
peaks = AdaptivePeakPicker.pick_peaks(spectrum, threshold=0.05)

print(f"Found {len(peaks.peaks)} peaks")
for peak in peaks.peaks[:5]:
    print(f"  {peak.position:.2f} ppm: {peak.intensity:.2e}")

# With negative peak detection (for DEPT)
dept_peaks = AdaptivePeakPicker.pick_peaks(
    spectrum,
    threshold=0.05,
    detect_negative=True
)
```

### DEPT-Guided HSQC Picking

```python
from ailsa import BrukerReader
from ailsa.processing import DEPTGuidedPicker

# Load spectra
hsqc = BrukerReader.read_2d("data/Ibuprofen/6")
dept135 = BrukerReader.read_1d("data/Ibuprofen/3")
dept90 = BrukerReader.read_1d("data/Ibuprofen/4")  # Optional

# Pick with DEPT-135 only
result = DEPTGuidedPicker.pick_hsqc_peaks(hsqc, dept135)

# Or with DEPT-90 for better disambiguation
result = DEPTGuidedPicker.pick_hsqc_peaks_with_dept90(hsqc, dept135, dept90)

# Access results
print(result.summary())
print(f"DEPT peaks: {len(result.dept_peaks.peaks)}")
print(f"HSQC peaks: {len(result.peaks.peaks)}")
print(f"All carbons found: {result.all_carbons_found}")

# Carbon multiplicities
for ppm, mult in result.carbon_multiplicities.items():
    print(f"  {ppm:.1f} ppm: {mult}")
```

### HMBC-Guided Picking

```python
from ailsa import BrukerReader
from ailsa.processing import HMBCGuidedPicker

hmbc = BrukerReader.read_2d("data/Ibuprofen/7")
c13 = BrukerReader.read_1d("data/Ibuprofen/2")
hsqc = BrukerReader.read_2d("data/Ibuprofen/6")
dept135 = BrukerReader.read_1d("data/Ibuprofen/3")

result = HMBCGuidedPicker.pick_hmbc_peaks_from_spectra(
    hmbc=hmbc,
    carbon_spectrum=c13,
    hsqc=hsqc,
    dept135=dept135,
)

print(result.summary())
print(f"Raw peaks: {result.raw_peak_count}")
print(f"Validated: {result.validated_count}")
print(f"Rejected: {result.rejected_count}")
```

### Symmetry Analysis

```python
from ailsa import BrukerReader
from ailsa.processing import DEPTGuidedPicker
from ailsa.analysis import SymmetryAnalyzer

# Load spectra and pick peaks
hsqc = BrukerReader.read_2d("data/Ibuprofen/6")
dept135 = BrukerReader.read_1d("data/Ibuprofen/3")
dept_result = DEPTGuidedPicker.pick_hsqc_peaks(hsqc, dept135)

# Analyze symmetry
result = SymmetryAnalyzer.analyze("C13H18O2", dept_result, hsqc)

print(f"Expected carbons: {result.expected_carbons}")
print(f"Observed signals: {result.signal_count}")
print(f"Has symmetry: {result.has_symmetry}")
print(f"\nHydrogen budget:")
print(f"  Expected: {result.hydrogen_budget.expected_h}")
print(f"  Accounted: {result.hydrogen_budget.total_accounted}")
print(f"  Missing: {result.hydrogen_budget.missing_h}")
```

### Dereplication

```python
from ailsa import BrukerReader
from ailsa.dereplication import DereplicationService, CoconutLoader, NMRShiftDBLoader

# Load spectrum
spectrum = BrukerReader.read_1d("data/Ibuprofen/2")

# Option 1: Using COCONUT (streaming, recommended for large DB)
loader = CoconutLoader("data/reference/coconut_predicted.sd")
service = DereplicationService(loader)
result = service.dereplicate_from_spectrum(
    spectrum=spectrum,
    molecular_formula="C13H18O2",
    top_n=5,
)

# Option 2: Using NMRShiftDB (loads into memory)
loader = NMRShiftDBLoader("data/reference/nmrshiftdb2withsignals.sd")
loader.load()  # Required for NMRShiftDB
service = DereplicationService(loader)
result = service.dereplicate_from_spectrum(spectrum, "C13H18O2")

# Process results
print(f"Candidates found: {result.candidates_found}")
print(f"Best score: {result.best_score:.2f}")
print(f"Is match: {result.is_match}")

for match in result.top_matches:
    print(f"\n{match.entry.name}")
    print(f"  Formula: {match.entry.molecular_formula}")
    print(f"  Score: {match.score:.2f}")
    print(f"  Matched peaks: {match.matched_peaks}")
```

### LSD Integration

```python
from ailsa import BrukerReader
from ailsa.processing import DEPTGuidedPicker, HMBCGuidedPicker
from ailsa.lsd import LSDInputGenerator, LSDRunner

# Load all spectra
hsqc = BrukerReader.read_2d("data/Ibuprofen/6")
dept135 = BrukerReader.read_1d("data/Ibuprofen/3")
hmbc = BrukerReader.read_2d("data/Ibuprofen/7")
c13 = BrukerReader.read_1d("data/Ibuprofen/2")

# Pick peaks
dept_result = DEPTGuidedPicker.pick_hsqc_peaks(hsqc, dept135)
hmbc_result = HMBCGuidedPicker.pick_hmbc_peaks_from_spectra(
    hmbc=hmbc, carbon_spectrum=c13, hsqc=hsqc, dept135=dept135
)

# Generate LSD problem
problem = LSDInputGenerator.from_dept_result(
    dept_result=dept_result,
    hmbc_peaks=hmbc_result.peaks,
    molecular_formula="C13H18O2",
    name="ibuprofen",
)

# Generate input file content
lsd_content = LSDInputGenerator.generate(problem)
print(lsd_content)

# Write to file
LSDInputGenerator.write_file(problem, "ibuprofen.lsd")

# Run LSD (if installed)
if LSDRunner.is_available():
    runner = LSDRunner()
    result = runner.run(problem, timeout=60)
    print(f"Solutions found: {result.solution_count}")
    for sol in result.solutions:
        print(sol)
```

### Solution Ranking

```python
from ailsa import SolutionRanker, BrukerReader, AdaptivePeakPicker
from ailsa.lsd.parser import LSDOutputParser
from pathlib import Path

# Load experimental 13C shifts
spectrum = BrukerReader.read_1d("data/Ibuprofen/2")
peaks = AdaptivePeakPicker.pick_peaks(spectrum)
experimental_shifts = [p.position for p in peaks.peaks]

# Or provide shifts directly
experimental_shifts = [180.5, 140.8, 137.0, 129.4, 127.1, 45.1, 40.4, 30.2, 22.4, 18.2]

# Load LSD solutions (one SMILES per line, the standard outlsd output format)
solutions = LSDOutputParser.parse_smiles_file(Path("outlsd.out"))

# Create ranker from HOSE lookup table
ranker = SolutionRanker.from_table_file(
    table_path="data/reference/hose_nmrshiftdb.json.gz",
    tolerance=3.0,  # ppm tolerance for matching
)

# Rank solutions
result = ranker.rank(solutions, experimental_shifts, top_n=10)

# Access results
print(result.summary())
print(f"Total solutions: {result.total_solutions}")
print(f"Successfully ranked: {result.ranked_count}")
print(f"Skipped (no SMILES): {result.skipped_count}")

# Iterate through ranked solutions (best first)
for i, sol in enumerate(result.solutions):
    print(f"\n{i+1}. Solution {sol.solution_index}")
    print(f"   SMILES: {sol.smiles}")
    print(f"   MAE: {sol.mae:.2f} ppm")
    print(f"   Matched: {sol.matched_count}/{sol.total_carbons} carbons")
    print(f"   Prediction rate: {sol.prediction_rate:.1%}")
```

### 13C Shift Prediction

```python
from ailsa import C13Predictor, HOSELookupTable
from pathlib import Path

# Load predictor from lookup table
predictor = C13Predictor.from_table_file(
    Path("data/reference/hose_nmrshiftdb.json.gz"),
    max_radius=6,  # Use up to 6-sphere HOSE codes
)

# Predict shifts from SMILES
result = predictor.predict_from_smiles("CC(C)Cc1ccc(cc1)C(C)C(=O)O")

print(f"Carbons: {result.carbon_count}")
print(f"Success rate: {result.success_rate:.1%}")

for pred in result.predictions:
    print(f"  Atom {pred.atom_index}: {pred.shift:.1f} ppm "
          f"(confidence: {pred.confidence:.2f}, radius: {pred.radius_used})")

# Build a lookup table from SD file (one-time setup)
from ailsa.prediction import HOSELookupTable
from pathlib import Path

table = HOSELookupTable.build_from_nmrshiftdb(
    Path("data/reference/nmrshiftdb2withsignals.sd"),
    max_radius=6,
)
# Or, for a COCONUT SD file:
# table = HOSELookupTable.build_from_coconut(Path("data/reference/coconut_predicted.sd"))

# Save table for future use
table.save("my_hose_table.json.gz")
```

---

## Workflow Examples

### Complete Structure Elucidation Workflow

```python
from pathlib import Path
from ailsa import BrukerReader, SolutionRanker, AdaptivePeakPicker
from ailsa.processing import DEPTGuidedPicker, HMBCGuidedPicker
from ailsa.analysis import SymmetryAnalyzer
from ailsa.dereplication import DereplicationService, NMRShiftDBLoader
from ailsa.lsd import LSDInputGenerator, LSDRunner

def elucidation_workflow(data_dir: str, formula: str):
    """Complete structure elucidation workflow."""
    data_path = Path(data_dir)

    # Step 1: Load all spectra
    print("Loading spectra...")
    c13 = BrukerReader.read_1d(str(data_path / "2"))
    dept135 = BrukerReader.read_1d(str(data_path / "3"))
    hsqc = BrukerReader.read_2d(str(data_path / "6"))
    hmbc = BrukerReader.read_2d(str(data_path / "7"))

    # Step 2: DEPT-guided HSQC picking
    print("Picking HSQC peaks...")
    dept_result = DEPTGuidedPicker.pick_hsqc_peaks(hsqc, dept135)
    print(f"  Found {len(dept_result.peaks.peaks)} HSQC peaks")

    # Step 3: Guided HMBC picking
    print("Picking HMBC peaks...")
    hmbc_result = HMBCGuidedPicker.pick_hmbc_peaks_from_spectra(
        hmbc=hmbc, carbon_spectrum=c13, hsqc=hsqc, dept135=dept135
    )
    print(f"  Validated {hmbc_result.validated_count} HMBC peaks")

    # Step 4: Symmetry analysis
    print("Analyzing symmetry...")
    symmetry = SymmetryAnalyzer.analyze(formula, dept_result, hsqc)
    print(f"  Has symmetry: {symmetry.has_symmetry}")
    if symmetry.has_symmetry:
        print(f"  Missing carbons: {symmetry.missing_carbons}")

    # Step 5: Try dereplication first
    print("Checking database...")
    try:
        loader = NMRShiftDBLoader("data/reference/nmrshiftdb2withsignals.sd")
        loader.load()
        service = DereplicationService(loader)
        derep = service.dereplicate_from_spectrum(c13, formula)

        if derep.is_match:
            print(f"  MATCH FOUND: {derep.top_matches[0].entry.name}")
            print(f"  Score: {derep.top_matches[0].score:.2f}")
            return {"match": derep.top_matches[0]}
    except FileNotFoundError:
        print("  No database available, proceeding to LSD...")

    # Step 6: Generate LSD input
    print("Generating LSD input...")
    problem = LSDInputGenerator.from_dept_result(
        dept_result=dept_result,
        hmbc_peaks=hmbc_result.peaks,
        molecular_formula=formula,
    )
    print(f"  Atoms: {len(problem.atoms)}")
    print(f"  Correlations: {len(problem.correlations)}")

    # Step 7: Run LSD
    if not LSDRunner.is_available():
        print("  LSD not installed, returning input file")
        return {"lsd_input": LSDInputGenerator.generate(problem)}

    print("Running LSD solver...")
    runner = LSDRunner()
    lsd_result = runner.run(problem, timeout=120)
    print(f"  Solutions: {lsd_result.solution_count}")

    if lsd_result.solution_count == 0:
        return {"solutions": [], "count": 0}

    if lsd_result.solution_count == 1:
        print("  Single solution found - no ranking needed")
        return {"solutions": lsd_result.solutions, "count": 1}

    # Step 8: Rank solutions by 13C spectrum prediction
    print("Ranking solutions...")
    try:
        # Get experimental 13C shifts
        peaks = AdaptivePeakPicker.pick_peaks(c13)
        experimental_shifts = [p.position for p in peaks.peaks]

        # Create ranker and rank solutions
        ranker = SolutionRanker.from_table_file(
            "data/reference/hose_nmrshiftdb.json.gz",
            tolerance=3.0,
        )
        ranking = ranker.rank(lsd_result.solutions, experimental_shifts, top_n=10)

        print(f"  Ranked {ranking.ranked_count} solutions")
        if ranking.solutions:
            best = ranking.solutions[0]
            print(f"  Best match: Solution {best.solution_index}")
            print(f"  MAE: {best.mae:.2f} ppm")
            print(f"  SMILES: {best.smiles}")

        return {
            "solutions": lsd_result.solutions,
            "count": lsd_result.solution_count,
            "ranking": ranking,
        }
    except FileNotFoundError:
        print("  HOSE table not found, skipping ranking")
        return {"solutions": lsd_result.solutions, "count": lsd_result.solution_count}

# Run workflow
result = elucidation_workflow("data/Ibuprofen", "C13H18O2")
```

### Batch Processing

```python
from pathlib import Path
from ailsa import BrukerReader, AdaptivePeakPicker
import json

def batch_peak_picking(base_dir: str, output_file: str):
    """Process multiple spectra and save results."""
    results = []

    for compound_dir in Path(base_dir).iterdir():
        if not compound_dir.is_dir():
            continue

        compound_name = compound_dir.name
        print(f"Processing {compound_name}...")

        # Find 13C experiment
        for exp_dir in compound_dir.iterdir():
            if not exp_dir.is_dir():
                continue
            try:
                spectrum = BrukerReader.read_1d(str(exp_dir))
                if spectrum.nucleus == "13C":
                    peaks = AdaptivePeakPicker.pick_peaks(spectrum)
                    results.append({
                        "compound": compound_name,
                        "experiment": exp_dir.name,
                        "peaks": [
                            {"ppm": p.position, "intensity": p.intensity}
                            for p in peaks.peaks
                        ]
                    })
                    break
            except Exception:
                continue

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Processed {len(results)} compounds")

batch_peak_picking("data/", "peak_results.json")
```

---

## Best Practices

### 1. Use Guided Peak Picking

Always prefer guided peak picking over raw 2D peak picking:

```python
# Good: Use DEPT-guided HSQC
result = DEPTGuidedPicker.pick_hsqc_peaks(hsqc, dept135)

# Avoid: Raw 2D picking produces noise
peaks = PeakPicker2D.pick_peaks(hsqc)  # Many false peaks
```

### 2. Check Results

Always check if operations succeeded:

```python
# For dereplication
if result.is_match:
    # High confidence match
    structure = result.top_matches[0]
else:
    # Need structure generation
    ...

# For LSD
if result.success and result.solution_count > 0:
    # Valid solutions found
    ...
elif result.solution_count == 0:
    # No solutions - check constraints
    ...
```

### 3. Handle Symmetry

For symmetric molecules, check symmetry analysis:

```python
symmetry = SymmetryAnalyzer.analyze(formula, dept_result, hsqc)
if symmetry.has_symmetry:
    print(f"Warning: {symmetry.missing_carbons} equivalent carbons detected")
    # May need to adjust LSD input
```

### 4. Use Appropriate Thresholds

Default thresholds work for most spectra, but adjust if needed:

```python
# Default (good for most cases)
peaks = AdaptivePeakPicker.pick_peaks(spectrum, threshold=0.05)

# Lower threshold for weak signals
peaks = AdaptivePeakPicker.pick_peaks(spectrum, threshold=0.02)

# Higher threshold for noisy spectra
peaks = AdaptivePeakPicker.pick_peaks(spectrum, threshold=0.10)
```

### 5. Save Intermediate Results

For reproducibility, save intermediate results:

```python
import json

# Save peak lists
with open("peaks.json", "w") as f:
    json.dump({
        "hsqc": [{"c": p.f1_position, "h": p.f2_position}
                 for p in result.peaks.peaks],
        "multiplicities": result.carbon_multiplicities,
    }, f)

# Save LSD input
LSDInputGenerator.write_file(problem, "problem.lsd")
```
