# Requirements — Milestone v11.0 AILSA Rename and Skill Rebuild

**Goal:** rename the project from the working title *lucy-ng* to **AILSA** (*AI + LSD + Agents*) everywhere it is visible, without breaking the running benchmark or rewriting the historical record.

**Ordering constraint:** the original gate (skill and repository only after the Opus-5 re-run) is lifted — the re-run finished 2026-09-29. **Extended 2026-10-12:** the skill is also rebuilt to Anthropic's skill-authoring best practices and made measurable as designed (agent team + full toolchain); see ROADMAP.md v11.0 and the plan `AILSA-Skills-Ueberarbeitungsplan.pdf`.

## v11.0 Requirements

### Package and CLI (PKG)

- [ ] **PKG-01**: A user can `pip install ailsa` from PyPI and get the real package (replacing the 0.0.1 name-reservation placeholder), with `pyproject.toml` naming the project `ailsa`. *(pyproject half done in 104-02/05; PyPI upload deferred by user decision 2026-10-03 until after the documentation phase so the PyPI page shows the rewritten README; moved 2026-10-06 to after the repository rename (now Phase 111) so every command and link in the frozen README works (105-CONTEXT.md D-05) — artifacts built and twine-verified in 104-06)*
- [x] **PKG-02**: A developer imports everything from the Python module `ailsa`; no `lucy_ng` module or import remains in `src/`, `tests/` or `scripts/`.
- [x] **PKG-03**: A user runs every subcommand as `ailsa …`; `lucy …` still works for one release and prints a one-line deprecation hint pointing to `ailsa`.
- [x] **PKG-04**: The full test suite passes on the renamed tree with the same pass count as before (1345 passed / 74 environment failures), and `mypy --strict` and `ruff` report no new findings.
- [x] **PKG-05**: A user with the existing database file `data/reference/lucy-ng-derep.db` keeps working; `ailsa database download` and `ailsa database info` accept the old file name as well as the new default.

### Documentation and outside face (DOC)

- [x] **DOC-01**: A reader of the README sees the project as AILSA, with the expansion *AI + LSD + Agents*, and LSD and Jean-Marc Nuzillard credited up front. *(Amended 2026-10-06: the "formerly called lucy-ng" note is struck — the user wants the old name to disappear as far as possible; see 105-CONTEXT.md D-01.)*
- [x] **DOC-02**: `docs/` (ARCHITECTURE, USER_GUIDE, BENCHMARK, NUS-PORTABILITY and the rest) and `CLAUDE.md` refer to the project, package, CLI and commands by the new names; no living document still instructs the reader to type `lucy`.
- [x] **DOC-03**: The figshare record of the reference database carries the new project name in title and description; the DOI and the uploaded file are unchanged.
- [x] **DOC-04**: The infographic deck (`docs/infographics/build.py`) is rebuilt under the new name with the current headline numbers (this also clears the "stale deck" backlog item).

### Freeze the measured state (FREEZE)

- [ ] **FREEZE-01**: Git tags mark the two skill states the benchmark ran on (state 1 `f9aa7b3`, 45 runs 2026-08-11..14; state 2 `6d2d126` incl. `d62d833`, 211 runs), and `docs/BENCHMARK.md` records them with the compute host's environment (Claude Code 2.1.205, LSD 3.5.3, reference DB schema 3, no fragment DB).

### Skill system (SKILL)

- [ ] **SKILL-01**: A user runs `/ailsa:case`, `/ailsa:dereplicate`, `/ailsa:predict`, `/ailsa:sanitise` and `/ailsa:status`; the `/lucy-ng:*` commands are gone and the symlinks under `~/.claude/commands` point at the new directory.
- [ ] **SKILL-02**: The agents are `ailsa-nmr-chemist`, `ailsa-lsd-engineer`, `ailsa-solution-analyst`, `ailsa-devils-advocate` and `ailsa-diagnostic`; the unused supervisor agent is removed; the SHA-256 guard references the new files, and the `~/.claude/agents` symlinks are updated.
- [ ] **SKILL-03**: One blind CASE run on the compute host, started through the renamed command with the renamed agents, completes and grades — the proof that the restructured chain still works.
- [ ] **SKILL-04**: The blind runner script and the watchdog scripts call the new command and paths, and the LaunchAgent (label, program path, log name) is re-registered under the new name.
- [ ] **SKILL-05**: Every skill file follows Anthropic's skill-authoring best practices in form: body under 500 lines with details in one-level reference files (one shared LSD reference), a table of contents in files over 100 lines, no dead references, no project history or defect numbers, no dataset numbers, no fixed model IDs, one term per role, rationale instead of capital-letter emphasis.
- [ ] **SKILL-06**: An automated skill-lint check enforces SKILL-05 on every commit, and a local check (answer key never in the repository) finds no benchmark compound by name or structure in any skill file.

### Evaluation bench and team-mode spike (EVAL, TEAM)

