# AILSA lite: structure elucidation with a small open-weight model

`ailsa-lite` is the lean AILSA skill for models of about 20–35 B parameters running locally, for
example in [OpenCode](https://opencode.ai) with llama.cpp. It asks the model for the same work as
the full AILSA skill asks of a frontier model, with the same `ailsa` commands: read the spectra,
build the atom list, write the input file for the LSD solver, judge the candidates. The full skill
spreads this over an agent team and about 70 000 tokens of instructions; the lean skill is one
agent with a short core instruction and reference files it reads when it needs them. Why there
are two skills, and how they are kept apart: [SKILLS.md](SKILLS.md).

## Contents

- [What the model does](#what-the-model-does)
- [Install](#install)
- [OpenCode with a local model](#opencode-with-a-local-model)
- [Run](#run)
- [Blind runs](#blind-runs)
- [Results](#results)
- [Status](#status)

## What the model does

| Step | The model | Commands it uses | Reference file |
|---|---|---|---|
| 0 | checks the tools and creates the run record | `ailsa run init` | — |
| 1 | picks peaks, decides multiplicities, hybridisation and heteroatoms, writes `setup.md` | `ailsa pick`, `ailsa detect`, `ailsa analyze`, `ailsa run note` | `nmr-analysis.md` |
| 2 | writes each LSD file, checks it, runs LSD, adds HMBC correlations in batches, diagnoses failures | `ailsa lsd run`, `ailsa lsd validate-inventory`, `ailsa run note` | `lsd-input.md`, `checks-and-diagnosis.md` |
| 3 | ranks the candidates, checks identities, declares the result | `ailsa lsd rank`, `ailsa predict c13`, `ailsa identify`, `ailsa run finalize` | `ranking.md` |

`ailsa run init DATASET` creates the run record ([RUN-RECORD.md](RUN-RECORD.md)) in the workspace
and prints the run's work folder; the model works there and never writes into the dataset. The
run's state is in files the model writes in that folder: `setup.md`, `iterations.md` and one
`iteration_NN/compound.lsd` per solver run. The model does not write the report: it declares the
result with `ailsa run finalize`, and the report is generated from the record.

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
- Keep earlier runs on the same data out of the run workspace (`AILSA_WORKSPACE`, see
  [RUN-RECORD.md](RUN-RECORD.md)): the agent can read it. `ailsa run init --blind` refuses to
  start when it finds such runs, but this guards against accident only.
- Grade from the run folder, not from the dataset: the rendered `renderings/final_results.md`
  (the declared candidate with its SMILES and the top-10 table) or the ranking files in
  `rankings/` (one `rkNN.json` per ranking; the declaration names the one it used).

## Results

Everything lands in the run folder in the workspace ([RUN-RECORD.md](RUN-RECORD.md)); the dataset
is left unchanged.

| File in the run folder | Content |
|---|---|
| `renderings/final_results.md` | generated from the declaration: proposed structure, confidence, caveats, top candidates |
| `renderings/CASE-PROGRESS.md` | generated progress log: every tool step, note and the declaration in time order |
| `rankings/rkNN.json` | each ranking `ailsa lsd rank` made (SMILES, errors), with its id |
| `agent/setup.md` | peaks, atoms with the evidence for each, correlations, open questions |
| `agent/iterations.md` | one entry per solver run: constraints added and removed, solution count |
| `agent/iteration_NN/` | the LSD file the model wrote, the solver output and the SMILES of each run |

Regenerate the two reports with `ailsa run render`; never edit them by hand.

## Status

Version 0.3 writes the run record instead of files in the dataset; otherwise it is version 0.2.
Version 0.2: the same tools and rules as the full AILSA skill, the model does the work itself.
Version 0.1 had moved that work into scripts; on 40 blind benchmark datasets the model then could
add nothing to what the scripts found (see [SKILLS.md](SKILLS.md)). Version 0.2 is being measured
on the same datasets. NUS and JCAMP-DX data must be converted first (`ailsa nus`, `ailsa jcamp`).
