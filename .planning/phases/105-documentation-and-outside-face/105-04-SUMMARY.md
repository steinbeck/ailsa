---
phase: 105-documentation-and-outside-face
plan: 04
subsystem: docs
tags: [documentation, rename, mcp-removal, installation, server-bootstrap, nus]

# Dependency graph
requires:
  - phase: 104-package-and-cli
    provides: "src/ailsa package, pyproject.toml extras (dev/prediction/webview/nus, no mcp), ailsa console script, DatabaseFinder with ailsa-derep.db as NEW_DB_NAME"
provides:
  - "docs/INSTALLATION.md rewritten as AILSA-only, MCP-free, with real extras and a real DatabaseFinder search path"
  - "docs/SERVER_BOOTSTRAP.md rewritten as AILSA-only with a ~/.local/share/ailsa DB-discovery step that DatabaseFinder actually searches"
  - "docs/NUS-PORTABILITY.md pure rename pass (ailsa nus, src/ailsa/nus/platform_check.py)"
  - "D-13a team-design language (agent-team flag as requirement, 'do not form a team' for unattended runs, schema-version check for statistical detection) landed in both setup guides"
affects: [106-skill-rename, 107-repo-and-hosts, 105-09-doc-gate]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Setup docs state what the team design needs and what the benchmark's restricted configuration actually measured, rather than describing hub-and-spoke as the system design"]

key-files:
  created: []
  modified:
    - docs/INSTALLATION.md
    - docs/SERVER_BOOTSTRAP.md
    - docs/NUS-PORTABILITY.md

key-decisions:
  - "Followed D-04: docs use the final names (github.com/steinbeck/ailsa, .claude/commands/ailsa, ailsa-*.md, /ailsa:*) even though they only become true in Phases 106/107."
  - "Followed D-03: database instructions show only ailsa-derep.db and the real DatabaseFinder locations (data/reference/, ~/ailsa/data/reference/, ~/.local/share/ailsa/); no ~/.lucy, no LUCY_DATABASE, no legacy filename."
  - "Followed D-13a: both setup guides state the agent-team flag as a requirement of the team design and add the fixed sentence that unattended `claude -p` runs do not form a team; no 'hub-and-spoke' framing of the design."
  - "Did not claim a fresh `ailsa database download` yields the current schema (unverified - see Known Open Question below); docs only say `ailsa database info` prints the schema version and the full current-schema database is what statistical detection needs."
  - "Removed the host name 'sheldon' from INSTALLATION.md's SERVER_BOOTSTRAP pointer (generalised to 'a fresh headless server set up to run CASE unattended') for consistency with SERVER_BOOTSTRAP.md's own no-host-name rule, even though INSTALLATION.md was not explicitly in the interfaces-block host-naming instruction."

patterns-established:
  - "When a long rename-pass sentence would reflow across a hard line-wrap boundary, keep the original wrap points so the diff shows only the renamed token changing (verified via `git diff ... | grep -v -i ailsa` for NUS-PORTABILITY.md)."

requirements-completed: [DOC-02]

# Metrics
duration: 25min
completed: 2026-10-13
---

# Phase 105 Plan 04: Setup Documentation Rename and Correction Summary

**INSTALLATION.md, SERVER_BOOTSTRAP.md and NUS-PORTABILITY.md now say `ailsa` only, INSTALLATION.md is MCP-free, and both host guides state the agent team's real requirements (flag + current-schema database) and the honest scope of what the published benchmark measured.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-10-13T09:40:00+02:00 (approx.)
- **Completed:** 2026-10-13T10:03:04+02:00
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- `docs/INSTALLATION.md` rewritten end to end: every `lucy`/`lucy-ng`/MCP mention gone (install blocks, the `mcp[cli]` dependency row, the MCP-server verification subsection, the "MCP Server Not Found" troubleshooting section, both `rank_lsd_solutions`/`predict_c13_shifts` MCP-tool mentions); only the real extras (`dev`) appear; `/ailsa:*` command table and `ailsa-*` agent table use the final names (D-04); Reference Database section documents only real `DatabaseFinder` locations and adds the schema-version caveat for statistical detection (D-13a) without overclaiming freshness.
- `docs/SERVER_BOOTSTRAP.md` rewritten end to end: five-item prerequisite list, every command and path renamed to `ailsa`; the `~/.lucy` database-discovery step replaced with `~/.local/share/ailsa/ailsa-derep.db`, a location `DatabaseFinder` actually searches (verified against `src/ailsa/database/finder.py`); the "Enable agent teams" section states the flag as a requirement of the team design and adds the fixed sentence that unattended runs do not form a team, linking to the benchmark's restricted-configuration explanation instead of using "hub-and-spoke"; a note added that `scripts/bootstrap_case_host.sh` (not edited here, D-12) needs to catch up to these names; no host name/address/port/user appears anywhere in the file.
- `docs/NUS-PORTABILITY.md` done as a pure rename pass: `lucy nus` -> `ailsa nus`, `src/lucy_ng/nus/platform_check.py` -> `src/ailsa/nus/platform_check.py`, "lucy-ng never invokes" -> "AILSA never invokes", "Install `lucy-ng` itself" -> "Install AILSA (`pip install ailsa`) itself" — every other technical statement byte-identical, confirmed via `git diff docs/NUS-PORTABILITY.md | grep -E '^\+[^+]' | grep -v -i ailsa` returning empty.
- Verified every renamed command/path/import against the live environment rather than assuming it from the plan text: `ailsa --version` (0.1.0), `ailsa nus --help` (check/reconstruct/pipeline present), `ailsa predict --help`, `ailsa dereplicate c13 --help` (`-d/--database` flag confirmed), `ailsa lsd --help` (`rank`/`check` present), `ailsa database info` (ran against the local `data/reference/lucy-ng-derep.db`, legacy-named but auto-detected — schema version 7), and `from ailsa.prediction import HOSEGEN_AVAILABLE` (imports, returns `True`) via the `ailsa` console script's own interpreter.

