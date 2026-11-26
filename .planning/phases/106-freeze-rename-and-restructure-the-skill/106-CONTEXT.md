# Phase 106: Freeze, rename and restructure the skill - Context

**Gathered:** 2026-11-26
**Status:** Ready for planning

<domain>
## Phase Boundary

The frontier CASE skill (coordinator `case.md`, the four specialists, the diagnostic agent and the
small commands) carries the AILSA name, lives in the `ailsa` package like the lean skill, and
follows Anthropic's skill-authoring best practices in form: every file under 500 lines with
details in one-level reference files (one shared LSD reference), a table of contents in files over
100 lines, no dead references, no project history, no dataset numbers or benchmark compounds, no
fixed model IDs, one term per role, rationale instead of capital-letter emphasis. A pytest lint
enforces this on every change; a local scan checks the skill against the private answer key. The
benchmark skill states stay recoverable (tags exist; the host environment is still to be recorded).
One blind run on Sheldon through `/ailsa:case` proves the renamed chain.

Content-preserving restructuring only. How the agents coordinate (team vs headless route), which
tools they use and which rules survive are Phases 107-109. The run record is wired into the
frontier skill in Phase 106.2, and the old web view is removed there, not here.

</domain>

<decisions>
## Implementation Decisions

Locked by roadmap and requirements, not re-asked: command names `/ailsa:case`, `/ailsa:dereplicate`,
`/ailsa:predict`, `/ailsa:sanitise`, `/ailsa:status`; agent names `ailsa-nmr-chemist`,
`ailsa-lsd-engineer`, `ailsa-solution-analyst`, `ailsa-devils-advocate`, `ailsa-diagnostic`; the
`/lucy-ng:*` commands and the unused supervisor agent are removed with no aliases; skill files
that describe the reference DB carry "COCONUT 13C shifts: from J.-M. Nuzillard, Zenodo,
doi:10.5281/zenodo.6561449, CC BY 4.0" (roadmap note D-17); never name the commercial predictor.

### How far the text may change
- **D-01: Model check — report, do not compare.** Remove every fixed model ID (`claude-opus-4-8` in
  the spawn calls and in the mismatch block) and the "MODEL MISMATCH" warning. Each specialist
  still states its actual runtime model in its first message and the coordinator records it in the
  progress log. (The pin never worked: the spawn tool accepts aliases only, so every run printed a
  meaningless warning. The run record of 106.1 captures the model from the launch configuration.)
