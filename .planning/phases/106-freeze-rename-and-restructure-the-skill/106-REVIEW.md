---
phase: 106-freeze-rename-and-restructure-the-skill
reviewed: 2026-11-27T11:50:00Z
depth: standard
files_reviewed: 18
files_reviewed_list:
  - scripts/bootstrap_case_host.sh
  - scripts/skill_rule_inventory.py
  - scripts/uat_run_baseline_opus5.sh
  - scripts/uat_watchdog.py
  - src/ailsa/cli/database.py
  - src/ailsa/cli/skill.py
  - tests/case-benchmark/blind_case_batch.py
  - tests/case-benchmark/blind_case_run.sh
  - tests/test_benchmark_scripts.py
  - tests/test_case_md_wv07.py
  - tests/test_cli_database_help.py
  - tests/test_cli_skill.py
  - tests/test_freeze.py
  - tests/test_skill_answer_scan.py
  - tests/test_skill_files_unchanged.py
  - tests/test_skill_frontier.py
  - tests/test_skill_lite.py
  - tests/test_skill_rule_inventory.py
findings:
  critical: 3
  warning: 12
  info: 7
  total: 22
status: issues_found
---

# Phase 106: Code Review Report

**Reviewed:** 2026-11-27T11:50:00Z
**Depth:** standard (diff base `frontier-skill-pre-106`)
**Files Reviewed:** 18
**Status:** issues_found

## Summary

All 412 tests in the reviewed test files pass (`pytest -o addopts=""`, 8 s, no skips on this
machine). Passing tests here mean little, though. Several of the new contract tests are vacuous
or are satisfied by a comment, and three defects in the shipped code were confirmed on a
synthetic tree in the scratchpad:

1. **Installer (`ailsa skill install ailsa`)** follows symlinked parent folders. With `--force`
   it deletes the package's own `references/` and `INDEX.md` and replaces them with symlinks
   that point to themselves. It still exits 0 and prints "Installed". A failed install also
   leaves things half done, `--force` means different things for symlinks and for regular files,
   agents dropped from the package stay installed, and `--root` produces installs whose
   reference paths point back to `~/.claude`.
2. **Benchmark runner**: the model pin moved to `claude-opus-5-5`, but every launcher still
   writes into the Opus 5 result folders, and the watchdog's default target is the historical
   4.8 folder. `meta.json` does not record the model, so mixed results cannot be told apart
   afterwards.
3. **Rule inventory**: the tool used as evidence that no rule was lost treats every
   emphasis/polarity word as a stopword and checks negation in one direction only. "Always X"
   rewritten as "Never X" scores 1.00 "same", and `check` exits 0.

The answer-scan test leaks no key content today. Its output has dataset numbers and file:line
only, and RDKit logging is off in the scan script. It can, however, pass with zero datasets or
zero files, and it skips silently once the date-stamped key folder moves.

## Critical Issues

### CR-01: Installer deletes package source files through a symlinked parent folder (exit 0)

**File:** `src/ailsa/cli/skill.py:69-96` (called from `:115-119`)
**Issue:** `_place()` tests only the last path component with `dst.is_symlink()`. If an
intermediate folder is a symlink, the code goes through it. Example: `~/.claude/ailsa` linked by
hand to `src/ailsa/skills/ailsa`, the obvious manual setup, since every agent reads
`~/.claude/ailsa/references/`. In that case `root/ailsa/references` resolves to the package's
own `references/` folder, which is a real folder. With `--force`, `_remove_owned()` calls
`shutil.rmtree()` on the source. In link mode it then creates `references -> references`, a
link to itself. Copy mode crashes in `copytree` after the delete. The same happens to
`INDEX.md`. No check ensures that `dst` lies outside `src_dir`, or that `dst` differs from
`src`. A `--root` that points into the checkout has the same effect: agents get unlinked and
then re-created as self-links.
Reproduced in the scratchpad (`repro_skill.py`, scenario 1): exit 0, `source references
is_symlink: True exists: False`, and the source `INDEX.md` became a link to itself. Uncommitted
edits in a maintainer's checkout are lost.
`test_nothing_written_outside_root` covers only a fresh link install into an empty root, so it
gives false confidence here.
**Fix:**
```python
def _check_destination(src: Path, dst: Path, root: Path) -> None:
    root_r = root.resolve()
    parent_r = dst.parent.resolve()
    if parent_r != root_r and root_r not in parent_r.parents:
        raise click.ClickException(f"{dst.parent} resolves outside {root} (symlinked folder?)")
    src_r = src.resolve()
    target = parent_r / dst.name
    if target == src_r or src_r in target.parents or target in src_r.parents:
        raise click.ClickException(f"{dst} resolves into the package itself ({src_r})")
```
Call it for every destination in a preflight pass before anything is changed (see WR-01). Add
a test where `root/ailsa` is a symlink to the fake package, run with `--link --force`, and
assert that the package files are unchanged.

