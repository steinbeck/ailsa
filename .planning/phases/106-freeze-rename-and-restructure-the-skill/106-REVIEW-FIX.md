---
phase: 106-freeze-rename-and-restructure-the-skill
fixed_at: 2026-11-27T15:30:00Z
review_path: .planning/phases/106-freeze-rename-and-restructure-the-skill/106-REVIEW.md
iteration: 1
findings_in_scope: 15
fixed: 15
skipped: 0
status: all_fixed
---

# Phase 106: Code Review Fix Report

**Fixed at:** 2026-11-27T15:30:00Z
**Source review:** .planning/phases/106-freeze-rename-and-restructure-the-skill/106-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 15 (3 blockers, 12 warnings)
- Fixed: 15
- Skipped: 0
- Info items also applied: IN-01, IN-02, IN-03, IN-07 in full; IN-04, IN-05, IN-06 in part
  (see "Decisions taken without the user")

The affected test files now hold 447 tests (412 at review time), all passing in 20 s on vitus
(`pytest -o addopts=""` over the ten skill, installer, benchmark and inventory test files).
`ruff check` passes on every touched Python file except one long line in
`tests/case-benchmark/blind_case_batch.py:105`, which predates this fix and was left alone.
`mypy` passes on `src/ailsa/cli/skill.py`. Nothing was pushed.

## Fixed Issues

### CR-01: Installer deletes package source files through a symlinked parent folder (exit 0)

**Files modified:** `src/ailsa/cli/skill.py`, `tests/test_cli_skill.py`
**Commit:** 133d116 (together with WR-01)
**Applied fix:** every destination is checked before anything changes. A folder above a
destination that resolves outside `~/.claude`, or a destination that lands in the package's own
skill files, is refused with a message naming the resolved path ("a symlinked folder?"). The
Agent Skill branch applies the same package check to `--dest`. Regression tests rebuild the
reviewer's scratchpad scenario in `tmp_path`: `~/.claude/ailsa` linked to the package with
`--link --force` and copy `--force`, `~/.claude` itself resolving into the package, and `--dest`
pointing at the package. Each asserts that the package tree is byte-for-byte unchanged. The
reviewer's repro script now reports exit 1 with the source `references/` and `INDEX.md` intact.

### CR-02: Opus 5.5 pin writes into the Opus 5 and 4.8 result folders, and the model is not recorded

**Files modified:** `scripts/uat_watchdog.py`, `tests/case-benchmark/blind_case_run.sh`,
`tests/case-benchmark/blind_case_batch.py`, `scripts/uat_run_baseline_opus5.sh`,
`scripts/uat_run_remaining.sh`, `scripts/README.md`, `tests/case-benchmark/README.md`,
`tests/test_benchmark_scripts.py`
**Commits:** 7b6b5a3, f56ee2a (README)
**Applied fix:**
- Watchdog: `--results-dir` is required (no default). The four paper-benchmark folders are
  refused at start. Before each launch the watchdog reads the `meta.json` files already in the
  folder and refuses it if any names another model or none. Runs from before model recording
  name none, so every older folder is refused even if it is missing from the list.
- `blind_case_batch.py`, the last step before the compute host writes anything, requires
  `CLAUDE_MODEL` and refuses the same mixed folders. Launchers other than the watchdog are
  covered too.
- `blind_case_run.sh` records `model`, `claude_bin` and `claude_version` in every `meta.json`,
  including the early-error one.
- The two paper launchers are retired. They exit 2 with a pointer to the watchdog, and their
  bodies stay in git history (`8060ba3`).
- Tests: the required flag and the paper-folder refusal run with SSH patched to fail, plus the
  pure folder check. An end-to-end batch run uses a fake `claude` binary in `tmp_path`: it checks
  the recorded provenance, that the same series can resume, and that a second model is refused.
  Further tests cover a folder without a recorded model and the retired launchers.

### CR-03: Rule inventory certifies inverted rules as "same"

