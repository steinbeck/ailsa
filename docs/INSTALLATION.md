# Installation Guide

This guide covers all installation options for AILSA.

## Table of Contents

- [Requirements](#requirements)
- [Quick Installation](#quick-installation)
- [Installation Options](#installation-options)
- [External Dependencies](#external-dependencies)
- [Reference Databases](#reference-databases)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)
- [Claude Code Skill Installation](#claude-code-skill-installation)

## Requirements

### Python Version

AILSA requires **Python 3.10 or higher**.

Check your Python version:
```bash
python3 --version
```

### System Dependencies

AILSA's Python dependencies will be installed automatically. The core dependencies are:

| Package | Version | Purpose |
|---------|---------|---------|
| nmrglue | >=0.9 | Bruker NMR file parsing |
| numpy | >=1.24 | Numerical operations |
| scipy | >=1.10 | Peak picking algorithms |
| pydantic | >=2.0 | Data model validation |
| rdkit | >=2023.0 | SD file parsing for databases |
| click | >=8.0 | CLI framework |
| tqdm | >=4.0 | Progress bars |

**Optional dependencies:**

| Package | Purpose | Notes |
|---------|---------|-------|
| hose-code-generator | 13C shift prediction | See [Python 3.12 note](#13c-prediction-python-312) |

## Quick Installation

### From PyPI (Recommended)

```bash
pip install ailsa
```

### From GitHub (development head)

```bash
pip install "ailsa @ git+https://github.com/steinbeck/ailsa.git"
```

> **Note for macOS/zsh users**: Quotes are required when a package spec contains
> brackets (e.g. an extra like `ailsa[dev]`), because zsh interprets square brackets
> as glob patterns. Without quotes, you'll get a "no matches found" error.

### Full Installation (All Features)

```bash
pip install "ailsa[dev] @ git+https://github.com/steinbeck/ailsa.git"
```

## Installation Options

### Option 1: User Installation

Install for the current user only (no root required):

```bash
pip install --user "ailsa @ git+https://github.com/steinbeck/ailsa.git"
```

### Option 2: Virtual Environment (Recommended)

```bash
# Create virtual environment
python3 -m venv ailsa-env
source ailsa-env/bin/activate  # Linux/macOS
# or: ailsa-env\Scripts\activate  # Windows

# Install AILSA
pip install "ailsa @ git+https://github.com/steinbeck/ailsa.git"
```

### Option 3: Development Installation (For Contributors)

For contributing or modifying AILSA:

```bash
# Clone repository
git clone https://github.com/steinbeck/ailsa.git
cd ailsa

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Verify installation
pytest
```

### Option 4: System-Wide Installation

```bash
sudo pip install "ailsa @ git+https://github.com/steinbeck/ailsa.git"
```

## 13C Prediction (Python 3.12)

The 13C shift prediction feature (`ailsa predict c13`, `ailsa lsd rank` solution
ranking) requires the `hose-code-generator` package for HOSE code generation.

### Python 3.10/3.11

On Python 3.10 or 3.11, hosegen installs automatically with all its dependencies.

### Python 3.12+

On Python 3.12, the `hose-code-generator` package has a broken test dependency (`xmlrunner`) that fails to install. Install it manually without dependencies:

```bash
# After installing AILSA
pip install git+https://github.com/Ratsemaat/HOSE_code_generator.git --no-deps
```

The `--no-deps` flag skips the broken `xmlrunner` dependency, which is only needed for running hosegen's own tests, not for HOSE code generation. The prediction features work correctly without it.

### Checking Availability

You can check if HOSE code prediction is available:

```python
from ailsa.prediction import HOSEGEN_AVAILABLE
print(f"HOSE prediction available: {HOSEGEN_AVAILABLE}")
```

Or via CLI:
```bash
ailsa predict c13 "CCO"  # Will show error if hosegen not installed
```

## External Dependencies

### LSD Solver (Optional)

LSD (Logic for Structure Determination) is required for structure generation. It's optional for dereplication and analysis.

#### Download and Install

1. Download LSD from: http://eos.univ-reims.fr/LSD/
2. Extract the archive:
   ```bash
   tar -xzf LSD-3.5.3.tar.gz
   cd LSD-3.5.3
   ```
3. Compile (if needed):
   ```bash
   make
   ```
4. Add to PATH or copy to standard location:
   ```bash
   # Option A: Add to PATH
   export PATH="$PATH:$HOME/LSD-3.5.3"

   # Option B: Copy to ~/bin
   mkdir -p ~/bin
   cp lsd ~/bin/
   export PATH="$PATH:$HOME/bin"

   # Option C: Copy to system location
   sudo cp lsd /usr/local/bin/
   ```

#### Install outlsd (Recommended)

The `outlsd` program converts LSD solutions to SMILES format, which is required for solution ranking. It is distributed with LSD.

```bash
# Copy outlsd alongside lsd
cp outlsd ~/bin/
# or
sudo cp outlsd /usr/local/bin/
```

Without `outlsd`:
- LSD will still generate solutions
- But `ailsa lsd rank` cannot rank them (no SMILES available) — the command will skip all solutions

#### Verify LSD Installation

```bash
# Using CLI - shows both lsd and outlsd status
ailsa lsd check

# Or directly
which lsd
which outlsd
```

Expected output:
```
LSD: available
outlsd: available (SMILES conversion enabled)
```

### pyLSD (Alternative Solver)

pyLSD is a Python wrapper around LSD with additional features. Install separately if needed:

```bash
pip install pylsd
```

## Reference Database

AILSA uses **one pre-built SQLite database** for BOTH dereplication and 13C
prediction (formula-indexed compound lookup + HOSE-based shift prediction). It is
required for the `dereplicate`, `predict c13`, and CASE-ranking paths. You do **not**
build it from raw SD files for a normal install — download the pre-built one:

```bash
mkdir -p data/reference
ailsa database download                 # ~830 MB -> ~2.8 GB
ailsa database info                      # verify row counts and schema version
```

| Property | Value |
|----------|-------|
| Source | Figshare, DOI [10.6084/m9.figshare.31073554](https://doi.org/10.6084/m9.figshare.31073554) |
| Default path | `data/reference/ailsa-derep.db` |
| Contents | 928,443 compounds (COCONUT: 895,099 with predicted 13C shifts; NMRShiftDB: 33,344 with experimental 13C shifts), 7.9M HOSE statistics |
| COCONUT shift source | COCONUT 13C shifts: ACD/Labs predictions from J.-M. Nuzillard, Zenodo, doi:[10.5281/zenodo.6561449](https://doi.org/10.5281/zenodo.6561449), CC BY 4.0 — predicted, not measured (ACD/Labs C+H NMR Predictors and DB 2020.1.0) |

Statistical detection (`ailsa detect …`, used by the NMR-chemist agent) needs the
full reference database with the **current schema**: with a database file on an
older schema, the detection commands return no usable data even though prediction
and ranking still work from the same file. `ailsa database info` prints a "Schema
version" line — check it after any download.

### Auto-Discovery

`DatabaseFinder` discovers `data/reference/ailsa-derep.db` automatically, including
from a CASE data directory outside the repo (it also checks
`~/ailsa/data/reference/ailsa-derep.db` and `~/.local/share/ailsa/ailsa-derep.db`).
Override explicitly with `--database`:

```bash
ailsa dereplicate c13 spectrum_path formula --database /path/to/ailsa-derep.db
```

> The raw COCONUT/NMRShiftDB SD files are only needed to **rebuild** the SQLite DB from
> source (a maintenance task) — not for running AILSA.
> The COCONUT SD file with the predicted 13C shifts comes from the Zenodo record credited in the table above.

## Verification

After installation, verify everything works:

### Check CLI Installation

```bash
# Should show help message
ailsa --help

# Check version
ailsa --version
```

### Run Tests

```bash
# Quick test (if dev dependencies installed)
pytest -q

# Full test suite
pytest
```

### Test with Sample Data

```bash
# Read a spectrum (if test data available)
ailsa read 1d data/Ibuprofen/2

# Pick peaks
ailsa pick 1d data/Ibuprofen/2
```

## Troubleshooting

### Import Errors

**Problem**: `ModuleNotFoundError: No module named 'ailsa'`

**Solution**:
```bash
# Ensure you're in the right environment
which python3
pip list | grep ailsa

# Reinstall if needed
pip install --force-reinstall ailsa
```

### RDKit Installation Issues

**Problem**: RDKit fails to install

**Solution**:
```bash
# Try conda instead
conda install -c conda-forge rdkit

# Or use mamba
mamba install rdkit
```

### LSD Not Found

**Problem**: `ailsa lsd check` says LSD is not available

**Solution**:
```bash
# Find LSD binary
find ~ -name "lsd" -type f 2>/dev/null

# Add to PATH
export PATH="$PATH:/path/to/lsd/directory"

# Verify
which lsd
```

### Database Loading Slow

**Problem**: Dereplication takes very long with COCONUT

**Solution**: This is normal for the first query. AILSA uses streaming mode so it doesn't load the entire 4.8 GB file into memory. Typical query time is 1-2 minutes for formula-based filtering.

### Memory Issues

**Problem**: Out of memory errors with large databases

**Solution**: AILSA's COCONUT loader uses streaming mode by default. If you're still seeing issues:
```bash
# Increase available memory
ulimit -v unlimited

# Or use NMRShiftDB instead
ailsa dereplicate c13 spectrum formula --database data/reference/nmrshiftdb2withsignals.sd
```

### HOSE Code Generator Issues (Python 3.12)

**Problem**: Installation fails with `xmlrunner` or `_TextTestResult` errors

```
ImportError: cannot import name '_TextTestResult' from 'unittest'
```

**Solution**: This is a known issue with Python 3.12. Install hosegen without its broken test dependency:

```bash
pip install git+https://github.com/Ratsemaat/HOSE_code_generator.git --no-deps
```

**Problem**: `hosegen package not installed` error when using prediction

**Solution**: Install hosegen as shown above. The prediction features require this package for HOSE code generation.

## Claude Code Skill Installation

AILSA's Claude Code integration is the `/ailsa:*` **commands** plus the **CASE
agent team** that `/ailsa:case` starts: a coordinator and four specialists that
coordinate with each other. Both must be present, and an environment flag must
be set, or CASE fails at its prerequisite gate.

> For a fresh headless server set up to run CASE unattended, follow the
> end-to-end **[SERVER_BOOTSTRAP.md](SERVER_BOOTSTRAP.md)** guide (or run
> `scripts/bootstrap_case_host.sh`) — it does the steps below plus Python/LSD/DB.

### Install the commands and agents

Symlink the repo's `.claude/` content into `~/.claude` (edits stay in sync; use `cp -r`
for a frozen snapshot):

```bash
git clone https://github.com/steinbeck/ailsa.git
cd ailsa
mkdir -p ~/.claude/agents ~/.claude/commands

# Commands (case, dereplicate, predict, sanitise, status + references/)
ln -sfn "$PWD/.claude/commands/ailsa" ~/.claude/commands/ailsa

# CASE team agents — REQUIRED for /ailsa:case to spawn its team
for a in "$PWD"/.claude/agents/ailsa-*.md; do
  ln -sfn "$a" ~/.claude/agents/"$(basename "$a")"
done
```

### Enable agent teams

The CASE agent team is built on Claude Code's agent-team feature. This is a
requirement of the team design, not an optional toggle — `/ailsa:case` checks the
flag before it starts:

```bash
echo 'export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1' >> ~/.bashrc   # or ~/.zshrc
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

Unattended runs (`claude -p`) do not form a team even with the flag set — the
coordinator then runs the specialists one at a time, which is the restricted
configuration the published benchmark measured (see
[BENCHMARK.md#how-a-benchmark-run-executes](BENCHMARK.md#how-a-benchmark-run-executes)).

### Verify

After restarting Claude Code, the commands are available:

```
/ailsa:case        /ailsa:dereplicate        /ailsa:predict
/ailsa:sanitise    /ailsa:status
```

### Available commands

| Command | Purpose |
|---------|---------|
| `/ailsa:case` | Full de novo structure elucidation (coordinator + four-specialist team) |
| `/ailsa:dereplicate` | Database matching only |
| `/ailsa:predict` | Predict 13C shifts for a SMILES |
| `/ailsa:sanitise` | Remove compound identity from datasets for blind CASE |
| `/ailsa:status` | Check environment readiness (ailsa/LSD/DB) |

### CASE team agents (in `~/.claude/agents/`)

| Agent | Role |
|-------|------|
| `ailsa-nmr-chemist` | Peak picking, statistical detection, spectral QA |
| `ailsa-lsd-engineer` | LSD constraint building + solver runs |
| `ailsa-solution-analyst` | Solution ranking + identity reporting |
| `ailsa-devils-advocate` | Pre-run validation + post-solution G-IDENT/G-MULT gates |
| `ailsa-diagnostic` | Deep LSD-failure diagnosis (escalation only) |

## Next Steps

After installation:

1. **Read the User Guide**: See [USER_GUIDE.md](USER_GUIDE.md) for detailed usage
2. **The CASE Agent Team**: See [../README.md#the-case-agent-team](../README.md#the-case-agent-team) for how the coordinator and specialists work together
3. **Explore the CLI**: Run `ailsa --help` to see all commands
4. **Try the examples**: See the Quick Start section in the main README