### CR-02: Opus 5.5 pin writes into the Opus 5 and 4.8 result folders, and the model is not recorded

**File:** `scripts/uat_watchdog.py:47,72,610`; `scripts/uat_run_baseline_opus5.sh:2,35`;
`tests/case-benchmark/blind_case_run.sh:132-133`
**Issue:** `REMOTE_ENV["CLAUDE_MODEL"]` changed from `claude-opus-5` to `claude-opus-5-5`. The
target folders did not change with it:
- `uat_run_baseline_opus5.sh` still writes into `case-uat-results-opus5-baseline`. Its header
  says "Re-run the 103 baseline datasets on Opus 5" so that "the whole benchmark ends up on one
  model". `uat_run_remaining.sh` likewise writes into `case-uat-results-opus5-rest`. Both are
  the paper arms that the answer-scan test reads (`ARMS`).
- `--results-dir` defaults to `REMOTE_RESULTS = .../case-uat-results`, the 4.8 arm. Its own
  help text says it must stay untouched.
- Both scripts are "safe to re-run". Any dataset they still consider pending (no
  `final_results.md` and `runtime_s < 600`) is therefore run on Opus 5.5 and filed under the
  Opus 5 or 4.8 arm.
- `blind_case_run.sh` writes `meta.json` without the model or CLI version, so the
  contamination cannot be detected afterwards. The script's own comment says this is exactly
  what makes a benchmark "unreadable six months later".
**Fix:** record provenance, and refuse mixed folders:
```bash
# blind_case_run.sh, meta.json
printf '{"case":"%s","model":"%s","claude_bin":"%s",...}\n' "$CASE_NAME" "$CLAUDE_MODEL" "$CLAUDE_BIN" ...
```
```python
# uat_watchdog.py: no default results dir; refuse a dir whose meta.json files name another model
p.add_argument("--results-dir", required=True, ...)
```
Point the two launchers at a new `case-uat-results-opus5-5-*` folder, or retire them
explicitly and say so in their headers.

### CR-03: Rule inventory certifies inverted rules as "same"

**File:** `scripts/skill_rule_inventory.py:57-63,254-260`
**Issue:** `STOPWORDS` contains every `EMPHASIS_WORDS` entry (`must`, `never`, `always`,
`only`, `required`, ...). Swapping "always" for "never", or dropping "only", therefore leaves
the token set unchanged (Jaccard 1.00). `status_of()` flags negation only when the old unit has
it and the new one does not. An added negation is never flagged. Confirmed: old
`- Always run the duplicate filter before ranking.` / `- Run the solver only after validation.`
against new `- Never run ...` / `- Run the solver after validation.` gives `same 2`, and
`check --lost-only --meaning` reports `unresolved: 0` and exits 0. The restructure removed
capital-letter emphasis everywhere (see `test_emphasis`), so the rewritten sentences are exactly
where this blind spot lies. The phase's "no rule lost" evidence does not cover polarity
changes. `test_negation_dropped_needs_review` tests only the removal direction.
**Fix:**
```python
POLARITY = {"never", "not", "no", "without", "always", "only", "must", "may", "optional"}

def polarity(norm: str) -> frozenset:
    return frozenset(w for w in re.findall(r"[a-z']+", norm) if w in POLARITY or w.endswith("n't"))

def status_of(score, o, n):
    st = "same" if score >= SAME_AT else "reworded" if score >= REWORDED_AT else "LOST"
    extra = []
    if st != "LOST" and n is not None and polarity(o.norm) != polarity(n.norm):
        extra.append("polarity?")
        st = "reworded"
    return st, extra
```
Then re-run `build` and `check --meaning` on the real inventory and review the units that move
from "same" to "reworded". Add tests for "always to never", "only" dropped, and negation added.