- [ ] **EVAL-01**: A fixed evaluation sample of about 25 blind datasets, stratified by heavy-atom count and mixing solved and unsolved cases, is recorded privately with the old configuration's result for each.
- [ ] **EVAL-02**: Every evaluation run produces a mechanics report — team formed or not, messages between specialists, tool outputs usable or not, runtime, tokens.
- [ ] **EVAL-03**: A parity check compares Mac and compute host (reference DB schema, fragment DB, LSD version, Claude Code version) and fails loudly on any difference.
- [ ] **TEAM-01**: A spike decides the route for unattended team runs (named subagents messaging each other in `claude -p`, or a remotely driven interactive session); its mechanics report shows real messages between specialists in an unattended run.

### Foundation (FOUND)

- [ ] **FOUND-01**: The compute host has the full reference DB (current schema; the detection commands return data), and it is known whether the public figshare file is the outdated schema; a re-upload follows the user's decision.
- [ ] **FOUND-02**: `detect hhb` reports no data when its table is missing instead of `has_data: true` with empty lists.
- [ ] **FOUND-03**: The fragment DB is installed on the compute host and used, or fragment search is removed from the workflow (user's decision).
- [ ] **FOUND-04**: The prerequisite check (`/ailsa:status` and the coordinator's first step) verifies every capability the skill relies on and stops with a clear message if one is missing.
- [ ] **FOUND-05**: The devil's-advocate structural checks run as a CLI command instead of shell snippets in the prompt.
- [ ] **FOUND-06**: Sanitisation runs as a script whose final check fails loudly if a known compound name remains anywhere in the dataset, directory names included.

### CASE workflow (FLOW)

- [ ] **FLOW-01**: Coordinator and specialists coordinate along the route chosen in TEAM-01, with the direct channels (LSD engineer ↔ devil's advocate review loop, requests to the NMR chemist) described and logged; gates that can be enforced technically are enforced by hooks or scripts.
- [ ] **FLOW-02**: The skill's use of statistical detection and fragment search matches what FOUND-01/FOUND-03 delivered.
- [ ] **FLOW-03**: Every rule kept from the old skill states the failure it prevents; rules without evidence are removed or marked for measurement.

### Comparison run (MEAS)

- [ ] **MEAS-01**: The reworked skill (full system) has run on the evaluation sample and is compared at rank 1 and top 10 with the old configuration, with run-to-run variation stated.
- [ ] **MEAS-02**: If the user decides so: no-team and no-statistics ablation arms on the same sample, with their contributions reported.

### Repository and hosts (REPO)

- [ ] **REPO-01**: The GitHub repository is `steinbeck/ailsa`; the old URL redirects; the remotes of the local clone and of the compute host's checkout point at the new name.
- [ ] **REPO-02**: The local working copy lives at `~/Dropbox/develop/ailsa`; the auto-memory directory is moved with it so the next session starts with its memory; every absolute path on the Mac (LaunchAgent, symlinks, scripts) is updated.
- [ ] **REPO-03**: `.planning/PROJECT.md`, `STATE.md`, `ROADMAP.md`, `MEMORY.md` and the CASE identity/UAT files speak the new name; `.planning/phases/` history, `milestones/`, git history and the compute host's result directories are untouched.
- [ ] **REPO-04**: A release tag `v11.0` marks the first release under the new name, with a changelog entry explaining the rename.

## Future Requirements

- Backlog items untouched by the rename: sanitiser hardening and the constraint-traceability check (publication needs both), PROV-01, JVAL-F2, spec `49057ef`, tags `v4.0`/`v5.0`.

## Out of Scope

- **Rewriting git history** — the old name stays in every historical commit; the user decided on 2026-09-09 never to rewrite published history.
- **Rewriting `.planning/phases/` and `milestones/`** — 344 files and 6,646 mentions of the old name are the record of how the project was built; they stay.
- **Renaming result directories on the compute host** (`case-uat-results*`) — historical arms, read-only.
- **The manuscript** — lives in the private repository `steinbeck/ailsa-paper`.
- **A new figshare upload** — the 830 MB database file and its DOI stay; only the record's text changes. *(Reopened 2026-10-12: if the public file turns out to be the outdated schema, a re-upload as a new version is open decision 3 — see FOUND-01.)*

## Traceability

| Requirement | Phase |
|-------------|-------|
| PKG-01 | 104 |
| PKG-02 | 104 |
| PKG-03 | 104 |
| PKG-04 | 104 |
| PKG-05 | 104 |
| DOC-01 | 105 |
| DOC-02 | 105 |
| DOC-03 | 105 |
| DOC-04 | 105 |
| FREEZE-01 | 106 |
| SKILL-01 | 106 |
| SKILL-02 | 106 |
| SKILL-03 | 106 |
| SKILL-04 | 106 |
| SKILL-05 | 106 |
| SKILL-06 | 106 |
| EVAL-01 | 107 |
| EVAL-02 | 107 |
| EVAL-03 | 107 |
| TEAM-01 | 107 |
| FOUND-01 | 108 |
| FOUND-02 | 108 |
| FOUND-03 | 108 |
| FOUND-04 | 108 |
| FOUND-05 | 108 |
| FOUND-06 | 108 |
| FLOW-01 | 109 |
| FLOW-02 | 109 |
| FLOW-03 | 109 |
| MEAS-01 | 110 |
| MEAS-02 | 110 |
| REPO-01 | 111 |
| REPO-02 | 111 |
| REPO-03 | 111 |
| REPO-04 | 111 |