## Task Commits

Each task was committed atomically:

1. **Task 1: INSTALLATION.md — rename, remove all MCP content, final skill names, current DB instructions, team requirements** - `3df9550` (docs)
2. **Task 2: SERVER_BOOTSTRAP.md and NUS-PORTABILITY.md — final names, neutral DB discovery with schema check, team requirements, rename pass** - `11e3b18` (docs)

**Plan metadata:** (this SUMMARY's own commit, made by the orchestrator/caller after this agent returns)

## Files Created/Modified
- `docs/INSTALLATION.md` - AILSA-only install guide; no MCP; real extras; final skill names; schema-aware DB section; team-design language
- `docs/SERVER_BOOTSTRAP.md` - AILSA-only headless host guide; `~/.local/share/ailsa` DB-discovery step; team-design language; no host identifiers
- `docs/NUS-PORTABILITY.md` - pure rename pass, no technical content changed

## Decisions Made
See `key-decisions` in frontmatter. The one decision made at this agent's own discretion (not dictated verbatim by the plan text): dropping the `sheldon` host name from INSTALLATION.md's cross-reference to SERVER_BOOTSTRAP.md, generalising it to "a fresh headless server set up to run CASE unattended" — consistent with the no-host-naming rule that the interfaces block states explicitly for SERVER_BOOTSTRAP.md and that this agent's own objective states globally for the whole plan.

## Deviations from Plan

None — plan executed exactly as written. One self-correction during execution (not a deviation from the plan's intent, just a drafting fix): the first pass at the NUS-PORTABILITY.md WSL2-install sentence reflowed across its original line-wrap boundaries, which would have failed the plan's own "pure rename pass" diff check (`git diff ... | grep -v -i ailsa` must print nothing). Rewrapped the sentence to match the original line boundaries so only the renamed token changed; verified the check now passes before committing.

## Issues Encountered

None blocking. One fact worth flagging for anyone reading `src/ailsa/database/schema.py` next to a locally-downloaded database: the code constant `SCHEMA_VERSION` is `6`, but this worktree's local `data/reference/lucy-ng-derep.db` (the file actually on disk, pre-rename name, auto-detected by `DatabaseFinder`) reports `Schema version: 7` via `ailsa database info`. That gap is a code/data fact, not a documentation defect — the docs written in this plan correctly say only "current schema" and point readers at `ailsa database info`'s own output rather than asserting a number, per the interfaces-block instruction. Recorded here in case it is relevant to Phase 110 or a future schema-migration task; out of scope for this docs-only plan.

## Known Open Question (for the record, per plan `<output>` instruction)

**Could not verify that a fresh figshare download carries the current schema.** The figshare DOI (10.6084/m9.figshare.31073554, file ID 61078393) is a static download; checking its schema would require downloading the ~830 MB/2.8 GB file, which this plan's instructions explicitly say not to do. The only artifact inspected locally (`data/reference/lucy-ng-derep.db`, this dev machine's existing legacy-named file, not confirmed to be the same bytes as the figshare upload) reports schema version 7, while the code's `SCHEMA_VERSION` constant in `src/ailsa/database/schema.py` is 6 — the two don't need to match if the on-disk file was migrated locally after download, so this observation does not resolve the question either way. **Docs in this plan deliberately do not claim the figshare file is current-schema**; they say only that `ailsa database info` prints the schema version and that the database must have the current schema for statistical detection to work. This remains open for whoever next touches the figshare record (D-09/D-10) or the schema-migration code.

## For Phases 106/107 (per plan `<output>` instruction)

`scripts/bootstrap_case_host.sh` (out of scope for this plan — D-12) must be brought in line with what `docs/SERVER_BOOTSTRAP.md` now says, specifically:
- Symlink commands into `.claude/commands/ailsa` (not `lucy-ng`)
- Symlink agents matching `ailsa-*.md` (not `lucy-*.md`)
- Symlink the CLI console-script into `~/.local/bin/ailsa` (not `lucy`)
- Symlink the reference DB into `~/.local/share/ailsa/ailsa-derep.db` (not `~/.lucy/lucy-ng-derep.db`)
- Add a check of the database schema version (e.g. via `ailsa database info`), since statistical detection silently returns no usable data on an outdated schema (D-13a) — the script currently has no such check.

`docs/SERVER_BOOTSTRAP.md` already carries a sentence noting the installer script is being brought in line with these names and that the document is authoritative where they currently differ, so readers following the doc today are not misled by the script's current state.

## User Setup Required

None — no external service configuration required by this plan.

## Next Phase Readiness

- The three setup docs are internally consistent with the final names and with the real CLI/DatabaseFinder/schema behaviour; nothing in them needs re-editing when Phases 106/107 land (per D-04's "each doc file is touched once" goal) except the cross-references noted above for the bootstrap script, which is explicitly out of scope here.
- `docs/SERVER_BOOTSTRAP.md`'s and `docs/INSTALLATION.md`'s two fixed phrases ("do not form a team", "current schema") are present verbatim in both files for the 105-09 gate to check.
- No blockers for other 105-wave plans; this plan touched only its own three files.

## Self-Check: PASSED

- FOUND: docs/INSTALLATION.md
- FOUND: docs/SERVER_BOOTSTRAP.md
- FOUND: docs/NUS-PORTABILITY.md
- FOUND commit: 3df9550
- FOUND commit: 11e3b18

---
*Phase: 105-documentation-and-outside-face*
*Completed: 2026-10-13*