## Warnings

### WR-01: A failed command-skill install leaves a half-installed state, with the legacy links already gone

**File:** `src/ailsa/cli/skill.py:112-120`
**Issue:** `_drop_legacy()` runs first, and each `_place()` changes the disk before the next one
is checked. When a regular file exists further down the list and `--force` is not given, the
install stops with exit 1. By then the old `lucy-ng` links are deleted and `commands/ailsa` and
some agents are placed, but the remaining agents, `references` and `INDEX.md` are not. The user
has neither a working old install nor a complete new one. Reproduced (scenario 2).
**Fix:** two passes. First collect `(src, dst)` pairs and check every one of them (existence
without `--force`, plus the CR-01 check). Only then drop the legacy links and place the files.

### WR-02: `--force` means different things; unrelated symlinks are removed silently

**File:** `src/ailsa/cli/skill.py:28-36,82-83,99-109`
**Issue:** `_place()` unlinks any symlink at a destination without `--force`, even in copy
mode, but refuses regular files. A user's own override, e.g.
`~/.claude/agents/ailsa-nmr-chemist.md -> ~/my-variant.md`, is replaced without a word
(reproduced, scenario 3). `_drop_legacy()` deletes any symlink named `agents/supervisor.md`
whatever its target. That is a generic name that another project's agent can carry, and
`test_legacy_cleanup_only_symlinks` locks this in with a target in an unrelated folder.
`test_force_over_symlink_never_touches_package` never exercises `--force`, because symlinks are
unlinked anyway.
**Fix:** replace a symlink without `--force` only when `os.readlink(dst)` resolves into an
`ailsa`/`lucy-ng` skill tree. Remove legacy links only when their target path contains
`lucy-ng` or `/.claude/agents/lucy-`. Otherwise report them and leave them alone.

### WR-03: Agents dropped from the package stay installed

**File:** `src/ailsa/cli/skill.py:116-117`
**Issue:** only the agents currently shipped are placed. An `ailsa-*.md` from an earlier version
stays in `~/.claude/agents`: a dangling link in link mode, a stale copy in copy mode. Claude
Code still loads it, so an old agent text can run against a newer CLI. Reproduced (scenario 4):
the link was left behind and dangling.
**Fix:** after placing the agents, remove `root/agents/ailsa-*.md` entries that are not in the
shipped set. Do this for symlinks into the package without asking, and for copies with
`--force`. Report each removal.

### WR-04: `--root` produces installs whose references point to `~/.claude`

**File:** `src/ailsa/cli/skill.py:160-165,192`
**Issue:** the commands and agents read `~/.claude/ailsa/references/*.md` (path hard-coded in
`case.md` and four agent files). An install with `--root /elsewhere` places the references
under `/elsewhere/ailsa/references`. The skill then reads either nothing or a different
version's references from `~/.claude`, and nothing reports it.
**Fix:** drop `--root` (the tests can monkeypatch `Path.home`). Alternatively, rewrite
`~/.claude/ailsa/` to the actual root when copying, and refuse `--link` with a non-default root.

### WR-05: Lean-skill `--force` over a regular file crashes

**File:** `src/ailsa/cli/skill.py:203-210`
**Issue:** when the destination exists as a file, `shutil.rmtree(destination)` raises
`NotADirectoryError` and the user sees a traceback (reproduced, scenario 5).
**Fix:** call `_remove_owned(destination)`, which already handles symlinks, folders and files.

### WR-06: The reference check in `test_real_copy_install` runs zero times

**File:** `tests/test_cli_skill.py:211-215`
**Issue:** `package = Path(available_skills()["ailsa"]["path"]).parent` gives `.../skills`. So
`(package / "references").glob("*.md")` looks in `src/ailsa/skills/references`, which does not
exist. Confirmed: the glob returns `[]`, and the loop body asserting that each reference was
copied never runs.
**Fix:**
```python
package = Path(available_skills()["ailsa"]["path"])
refs = sorted((package / "references").glob("*.md"))
assert refs
for ref in refs:
    assert (root / "ailsa" / "references" / ref.name).is_file()
```

### WR-07: The bootstrap contract test passes because of a comment