**Files modified:** `scripts/skill_rule_inventory.py`, `tests/test_skill_rule_inventory.py`
**Commit:** 3f49e0c
**Status:** fixed: requires human verification (matching logic)
**Applied fix:** each unit has a polarity: the number of negations (never, not, no, none,
without, cannot, avoid, forbidden, n't, ...), the number of "only" restrictions, and whether
permission wording appears (may, optional, allowed, permitted). A unit whose polarity differs
from its best match is downgraded to `reworded` with the hint `polarity?`, so it needs a
meaning verdict. The same happens when any other candidate at the "same" threshold has a
different polarity, so an inverted copy cannot hide behind an unchanged copy elsewhere. The
check runs in both directions. Plain emphasis removal ("must X" becomes "X") is deliberately
not flagged (D-02). Tests: negation dropped and added, "do not" added, always→never and
never→always, "only" dropped, must→may, a typographic apostrophe, emphasis removal kept as
same, and an inverted copy next to an unchanged one. Every polarity case also makes
`check --meaning` exit 1.

**Re-run on the real skill text (old = tag `frontier-skill-pre-106`, new = `src/ailsa/skills/ailsa/`):**
the rebuilt inventory went into a new folder,
`~/Dropbox/develop/data/skill-rule-inventory-106/rerun-2026-11-27-polarity/`. The hand-made
verdict, meaning and reasons files were copied in, and the original inventory was not
overwritten.
- 1 642 old rule units; same 1 026, reworded 558, lost 58 (before the fix: 1 029 / 555 / 58).
- **300 units are flagged as possibly inverted** (`polarity?`). 3 of them moved from "same" to
  "reworded"; the other 297 were already "reworded" and had a meaning verdict.
- I compared all 300 by hand. For each, I put the old text next to the new units that share most
  of its words, and looked up the remaining dozen by searching the new tree. **No rule was
  inverted.** Almost all flags (294 of 300) come from the best match being a different, rewritten
  sentence, or from rationale clauses added in D-02. The 3 new flags are harmless: one extra
  negation is part of a check's name, one prohibition was split into two negated clauses with the
  same meaning, and two name-check triggers were written out in words after their dataset-number
  labels were removed (D-03).
- So the skill text and `tests/skill_files.sha256` are unchanged. The 3 new verdicts are in the
  rerun folder's `meaning.tsv`. The per-unit result of the hand check is in
  `polarity-review.tsv` there. `check --lost-only --meaning` on the rerun folder now reports
  `unresolved: 0` and exits 0.
- Limitation that remains: a swap that keeps the counts, such as a negation moving to a
  different verb in the same sentence, is not detected. That would need a sentence parse.

### WR-01: A failed command-skill install leaves a half-installed state

**Files modified:** `src/ailsa/cli/skill.py`, `tests/test_cli_skill.py`
**Commit:** 133d116
**Applied fix:** two passes. `_plan()` lists every (source, destination) pair, and
`_preflight()` collects every problem first (containment, an existing file without `--force`,
legacy paths). Only a clean preflight drops legacy links and places files. A refused install
prints each reason plus "Nothing was changed.". The test rebuilds scenario 2 and compares the
whole root tree before and after.

### WR-02: `--force` means different things; unrelated symlinks are removed silently

**Files modified:** `src/ailsa/cli/skill.py`, `tests/test_cli_skill.py`
**Commit:** 47ba329
**Status:** fixed: requires human verification (ownership heuristic)
**Applied fix:** a link at a destination is replaced without `--force` only when it points into
an ailsa skill tree (this package, another checkout or a wheel: `/skills/ailsa/`) or into the
old `lucy-ng/.claude/{commands,agents}` folders. Any other link needs `--force` in both modes,
and even then only the link is removed, never its target. Legacy names, including the generic
`agents/supervisor.md`, are removed only when their target lies in a lucy-ng tree; otherwise
they are reported and kept. The tests replace the reviewer's: a foreign agent link is refused
without `--force` and replaced with it (target untouched), a copy over the installer's own links
needs no `--force`, and a `supervisor.md` linked into another project stays.

### WR-03: Agents dropped from the package stay installed

**Files modified:** `src/ailsa/cli/skill.py`, `tests/test_cli_skill.py`
**Commit:** 5d78161
**Applied fix:** after placing the agents, `ailsa-*.md` entries the package no longer ships are
removed: links into an ailsa tree at once (dangling ones too), copies with `--force` (otherwise
reported), and a user's own link is reported and kept. Tests cover link mode (scenario 4) and
copy mode.

### WR-04: `--root` produces installs whose references point to `~/.claude`

**Files modified:** `src/ailsa/cli/skill.py`, `tests/test_cli_skill.py`
**Commit:** 3d95977
**Applied fix:** `--root` is removed (the review's first option). The command skill always
installs into `~/.claude`, and the help text and errors say why. The tests run with a temporary
home folder through an autouse fixture, so no test can touch the real `~/.claude`. I checked the
real links on vitus afterwards and they were untouched. A new test checks that `--root` is
rejected (exit 2) and writes nothing.

### WR-05: Lean-skill `--force` over a regular file crashes

**Files modified:** `src/ailsa/cli/skill.py`, `tests/test_cli_skill.py`
**Commit:** 32c3408
**Applied fix:** the Agent Skill branch uses `_remove_owned()` (link, folder or file). Test added.

### WR-06: The reference check in `test_real_copy_install` runs zero times

**Files modified:** `tests/test_cli_skill.py`
**Commit:** f36f502
**Applied fix:** the test reads the skill's own `references/`, requires at least one file, checks
each one and also `INDEX.md`.

### WR-07: The bootstrap contract test passes because of a comment

**Files modified:** `scripts/bootstrap_case_host.sh`, `tests/test_benchmark_scripts.py`
**Commit:** b8c905b (together with IN-07)
**Applied fix:** the trailing comment is gone. The test matches the real command line with an
anchored regex and refuses any comment that mentions the install.

### WR-08: The abort cannot match the pinned claude processes

**Files modified:** `scripts/uat_watchdog.py`, `tests/test_benchmark_scripts.py`
**Commit:** 779fe05
**Applied fix:** the pkill fallbacks match the arguments, `-p /ailsa:cas[e] ` and
`--resum[e] .* --dangerously-skip-permissions`, not argv[0]. The test builds the real argv from
the pinned `CLAUDE_BIN` and the runner's command lines, and asserts that both patterns hit and
that neither matches the abort script itself or an interactive session.

### WR-09: The pinned CLI sits in the auto-updater's pruned folder

**Files modified:** `scripts/uat_watchdog.py`, `scripts/README.md`, `tests/test_benchmark_scripts.py`
**Commit:** e35e47d
**Applied fix:** the pin is now `/home/chris/opt/claude-2.1.332/claude`, outside the updater's
folder. If the binary is missing there, the pre-launch check halts with the exact
`mkdir`/`cp` command. `scripts/README.md` documents the one-time copy. The compute host was not
touched (see "Open item for the user").

### WR-10: Preflight does not check that `/ailsa:case` is installed on the host

**Files modified:** `scripts/uat_watchdog.py`, `tests/test_benchmark_scripts.py`
**Commit:** 6e2f131
**Applied fix:** the pre-launch SSH check also tests that `~/.claude/commands/ailsa/case.md` is
readable and `~/.claude/ailsa/references` exists. Otherwise it halts with the install command.
The test captures the remote command and checks both the probe and the halt.

### WR-11: The answer-scan test can pass with nothing scanned, and skips silently

**Files modified:** `tests/test_skill_answer_scan.py`
**Commit:** b7ad116 (together with IN-06)
**Applied fix:** the test parses the scan's summary line. It requires more than 0 datasets, a file
count equal to the folder's `.md` count (and more than 0), and as many parsed hit lines as
reported hits. The key folder is the newest `benchmark-grading-*` folder, so renaming the date no
longer turns the check off. On the maintainer's checkout, which is recognised by the git-ignored
identities table, missing inputs fail instead of skipping. I checked by hand with a fake scan
script: zero datasets, unparsed hits and a wrong file count each fail.

### WR-12: The inventory's output guard depends on the working folder

**Files modified:** `scripts/skill_rule_inventory.py`, `tests/test_skill_rule_inventory.py`
**Commit:** cc95d67
**Applied fix:** the guard protects the checkout found from the script's own location (and its
git top level), and the git calls run there. The new test starts the script from `tmp_path` and
from a subfolder.

### Info items

- **IN-01** (installer tests weaker than they look): covered by the CR-01, WR-01, WR-02 and WR-03
  tests above.
- **IN-02** (stale web-view test notes), commit 2cc31af: removed.
- **IN-03** (checkout heuristic, archive import), commit 5deda14: `--link` only when the skill
  folder sits next to a `pyproject.toml` three levels up; a zip/PEX import is refused. The test
  tree now has the checkout layout, plus a `pip install --target` case.
- **IN-04** (env names tied together), commit 569ad53: the test ties the runner's webview opt-out
  export to `ailsa.cli.webview.WEBVIEW_OPT_OUT_ENV`.
- **IN-05** (silent passes outside git), commit 2cc31af: the roster test skips with a reason when
  `git ls-files` fails.
- **IN-06** (private paths, stderr echo), commit b7ad116: the assertions use plain locals, so
  pytest never prints the scan's stdout or stderr.
- **IN-07** (bootstrap verification), commit b8c905b: step 6 checks `/ailsa:case` and the
  reference folder.

## Decisions taken without the user

1. **No separate worktree.** The fixes were made in the main working tree. The project rules for
   this run forbid `rm`, `git checkout -- <file>` and removing folders, which the worktree
   cleanup and rollback need. Also, the vitus venv imports `ailsa` from the main checkout, so
   tests in a worktree would have tested the wrong code. No rollback was needed.
2. **`--root` dropped** rather than rewriting reference paths on copy (WR-04, the review's first
   option).
3. **Paper launchers retired**, not repointed: their purpose ended with the benchmark (closed on
   2026-10-01). Repointing them would have meant changing remote shell quoting that I could not
   test without touching the compute host. A new series uses the watchdog directly.
4. **Model guard in two places:** the watchdog (early, over SSH) and the batch (authoritative,
   local on the compute host).
5. **The inventory re-run went into a new folder** instead of overwriting the inventory the phase
   evidence refers to.
6. **Polarity rule:** emphasis removal alone is not a polarity change (D-02). Negation, "only" and
   permission wording are.
7. **Answer scan required on the maintainer's checkout** by default (identities table present),
   with `AILSA_REQUIRE_ANSWER_SCAN=0` to opt out. An opt-in variable alone would never be set,
   and the check would stay silent.
8. **Partly applied Info items:** IN-04's case-insensitive old-name check was not added, because
   the `LUCY_*` variables are still in use until the later rename. IN-05's CI note about missing
   tags was not written. IN-06's environment-only paths were not adopted: the folder names
   already appear in tracked planning documents, and environment-only lookup would make the
   check depend on a variable nobody sets.

## Open item for the user

**The next benchmark series cannot start until one file is copied on the compute host.** The
watchdog now expects Claude Code 2.1.332 in its own folder, `~/opt/claude-2.1.332/claude`, because
the updater deletes old versions from the default folder (the previous pinned version is already
gone there). I did not touch the compute host. Until the copy exists, the watchdog stops before
the first launch and prints the command:

```bash
mkdir -p ~/opt/claude-2.1.332 && cp ~/.local/share/claude/versions/2.1.332 ~/opt/claude-2.1.332/claude
```

If 2.1.332 has meanwhile been deleted there too, the alternative is to pin a version that still
exists and note it in `docs/BENCHMARK.md`. That would put the new series on a different CLI from
the acceptance run. Recommendation: make the copy before the next series. It takes a minute and
keeps the CLI constant.

---

_Fixed: 2026-11-27T15:30:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
