# Headless CASE Host Bootstrap

Authoritative, end-to-end guide to provision a **fresh headless server** so it can
run the full autonomous CASE skill `/ailsa:case` — not just the `ailsa` CLI. This is
the canonical "what does a CASE-capable host need" reference; the per-package
details live in [INSTALLATION.md](INSTALLATION.md).

A CASE run needs **five** things present together. Missing any one makes
`/ailsa:case` fail at its prerequisite gate:

1. A compatible **Python** (3.11/3.12 — **not** 3.13/3.14) + the `ailsa` package
2. The **LSD solver** (`LSD` + `outlsd`) on `PATH`
3. The **reference DB** (`ailsa database download` → `data/reference/ailsa-derep.db`)
4. The **CASE skill**: the `/ailsa:*` commands and the four specialist agents symlinked into `~/.claude`
5. `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in the environment — the agent team
   requires Claude Code's agent-team feature, which this flag enables

> A one-shot installer that performs steps 1–5 lives at
> [`scripts/bootstrap_case_host.sh`](../scripts/bootstrap_case_host.sh). This document
> explains each step so the script can be audited and steps can be run by hand. The
> installer script is being brought in line with these names; where it differs, this
> document is authoritative.

---

## 0. Prerequisites already on the host

- `git`, `tmux`, a recent **Claude Code** CLI (`claude --version`), and GSD installed in `~/.claude`.
- Outbound network to GitHub, Figshare (the DB), and `http://eos.univ-reims.fr/LSD/` (the solver).

## 1. Python — avoid 3.13/3.14

RDKit / nmrglue / numpy wheels lag the newest CPython. A bare host whose only
`python3` is 3.13+ **will fail** to install the deps. Use a pinned 3.12 via `uv`
(preferred — the repo ships a `uv.lock`) or `pyenv`.

```bash
git clone https://github.com/steinbeck/ailsa.git
cd ailsa

# Preferred: uv (reproducible from uv.lock, brings its own Python 3.12)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.12
uv sync                       # creates .venv from uv.lock
source .venv/bin/activate

# Alternative: pyenv + venv
# pyenv install 3.12.8 && pyenv local 3.12.8
# python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
```

### 13C prediction dependency (required for CASE ranking)

`hose-code-generator` has a broken test dep on 3.12+; install it without deps:

```bash
uv pip install "git+https://github.com/Ratsemaat/HOSE_code_generator.git" --no-deps
# (or: pip install ... --no-deps  in a plain venv)
```

### Expose `ailsa` on PATH (required for CASE runs)

A CASE run starts from an NMR **data dir outside this repo**, with the venv **not
activated** — so `ailsa` must be on PATH without activation. Symlink the venv
console-script into `~/.local/bin` (on PATH by default on Linux; the script has an
absolute shebang, so no activation is needed):

```bash
mkdir -p ~/.local/bin
ln -sfn "$PWD/.venv/bin/ailsa" ~/.local/bin/ailsa
```

## 2. LSD solver (`LSD` + `outlsd`)

The solver is an **external** download (not on PyPI). `outlsd` (SMILES conversion) is
required for ranking — without it CASE cannot produce rankable solutions.

```bash
mkdir -p ~/opt && cd ~/opt
# Fetch the current LSD release from http://eos.univ-reims.fr/LSD/ (version may differ)
# e.g.:  wget http://eos.univ-reims.fr/LSD/LSD-3.5.3.tar.gz && tar -xzf LSD-3.5.3.tar.gz
cd LSD-*/ && make 2>/dev/null || true
# put BOTH binaries on PATH (persist in the shell profile):
echo 'export PATH="$HOME/opt/'"$(basename "$PWD")"'/bin:$PATH"' >> ~/.bashrc
export PATH="$PWD/bin:$PATH"
```

Verify (this is the gate — fix until both report available):

```bash
ailsa lsd check        # must show: LSD available + outlsd available
```

The `~/.bashrc` PATH entry above only applies to **interactive** shells; CASE runs in
non-interactive ones. Mirror the binaries into `~/.local/bin` so they're found from any
data dir:

```bash
for b in lsd outlsd genpos mol2ab; do ln -sfn "$(command -v "$b")" ~/.local/bin/$b; done
```

## 3. Reference database (pre-built SQLite)

CASE ranking + dereplication use one pre-built SQLite DB (~830 MB download → ~2.8 GB),
NOT raw SD files. Fetch it with the CLI (Figshare, DOI 10.6084/m9.figshare.31073554):

```bash
mkdir -p data/reference
ailsa database download
ailsa database info   # sanity-check row counts and schema version
```