**File:** `tests/test_benchmark_scripts.py:85-88`; `scripts/bootstrap_case_host.sh:95`
**Issue:** the test asserts that `"ailsa skill install ailsa"` appears in the script. The real
command is `"$AILSA" skill install ailsa --target claude --link`, and the literal string exists
only in the trailing comment `# ailsa skill install ailsa`. If the command is deleted and the
comment kept, the test still passes.
**Fix:** delete the comment and assert the real line:
```python
assert re.search(r'^"\$AILSA" skill install ailsa --target claude --link\s*$', text, re.M)
```

### WR-08: The abort cannot match the pinned claude processes; the test checks only that the string exists

**File:** `scripts/uat_watchdog.py:404-405`; `tests/test_benchmark_scripts.py:61-62`
**Issue:** `blind_case_run.sh` starts `"$CLAUDE_BIN" -p "/ailsa:case ..."` with
`CLAUDE_BIN=/home/chris/.local/share/claude/versions/2.1.332`. The process command line is
therefore `.../versions/2.1.332 -p /ailsa:case ...`, and `pkill -f '[c]laude -p /ailsa:case'`
and `'[c]laude --resume'` never match it. A claude process on the compute host keeps its argv
as launched. These two lines are the fallback for claude processes that survive the
`timeout` TERM. `test_watchdog_abort_pattern` asserts only that the literal string is in the
file.
**Fix:** match the arguments instead of argv[0], e.g. `pkill -KILL -f -- '-p /ailsa:cas[e] '`
and `pkill -KILL -f -- '--resum[e] .* --dangerously-skip-permissions'`, or install the pinned
binary as `.../claude-2.1.332/claude` (see WR-09). Test it by building the real argv from
`REMOTE_ENV["CLAUDE_BIN"]` and running `re.search` on it with the pattern.

### WR-09: The pinned CLI sits in the auto-updater's pruned folder

**File:** `scripts/uat_watchdog.py:77`
**Issue:** the pin exists for comparability within a series. But `~/.local/share/claude/versions/`
is managed by the updater: the previous pin `2.1.205` is already gone from the compute host,
which now has 224, 263, 331 and 332. `2.1.332` will be pruned the same way. `preflight()` then
halts (fail-loud), and the series cannot continue on its binary.
**Fix:** copy the binary to a stable path the updater does not touch, e.g.
`~/opt/claude-2.1.332/claude`, and pin that path. Naming it `claude` also makes the abort
pattern in WR-08 work.

### WR-10: Preflight does not check that `/ailsa:case` is installed on the host

**File:** `scripts/uat_watchdog.py:541-563`
**Issue:** this phase renamed the command. `preflight()` checks only that the binary runs and
is logged in. If the host's `~/.claude/commands/ailsa` is missing, or still the old
`lucy-ng` install, every chunk sends an unknown slash command and burns quota or marks cases
as failed.
**Fix:** add `test -f "$HOME/.claude/commands/ailsa/case.md" || echo NO_SKILL` to the
preflight SSH command, and halt on `NO_SKILL`.

### WR-11: The answer-scan test can pass with nothing scanned, and skips silently

**File:** `tests/test_skill_answer_scan.py:23-41,72-83`
**Issue:** the test asserts only that `"skill files"` occurs in stdout. Three gaps:
- `datasets 0` (arm folders exist but hold no `meta.json`) passes.
- `skill files 0` (wrong folder) passes.
- Hit lines whose format no longer matches the regex are dropped, so `datasets with a hit 3`
  combined with zero parsed lines passes.

The whole module skips once the hard-coded, date-stamped key folder
`benchmark-grading-2026-10-01` is renamed or replaced, and that happens on the maintainer's
machine too. Today the scan reports 256 datasets and 31 or 6 files, so it is not vacuous yet.
**Fix:**
```python
m = re.search(r"datasets (\d+), skill files (\d+), datasets with a hit (\d+)", result.stdout)
assert m and int(m[1]) > 0 and int(m[2]) > 0
assert int(m[3]) == len({h.split()[0] for h in all_hit_lines})  # before the pending filter
```
Also turn the skip into a failure when `AILSA_REQUIRE_ANSWER_SCAN=1` is set on the
maintainer's machine.

### WR-12: The inventory's output guard depends on the working folder