- **D-02: Rationale instead of emphasis.** Every capital-letter imperative (about 180, 80 of them in
  the devil's advocate) becomes a plain sentence with the same content. Where the project history
  shows which failure the rule prevents, add one sentence saying so (the reason replaces the
  anecdote). Rules without a known reason stay as plain sentences and get a marker for measurement
  in Phase 109; do not delete or weaken them here.
- **D-03: Rule stays, molecule goes.** Remove every worked example that names a dataset number or a
  compound (about 25 places in the agent files; the CASE4 example de-blinded a benchmark dataset).
  The rule stays without the story. Where an example is needed for syntax (e.g. what an LSD line
  looks like), use atom numbers and shifts only, never a named compound. α-terpineol is
  deliberately NOT used as an example: it is the public demo dataset and would stop being blind.
- **D-04: Double workflow — reorder only.** The team flow and the headless caveat both keep their
  content; restructure them for clarity but do not split them into mode-specific files and do not
  add mode detection. Phase 107 decides the route and Phase 109 rewrites the flow.

### Where the skill lives and how it is installed
- **D-05: Into the package now.** Commands, agents and reference files become package data of
  `ailsa` (next to `src/ailsa/skills/ailsa-lite/`), so each file moves only once and pip users get
  the skill that matches their CLI version (`docs/SKILLS.md`, Rule 3). `ailsa skill install ailsa`
  sets them up for Claude Code: commands under `~/.claude/commands/ailsa/` (giving `/ailsa:*`),
  agents under `~/.claude/agents/`. A link option creates symlinks into the checkout instead of
  copies, for the maintainer machines, so edits apply at once. Old `lucy-ng` symlinks are removed.

### How we rule out a regression
- **D-06: One run plus a rule inventory.** Besides the one blind run, build an inventory that maps
  every rule of the old files (byte-identical to `paper-skill-v2`) to its new location, and check
  it: any rule that is lost, or whose meaning changed beyond D-01..D-03, is reported. No extra
  model runs for comparison (a 5-dataset before/after check was rejected: too noisy for its cost).
- **D-07: Acceptance run passes when it completes and is graded.** Dataset: a blind benchmark dataset
  that the old skill solved at rank 1 (not one of the non-blind ones). The rank is reported. If the
  truth is not at rank 1, inspect the transcript for a restructuring cause (lost or misread rule)
  versus run-to-run noise (repeat agreement was 11 of 15) and put the finding to the user; the
  phase does not auto-fail on rank.

### Benchmark control after the move
- **D-08: Watchdog on vitus in a herdr pane, no LaunchAgent.** Follows the global rule of
  2026-11-14 (nothing persistent on the laptop; control services on vitus in their own herdr pane
  in the lane's space). SKILL-04 and roadmap success criterion 6 say "LaunchAgent re-registered";
  reword them accordingly (the plist under `scripts/launchd/` is retired or kept only as history).
  The pane is started when a measurement series is due and restarted by hand after a vitus reboot.
- **D-09: Update the main Sheldon checkout.** After the restructuring is complete, bring
  `/mnt/raid_drive/chris/lucy-ng` (the checkout the blind runner uses) to the new state and install
  the new skill there. This lifts the 106.1-era rule "do not touch the main Sheldon checkout" for
  this purpose. The paper skill stays recoverable through the tags; result directories under
  `/mnt/raid_drive/chris/case-uat-results*` stay untouched. The path itself moves only in Phase 111.
- **D-10: Acceptance run on today's configuration.** Opus 5.5 with the current Claude Code (Opus 5.5
  needs >= 2.1.280). The watchdog's pinned `CLAUDE_BIN` (2.1.205) is updated; the benchmark
  environment (Claude Code 2.1.205, LSD 3.5.3, reference DB schema 3, no fragment DB) is recorded
  in `docs/BENCHMARK.md` as part of FREEZE-01.

### Folded Todos
- **`2026-10-14-cli-database-help-shift-credit.md`:** `ailsa database download --help` describes the
  reference DB without the COCONUT shift source credit. Add the same credit sentence as the skill
  files (D-17 wording). A few minutes; fits the credit rule this phase applies anyway.

### Claude's Discretion
- File layout inside the package (e.g. `src/ailsa/skills/ailsa/commands/`, `agents/`,
  `references/`), how the installer handles agents and commands, the link option's name, and a
  version stamp plus `CHANGELOG.md` for the frontier skill as the lean skill has.
- How each oversized file is split (coordinator 978 lines, diagnostic 1 122, LSD engineer 700,
  devil's advocate 680): which parts become references and at which named step an agent reads
  them; one shared LSD reference read by the LSD engineer, the devil's advocate and the diagnostic
  agent instead of today's copies; tables of contents.
- The single term per role ("coordinator" is the most frequent; "devil's advocate" introduced once
  with its abbreviation), and removal of the 32 dead `skill/SKILL.md` references.
- Lint implementation: extend the lean skill's pytest checks (`tests/test_skill_lite.py`) to the
  frontier skill (format, size, TOC, hygiene, dead references); the answer scan reuses
  `~/Dropbox/develop/ailsa-paper/scripts/blindness/prompt_answer_scan.py` against the private key
  (`~/Dropbox/develop/data/nmrdata/benchmark-grading-2026-10-01/`), runs locally and before every
  benchmark, never in CI and never with the key in the repository.
- The rule-inventory format and how meaning changes are checked (e.g. a fresh reviewer instance
  comparing old and new text rule by rule).
- Which blind dataset the acceptance run uses (within D-07), and keeping the inventory and any
  dataset identities out of tracked files (the repo is public).
- Git tag names already exist (`paper-skill-v1` = `f9aa7b3`, `paper-skill-v2` = `6d2d126`); keep
  them, never move them.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` § "Phase 106: Freeze, rename and restructure the skill" — goal, success
  criteria, the D-17 credit note and the content-preserving note
- `.planning/REQUIREMENTS.md` — FREEZE-01, SKILL-01 .. SKILL-06 (SKILL-04 to be reworded per D-08)

### Skill rules and prior analysis
- `docs/SKILLS.md` — paper skill tags, frontier vs lean skill, Rule 3 (a skill ships with the CLI
  it calls), the checks every change must pass
- `.planning/research/skill-rebuild/ailsa-skills-best-practices-review.md` (local, not in git) —
  the October review: file sizes, dead references, terms, emphasis count, the de-blinding example
- `.planning/research/skill-rebuild/ailsa-skill-rebuild-plan.md` (local, not in git) — the rebuild
  plan behind Phases 106-110
- `.planning/phases/106.1-run-record-core/106.1-CONTEXT.md` — D-01: the frontier skill is touched
  once, in its renamed and split form; run-record wiring belongs to 106.2

### Benchmark machinery
- `docs/BENCHMARK.md` — where the benchmark environment gets recorded (FREEZE-01)
- `tests/case-benchmark/blind_case_batch.py`, `tests/case-benchmark/blind_case_run.sh`,
  `tests/case-benchmark/README.md` — the blind runner (calls the old command)
- `scripts/uat_watchdog.py` — quota watchdog (pins `CLAUDE_BIN` 2.1.205, calls the runner on Sheldon)
- `scripts/launchd/` — the LaunchAgent being retired (D-08)
- `scripts/bootstrap_case_host.sh` — host bootstrap that names the old command

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/ailsa/cli/skill.py`: `ailsa skill list|install` for package-data skills (targets claude,
  opencode, agents; `--project`, `--dest`, `--force`); today it copies SKILL.md directories, so it
  needs an extension for commands plus agents and a link mode (D-05).
- `src/ailsa/skills/ailsa-lite/`: the model for packaging (SKILL.md with version, references,
  CHANGELOG).
- `tests/test_skill_lite.py`: format, size and hygiene checks to extend to the frontier skill.
- `~/Dropbox/develop/ailsa-paper/scripts/blindness/prompt_answer_scan.py`: name and structure scan
  against the answer key.

### Established Patterns
- `tests/test_skill_files_unchanged.py` is a SHA-256 byte guard on `case.md` and the agent files; it
  must reference the new files, with the baseline updated in the same commit that changes them.
- `tests/test_case_md_wv07.py` asserts phrases in `case.md`; it will break on the split and must be
  migrated (its web-view phrases go away in 106.2).
- Skill files are live via symlinks in `~/.claude/commands/lucy-ng` and `~/.claude/agents/lucy-*.md`
  (vitus; the same on the laptop and Sheldon); a fresh Claude Code session is needed to load edits.
- `CLAUDE.md` (repo) already names `.claude/commands/ailsa/` and `ailsa-*` agents; after D-05 its
  "CASE skill location" section must point at the package location.

### Integration Points
- The lean skill and the frontier skill share CLI contracts (`docs/SKILLS.md` Rule 2); renaming must
  not change any command the skills call.
- The global `~/.claude/CLAUDE.md` mentions `/lucy-ng:case` as an example of a colon command; its
  template lives in the session-manager project, not in this repo (see Deferred).

</code_context>

<specifics>
## Specific Ideas

- The user skipped the paper-prototype sessions on 2026-11-26 to get to this phase sooner.
- Recommendations were accepted on every question; no deviation from the recommended options.

</specifics>

<deferred>
## Deferred Ideas

- The global `~/.claude/CLAUDE.md` (all three herdr machines) cites `/lucy-ng:case` as an example of
  a colon-form plugin command. Update the template in `Claude-Code Session-Manager/claude-global/`
  and redistribute once `/ailsa:case` exists (outside this repo; the user's session manager).

### Reviewed Todos (not folded)
- `2026-06-25-case4-azulene-regiochemistry-enumeration-gap.md` — a chemistry/workflow gap; Phase 109.
- `2026-11-24-2d-picker-indexerror-on-empty-spectrum.md` — code fix; Phase 108 (foundation).
- `2026-06-30-ranking-tests-hardfail-without-hosegen.md` — test hygiene; Phase 108.

</deferred>

---

*Phase: 106-freeze-rename-and-restructure-the-skill*
*Context gathered: 2026-11-26*