The 13C shifts of the 895,099 COCONUT natural products are predicted, not measured; the 33,344 NMRShiftDB compounds carry experimental 13C shifts. COCONUT 13C shifts: from J.-M. Nuzillard, Zenodo, doi:[10.5281/zenodo.6561449](https://doi.org/10.5281/zenodo.6561449), CC BY 4.0.

Statistical detection (`ailsa detect …`) needs the full reference database with the
**current schema**. Check the "Schema version" line of `ailsa database info` on the
host — a database on an older schema leaves the detection commands without usable
data, even though prediction and ranking still work from the same file.

`DatabaseFinder` only finds `data/reference/ailsa-derep.db` when the CWD is the repo.
A CASE run starts from a data dir, so link the DB into `~/.local/share/ailsa/`, which
`DatabaseFinder` searches from any working directory. **Without this, CASE silently
falls back to a tiny bundled HOSE table (~11 matches) instead of the full
928k-compound DB:**

```bash
mkdir -p ~/.local/share/ailsa
ln -sfn "$PWD/data/reference/ailsa-derep.db" ~/.local/share/ailsa/ailsa-derep.db
```

## 4. Install the CASE skill (commands + agents) into `~/.claude`

The skill is the `/ailsa:*` **commands** PLUS the **CASE team agents**. Symlink the
repo's `.claude/` content so edits stay in sync (mirrors the dev-machine setup). Copy
instead of symlink only if you want a frozen snapshot.

```bash
REPO="$(pwd)"                       # the cloned ailsa checkout
mkdir -p ~/.claude/agents ~/.claude/commands

# Commands (directory symlink): case.md, references/, dereplicate/predict/sanitise/status
ln -sfn "$REPO/.claude/commands/ailsa" ~/.claude/commands/ailsa

# CASE team agents (per-file symlinks) — REQUIRED for /ailsa:case to spawn its team
for a in "$REPO"/.claude/agents/ailsa-*.md; do
  ln -sfn "$a" ~/.claude/agents/"$(basename "$a")"
done
```

Agents linked: `ailsa-nmr-chemist`, `ailsa-lsd-engineer`, `ailsa-solution-analyst`,
`ailsa-devils-advocate` (the four-specialist team) + `ailsa-diagnostic` (escalation).

> **Blind-UAT hygiene (read if this host runs blind benchmarks):** link ONLY the
> decontaminated repo `.claude/` (FIX-09 removed answer keys/dev-meta from it). Keep any
> ground-truth/answer-key manifest and compound-identity auto-memory **off the run path**
> — never in this host's `~/.claude` or in a CASE data directory a blind instance reads.

## 5. Enable agent teams

The CASE agent team — a coordinator plus four specialists that coordinate with each
other — is built on Claude Code's agent-team feature. This flag is a requirement of
the team design, not an optional toggle; `/ailsa:case` also checks it before it
starts:

```bash
echo 'export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1' >> ~/.bashrc
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

Unattended runs (`claude -p`, as on a benchmark host) do not form a team even with
the flag set — the coordinator then runs the specialists one at a time, the
restricted configuration in which the published benchmark was measured (see
[BENCHMARK.md#how-a-benchmark-run-executes](BENCHMARK.md#how-a-benchmark-run-executes)).

## 6. Verify the full CASE prerequisite chain

These are exactly the gates `case.md` checks at startup — all four must pass:

```bash
echo "$CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"           # -> 1
ailsa --version                                         # CLI installed
ailsa lsd check                                         # LSD + outlsd available
ailsa predict c13 "CCO" --format json | head -1         # DB + hosegen working
```

Then confirm they also work **from outside the repo** — a CASE run never starts in the
repo, so this is what actually exercises the `~/.local/bin` and `~/.local/share/ailsa`
symlinks from §1–§3 (`predict` here must report the full DB, not a ~11-match fallback):

```bash
( cd /tmp && ailsa --version && ailsa lsd check && ailsa predict c13 "CCO" --format json >/dev/null && echo "OK: discoverable from any dir" )
```

Then a **smoke CASE** on bundled test data (non-blind, just proves the pipeline):

```bash
cd data/Ibuprofen   # or any Bruker dir with the needed experiments
# In a fresh Claude Code session on the host:  /ailsa:case . C13H18O2
```

If the coordinator runs to `final_results.md`, and `ailsa lsd check`/DB/prediction all
pass, the host is CASE-capable.

---

## Provisioning checklist (copy/paste)

- [ ] `git clone` the repo; `uv sync` with Python 3.12; activate `.venv`
- [ ] `hose-code-generator` installed `--no-deps`
- [ ] LSD + outlsd on PATH (`ailsa lsd check` green)
- [ ] `ailsa database download` → `data/reference/ailsa-derep.db` (`ailsa database info` ok)
- [ ] `ailsa database info` reports the current schema (needed for statistical detection)
- [ ] **discoverability:** `ailsa` + LSD binaries symlinked into `~/.local/bin`, DB into `~/.local/share/ailsa/`
- [ ] commands symlink + **agents symlinks** in `~/.claude`
- [ ] `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` persisted
- [ ] all four `case.md` prereq gates pass + a smoke CASE completes
- [ ] (blind hosts) answer-key manifest is OFF the run path

See also: [INSTALLATION.md](INSTALLATION.md) (package detail), [../CLAUDE.md](../CLAUDE.md)
(local-prerequisites + DB reference), [USER_GUIDE.md](USER_GUIDE.md).