**File:** `scripts/skill_rule_inventory.py:263-274`
**Issue:** `repo_root()` runs `git rev-parse --show-toplevel` in the current folder and falls
back to `Path.cwd()`. Run from outside the checkout (or from another repository) with
`--old-dir`/`--new-dir`, it accepts an `--out` inside this public work tree and writes
`pairs.tsv`, which holds the old skill text the docstring says may contain benchmark
identities. `test_out_inside_repo_refused` always runs with `cwd=ROOT`.
**Fix:** anchor the guard on the script's location:
`root = Path(__file__).resolve().parents[1]`, combined with the git top level when available.
Add a test that runs from `tmp_path`.

## Info

### IN-01: Installer tests that look stronger than they are

**File:** `tests/test_cli_skill.py:112-120,167-173`
**Issue:** `test_force_over_symlink_never_touches_package` passes without `--force` (see WR-02).
`test_nothing_written_outside_root` covers a fresh link install only: no `--force`, no copy
mode, no symlinked folders (see CR-01). The `root` fixture writes `keep.txt`, but no test reads
it.
**Fix:** add the CR-01, WR-01 and WR-03 scenarios as tests.

### IN-02: Stale comments in the webview contract test

**File:** `tests/test_case_md_wv07.py:3-11,25`
**Issue:** the comment "pytest must be invoked from the repo root" is no longer true, since the
path now resolves from `__file__`. The RED/GREEN status notes refer to a long-finished plan.
**Fix:** delete both.

### IN-03: The source-checkout detection is a heuristic

**File:** `src/ailsa/cli/skill.py:39-41,65-66`
**Issue:** `_is_site_packages()` misses `pip install --target` and zip/PEX imports. And
`_skills_root()` returns the path after the `as_file()` context has closed, so for a zipped
package the temporary folder is already gone and link targets would dangle.
**Fix:** treat a folder as a checkout only if `src_dir.parents[3] / "pyproject.toml"` exists.
Refuse `--link` when `files("ailsa")` is not a real folder.

### IN-04: The old-name checks are case-sensitive and do not tie the env names together

**File:** `tests/test_benchmark_scripts.py:14-21`
**Issue:** `"lucy" in line` misses `Lucy`/`LUCY`. That is why `LUCY_NO_WEBVIEW`,
`LUCY_PY_VERSION` and `LUCY_LSD_URL` pass. No test checks that the variable exported by
`blind_case_run.sh:80` equals `ailsa.cli.webview.WEBVIEW_OPT_OUT_ENV`. If the later rename
changes one and not the other, benchmark dashboards pile up again without any notice.
**Fix:** add `assert f'export {WEBVIEW_OPT_OUT_ENV}=' in run_sh`.

### IN-05: Silent passes outside a git checkout

**File:** `tests/test_skill_files_unchanged.py:70-74`; `tests/test_freeze.py:17-30`
**Issue:** `git ls-files` with `check=False` returns empty output outside a repository (exit
128), so `tracked == []` passes. The tag test skips whenever the tags are missing, for example
in shallow CI clones. Also, the inventory's default baseline tag `frontier-skill-pre-106`
exists only locally; it is not on the remote.
**Fix:** check `returncode == 0` before comparing the output. Name the skip reason in the CI
docs.

### IN-06: The answer-scan test exposes private paths and could echo scan stderr

**File:** `tests/test_skill_answer_scan.py:23-34,72-73`
**Issue:** this public test file names the private key and scan-script locations. On failure,
pytest's assertion introspection prints the whole `CompletedProcess` repr (`+ where 1 =
CompletedProcess(..., stdout=..., stderr=...)`, in full under `-vv`). The scan's stdout carries
no names, but an unexpected traceback on stderr is not filtered.
**Fix:** `rc = result.returncode; assert rc == 0, f"answer scan exited {rc}"`, and test the
summary line through a bool local in the same way. Take the paths from the environment only,
with no home-relative defaults.

### IN-07: Bootstrap verification skips the skill install

**File:** `scripts/bootstrap_case_host.sh:105-115`
**Issue:** step 6 prints "host is CASE-capable" without checking that
`~/.claude/commands/ailsa/case.md` and `~/.claude/ailsa/references` resolve.
**Fix:** add
`[ -r "$HOME/.claude/commands/ailsa/case.md" ] && echo "  [ok] /ailsa:case installed" || { echo "  [FAIL] skill"; ok=0; }`.

---

_Reviewed: 2026-11-27T11:50:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
