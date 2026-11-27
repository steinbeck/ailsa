---
phase: 106-freeze-rename-and-restructure-the-skill
plan: 12
subsystem: benchmark-machinery
tags: [benchmark, watchdog, herdr, rename]
requires: ["106-11"]
provides: ["blind runner and watchdog call /ailsa:case", "watchdog documented for a herdr pane on vitus"]
affects: [scripts, tests/case-benchmark, REQUIREMENTS.md SKILL-04, ROADMAP.md criterion 6]
key-files:
  created: [scripts/README.md, tests/test_benchmark_scripts.py]
  modified: [tests/case-benchmark/blind_case_run.sh, tests/case-benchmark/blind_case_batch.py, tests/case-benchmark/README.md, scripts/uat_watchdog.py, scripts/uat_run_baseline_opus5.sh, scripts/bootstrap_case_host.sh]
  removed: [scripts/launchd/ (plist and README)]
metrics:
  completed: 2026-11-27
  tasks: 2
---

# Phase 106 Plan 12: Benchmark machinery on the renamed skill Summary

The blind runner starts `claude -p "/ailsa:case ..."`, the watchdog pins Claude Code 2.1.332 and `claude-opus-5-5`, the LaunchAgent is retired in favour of a documented herdr pane on vitus, and the host bootstrap installs the packaged skill.

Model probe: succeeded. `/home/chris/.local/share/claude/versions/2.1.332 -p hi --model claude-opus-5-5` on Sheldon answered normally ("Hi! What can I help you with today?"), so binary and model id are as expected.

## Commits
- `a1789cf` runner, batch harness, README, watchdog, contract test (4 tests green)
- `ecf6fa7` LaunchAgent removed, `scripts/README.md`, bootstrap, wrapper script, SKILL-04 and criterion 6 reworded (8 tests green)

## What changed
- Runner: new command, comments, rewritten pin comment (no dataset or compound), model example `claude-opus-5-5`.
- Watchdog: pins, abort pattern `[c]laude -p /ailsa:case` (bracket form kept), lockout comments say it is a no-op because the key is off Sheldon, `RETIRED` comment no longer names a compound, docstring points to the herdr pane. `REMOTE_REPO` unchanged until Phase 111.
- Bootstrap: `ailsa` CLI everywhere, `ailsa-derep.db` (with `~/.lucy` finder folder kept), skill installed via `ailsa skill install ailsa --target claude --link`.
- `uat_run_baseline_opus5.sh`: launchd wording replaced by herdr pane, log `~/Library/Logs/ailsa-uat-baseline.log`. `uat_run_remaining.sh` had no launchd wording and needed no change.
- REQUIREMENTS.md SKILL-04 and ROADMAP.md criterion 6 edited by hand; `git diff` showed only those two lines. STATE.md untouched. Watchdog not started (no process running).

## Deviations from Plan
- [Rule 3] The `test_bootstrap_installs_packaged_skill` assertion needs the literal `ailsa skill install ailsa`; the call goes through a `$AILSA` variable, so the line carries a trailing comment with that literal. No behaviour change.
- [Rule 1] A ruff line-length error in the watchdog docstring was fixed by rewrapping.

## Known Stubs
None.

## Self-Check: PASSED
Commits a1789cf and ecf6fa7 exist; scripts/README.md and tests/test_benchmark_scripts.py exist.
