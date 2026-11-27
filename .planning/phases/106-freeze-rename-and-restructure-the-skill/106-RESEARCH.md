# Phase 106: Freeze, rename and restructure the skill - Research

**Researched:** 2026-11-27
**Domain:** packaging and restructuring a Claude Code command/agent skill inside a Python package; lint and benchmark machinery
**Confidence:** HIGH for repository facts and Sheldon state (read directly), MEDIUM for Claude Code behaviour (official docs read, not exercised), MEDIUM for the acceptance-run procedure (not executed)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

Locked by roadmap and requirements, not re-asked: command names `/ailsa:case`, `/ailsa:dereplicate`,
`/ailsa:predict`, `/ailsa:sanitise`, `/ailsa:status`; agent names `ailsa-nmr-chemist`,
`ailsa-lsd-engineer`, `ailsa-solution-analyst`, `ailsa-devils-advocate`, `ailsa-diagnostic`; the
`/lucy-ng:*` commands and the unused supervisor agent are removed with no aliases; skill files
that describe the reference DB carry "COCONUT 13C shifts: from J.-M. Nuzillard, Zenodo,
doi:10.5281/zenodo.6561449, CC BY 4.0" (roadmap note D-17); never name the commercial predictor.

- **D-01: Model check — report, do not compare.** Remove every fixed model ID (`claude-opus-4-8` in the spawn calls and in the mismatch block) and the "MODEL MISMATCH" warning. Each specialist still states its actual runtime model in its first message and the coordinator records it in the progress log. (The pin never worked: the spawn tool accepts aliases only, so every run printed a meaningless warning. The run record of 106.1 captures the model from the launch configuration.)
- **D-02: Rationale instead of emphasis.** Every capital-letter imperative (about 180, 80 of them in the devil's advocate) becomes a plain sentence with the same content. Where the project history shows which failure the rule prevents, add one sentence saying so (the reason replaces the anecdote). Rules without a known reason stay as plain sentences and get a marker for measurement in Phase 109; do not delete or weaken them here.
- **D-03: Rule stays, molecule goes.** Remove every worked example that names a dataset number or a compound (about 25 places in the agent files; the CASE4 example de-blinded a benchmark dataset). The rule stays without the story. Where an example is needed for syntax (e.g. what an LSD line looks like), use atom numbers and shifts only, never a named compound. α-terpineol is deliberately NOT used as an example: it is the public demo dataset and would stop being blind.
- **D-04: Double workflow — reorder only.** The team flow and the headless caveat both keep their content; restructure them for clarity but do not split them into mode-specific files and do not add mode detection. Phase 107 decides the route and Phase 109 rewrites the flow.
- **D-05: Into the package now.** Commands, agents and reference files become package data of `ailsa` (next to `src/ailsa/skills/ailsa-lite/`), so each file moves only once and pip users get the skill that matches their CLI version (`docs/SKILLS.md`, Rule 3). `ailsa skill install ailsa` sets them up for Claude Code: commands under `~/.claude/commands/ailsa/` (giving `/ailsa:*`), agents under `~/.claude/agents/`. A link option creates symlinks into the checkout instead of copies, for the maintainer machines, so edits apply at once. Old `lucy-ng` symlinks are removed.
- **D-06: One run plus a rule inventory.** Besides the one blind run, build an inventory that maps every rule of the old files (byte-identical to `paper-skill-v2`) to its new location, and check it: any rule that is lost, or whose meaning changed beyond D-01..D-03, is reported. No extra model runs for comparison (a 5-dataset before/after check was rejected: too noisy for its cost).
- **D-07: Acceptance run passes when it completes and is graded.** Dataset: a blind benchmark dataset that the old skill solved at rank 1 (not one of the non-blind ones). The rank is reported. If the truth is not at rank 1, inspect the transcript for a restructuring cause (lost or misread rule) versus run-to-run noise (repeat agreement was 11 of 15) and put the finding to the user; the phase does not auto-fail on rank.
- **D-08: Watchdog on vitus in a herdr pane, no LaunchAgent.** Follows the global rule of 2026-11-14 (nothing persistent on the laptop; control services on vitus in their own herdr pane in the lane's space). SKILL-04 and roadmap success criterion 6 say "LaunchAgent re-registered"; reword them accordingly (the plist under `scripts/launchd/` is retired or kept only as history). The pane is started when a measurement series is due and restarted by hand after a vitus reboot.
- **D-09: Update the main Sheldon checkout.** After the restructuring is complete, bring `/mnt/raid_drive/chris/lucy-ng` (the checkout the blind runner uses) to the new state and install the new skill there. This lifts the 106.1-era rule "do not touch the main Sheldon checkout" for this purpose. The paper skill stays recoverable through the tags; result directories under `/mnt/raid_drive/chris/case-uat-results*` stay untouched. The path itself moves only in Phase 111.
- **D-10: Acceptance run on today's configuration.** Opus 5.5 with the current Claude Code (Opus 5.5 needs >= 2.1.280). The watchdog's pinned `CLAUDE_BIN` (2.1.205) is updated; the benchmark environment (Claude Code 2.1.205, LSD 3.5.3, reference DB schema 3, no fragment DB) is recorded in `docs/BENCHMARK.md` as part of FREEZE-01.

Folded todo: `2026-10-14-cli-database-help-shift-credit.md` — `ailsa database download --help` describes the reference DB without the COCONUT shift source credit; add the same credit sentence as the skill files (D-17 wording).

### Claude's Discretion

- File layout inside the package (e.g. `src/ailsa/skills/ailsa/commands/`, `agents/`, `references/`), how the installer handles agents and commands, the link option's name, and a version stamp plus `CHANGELOG.md` for the frontier skill as the lean skill has.
- How each oversized file is split (coordinator 978 lines, diagnostic 1 122, LSD engineer 700, devil's advocate 680): which parts become references and at which named step an agent reads them; one shared LSD reference read by the LSD engineer, the devil's advocate and the diagnostic agent instead of today's copies; tables of contents.
- The single term per role ("coordinator" is the most frequent; "devil's advocate" introduced once with its abbreviation), and removal of the 32 dead `skill/SKILL.md` references.
- Lint implementation: extend the lean skill's pytest checks (`tests/test_skill_lite.py`) to the frontier skill (format, size, TOC, hygiene, dead references); the answer scan reuses `~/Dropbox/develop/ailsa-paper/scripts/blindness/prompt_answer_scan.py` against the private key (`~/Dropbox/develop/data/nmrdata/benchmark-grading-2026-10-01/`), runs locally and before every benchmark, never in CI and never with the key in the repository.
- The rule-inventory format and how meaning changes are checked (e.g. a fresh reviewer instance comparing old and new text rule by rule).
- Which blind dataset the acceptance run uses (within D-07), and keeping the inventory and any dataset identities out of tracked files (the repo is public).
- Git tag names already exist (`paper-skill-v1` = `f9aa7b3`, `paper-skill-v2` = `6d2d126`); keep them, never move them.

### Deferred Ideas (OUT OF SCOPE)

- The global `~/.claude/CLAUDE.md` (all three herdr machines) cites `/lucy-ng:case` as an example of a colon-form plugin command. Update the template in `Claude-Code Session-Manager/claude-global/` and redistribute once `/ailsa:case` exists (outside this repo; the user's session manager).
- Reviewed todos not folded: case4 regiochemistry enumeration gap (Phase 109); 2D picker IndexError on empty spectrum (Phase 108); ranking tests hard-fail without hosegen (Phase 108).
- Also out of scope by the phase boundary: how agents coordinate (107-109), the run-record wiring and removal of the old web view (106.2).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FREEZE-01 | Tags for the two skill states; `docs/BENCHMARK.md` records them with host environment | Tags exist locally and on origin (verified); environment facts verified on Sheldon; section to add and its content in "FREEZE-01" below |
| SKILL-01 | `/ailsa:*` commands, `/lucy-ng:*` gone, symlinks point at new directory | Slash name comes from the path under `commands/`, not from `name:` (docs); installer design in "Packaging" |
| SKILL-02 | `ailsa-*` agents, supervisor removed, SHA guard references new files, `~/.claude/agents` links updated | Agent identity comes from `name:` frontmatter; guard migration in "Existing tests" |
| SKILL-03 | One blind run through the renamed command completes and grades | Runner, env vars, dataset candidates, grading in "Benchmark machinery" |
| SKILL-04 | Runner and watchdog call new command and paths; LaunchAgent re-registered (reword per D-08) | Exact lines to change; vitus-pane replacement; stale items found in the watchdog |
| SKILL-05 | Best-practice form of every skill file | Per-file split plan, counts, lint spec |
| SKILL-06 | Automated lint on every commit plus local answer scan | `tests/test_skill_frontier.py` spec; scan wrapper spec; baseline scan result |
</phase_requirements>

## Summary

The phase is mostly mechanical work wrapped around three genuinely editorial jobs: the splitting of four oversized agent/coordinator files, the merge of two non-identical LSD references into one shared file, and the rewrite of about 240 emphasis words. Everything else (rename, packaging, tests, runner scripts, docs) is well-bounded. The repo's public docs (`README.md`, `docs/INSTALLATION.md`, `docs/SERVER_BOOTSTRAP.md`, `docs/ARCHITECTURE.md`, `CLAUDE.md`) already speak of `/ailsa:*` and `.claude/commands/ailsa/`; they describe the target name but point at a location that never existed, so they need a second correction to the package location and `ailsa skill install ailsa`.

Six findings change what the planner must do and contradict assumptions in CONTEXT.md:

1. **The old files are not byte-identical to `paper-skill-v2`.** Six skill files differ (+179/-116 lines) through two commits of 2026-11-19 (`9377d45`, `6a80d9e`: atom-by-atom ranking, corrected LSD facts). The rule inventory (D-06) must take the files at the start of this phase as its baseline, not the tag. Recommend one new local tag on that commit before any edit.
2. **The frontier skill still calls the deprecated `lucy` CLI alias** (about 150 call sites; the alias prints a warning to stderr), and refers to `lucy-ng-derep.db`, `pip install lucy-ng` and `lucy-ng[webview]`. "Rename" therefore includes `lucy <cmd>` to `ailsa <cmd>`. The existing contract test already matches `ailsa|lucy`.
3. **A `references/` folder inside `commands/ailsa/` would register every reference file as a slash command** (and, since commands merged into skills, as model-invocable items). Today this already happens for `lucy-ng/references/*.md`. Put references outside `commands/`.
4. **Sheldon has moved on:** the pinned Claude Code `2.1.205` no longer exists there (only 2.1.224, 2.1.263, 2.1.331, 2.1.332); the answer files the watchdog locks out are gone (moved 2026-10-29), so its lockout list is stale and its heavy-atom ordering falls back to case-number order; the DB is still schema 3. The main checkout is clean at `5ed443a`, an ancestor of local HEAD, so a fast-forward by git bundle works.
5. **The watchdog cannot work on vitus as is:** its only quota source `~/.claude/usage-snapshot.json` does not exist on vitus, and claude-hud on vitus has no `externalUsageWritePath`. The acceptance run should not use the watchdog at all; call `blind_case_batch.py` directly with the env vars.
6. **Splitting breaks internal "Section N" cross-references** (about 40 in the agent files) and `sanitise.md` is 499 lines, so adding a table of contents pushes it over 500.

**Primary recommendation:** Execute in this order: (a) tag the pre-phase baseline, build the lint and the inventory generator first so every later step is measured; (b) one mechanical commit that `git mv`s everything into `src/ailsa/skills/ailsa/`, renames, removes supervisor, repoints tests; (c) per-file restructuring tasks, each ending with lint, answer scan and inventory diff green; (d) runner/watchdog/docs/BENCHMARK/help-text changes; (e) Sheldon update and one acceptance run on a small blind dataset (recommended: CASE146).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Skill text (commands, agents, references) | Package data (`src/ailsa/skills/ailsa/`) | — | Rule 3 in `docs/SKILLS.md`: skill ships with the CLI it calls |
| Installing the skill into Claude Code | CLI (`ailsa skill install`) | User home (`~/.claude`) | Copy or link; must work from a wheel and from a checkout |
| Lint of skill form | pytest (`tests/`) | — | Runs on every commit; no CI exists (`.github` absent) |
| Answer scan against private key | Local maintainer machine | — | Key must never enter repo or CI or Sheldon |
| Blind run execution | Sheldon (headless `claude -p`) | vitus (control, grading) | Jobs over one minute never on vitus; key lives on the Mac side |
| Quota watchdog | vitus herdr pane | Sheldon (harness) | D-08; needs a local usage snapshot |
| Rule inventory | Private local folder | Generator script in repo | Old text contains benchmark identities; repo is public |

## Standard Stack

No new external packages are needed. Everything below already exists in the repo environment.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| click | pinned in `pyproject.toml` | `ailsa skill` subcommands | existing `src/ailsa/cli/skill.py` |
| importlib.resources | stdlib (Python >= 3.10) | locate package data | existing `_skills_root()` |
| hatchling | build backend | ships package data | wheel build verified: `ailsa/skills/ailsa-lite/**/*.md` is included with no `artifacts` entry [VERIFIED: `uv build --wheel`, zip listing, 2026-11-27] |
| pytest | >= 7 | lint, installer tests | existing; `tests/test_skill_lite.py` is the template |
| RDKit | 2026.03.5 in `~/.venvs/ailsa` | answer scan (inside the paper script) | existing dependency of the scan script |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `prompt_answer_scan.py` | in `~/Dropbox/develop/ailsa-paper/scripts/blindness/` | name and constitution scan | local-only test, run with `python -I` |
| `git bundle` | git | move code to Sheldon without pushing | D-09 and the 106.1 pattern |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Frontier skill as a real skill directory (`SKILL.md`) | commands + agents | Skill names cannot contain `:` so `/ailsa:case` would be lost; locked decisions rule this out |
| Hash table per file in the SHA guard | one committed manifest file of hashes | Table needs editing in Python for every file touched; a `sha256sum`-style manifest is regenerated by one command (recommended, see below) |

**Installation:** none.

**Version verification:** not applicable (no new packages). Existing facts: `ailsa --version` = 0.1.0 locally and on Sheldon [VERIFIED: command output].

## Package Legitimacy Audit

No external package is added in this phase. slopcheck was not run because there is nothing to check. The pinned HOSE generator install (`uv pip install --no-deps git+https://github.com/Ratsemaat/HOSE_code_generator.git@e4ae6c9a...`) is an existing project dependency documented in STATE.md, not new.

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
 src/ailsa/skills/ailsa/                     (package data, single source of truth)
   INDEX.md  CHANGELOG.md
   commands/*.md      agents/ailsa-*.md      references/*.md
        |                   |                      |
        |   ailsa skill install ailsa [--link] [--root ~/.claude] [--force]
        v                   v                      v
 ~/.claude/commands/ailsa/  ~/.claude/agents/   ~/.claude/ailsa/references/
   /ailsa:case ...           ailsa-*.md           (read by commands and agents
        |                         |                with an absolute ~/.claude path)
        |  Task/Agent(subagent_type="ailsa-...")  |
        +------------> specialists <--------------+
                              |
                        ailsa CLI (pick, lsd, predict, identify ...)  -> JSON on stdout

 Benchmark path (headless):
 vitus: ssh + env vars -> Sheldon: blind_case_batch.py -> blind_case_run.sh
        -> claude -p "/ailsa:case <dataset> <MF>" (cwd = scratch) -> results dir
 vitus: rsync results -> grade_blind.py with private truth.tsv -> scorecard
 local: lint + answer scan (key stays on the Mac side, never on Sheldon)
```

### Recommended Project Structure
```
src/ailsa/skills/
├── ailsa-lite/                    # existing
└── ailsa/                         # new (frontier skill)
    ├── INDEX.md                   # frontmatter: name, description, metadata.version; read by `skill list`
    ├── CHANGELOG.md               # each entry says which skill and which measurement supports it
    ├── commands/                  # case.md dereplicate.md predict.md sanitise.md status.md help.md
    ├── agents/                    # ailsa-nmr-chemist.md ailsa-lsd-engineer.md ailsa-solution-analyst.md
    │                              # ailsa-devils-advocate.md ailsa-diagnostic.md
    └── references/                # lsd-reference.md (shared), progress-format.md, loop-patterns.md,
                                   # advisory-templates.md, nmr-basics.md, + the split-off parts
tests/
├── test_skill_lite.py             # FRONTIER constant repointed
├── test_skill_frontier.py         # new lint (this phase)
├── test_skill_answer_scan.py      # new, local-only (skips without key)
├── test_cli_skill.py              # new: installer (there is no test of skill.py today)
└── test_skill_files_unchanged.py  # migrated, see below
```
Notes: `help.md` replaces `lucy-ng.md` (today `/lucy-ng:lucy-ng`, description only "command listing"); naming it `help` gives `/ailsa:help` and a real description (review item 4.4) [recommendation, discretion]. `INDEX.md` instead of `SKILL.md` so Claude Code never treats the folder as a skill if it is copied into a skills directory.

### Pattern 1: Slash name from path, agent name from frontmatter
**What:** A command file's name is its path under `commands/` with `/` turned into `:`; the `name:` field is ignored for command files. Agent identity comes only from `name:` (no `:` allowed, subfolders irrelevant).
**Evidence:** [CITED: code.claude.com/docs/en/skills (naming table) and /slash-commands: "`.claude/commands/frontend/component.md` -> `/frontend:component`"; "Writing `name: foo:bar` in the frontmatter does not produce that name for a command file"] [CITED: code.claude.com/docs/en/sub-agents: "Names can't contain `:`", "Claude Code scans `.claude/agents/` and `~/.claude/agents/` recursively ... identity comes only from the `name` frontmatter field"].
**Consequence:** `commands/ailsa/case.md` gives `/ailsa:case`. Drop the misleading `name: lucy-ng:case` lines (no `name:` in command frontmatter). Agent files keep `name: ailsa-...` and each file name equals its agent name. Current practice (a directory symlink for commands, per-file symlinks for agents) works today on vitus and Sheldon [VERIFIED: `ls -la`, and the benchmark ran through it]; docs say nothing about symlinks, so keep exactly this mechanism in link mode.

### Pattern 2: References outside the commands folder
**What:** Install references to `<root>/ailsa/references/` (e.g. `~/.claude/ailsa/references/lsd-reference.md`), never under `commands/`.
**Why:** Markdown files in a commands subfolder are treated as commands [CITED: docs naming table; no exclusion documented; the docs page itself says "would likely become `/foo:references:x`" is an inference, so tag the stray-command effect MEDIUM]. Today `commands/lucy-ng/references/*.md` are exactly that.
**How referenced:** commands and agents tell the model `Read file: ~/.claude/ailsa/references/<name>.md` at a named step, as `case.md:299` and `lucy-nmr-chemist.md:42` do now with `~/.claude/commands/lucy-ng/references/...`. The `~` form works in today's benchmark runs [VERIFIED by practice]. For `--project` installs the text cannot be both; recommend the installer supports only the user-level root plus an explicit `--root` for tests, and says so in `--help` [ASSUMED acceptable; flag in plan].
**Link mode:** `<root>/ailsa/references` symlink into the checkout's `references/` dir.

### Pattern 3: Installer extension (`src/ailsa/cli/skill.py`)
Current behaviour: `available_skills()` globs `*/SKILL.md`; `install` copytrees into `<harness skills dir>/<name>` and uses `shutil.rmtree` on `--force` (`skill.py:62-80`). There is no test file for it.
Recommended change:
- `available_skills()` also reads `*/INDEX.md` (same regexes) and returns `kind: "commands"` for those.
- `install ailsa` is special-cased by kind: ignores `--target` other than claude (error if another target is given), accepts `--root` (default `~/.claude`) and `--link`.
- Copy mode writes `<root>/commands/ailsa/`, `<root>/agents/ailsa-*.md`, `<root>/ailsa/references/`, `--force` replaces only those paths.
- Link mode: one symlink `<root>/commands/ailsa` -> `<pkg>/commands`; per-file symlinks for the five agents; `<root>/ailsa/references` -> `<pkg>/references`. Refuse link mode if the package is not a checkout (path inside `site-packages`), because links into an installed wheel break on upgrade.
- Legacy cleanup: remove only **symlinks** named `<root>/commands/lucy-ng` and `<root>/agents/{lucy-nmr-chemist,lucy-lsd-engineer,lucy-solution-analyst,lucy-devils-advocate,lucy-diagnostic,supervisor}.md`; a regular file there is reported and left alone. Use `Path.unlink()` for symlinks (never `rmtree` on a link).
- Print what was done, one line per path, and the version from INDEX.md.
**Pitfall:** `shutil.rmtree` on `--force` for the copy path must refuse when the destination is a symlink.

### Pattern 4: Lint file (`tests/test_skill_frontier.py`)
Reuse the structure of `tests/test_skill_lite.py` (frontmatter regex, `FILES = sorted(DIR.rglob("*.md"))`, parametrised tests by file). Checks, each a small function:

| Check | Rule | Notes |
|-------|------|-------|
| size | `len(lines) <= 500` for every md except CHANGELOG | `sanitise.md` is 499 now; a TOC must be paid for by trimming |
| toc | file over 100 lines has a heading `## Contents` within its first 40 lines, and every list item names a heading that exists | agent files use XML-like tags; the TOC is a bullet list of section titles |
| frontmatter commands | `description` present, 1..1024 chars, contains "Use when"; no `name:` key | docs: `name` ignored for command files |
| frontmatter agents | `name` equals file stem, matches `^ailsa-[a-z-]+$`; `description`; no `model:` key | D-01 |
| model ids | no `claude-`, `opus-\d`, `sonnet-\d`, `MODEL MISMATCH` | extend the lean regex |
| history | no `\bPhase \d+`, ISO dates, `\bUAT\b`, `\bBug \d`, ticket-style IDs `\b[A-Z]{2,5}-\d{2}\b` (finds `MULT-04`, `WV-07`, `D-02`), `D-\d+` | gate names such as `G-IDENT`, `G-MULT` and `[BEGIN]`-style message tags do not match and are legitimate |
| datasets | no `\bCASE\d+\b` | 27 hits now, locations below |
| old name | no `lucy-ng`, no `/lucy`, no `\blucy [a-z]` CLI call, no `lucy-` agent name, no `skill/` paths | after the CLI rename the frontier skill must call `ailsa` only |
| dead refs | every `references/<x>.md` mention and `Read file:` path resolves to a packaged file; every `/ailsa:<cmd>` mention has a command file; every `subagent_type="ailsa-..."`/`agent_type=` name has an agent file; an agent file never names another agent's `.md` file (one level rule) | the 32 dead `skill/SKILL.md` references: 19 in `supervisor.md` (deleted with it), 9 in `lucy-diagnostic.md`, 4 in `case.md` |
| section refs | any `Section N` reference points at a heading number that exists in the same file | splitting breaks about 40 of them (see pitfalls) |
| terms | no `orchestrator`, `supervisor`, `team lead`, `Devils-Advocate`, `devils-advocate` except as part of `ailsa-devils-advocate`; `\bDA\b` allowed only in a file that also contains "devil's advocate (DA)" | counts now: coordinator 83, orchestrator 49, supervisor 6, team lead 2, `devils-advocate` 48, `Devils-Advocate` 48, `DA` 25 |
| emphasis | zero of `MUST`, `NEVER`, `ALWAYS`, `MANDATORY`, `BINDING`, `IMPORTANT`, `REQUIRED`, `FORBIDDEN`, `DO NOT`, `CRITICAL` outside fenced code, inline code and `[...]` tags | the devil's advocate uses `CRITICAL/WARNING/INFO` as severity labels 113 times: keep them only in backticks or a labelled table, or rename the labels (decision for the plan; recommend backticks) |
| contract | extend `FRONTIER` in `test_skill_lite.py` to the new tree; replace `skipif(not FRONTIER)` by an assertion that FRONTIER is non-empty | otherwise the lean-vs-frontier contract tests skip silently after the move; `test_skill_lite.py:90-93` globs the old paths |

Run time: the three existing skill test files take 2.3 s together [VERIFIED: pytest run].

### Pattern 5: Answer-scan wrapper (`tests/test_skill_answer_scan.py`)
Skip the whole module unless all hold: `AILSA_ANSWER_KEY_DIR` (default `~/Dropbox/develop/data/nmrdata/benchmark-grading-2026-10-01`) contains `truth.tsv` and the two arm folders; `AILSA_ANSWER_SCAN` (default `~/Dropbox/develop/ailsa-paper/scripts/blindness/prompt_answer_scan.py`) exists; `rdkit` imports. Then run

```python
subprocess.run([sys.executable, "-I", scan, "--truth", f"{key}/truth.tsv",
  "--cases", f"{key}/case-uat-results-opus5-rest", f"{key}/case-uat-results-opus5-baseline",
  "--skills", str(SKILL_DIR)], capture_output=True, text=True, timeout=120)
```
and assert the last summary line ends with `datasets with a hit 0`. On failure print the hit lines (they carry dataset numbers and file:line only, no names) [VERIFIED: script docstring and run]. The key path is read from the environment or the default home path, never stored in the repo. No `.github` directory exists, so there is no CI to exclude, but the skip keeps it that way for any future CI.
**Baseline measured now (old files):** 3 benchmark datasets hit: a name in the devil's advocate worked example (`lucy-devils-advocate.md:527`), names in `sanitise.md` (257, 260, 283) and a constitution match in `sanitise.md:229` [VERIFIED: scan run, output kept at `/private/tmp/claude-501/-Users-christophsteinbeck-Dropbox-develop-lucy-ng/fd48c9f2-8df9-46d2-88a9-2d4c6a122b10/scratchpad/research106/scan-baseline.txt`].
**Gap of the scan:** it only knows the 256 benchmark answers. Example compounds that are not benchmark answers (CASE1-9 teaching set, formulas) are not covered; add a manual pass (grep list below). Also scan `ailsa-lite` with the same call (it is part of the same blindness story); recommended, cheap.

### Pattern 6: SHA-256 guard migration
`tests/test_skill_files_unchanged.py` pins six files by path (`lines 64, 111-127`), has an agent roster test that globs `lucy-*.md` and a supervisor-must-exist assertion (`lines 190-206`). Every new file differs from the old bytes, so the baseline is replaced wholesale. Recommend replacing the dict by a committed manifest `tests/skill_files.sha256` (lines `<hash>  <relative path>`) covering **every** file of `src/ailsa/skills/ailsa/` except CHANGELOG, plus a test that the tree and the manifest list the same paths (this subsumes the roster test; change it to assert supervisor is absent). Regenerate with one command at the end of each task that edits skill text (`(cd src/ailsa/skills/ailsa && find . -name '*.md' ! -name CHANGELOG.md | sort | xargs shasum -a 256) > ...`). Keep the long explanatory docstring's intent (explicit reviewed updates, no loosening) in short form.

### Anti-Patterns to Avoid
- **Editing in place at old paths first, moving later:** moves each file twice and the hash guard fails in between. Move once with `git mv`, rename in the same commit.
- **Installing the link mode mid-phase:** the live symlinks on vitus point at `.claude/commands/lucy-ng`; after the `git mv` they dangle until `ailsa skill install ailsa --link --force` runs. Do the move and the install back to back; do not leave the tree half-moved across sessions.
- **Putting inventory text or identities in `.planning/phases/...`:** the phase folder is tracked and the repo is public.
- **Using `rm -rf` style cleanup in the installer on a symlink**, or deleting regular files in `~/.claude`.
- **Letting `blind_case_run.sh`'s `rm -rf "$CASE_DIR/analysis"` run against a dataset that holds a previous run's analysis:** it is existing behaviour; for the acceptance run confirm the dataset has no `analysis/` first (verified for the candidates below).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Name and structure scan against the answer key | a new scanner | `prompt_answer_scan.py` (wrapper only) | already written, tested on the 256-dataset key, prints only dataset numbers and file:line |
| Grading a blind run | a new grader | `tests/case-benchmark/grade_blind.py` with `CASE_GROUNDTRUTH` | InChIKey first block comparison, rank logic, the earlier `top_smiles` artefact is fixed |
| Locating package data | path arithmetic on `__file__` | `importlib.resources.files("ailsa")` as in `skill.py` | works from wheel and checkout |
| Frontmatter parsing in tests | a YAML dependency | the regex approach of `test_skill_lite.py` | no new dependency; frontmatter is flat |
| Moving code to Sheldon | push to the public remote | `git bundle` + `git fetch <bundle>` + `merge --ff-only` | subagents never push; remote is public |

**Key insight:** the risky part of this phase is textual fidelity, not code. Machine checks (lint, scan, inventory diff) are cheap and fast; model runs are expensive and noisy (D-06 already rejects a before/after run set).

## Per-file facts for the split (item 3)

Line counts at the start of the phase [VERIFIED: wc -l]:

| File | Lines | Splitting proposal (line ranges of today's file) |
|------|------:|---------------------------------------------------|
| `commands/lucy-ng/case.md` | 978 | Core keeps: frontmatter, objective (20-28), `parse_arguments` (30-86), `validate_prerequisites` (88-96), `spawn_case_team` (98-294, includes the web-view launch block 238-282 that 106.2 removes and the headless caveat), `write_progress` (296-329), `validate_message` (418-460), `terminate_team` (942-976). Move out: `timing` (331-416) to `references/timing.md`; `monitor_progress`+`detect_loops`+`diagnose` (462-692) to a loop reference (merge with the existing `loop-patterns.md`, 134 lines, or add `monitoring.md`); `intervene`+`track_and_decide`+`escalate` (694-829); `coverage_gate`+`identity_gate` (831-906) to `references/gates.md`; `smoke_test_report` (916-940). Core lands near 460 lines plus a TOC. Step names in the core point at the reference by name at the step that needs it. |
| `commands/lucy-ng/sanitise.md` | 499 | At the limit; adding a TOC needs trimming. Names at lines 83, 390 (dataset numbers), example SMILES and paths naming a real compound at 229, 257-283; remove them (D-03). |
| `commands/lucy-ng/dereplicate.md` / `predict.md` / `status.md` / `lucy-ng.md` | 88 / 66 / 69 / 43 | Under 100: no TOC. Add the D-17 credit sentence to `dereplicate.md`, `predict.md` and the help command (they describe the database). `status.md:22,30,31` says `pip install lucy-ng`; `status.md:44` reads `data/reference/lucy-ng-derep.db`. |
| `references/advisory-templates.md` | 387 | needs TOC; `:171` has `agent_type="lucy-diagnostic"`; `:299` history line |
| `references/progress-format.md` / `loop-patterns.md` / `nmr-basics.md` | 209 / 134 / 37 | TOC for the first two; `progress-format.md:38-43` carries the "intended: claude-opus-4-8" model lines (D-01); `loop-patterns.md:95,127` history |
| `agents/lucy-nmr-chemist.md` | 450 | under 500, needs TOC; sections 5a (204-233) and 5b (234-316, long multiplicity-ambiguity block) are candidates for a reference to make room |
| `agents/lucy-lsd-engineer.md` | 700 | §1 LSD reference (59-405, about 347 lines) goes to the shared `lsd-reference.md`; §5 constraint inventory (519-638) to `references/constraint-inventory.md`; core about 230 lines |
| `agents/lucy-solution-analyst.md` | 328 | TOC only; `lsd rank` reference (61-104) and identity derivation (184-226) stay |
| `agents/lucy-devils-advocate.md` | 680 | bug checklist and integrity checks (79-258) and inventory validation (273-585, three-check reconciliation 314-563) to references; the `G-IDENT`/`G-MULT` gates (about 460-560) can stay in the core or move; 119 emphasis words |
| `agents/lucy-diagnostic.md` | 1 122 | inlined LSD reference (34-293) to the shared file; zero-solution procedure (296-537) and solution-explosion procedure (538-788) to two references; report template (904-1010) to a reference; `793-808` and `906`, `1008`, `1090` are the dead `skill/...` pointers |
| `agents/supervisor.md` | 484 | delete (not started anywhere; 19 `SKILL` mentions, `model: sonnet` frontmatter) |

**Shared LSD reference is a merge, not a move.** Of the engineer's 258 non-blank lines in §1 and the diagnostic's 187 in its inlined section, only **one** line is identical [VERIFIED: sorted-line `comm`]. The two texts are paraphrases with different organisation (the diagnostic adds per-command failure-focus; the engineer adds DUPL, per-family search, badlist filters, fragment goodlist). Reconciling them is editorial work; keep the union, and where they disagree prefer the engineer's version, which carries the 2026-11-19 corrections (`6a80d9e`, tested against LSD 3.4.9). The devil's advocate's partial copies (for example the HSQC order and `ELIM` rules in `lucy-devils-advocate.md:55-75, 152-247`) should point at the shared file. Budget: the union must stay under 500 lines with a TOC, else split into two files by topic and keep "one shared reference" in the sense of one copy per fact.

**Cross-agent references (two-level):** `lucy-lsd-engineer.md:222-223` and `lucy-devils-advocate.md:486` point into the nmr-chemist file ("Section 5b"). `case.md:311` names `lucy-nmr-chemist.md`. Resolve by moving the multiplicity-ambiguity protocol to a reference that all three name.

**Dataset-number mentions (`\bCASE\d+\b`), by file:line:** `lucy-solution-analyst.md:186`; `lucy-lsd-engineer.md:110,219,225,238,248,266`; `lucy-nmr-chemist.md:240,246,282`; `lucy-devils-advocate.md:465,467,469,479,496,526,554,560,676`; `references/advisory-templates.md:299`; `case.md:209,307,507,837,852,893`; `references/loop-patterns.md:95,127`; `sanitise.md:83,390`.

**Other history markers** (phase numbers, UAT, ticket IDs, dates, "Bug n"): `lucy-lsd-engineer.md:98,110,213,219,281,340,606,662`; `lucy-nmr-chemist.md:234,240,272,274,289,443`; `lucy-diagnostic.md:475,853-855,1012`; `lucy-devils-advocate.md` 21 places at lines 83-209 (the "Bug 1" to "Bug 5" headings 83,104,128,134,140), 245, 454-479, 568-583; `case.md:110,238,244,252,307,507,832,837,883,947`; `advisory-templates.md:299`; `loop-patterns.md:95`.

**Compound-like and example-compound locations (manual pass, the scan does not cover them; some hits are generic formulas):** `lucy-solution-analyst.md:186`; `lucy-lsd-engineer.md:110,227,265,559`; `lucy-nmr-chemist.md:246,285`; `lucy-devils-advocate.md:465,467,527,532,554,676`; `lucy-diagnostic.md:79,353,815,816`; `case.md:62,65,76,893`; `dereplicate.md:39,77,78`; `lucy-ng.md:42,43`; `sanitise.md:33,34,83,92,161,195,198,204,229,240,252,253,256,257,287,322,323,325,390,394,452,479`. In `lucy-diagnostic.md:815-816` an example path and file name use a real dataset name. The syntax examples that replace them use atom numbers and shifts only (D-03).

**Capital-letter emphasis, per file** (counts of `MUST|NEVER|ALWAYS|MANDATORY|BINDING|IMPORTANT|REQUIRED|FORBIDDEN|DO NOT|ONLY|EXACTLY|NOT`; this wide set overcounts because `NOT` and `ONLY` also occur in plain use; the narrower lint set above is the one to enforce): case 74, sanitise 16, advisory-templates 16, loop-patterns 6, progress-format 4, devils-advocate 63 (plus 113 severity labels), diagnostic 17, lsd-engineer 81, nmr-chemist 31, solution-analyst 15. Counting `MUST|NEVER|ALWAYS|MANDATORY|BINDING|IMPORTANT|REQUIRED|FORBIDDEN|DO NOT|CRITICAL|WARNING` gives 239 across the files kept (CONTEXT says about 180; the difference is the word list) [VERIFIED: grep].

**Fixed model IDs:** `case.md:162,174,188,201` (spawn calls), `case.md:219-225` (the `[MODEL]` first-line rule and the "MODEL MISMATCH" block), `references/progress-format.md:38-43`, `lucy-diagnostic.md:1003` ("Specialist model" line, no ID but model wording). No agent file other than `supervisor.md:17` (`model: sonnet`) has a `model:` key [VERIFIED: grep]. After D-01 the spawn calls should omit the `model` argument so specialists inherit the coordinator's model; the docs' resolution order is per-invocation parameter, then agent definition, then `CLAUDE_CODE_SUBAGENT_MODEL`, then the parent's model [CITED: code.claude.com/docs/en/sub-agents]. Note that in practice the coordinator today substitutes the alias `opus`; once the parameter is gone nothing forces an alias, which is the intended inheritance but changes nothing the lint can check.

**CLI call sites:** `lucy <cmd>` appears in every command and agent file (case 13, status 3, predict 2, dereplicate 2, nmr-chemist 16, lsd-engineer 27, solution-analyst 16, devils-advocate 12, diagnostic 1, advisory-templates 3, progress-format 1, supervisor 2) by line-start count; the real number of call sites is higher because several share a line. `ailsa` appears nowhere in these files. `lucy` is a deprecated alias that writes one warning line to stderr [VERIFIED: `src/ailsa/cli/main.py:129-142`; entry points `pyproject.toml:42-44`]. Replace with `ailsa` mechanically and re-run `test_commands_exist` (it checks every shown command against `--help`). Keep `ailsa webview serve|stop|status` text intact in this phase (106.2 removes the web view; `tests/test_case_md_wv07.py` pins `webview serve` before the first `[BEGIN]` push, a `**Dashboard:**` field in `progress-format.md`, and the header-at-run-start sentence; migrate its paths and its `lucy webview` strings to `ailsa webview`, keep its assertions, and leave deletion to 106.2).

## Places that name the old skill (item 2)

| Place | Lines | Class |
|-------|-------|-------|
| `.claude/commands/lucy-ng/*`, `.claude/agents/lucy-*.md`, `supervisor.md` | all | **106**: `git mv` into the package, rename, delete supervisor |
| `tests/test_skill_files_unchanged.py` | 13, 64, 80-81, 112-144, 184-206 | **106**: manifest migration; supervisor assertion inverted |
| `tests/test_case_md_wv07.py` | 13, 26-27 (+ `lucy webview` strings) | **106**: repoint, keep assertions; deleted in 106.2 |
| `tests/test_skill_lite.py` | 90-93 (`FRONTIER`), `skipif` at the contract test | **106**: repoint, make non-silent |
| `tests/case-benchmark/blind_case_run.sh` | 2, 23, 77, 102 | **106**: `/lucy-ng:case` to `/ailsa:case`; comment fixes; `CASE_PROJECT_DIR` comment "lucy-ng repo root" |
| `tests/case-benchmark/blind_case_batch.py` | 3 | **106**: docstring |
| `tests/case-benchmark/README.md` | 3, 33, 41, 51, 54-61 | **106**: command name, `lucy` on PATH to `ailsa`, key-variable table |
| `scripts/uat_watchdog.py` | 44, 60-84 (stale answer files), 73 (model), 79 (CLAUDE_BIN), 405 (`pkill ... /lucy-ng:case`) | **106** (see watchdog section) |
| `scripts/uat_run_remaining.sh`, `scripts/uat_run_baseline_opus5.sh` | whole | **106**: only if they name the old command (the grep found no hit); check the comment at 49 and the truth-table path |
| `scripts/launchd/` (plist label `de.doktor-steinbeck.lucyng-uat-watchdog`, `README.md`) | all | **106**: retire (D-08); keep as history with a note, or remove from the tree (planner's call; recommend keep + a note at the top of its README) |
| `scripts/bootstrap_case_host.sh` | 4, 6-7, 12, 26, 38-48, 76-99, 112-122 | **106**: links `lucy-ng` and `lucy-*.md`, installs `lucy` on PATH, names `/lucy-ng:case`, reads `lucy-ng-derep.db`; replace the linking block by `ailsa skill install ailsa --link`, `lucy` by `ailsa`, DB name per `DatabaseFinder` (accepts both) |
| `docs/SKILLS.md` | 9, 42, "Rule 3" last paragraph | **106**: table row and "still symlinked ... moves when rebuilt" |
| `docs/INSTALLATION.md` | 384-450 | **106**: replace `ln -sfn .../.claude/commands/ailsa` blocks with `ailsa skill install ailsa` |
| `docs/SERVER_BOOTSTRAP.md` | 4, 14, 133-198 | **106**: same |
| `docs/ARCHITECTURE.md`, `README.md:430`, `CLAUDE.md:111-112`, `docs/infographics/README.md:84` | | **106**: point at `src/ailsa/skills/ailsa/`; CLAUDE.md "CASE skill location" and the "Infographic" note |
| `docs/BENCHMARK.md` | add section | **106** (FREEZE-01) |
| `src/ailsa/cli/database.py` `download` docstring | about 219-220 | **106** (folded todo) |
| `.planning/**` mentions | many | **historical, leave** (STATE/ROADMAP/REQUIREMENTS wording of SKILL-04 and criterion 6 is reworded per D-08) |
| `~/.claude/CLAUDE.md` (three machines) | `/lucy-ng:case` example | **deferred** (outside repo, CONTEXT) |
| Sheldon `~/.claude/commands/lucy-ng`, `~/.claude/agents/lucy-*.md` links | | **106** (installer removes them, D-09) |
| LUCY_NO_WEBVIEW (runner `export`, test names) | | **106.2** |

Hits for `src/`: none outside `skill.py`, `main.py` (the `lucy` alias) and database help. `ailsa` Python package has no reference to `.claude/commands`.

## Rule inventory (item 5, D-06)

**Baseline:** the skill files at the start of this phase (`f746297`), **not** `paper-skill-v2`; the two differ [VERIFIED: `git diff --stat paper-skill-v2 HEAD -- .claude` shows 6 files, +179/-116, from commits `9377d45` and `6a80d9e`]. Add one local tag on the baseline commit before any edit (e.g. `skill-pre-restructure`; new tag, existing tags untouched; never push it from an executor). The reading `docs/SKILLS.md` gives ("byte-identical when the tags were set") was true on 2026-08 and is false now; fix that sentence in `docs/SKILLS.md` as part of FREEZE-01.

**Cheap format (two parts):**
1. A tracked generator/checker `scripts/skill_rule_inventory.py` with no skill text inside. It reads old files via `git show <baseline-tag>:<path>` and new files from the package, segments each file into rule units (one list item, numbered step, table row, or sentence containing a normative verb: `must|never|always|do not|only|required|mandatory|binding|critical|stop`, plus every fenced command block as its own unit), normalises whitespace and strips emphasis words and removed-by-decision text (model IDs, dataset numbers, example names), and fuzzy-matches each old unit to the best new unit by token Jaccard with a threshold. Output TSV columns: `id, old_file, old_lines, old_hash12, summary<=120 chars, new_file, new_lines, match_score, status, note, reason_known`. Status values: `same`, `reworded` (score below 0.9), `merged-into-shared`, `moved`, `dropped-by-D01`, `dropped-by-D03`, `LOST`, `CHANGED`.
2. The generated TSV and the reviewer's verdict file live **outside the repo**, in a private folder next to the grading set (suggest `~/Dropbox/develop/data/nmrdata/skill-rule-inventory-106/`, override with `AILSA_RULE_INVENTORY_DIR`), because old unit text carries benchmark identities (see the answer-scan hits). `.planning/research/skill-rebuild/` is untracked but not git-ignored (`git status` shows it as `??`), so it is a risky place.

**Checks:** (a) machine check: no old unit without a row; every `LOST` or score-below-threshold row is printed (this is the "report"); (b) meaning check: a fresh model instance with no repo context gets, for each `reworded`/`CHANGED` pair, the old and new text and returns one of `same`, `weaker`, `stronger`, `lost`, `changed`, with D-01, D-02 and D-03 stated as the only permitted differences; its output is saved beside the TSV; (c) rules without a known reason get `reason_known=no` in the TSV, which is the Phase 109 measurement marker. Recommend keeping the marker in the inventory rather than as text inside the shipped skill (shipped markers cost agent tokens and clash with the history lint). If the planner prefers an in-text marker, use an HTML comment and exempt it in the lint.

No model run is needed for (a); (b) is a single reviewer pass, in line with D-06 (no before/after run set).

## Benchmark machinery (item 6)

**How one blind run starts today** [VERIFIED: `tests/case-benchmark/blind_case_batch.py`, `blind_case_run.sh`, README, `scripts/uat_watchdog.py`]:
- `blind_case_batch.py <CASE...> -k N --mode full --results DIR` on Sheldon inside `/mnt/raid_drive/chris/lucy-ng` with `.venv` activated; it takes **environment variables**, not flags: `CASE_DATA_DIR` (required; missing it yields `skip(no-dataset)` for every case), `CASE_RESULTS_DIR`, `CASE_ANSWERKEY_PATHS` (colon list stashed for the batch; unset means no lockout and only a log line says so), `CASE_STASH_DIR`, `CASE_ANSWERKEY_DIR` (named in the prompt fence), `CLAUDE_MODEL` (required, exit 2 if unset), `CLAUDE_BIN`, `CASE_RUN_MAX_ATTEMPTS/CALL_TIMEOUT/DEADLINE_S` (8 / 3600 / 9000).
- The runner starts `claude -p "/lucy-ng:case $CASE_DIR $MF" --session-id ... --model $CLAUDE_MODEL --dangerously-skip-permissions --append-system-prompt "$FENCE" --add-dir $CASE_DIR` in a scratch cwd, then `--resume` nudges until `analysis/final_results.md` exists, then moves `analysis/` into the results dir and writes `meta.json`. It also exports `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` and `LUCY_NO_WEBVIEW=1`. Only the command string at `blind_case_run.sh:102` changes in 106; the fence text and the headless wording stay.
- The runner puts `$CASE_PROJECT_DIR/.venv/bin` on PATH; on Sheldon that directory has both `ailsa` and `lucy` [VERIFIED: ls]. After the skill calls `ailsa`, nothing in `~/.local/bin` is needed for the blind run; for interactive use add an `ailsa` link next to the existing `lucy` link there.

**Grading** [VERIFIED: `grade_blind.py` header, grading folder listing]: `CASE_GROUNDTRUTH=<truth.tsv> python tests/case-benchmark/grade_blind.py --results DIR`; needs RDKit (`~/.venvs/ailsa` has it; Sheldon's system Python does not). The key moved off Sheldon on 2026-10-29: `nmr-dataset-assembly/` on Sheldon now holds only progress and batch logs [VERIFIED: ls]. So grading happens on vitus: copy the finished results dir from Sheldon to a vitus scratch folder, grade against `~/Dropbox/develop/data/nmrdata/benchmark-grading-2026-10-01/truth.tsv` (columns `case, smiles, mf, inchikey, name, verdict`; contains the `inchikey` column the grader needs). Print only case number, verdict and rank.

**Dataset choice (D-07).** Candidates computed from the private scorecards: blind (excluding the non-blind set 86, 87, 93, 119, 120, 121, 133, 265, the retired 217, and the compound used as the sanitiser example), rank 1 in the Opus 5 campaign or re-run arms, one attempt, short runtime, with heavy-atom count from the teaching index [VERIFIED: computed; output carried dataset numbers only]:

| Dataset | Heavy atoms | Runtime (old run) | Note |
|---------|------------:|------------------:|------|
| CASE146 | 19 | 1 763 s, 1 attempt | **recommended**: big enough to exercise several iterations and the diagnostic path less trivially than the 11-atom cases |
| CASE142 | 12 | 1 230 s | cheapest fallback |
| CASE110 | 11 | 1 260 s | fallback |
| CASE132 | 21 | 1 589 s | alternative |

All four exist in `/mnt/raid_drive/chris/case-data` on Sheldon, have no leftover `analysis/` directory and have a formula file [VERIFIED: ssh test]. The "old skill" for the rank-1 claim is the benchmark skill (tag state), while today's master already carries the 2026-11-19 ranking change; mention this when reporting a rank different from 1 (restructuring cause versus the intervening ranking change versus noise).

**Sheldon update (D-09)** [VERIFIED state]: main checkout `/mnt/raid_drive/chris/lucy-ng` is clean on `master` at `5ed443a` (2026-11-24), an ancestor of local HEAD; `.venv/bin` has `ailsa` (0.1.0) and `lucy`; `~/.claude/commands/lucy-ng` and five `~/.claude/agents/lucy-*.md` are symlinks into that checkout. No benchmark batch is running and `~/.case-uat-stash` does not exist. Procedure: `git bundle create` on vitus for `5ed443a..master`, `scp -P 2222` the bundle to Sheldon (outside the checkout), in the checkout `git fetch <bundle> master` then `git merge --ff-only FETCH_HEAD`, `uv pip install --python .venv/bin/python -e .` (venv built with uv per STATE.md), then `.venv/bin/ailsa skill install ailsa --link --force`. Never push from an executor; the remote is public. Verify afterwards: `ailsa skill list`, `ls -la ~/.claude/commands ~/.claude/agents | grep -i "ailsa\|lucy"`, `ailsa lsd check`, `ailsa predict c13 CCO --format json`, `ailsa database info` (schema 3, 928 443 compounds).
**Database for the run:** the host DB is schema 3 (no hybridisation or neighbour statistics) [VERIFIED: `ailsa database info` on Sheldon]; a schema-7 DB exists at `/mnt/raid_drive/chris/ailsa-db/ailsa-derep.db` (used by the 106.1 gate). Recommend leaving the main checkout's DB untouched for the acceptance run so the recorded benchmark environment (schema 3) still describes it, and stating in the report that detection statistics return no data there. Tell the user; switching DB would add a variable the phase does not need.

**Watchdog (`scripts/uat_watchdog.py`)** [VERIFIED by reading]:
- `REMOTE_ENV["CLAUDE_BIN"]` (line 79) pins `/home/chris/.local/share/claude/versions/2.1.205`, which **does not exist** on Sheldon; installed: 2.1.224, 2.1.263, 2.1.331, 2.1.332. `preflight()` (line 550-558) would halt with "not executable". Update to `.../versions/2.1.332` (the version of the local `claude`, `2.1.332`; Opus 5.5 needs >= 2.1.280), and rewrite the explanatory comment (lines 74-79): the pin now keeps the acceptance and later series comparable, the 2.1.205 baseline is recorded in `docs/BENCHMARK.md`. Same value for `blind_case_run.sh` callers via env.
- `CLAUDE_MODEL` (line 73) is `claude-opus-5`; for an Opus 5.5 series use `claude-opus-5-5` [ASSUMED id: docs show `claude-opus-5-5` as a full model ID; confirm with one `claude -p hi --model claude-opus-5-5` on Sheldon before the run].
- Line 405: `pkill -KILL -f '[c]laude -p /lucy-ng:case'` becomes `/ailsa:case`; otherwise abort path leaves old-name processes unmatched.
- `REMOTE_TRUTH_PATHS` / `REMOTE_TRUTH` (lines 60-66, 84, 90): files no longer on Sheldon, so the lockout is a silent no-op and `uat_run_remaining.sh` orders by case number instead of heavy atoms (it falls back by design). Leave the code, update the comment, and do not claim lockout protects the run: blindness now rests on the key being absent from the host.
- `REMOTE_REPO` stays `/mnt/raid_drive/chris/lucy-ng` (moves only in Phase 111); `REMOTE_HARNESS` stays.
- Quota source: `~/.claude/usage-snapshot.json` does not exist on vitus and vitus's claude-hud config has no `externalUsageWritePath` [VERIFIED: ls, grep]. A watchdog pane on vitus therefore halts (stale snapshot over 12 h halts for real). For the acceptance run bypass the watchdog and start the batch directly (one dataset, `-k 1`). For later series, set `externalUsageWritePath` in vitus's claude-hud config and note that the statusline must render in an interactive vitus session. The launch itself: `herdr pane split --current --direction down --cwd "$PWD" --no-focus`, then `herdr pane run <pane> "python scripts/uat_watchdog.py ..."` (herdr 0.9.5 is installed on vitus [VERIFIED]); document it in a new short `scripts/` README replacing `scripts/launchd/README.md`'s role. No LaunchAgent is registered on vitus [VERIFIED: `~/Library/LaunchAgents` has no lucy entry].

## FREEZE-01 (item 7)

- Tags: `paper-skill-v1` (annotated, points at `f9aa7b3ccddf...`) and `paper-skill-v2` (annotated, points at `6d2d126f44b1...`) exist locally and on `origin` [VERIFIED: `git rev-parse`, `git ls-remote --tags origin`]. Nothing to create. Do not move them.
- `docs/BENCHMARK.md` today has no mention of the tags, of Claude Code 2.1.205, of LSD 3.5.3 or of "no fragment DB"; it mentions the outdated schema only in prose (line 50: "outdated schema ... statistics returned no usable data") [VERIFIED: grep].
- Add a section "Benchmark environment and skill states" after "How a benchmark run executes" (before "How blindness is enforced"). Rows: skill state 1 (`paper-skill-v1`, 45 runs 2026-08-11..14), state 2 (`paper-skill-v2`, 211 runs, adds the heteroatom-proton HSQC rule `d62d833`), Claude Code 2.1.205 [CITED: `scripts/uat_watchdog.py:74-79` and `blind_case_run.sh` pin comments; the baseline arm used 2.1.204/205; the binary is no longer on the host], LSD 3.5.3 [VERIFIED: `~/opt/LSD-3.5.3` on Sheldon; installed 2026-06-30 per the audit note], reference DB schema 3, 928 443 compounds, file of 3 130 183 680 bytes [VERIFIED: `ailsa database info`, `ls`], fragment database not installed [CITED: audit of 2026-10-09 in the private notes; every run that checked reported it unavailable], execution mode headless without team (already in the section above), model alias note (specialists inherited Opus 5 through the `opus` alias).
- Also fix `docs/SKILLS.md:35-42` ("still byte-identical ... when the tags were set") and mention the pre-restructure tag, and update the tag-worktree paragraph (`.claude/commands/lucy-ng/` and `.claude/agents/lucy-*.md` are the paper skill's file locations in that tree).

## Folded todo (item 8)

`ailsa database download` is defined at `src/ailsa/cli/database.py:202-216` (decorators) and its docstring starts after `def download(...)` at line 216; the todo cites lines 219-220 with the text "928K compounds (COCONUT + NMRShiftDB) with 13C NMR shifts and 7.9M HOSE statistics" [VERIFIED: file read; exact docstring lines to be confirmed by the executor]. Add one paragraph: "The COCONUT 13C shifts are predicted, not measured; the NMRShiftDB shifts are experimental. COCONUT 13C shifts: from J.-M. Nuzillard, Zenodo, doi:10.5281/zenodo.6561449, CC BY 4.0." (ASCII `13C`). Check `tests/` for a snapshot of this help text and add a test: `CliRunner().invoke(cli, ["database", "download", "--help"])` output contains `zenodo.6561449` and `predicted`. Never name the commercial predictor.

## Common Pitfalls

### Pitfall 1: Contract test silently skips after the move
**What goes wrong:** `tests/test_skill_lite.py:90-93` builds `FRONTIER` from the old paths and `@pytest.mark.skipif(not FRONTIER ...)`. After the move the list is empty and `test_same_tools_as_frontier_skill` skips; Rule 2 of `docs/SKILLS.md` stops being enforced with no failure.
**How to avoid:** repoint, and assert non-empty. **Warning sign:** a skipped test in the skill test run.

### Pitfall 2: `references/` inside `commands/` registers commands
See Pattern 2. **Warning sign:** `/ailsa:references:...` entries in the `/` menu.

### Pitfall 3: Section cross-references break
Agent files cite their own sections by number (about 40 occurrences, e.g. `lucy-nmr-chemist.md:279,439-446`, `lucy-lsd-engineer.md:222,645,663,676`, `lucy-devils-advocate.md:287,295,300,424,486,575,654-666`, `lucy-solution-analyst.md:94,315`). Splitting moves the targets. **How to avoid:** replace numbered cross-references by named references ("the three-check reconciliation in `references/...`") while restructuring, and lint "Section N" targets.

### Pitfall 4: TOC pushes `sanitise.md` over 500
It is at 499 lines. Trim (remove the example block with named compounds, lines 229-283) before adding a TOC.

### Pitfall 5: The old text is not the paper skill
See Summary 1. Do not describe the baseline as "byte-identical to `paper-skill-v2`" in any new document; say "the skill at the start of Phase 106, which includes two changes made after the benchmark".

### Pitfall 6: Rewriting emphasis can change behaviour
Phase 110 will measure it; this phase keeps content. Use the inventory to catch weakened rules; convert "NEVER x" to "Do not x, because ..." keeping the negation, never to "avoid x" or "prefer y".

### Pitfall 7: Symlinks and the live session
The skill loads at session start. Between the `git mv` and the install, new sessions on vitus see no `/ailsa:*` and a dangling `/lucy-ng`. Do the install right after the move (link mode on vitus), then keep working. Executors run sequentially on the main checkout (no worktrees): the editable install and `python -I` ignore `PYTHONPATH`.

### Pitfall 8: Sheldon quota and run bookkeeping
`blind_case_run.sh` deletes `$CASE_DIR/analysis` before the run and moves it afterwards; use a fresh results dir (e.g. `/mnt/raid_drive/chris/case-uat-results-106`), never an existing `case-uat-results*` (D-09 keeps those untouched). A killed batch skips its `finally`; with no answer paths set nothing is stashed, so nothing to restore. Never `pkill -f blind_case_batch.py` from an ssh command containing that string (use the `[b]` bracket form).

### Pitfall 9: Acceptance run must not depend on vitus uptime
The batch runs under `nohup` on Sheldon and writes its log there; a run takes about 30 to 60 minutes for the recommended dataset; judge progress by files in `analysis/`, not by log lines ("Execution error" is the call-timeout message, not a fault) [CITED: `blind_case_run.sh` comments, private ops notes].

### Pitfall 10: Full test suite on vitus
Jobs over one minute never on vitus: `tests/record` alone takes about 70 s. Run only the skill tests (about 3 s) and `tests/test_cli_skill.py` locally; run the whole suite on Sheldon in `/mnt/raid_drive/chris/ailsa-106.1/` with its own venv (code by bundle). The last full run there: 47 failed, 1 432 passed at the "baseline" checkout, and "1953 passed, 5 failures identical at baseline (webview extra missing)" at the end of 106.1 per STATE.md. Fresh venvs need the pinned HOSE generator or ranking and prediction tests fail; `run_gate.sh` there sets `LUCY_DATABASE`, `AILSA_EXAMPLE_TERPINEOL`, `AILSA_WORKSPACE` [VERIFIED: file read]. Compare against that baseline rather than expecting all green.

## Code Examples

### Installer skeleton
```python
# Source: derived from src/ailsa/cli/skill.py (existing) and the layout above
LEGACY_AGENT_LINKS = ["lucy-nmr-chemist", "lucy-lsd-engineer", "lucy-solution-analyst",
                      "lucy-devils-advocate", "lucy-diagnostic", "supervisor"]

def _link(src: Path, dst: Path, force: bool) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_symlink():
        dst.unlink()                      # never rmtree a link
    elif dst.exists():
        if not force:
            raise click.ClickException(f"{dst} exists and is not a link; use --force")
        _remove(dst)                      # regular file or dir, explicit --force only
    dst.symlink_to(src)

def _drop_legacy(root: Path) -> list[str]:
    done = []
    for p in [root / "commands" / "lucy-ng",
              *[root / "agents" / f"{n}.md" for n in LEGACY_AGENT_LINKS]]:
        if p.is_symlink():
            p.unlink(); done.append(str(p))
        elif p.exists():
            click.echo(f"left alone (not a link): {p}")
    return done
```

### Lint: emphasis and old-name checks
```python
# Source: pattern of tests/test_skill_lite.py
EMPHASIS = re.compile(r"\b(MUST|NEVER|ALWAYS|MANDATORY|BINDING|IMPORTANT|REQUIRED|FORBIDDEN|CRITICAL|DO NOT)\b")
def _prose(text: str) -> str:
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)    # fenced code
    text = re.sub(r"`[^`\n]*`", "", text)                      # inline code
    return re.sub(r"\[[A-Z][A-Z0-9 _/-]+\]", "", text)         # [BEGIN]-style tags

@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_no_emphasis_words(path):
    assert not EMPHASIS.search(_prose(path.read_text()))

OLD_NAME = re.compile(r"lucy-ng|/lucy\b|\blucy [a-z]|\blucy-[a-z]|skill/")
```

### Link-mode install result to verify by hand
```bash
ailsa skill install ailsa --link --force
ls -la ~/.claude/commands/ailsa ~/.claude/ailsa/references ~/.claude/agents/ailsa-*.md
# expect symlinks into <checkout>/src/ailsa/skills/ailsa/...; no lucy-* entries left
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `.claude/commands/` files | Skills (`SKILL.md`) preferred; commands "merged into skills" and still work | current docs | keep commands because the `:` namespace needs the path rule; commands are also model-invocable by default |
| `name:` in command frontmatter | ignored for commands; path decides | current docs [CITED] | remove the misleading `name: lucy-ng:case` lines |
| Subagent model pin in file | optional `model:`; per-invocation parameter accepts aliases only | docs | no `model:` in any ailsa agent (D-01) |
| `lucy` CLI | `ailsa` CLI, `lucy` deprecated alias | Phase 104 | frontier skill still on the alias |

**Deprecated/outdated:** the LaunchAgent for the watchdog (D-08); `Claude Code 2.1.205` pin (binary gone); the benchmark answer files in `nmr-dataset-assembly` on Sheldon (gone).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `claude-opus-5-5` is the right `--model` value for the acceptance run | Watchdog | run refuses to start; one probe fixes it |
| A2 | Files placed outside `commands/` and `agents/` (under `~/.claude/ailsa/`) are not scanned or listed by Claude Code | Pattern 2 | harmless extra entries; fall back to a differently named dir |
| A3 | Markdown reference files inside a commands subfolder become commands (docs table implies it; no exclusion documented) | Pattern 2 | if false, the argument for a separate folder is weaker but still harmless |
| A4 | Project-level (`--project`) install can be left unsupported for the frontier skill because the reference path in the text is user-level | Pattern 2 | pip users who want project scope are not served in 106 |
| A5 | `help.md` replaces `lucy-ng.md` as the overview command | Structure | one more command name for the user; trivial to change |
| A6 | Claude Code 2.1.205 was the version for the whole Opus 5 campaign (requirement text and pin comments; binary no longer present to confirm) | FREEZE-01 | environment table slightly wrong; check one run log if available |
| A7 | Keeping the host DB at schema 3 for the acceptance run is what the user wants | Benchmark machinery | the user may prefer the schema-7 DB; both are available on Sheldon |
| A8 | Skill version number for the first packaged frontier skill (suggest 0.1.0) | Packaging | cosmetic |

## Open Questions

1. **Which environment does the acceptance run use for the database (v3 vs v7)?**
   - What we know: host DB is v3; a v7 copy exists on Sheldon; D-10 says "today's configuration".
   - What's unclear: whether "today's" means the benchmark host as recorded or the current best.
   - Recommendation: v3, unchanged, because FREEZE-01 records v3 and the point is the chain, and say so in the report.
2. **Do `Agent(...)` calls in `case.md` need `model` at all after D-01?**
   - What we know: docs resolution order; today's coordinator passes the alias `opus`.
   - Unclear: whether omission changes which model the specialists get in headless runs (they should inherit the session model).
   - Recommendation: omit; the first message of each specialist reports its runtime model (D-01), so the acceptance run itself shows the result.
3. **How is the pre-restructure baseline tagged?** Recommendation: one new local tag, not pushed by an executor; the user pushes tags with the rest.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python + `~/.venvs/ailsa` with RDKit | lint, answer scan, grading | yes | 3.12.15, RDKit 2026.03.5 | — |
| `uv` | wheel check, Sheldon venv | yes | present | pip |
| `claude` CLI on vitus | probing model id | yes | 2.1.332 | — |
| `herdr` on vitus | watchdog pane | yes | 0.9.5 | — |
| Answer-key folder `benchmark-grading-2026-10-01` | answer scan, grading | yes (vitus) | 2026-10-01 set | scan test skips when absent |
| `prompt_answer_scan.py` | answer scan | yes | in `ailsa-paper/scripts/blindness/` | skip |
| Sheldon access `ssh sheldon` | update, acceptance | yes | load average about 14 at 08:45, GPUs idle | check `uptime` before the run (global rule) |
| Claude Code on Sheldon | acceptance run | yes | 2.1.331, 2.1.332 (needs >= 2.1.280) | — |
| LSD on Sheldon | acceptance run | yes | 3.5.3 at `~/opt/LSD-3.5.3` | — |
| Reference DB on Sheldon | acceptance run | yes | schema 3 | v7 at `/mnt/raid_drive/chris/ailsa-db/` |
| Claude Code login on Sheldon | acceptance run | not re-verified | — | `/login` needed once (STATE notes) |
| vitus usage snapshot | watchdog | **no** | — | bypass watchdog for the acceptance run; configure claude-hud later |
| Pinned `claude` 2.1.205 on Sheldon | old watchdog pin | **no** | — | pin 2.1.332 |

**Missing with fallback:** usage snapshot on vitus, 2.1.205 binary. **Missing with no fallback:** none.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >= 7 (`pyproject.toml` `[tool.pytest.ini_options]`, `testpaths = ["tests"]`, `pythonpath = ["src"]`) |
| Config file | `pyproject.toml` |
| Quick run command | `~/.venvs/ailsa/bin/python -m pytest tests/test_skill_lite.py tests/test_skill_frontier.py tests/test_skill_files_unchanged.py tests/test_cli_skill.py tests/test_case_md_wv07.py -q` (about 3 s now, three of these files exist) |
| Full suite command | on Sheldon only: `/mnt/raid_drive/chris/ailsa-106.1/run_gate.sh` pattern (own venv, pinned hosegen, `LUCY_DATABASE`, niced); also `ruff check src tests` and `mypy src/ailsa` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FREEZE-01 | tags exist and resolve to the two commits; BENCHMARK.md lists them and the environment | unit | `pytest tests/test_freeze.py -q` (git rev-parse, grep of the doc for the five facts) | Wave 0 gap |
| SKILL-01 | all five commands present as `commands/<name>.md`; installer produces `commands/ailsa/*.md`; no `lucy-ng` link remains | unit (tmp_path root) | `pytest tests/test_cli_skill.py -q` | Wave 0 gap |
| SKILL-02 | five agent files, names match, supervisor absent, manifest matches tree | unit | `pytest tests/test_skill_files_unchanged.py -q` | migrate |
| SKILL-03 | one blind run completes and grades | manual (Sheldon, about 30-60 min) | start batch with env vars; grade on vitus | manual |
| SKILL-04 | runner and watchdog name `/ailsa:case`; no `lucy-ng` in `scripts/` or `tests/case-benchmark/`; CLAUDE_BIN path exists check in preflight | unit (grep) + dry-run | `pytest tests/test_benchmark_scripts.py -q`; `python scripts/uat_watchdog.py --help`; the watchdog's `DRY-RUN` path | Wave 0 gap |
| SKILL-05 | size, TOC, hygiene, dead refs, terms, emphasis, frontmatter | unit | `pytest tests/test_skill_frontier.py -q` | Wave 0 gap |
| SKILL-06 (lint) | lint on every commit | unit | same as above | Wave 0 gap |
| SKILL-06 (scan) | no benchmark compound by name or structure | local-only unit | `pytest tests/test_skill_answer_scan.py -q` (skips without key) | Wave 0 gap |
| Contract (Rule 2) | every `ailsa ...` shown by the frontier skill exists | unit | `pytest tests/test_skill_lite.py -q` | exists; repoint |
| Folded todo | help text carries credit | unit | `pytest tests/test_cli_database_help.py -q` (or an existing database CLI test) | Wave 0 gap |
| D-06 | inventory has no LOST rows | script + reviewer | `python scripts/skill_rule_inventory.py --check` (private output dir) | Wave 0 gap |

### Sampling Rate
- **Per task commit:** the quick run command above (about 3 s) plus `ruff check` on touched files.
- **Per wave merge:** the quick run plus `python scripts/skill_rule_inventory.py --check` and, locally, the answer scan.
- **Phase gate:** full suite on Sheldon equal to or better than the recorded baseline (compare failures with the baseline list); answer scan 0 hits; acceptance run graded; before `/gsd:verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_skill_frontier.py` — SKILL-05/06 lint
- [ ] `tests/test_skill_answer_scan.py` — local-only scan wrapper
- [ ] `tests/test_cli_skill.py` — installer: copy mode, link mode (tmp root), legacy cleanup touches only symlinks, refuses link mode from site-packages, `--force` semantics
- [ ] `tests/test_freeze.py`, `tests/test_benchmark_scripts.py` — small grep-style contract tests
- [ ] `scripts/skill_rule_inventory.py` and its tests on a synthetic old/new pair (no real text)
- [ ] `tests/skill_files.sha256` manifest and generator command in the test docstring
- [ ] Wheel-contents check: build with `uv build --wheel` and list `ailsa/skills/ailsa/**` (manual or marked slow; builds took well under two minutes here)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | partly | answer key never on Sheldon, never in repo; local-only scan; private inventory folder |
| V5 Input Validation | yes | installer validates names against the package index; refuses paths outside `--root` |
| V6 Cryptography | no | SHA-256 manifest uses `hashlib` only as an integrity check |
| V12 Files and resources | yes | symlink handling: unlink links, never `rmtree` through them; refuse overwriting regular files without `--force`; no writes outside `<root>` |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Skill text tampering (agents execute it autonomously) | Tampering | hash manifest over the whole tree plus review of every diff |
| Answer-key leak into tracked files (public repo) | Information disclosure | private inventory folder; scan before every benchmark; `git status` check that nothing from the key folder was added |
| Symlink following in installer/`--force` | Tampering | `is_symlink()` before `exists()`, `unlink()` for links |
| Benchmark identity in dataset directory names or example text | Information disclosure | lint for `CASE\d+`, scan for names, manual pass for non-benchmark examples |
| Stale answer-lockout paths giving false assurance | Repudiation | state in docs that lockout is a no-op now; rely on the key being absent from Sheldon |
| Subagent pushing to the public remote | Tampering | every subagent prompt says "do not push"; D-09 uses a bundle |

## Sources

### Primary (HIGH confidence)
- Repository files read directly: `.claude/**`, `src/ailsa/cli/skill.py`, `src/ailsa/cli/main.py`, `pyproject.toml`, `tests/test_skill_lite.py`, `tests/test_skill_files_unchanged.py`, `tests/test_case_md_wv07.py`, `tests/case-benchmark/*`, `scripts/uat_watchdog.py`, `scripts/uat_run_remaining.sh`, `scripts/bootstrap_case_host.sh`, `scripts/launchd/README.md`, `docs/SKILLS.md`, `docs/BENCHMARK.md`, `.planning/phases/106-*/106-CONTEXT.md`, `.planning/phases/106.1-*/106.1-CONTEXT.md`, ROADMAP, REQUIREMENTS, STATE.
- Live checks (2026-11-27): `uv build --wheel` and zip listing; git tags local and on origin; `git diff --stat paper-skill-v2 HEAD -- .claude`; pytest run of the three skill test files (25 passed in 2.3 s); `prompt_answer_scan.py` run against the private key; Sheldon read-only listings (`git log`, `ls`, `ailsa database info`, `ls ~/opt`, `uptime`).

### Secondary (MEDIUM confidence)
- https://code.claude.com/docs/en/skills and /slash-commands: naming rule for command subdirectories, `name` ignored for command files, commands merged into skills (fetched; page text longer than the fetched part, last 21 000 characters not read).
- https://code.claude.com/docs/en/sub-agents: agent locations, recursive scan, `name` rules, `model` resolution order (fetched; last 14 800 characters not read). The docs say nothing about symlinked agent or command files and nothing about `${CLAUDE_SKILL_DIR}` in command files; the project's own working setup is the evidence for symlinks.

### Tertiary (LOW confidence)
- Private notes: `project_blind_uat_benchmark_ops.md`, `project_benchmark_blindness_audit.md` (auto-memory) for the watchdog history, the fragment-DB and schema-3 facts, and the traps; claims copied from them are tagged CITED where used.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH, nothing new and the wheel behaviour was tested.
- Architecture (layout, installer): MEDIUM, design is a recommendation; Claude Code behaviours for references outside `commands/` are inferred.
- Pitfalls: HIGH for the repo and Sheldon facts, MEDIUM for model-resolution behaviour in headless runs.
- Benchmark procedure: MEDIUM, not executed; dataset candidates computed from the private scorecards.

**Research date:** 2026-11-27
**Valid until:** about 14 days for Sheldon state (Claude Code versions, checkout position), 30 days for the rest
