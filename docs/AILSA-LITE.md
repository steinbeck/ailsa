# AILSA lite: structure elucidation with a small open-weight model

`ailsa-lite` is the lean AILSA skill for models of about 20–35 B parameters running locally, for
example in [OpenCode](https://opencode.ai) with llama.cpp. The full AILSA skill for frontier
models (an agent team with about 75 000 tokens of instructions) does not fit such a model. The
lean skill is about 1 000 tokens; the `ailsa case` commands do the bookkeeping that would
otherwise fill the context. Why there are two skills, and how they are kept apart:
[SKILLS.md](SKILLS.md).

## Contents

- [What the model does, and what the commands do](#what-the-model-does-and-what-the-commands-do)
- [Install](#install)
- [OpenCode with a local model](#opencode-with-a-local-model)
- [Run](#run)
- [Blind runs](#blind-runs)
- [Results](#results)
- [Status](#status)

## What the model does, and what the commands do

| Step | Command | Done by the command | Left to the model |
|---|---|---|---|
| 1 | `ailsa case scan DATASET` | finds and classifies the experiments, checks LSD and the prediction database | stop if a tool is missing |
| 2 | `ailsa case setup DATASET --formula MF` | picks peaks; removes solvent, noise and artefacts; builds the atoms (multiplicity, hybridisation, symmetry, heteroatoms) and the HMBC correlations | — |
| 3 | `ailsa case check` / `ailsa case edit` | lists errors and every assumption it made, with the command that reverses it | fix errors; change an assumption only with evidence |
| 4 | `ailsa case solve DATASET` | writes the LSD input, runs LSD, lets it ignore up to three correlations if nothing fits | react when no structure fits |
| 5 | `ailsa case rank DATASET` | predicts 13C shifts for every candidate and compares them atom by atom | judge the result |
| 6 | `ailsa case report DATASET --note "..."` | writes `analysis/final_results.md` | a short assessment |

All state is in `DATASET/analysis/problem.json`, including every edit and its reason. The LSD
input files are generated for each run and never edited by hand.

## Install

Python 3.10 or newer, then:

```bash
pip install git+https://github.com/steinbeck/ailsa
pip install git+https://github.com/Ratsemaat/HOSE_code_generator.git --no-deps   # 13C prediction
ailsa database download      # reference database, ~830 MB download, needed for ranking
ailsa lsd check              # LSD and outlsd must be on PATH, see INSTALLATION.md
ailsa skill install ailsa-lite --target opencode     # or --target claude
```

`ailsa skill install` copies the skill that belongs to the installed version of `ailsa` into
`~/.config/opencode/skills/ailsa-lite/` (with `--project`: `.opencode/skills/` in the current
folder). Reinstall it with `--force` after every update of `ailsa`.

## OpenCode with a local model

An `opencode.json` for a llama.cpp server (`llama-server`) on the same machine. Set the context
limit to what the server was started with:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "llama.cpp/local",
  "provider": {
    "llama.cpp": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "llama-server (local)",
      "options": { "baseURL": "http://127.0.0.1:8080/v1" },
      "models": {
        "local": { "name": "local model", "limit": { "context": 65536, "output": 16384 } }
      }
    }
  },
  "permission": {
    "bash": "allow",
    "external_directory": "allow",
    "webfetch": "deny",
    "websearch": "deny"
  }
}
```

The solver can take several minutes on a large molecule, longer than OpenCode's default
two-minute limit for a shell command. Raise it:

```bash
export OPENCODE_EXPERIMENTAL_BASH_DEFAULT_TIMEOUT_MS=1800000
```

## Run

Interactively, start OpenCode in a working folder and ask:

> Determine the structure of the unknown compound whose NMR data are in ./sample
> (molecular formula C12H18O3). Use the ailsa-lite skill.

Without interaction:

```bash
opencode run --auto "Determine the structure of the unknown compound whose NMR data are in \
./sample (molecular formula C12H18O3). Use the ailsa-lite skill."
```

`--auto` approves the shell commands; the denied web tools stay denied.

## Blind runs

For a benchmark the model must see nothing but the spectra and the formula:

- Give each run a fresh copy of the dataset in an empty working folder.
- `OPENCODE_DISABLE_CLAUDE_CODE=1` stops OpenCode from reading Claude Code files
  (`~/.claude/CLAUDE.md`, `.claude/skills`), which may carry notes from earlier work.
- Keep `webfetch` and `websearch` denied (see the configuration above).
- Grade from `analysis/ranking.json` (the ranked candidates as SMILES) or the table in
  `analysis/final_results.md`.

## Results

| File in `DATASET/analysis/` | Content |
|---|---|
| `final_results.md` | proposed structure, assessment, top candidates, assumptions and edits, solver runs |
| `ranking.json` | the ranked candidates (SMILES, InChIKey, errors) |
| `problem.json` | atoms, correlations with the peak each came from, every edit with its reason |
| `runs/run_NN/` | LSD input, solver output and SMILES of each solver run |

## Status

Version 0.1. Measured so far only on the development datasets: driven by the commands alone, and
with a small Claude model following the skill. Not yet measured with an open-weight model. Known
gaps: no search over several multiplicity models when DEPT and edited HSQC are both missing; no
automatic search for a contradicting correlation; NUS and JCAMP-DX data must be converted first
(`ailsa nus`, `ailsa jcamp`).
