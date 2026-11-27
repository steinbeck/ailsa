# Phase 106: Freeze, rename and restructure the skill - Pattern Map

**Mapped:** 2026-11-27
**Files analyzed:** 22 new or modified file groups
**Analogs found:** 20 / 22

Line numbers refer to the files as they are at the start of the phase. Excerpts are copied from the repository; no dataset identities appear here (the repo is public).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/ailsa/skills/ailsa/INDEX.md` | config (skill index, frontmatter + version) | file-I/O | `src/ailsa/skills/ailsa-lite/SKILL.md` | role-match |
| `src/ailsa/skills/ailsa/CHANGELOG.md` | doc | file-I/O | `src/ailsa/skills/ailsa-lite/CHANGELOG.md` | exact |
| `src/ailsa/skills/ailsa/commands/*.md` (case, dereplicate, predict, sanitise, status, help) | command (skill text) | request-response | `.claude/commands/lucy-ng/*.md` (moved by `git mv`) | exact (same files) |
| `src/ailsa/skills/ailsa/agents/ailsa-*.md` (5) | agent (skill text) | event-driven (team messages) | `.claude/agents/lucy-*.md` (moved) | exact (same files) |
| `src/ailsa/skills/ailsa/references/*.md` (shared LSD ref, split-offs) | reference (skill text) | file-I/O | `src/ailsa/skills/ailsa-lite/references/*.md` and `.claude/commands/lucy-ng/references/*.md` | role-match |
| `src/ailsa/cli/skill.py` (extend: commands/agents kind, `--link`, `--root`, legacy cleanup) | CLI command / installer | file-I/O | itself (`src/ailsa/cli/skill.py`) | exact (modify) |
| `src/ailsa/cli/database.py` (`download` docstring credit) | CLI help text | request-response | itself, lines 202-225 | exact (modify) |
| `tests/test_skill_frontier.py` (lint) | test | transform (text checks) | `tests/test_skill_lite.py` | exact |
| `tests/test_skill_answer_scan.py` (local-only scan wrapper) | test | batch (subprocess) | `tests/test_skill_lite.py` (structure) plus skip pattern | role-match |
| `tests/test_cli_skill.py` (installer) | test | file-I/O | no existing test of `skill.py`; use `CliRunner` pattern from `test_commands_exist` in `tests/test_skill_lite.py` | partial |
| `tests/test_skill_files_unchanged.py` (migrate to manifest) | test | file-I/O (hash) | itself | exact (modify) |
| `tests/skill_files.sha256` | config (manifest) | file-I/O | `EXPECTED_SHA256` dict in the same test | role-match |
| `tests/test_skill_lite.py` (repoint `FRONTIER`) | test | transform | itself, lines 85-119 | exact (modify) |
| `tests/test_case_md_wv07.py` (repoint paths, `lucy webview` to `ailsa webview`) | test | transform | itself | exact (modify) |
| `tests/test_freeze.py`, `tests/test_benchmark_scripts.py`, database help test | test | transform (grep contract) | `tests/test_case_md_wv07.py` (substring contract) | role-match |
| `scripts/skill_rule_inventory.py` | utility (generator/checker) | transform | no close analog (see No Analog) | none |
| `tests/case-benchmark/blind_case_run.sh`, `blind_case_batch.py`, `README.md` | runner script | batch | themselves | exact (modify) |
| `scripts/uat_watchdog.py` | service (watchdog) | event-driven / polling | itself | exact (modify) |
| `scripts/bootstrap_case_host.sh` | script | file-I/O | itself | exact (modify) |
| `scripts/launchd/` (retire) and new `scripts/README` for herdr pane | config / doc | n/a | `scripts/launchd/README.md` | role-match |
| `docs/BENCHMARK.md`, `docs/SKILLS.md`, `docs/INSTALLATION.md`, `docs/SERVER_BOOTSTRAP.md`, `README.md`, `CLAUDE.md` | doc | n/a | themselves | exact (modify) |

## Pattern Assignments

### `src/ailsa/cli/skill.py` (CLI installer, file-I/O)

**Analog:** itself. Extend, keep the existing conventions (click group, `as_file(files("ailsa") / "skills")`, regex index parsing, `click.echo` + `SystemExit(1)` for errors, no test exists yet).

**Imports and root lookup** (lines 7-26):
```python
from __future__ import annotations

import re
import shutil
from importlib.resources import as_file, files
from pathlib import Path

import click

TARGETS: dict[str, tuple[Path, Path]] = {
    "opencode": (Path.home() / ".config" / "opencode" / "skills", Path(".opencode") / "skills"),
    "claude": (Path.home() / ".claude" / "skills", Path(".claude") / "skills"),
    "agents": (Path.home() / ".agents" / "skills", Path(".agents") / "skills"),
}

def _skills_root() -> Path:
    with as_file(files("ailsa") / "skills") as root:
        return Path(root)
```

**Index parsing to extend** (lines 29-44): `available_skills()` globs `*/SKILL.md`. Add a second glob `*/INDEX.md` with the same three regexes (`name`, nested `version`, `description`) and return an extra `kind: "commands"`; the lean skill keeps `kind: "skill"`. Note the `version` regex expects an indented `version:` under `metadata:`, so `INDEX.md` frontmatter must use the same shape as `ailsa-lite/SKILL.md`.
```python
for skill_md in sorted(root.glob("*/SKILL.md")):
    text = skill_md.read_text()
    name = re.search(r"^name:\s*(\S+)", text, re.MULTILINE)
    version = re.search(r'^\s+version:\s*"?([^"\n]+)"?', text, re.MULTILINE)
    desc = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
```

**Install command shape** (lines 59-91): options `--target`, `--project`, `--dest`, `--force`; the destructive branch is the thing to change:
```python
if destination.exists():
    if not force:
        click.echo(f"Error: {destination} exists. Use --force to replace it.")
        raise SystemExit(1)
    shutil.rmtree(destination)
folder.mkdir(parents=True, exist_ok=True)
shutil.copytree(skills[name]["path"], destination)
click.echo(f"Installed {name} {skills[name]['version']} to {destination}")
```
Add for kind `commands`: `--link`, `--root` (default `~/.claude`); reject other targets; write `<root>/commands/ailsa/`, `<root>/agents/ailsa-*.md`, `<root>/ailsa/references/`; on `--force` never `rmtree` a symlink (check `is_symlink()` before `exists()`, `unlink()` for links); refuse `--link` when the package path is inside `site-packages`; remove only legacy symlinks (`commands/lucy-ng`, `agents/lucy-*.md`, `agents/supervisor.md`), report regular files and leave them. Skeleton is in 106-RESEARCH.md "Installer skeleton". Keep the one-line-per-path `click.echo` output style.

---

### `src/ailsa/skills/ailsa/INDEX.md` and `CHANGELOG.md` (packaging metadata)

**Analog:** `src/ailsa/skills/ailsa-lite/SKILL.md` frontmatter and `CHANGELOG.md`.

**Frontmatter pattern** (SKILL.md lines 1-7):
```yaml
---
name: ailsa-lite
description: ... Use when asked to elucidate, solve or identify ...
metadata:
  version: "0.3.0"
  requires: "ailsa (the same commands the full AILSA skill uses); LSD and outlsd on PATH; the reference database"
---
```
Use `name: ailsa`, `metadata.version: "0.1.0"` (suggested), description containing "Use when". Called `INDEX.md` so a copy into a skills dir is never treated as a skill.

**CHANGELOG pattern** (lines 1-9): intro sentence "Each entry says which skill it applies to (see docs/SKILLS.md) and, for a change of behaviour, which measurement supports it.", then `## <version>` with `Applies to: ...` and bullets, ending with a `Measurement:` bullet. The 106 entry says content-preserving restructure, no chemistry rule changed, measurement = inventory check plus one acceptance run.

---

### Moved skill files: commands, agents, references (skill text)

**Analog:** the files themselves (move with `git mv`, once, renaming in the same commit).

**Command frontmatter today** (`.claude/commands/lucy-ng/case.md` lines 1-14):
```yaml
---
name: lucy-ng:case
description: "Full CASE workflow — autonomous NMR structure elucidation. Use when: unknown compound, ..."
argument-hint: "<compound_path> <formula>"
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
  - Task
  - TeamCreate
---
```
Target: drop `name:` (ignored for command files; slash name comes from the path `commands/ailsa/case.md`), keep `argument-hint` and `allowed-tools`, description contains "Use when".

**Agent frontmatter today** (`.claude/agents/lucy-solution-analyst.md` lines 1-10): `name: lucy-solution-analyst`, folded `description: >`, `tools:` list. Target: `name: ailsa-solution-analyst`, file stem equals name, no `model:` key, description text says "Spawned by /ailsa:case coordinator".

**Reference reads by absolute path** (cited in research: `case.md:299`, `lucy-nmr-chemist.md:42`): `Read file: ~/.claude/commands/lucy-ng/references/<name>.md` at a named step. Target form: `Read file: ~/.claude/ailsa/references/<name>.md`, placed at the step that needs it. References live outside `commands/` (otherwise each file registers as a slash command).

**Reference file organisation analog:** `src/ailsa/skills/ailsa-lite/references/{checks-and-diagnosis,lsd-input,nmr-analysis,ranking}.md` show the "one level, read at a named workflow step" structure. Use `lsd-input.md` as the structural model for the shared `lsd-reference.md` (merge of the engineer's section 1 and the diagnostic's inlined copy; prefer the engineer's version).

Split plan per file is in 106-RESEARCH.md "Per-file facts for the split"; do not repeat here.

---

### `tests/test_skill_frontier.py` (test, transform)

**Analog:** `tests/test_skill_lite.py`.

**Imports and file discovery** (lines 7-20):
```python
from __future__ import annotations

import re
import shlex
from pathlib import Path

import click
import pytest

from ailsa.cli import cli

SKILL_DIR = Path(__file__).resolve().parents[1] / "src" / "ailsa" / "skills" / "ailsa-lite"
SKILL_MD = SKILL_DIR / "SKILL.md"
FILES = sorted(SKILL_DIR.rglob("*.md"))
```
Repoint to `.../skills/ailsa`; `FILES = sorted(SKILL_DIR.rglob("*.md"))`; add `COMMANDS`, `AGENTS`, `REFS` sub-lists.

**Frontmatter parse** (lines 23-32): regex `^---\n(.*?)\n---\n` with `re.DOTALL`, then flat `key: value` per line. Reuse unchanged (no YAML dependency); make it a function taking a path.

**Description and size** (lines 41-52): `0 < len(description) <= 1024`, `"Use when" in description`; size check `len(text.splitlines()) <= N`. Frontier: `<= 500` for every file except `CHANGELOG.md`, plus TOC check for files over 100 lines.

**Per-file parametrised hygiene** (lines 55-61):
```python
@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_hygiene(path: Path) -> None:
    text = path.read_text()
    assert not re.search(r"\b(claude|gpt|qwen|llama|gemini)-?\d", text, re.IGNORECASE)
    if path.name != "CHANGELOG.md":
        assert not re.search(r"\bCASE\d+\b|\bPhase \d+", text)
        assert not re.search(r"\b20\d\d-\d\d-\d\d\b", text)
```
Extend with the check table in 106-RESEARCH.md Pattern 4 (history markers, old name, terms, emphasis with `_prose()` stripping fenced code, inline code and `[TAG]` markers, dead refs, "Section N" targets).

**Link resolution** (lines 64-67) and **command existence** (lines 70-82, 122-139): `_commands()` and `test_commands_exist` already check every `` `ailsa ...` `` string against the click tree. They run on the lean skill; add a parametrised copy over the frontier `FILES` (the frontier text will contain `ailsa ...` after the `lucy` to `ailsa` rename).

---

### `tests/test_skill_lite.py` (modify, contract test)

**Analog:** itself, lines 85-119. The silent-skip trap:
```python
FRONTIER = [
    *sorted((SKILL_DIR.parents[3] / ".claude" / "commands" / "lucy-ng").rglob("*.md")),
    *sorted((SKILL_DIR.parents[3] / ".claude" / "agents").glob("lucy-*.md")),
]
...
@pytest.mark.skipif(not FRONTIER, reason="frontier skill not in this checkout")
def test_same_tools_as_frontier_skill() -> None:
    lean = _command_names([p for p in FILES if p.name != "CHANGELOG.md"], "ailsa")
    frontier = _command_names(FRONTIER, "ailsa|lucy")
```
Change: build `FRONTIER` from `src/ailsa/skills/ailsa/**/*.md` (excluding CHANGELOG), replace `skipif` by `assert FRONTIER`, change prefix to `"ailsa"` once the `lucy` alias calls are gone. Keep `RECORD_COMMANDS` allow-list.

---

### `tests/test_skill_files_unchanged.py` (modify, hash guard)

**Analog:** itself. Current mechanism:
```python
REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_MD_PATH = ".claude/commands/lucy-ng/case.md"
EXPECTED_SHA256: dict[str, str] = { CASE_MD_PATH: "8c69...", ".claude/agents/lucy-nmr-chemist.md": ("c643..."), ... }

def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

@pytest.mark.parametrize("relative_path,expected_hash", sorted(EXPECTED_SHA256.items()))
def test_skill_files_are_byte_unchanged(relative_path: str, expected_hash: str) -> None:
    path = REPO_ROOT / relative_path
    assert path.exists(), f"missing skill file: {relative_path}"
    ...
```
Roster test (lines 180-208) globs `lucy-*.md` and asserts `supervisor.md` exists; invert: glob `agents/ailsa-*.md` equals the five names, `supervisor.md` absent. `test_case_md_is_a_regular_readable_file` (lines 211-220) keeps its purpose (clear failure for broken or empty file) on the new `case.md` path.

Migration: replace the dict by reading `tests/skill_files.sha256` (`<hash>  <relative path>` lines as `shasum -a 256` prints them), parametrise over its entries, and add a test that the manifest paths equal the md files in the package tree except CHANGELOG. Keep the rule from the docstring (update the baseline in the same commit as the text change; never loosen) in a short docstring that also gives the regeneration command. The long history comments are dropped (the history lint concerns skill text, not this test, but the docstring is mostly obsolete).

---

### `tests/test_case_md_wv07.py` (modify, content contract)

**Analog:** itself. Repoint paths at lines 26-27 and keep assertions:
```python
CASE_MD = Path(".claude/commands/lucy-ng/case.md")
PROGRESS_FORMAT_MD = Path(".claude/commands/lucy-ng/references/progress-format.md")
TERMINATE_TEAM_MARKER = '<step name="terminate_team">'
FIRST_PUSH_MARKER = 'content="[BEGIN] peak-picking'
```
Prefer a path derived from `Path(__file__).resolve().parents[1]` (as the hash guard does) over the cwd-relative form. Change `lucy webview` strings to `ailsa webview`. If the split moves `terminate_team` or the first push out of `case.md`, update the markers to the new file; deletion belongs to 106.2. Check that the `[BEGIN]` marker survives the emphasis/tag rewrite.

---

### `tests/test_cli_skill.py` (new, installer test)

**Analog:** no test of `skill.py` exists. Use `click.testing.CliRunner().invoke(cli, ["skill", "install", "ailsa", "--root", str(tmp_path), ...])` with `tmp_path` as root (home is never touched). The `cli` import is `from ailsa.cli import cli` as in `tests/test_skill_lite.py` line 16. Cases per 106-RESEARCH.md Wave 0: copy mode creates `commands/ailsa/case.md`, five `agents/ailsa-*.md`, `ailsa/references/`; link mode creates symlinks; legacy `lucy-ng` symlink removed while a regular file named `lucy-nmr-chemist.md` is left alone; `--force` semantics; link mode refused when the package path contains `site-packages` (monkeypatch `_skills_root`).

---

### `tests/test_skill_answer_scan.py` (new, local-only)

**Analog:** `tests/test_skill_lite.py` for module layout; skip semantics from 106-RESEARCH.md Pattern 5. Skip the module when `AILSA_ANSWER_KEY_DIR` (default `~/Dropbox/develop/data/nmrdata/benchmark-grading-2026-10-01`) lacks `truth.tsv`, when `AILSA_ANSWER_SCAN` (default `~/Dropbox/develop/ailsa-paper/scripts/blindness/prompt_answer_scan.py`) is absent, or `rdkit` does not import (`pytest.importorskip("rdkit")`). Run it with `subprocess.run([sys.executable, "-I", scan, "--truth", ..., "--cases", ..., "--skills", str(SKILL_DIR)])`, assert the final line ends `datasets with a hit 0`, and on failure print only the hit lines (dataset numbers and file:line). The key path is never written into a tracked file other than as an environment default expressed relative to home.

---

### `tests/case-benchmark/blind_case_run.sh` (modify, runner)

**Analog:** itself. Exact change sites:
- Line 2 comment and README: `lucy-ng:case` to `ailsa:case`.
- Line 23: `CASE_PROJECT_DIR   lucy-ng repo root` comment.
- Line 102:
```bash
"$CLAUDE_BIN" -p "/lucy-ng:case $CASE_DIR $MF$SMOKE" --session-id "$SID" \
```
becomes `/ailsa:case`. Leave the fence text, the headless wording and `export LUCY_NO_WEBVIEW="${LUCY_NO_WEBVIEW:-1}"` (line 85; 106.2 removes it). Rewrite the pin comment at lines 33-47 to say the pin keeps later series comparable and the 2.1.205 baseline is recorded in `docs/BENCHMARK.md`.

---

### `scripts/uat_watchdog.py` (modify)

**Analog:** itself. Change sites:
- `REMOTE_ENV["CLAUDE_BIN"]` (line 79) from `.../versions/2.1.205` (binary gone) to `.../versions/2.1.332`; rewrite the comment at lines 74-79.
- `CLAUDE_MODEL` (line 73) `claude-opus-5` to the Opus 5.5 id after one probe (`claude -p hi --model ...` on Sheldon).
- Line 405: `pkill -KILL -f '[c]laude -p /lucy-ng:case'` to `/ailsa:case`. Keep the bracket trick (`[c]laude`) so the pattern does not match its own ssh command line.
- Lines 60-84: `REMOTE_TRUTH_PATHS` files no longer exist on Sheldon; update the comment only, say the lockout is a no-op now.
- Keep `REMOTE_REPO = "/mnt/raid_drive/chris/lucy-ng"` (moves in Phase 111).
- Replace the LaunchAgent story (D-08) by a short README: `herdr pane split --current --direction down --cwd "$PWD" --no-focus`, then `herdr pane run <pane> "python scripts/uat_watchdog.py ..."`. Note that vitus has no usage snapshot yet.

---

### `scripts/bootstrap_case_host.sh` (modify)

**Analog:** itself. Replace the block that links `.claude/commands/lucy-ng` and `.claude/agents/lucy-*.md` with `ailsa skill install ailsa --link --force`; replace `lucy` on PATH by `ailsa`; command name in messages to `/ailsa:case`; DB file name per `DatabaseFinder` (accepts both). Lines per research: 4, 6-7, 12, 26, 38-48, 76-99, 112-122.

---

### `src/ailsa/cli/database.py` (`download` docstring, folded todo)

**Analog:** itself, docstring after `def download` (about lines 216-225):
```python
"""Download pre-built compound database from Figshare.

Downloads the ailsa compound database containing 928K compounds
(COCONUT + NMRShiftDB) with 13C NMR shifts and 7.9M HOSE statistics
for 13C shift prediction.

DOI: 10.6084/m9.figshare.31073554
```
Insert one paragraph: "The COCONUT 13C shifts are predicted, not measured; the NMRShiftDB shifts are experimental. COCONUT 13C shifts: from J.-M. Nuzillard, Zenodo, doi:10.5281/zenodo.6561449, CC BY 4.0." Click renders docstring paragraphs, so keep blank lines and ASCII `13C`. Test: `CliRunner().invoke(cli, ["database", "download", "--help"])` output contains `zenodo.6561449` and `predicted`.

---

### `docs/*`, `README.md`, `CLAUDE.md` (doc updates)

**Analog:** themselves. Sites are listed in 106-RESEARCH.md "Places that name the old skill". Two constraints for the planner: `CLAUDE.md` "CASE skill location" must point at `src/ailsa/skills/ailsa/` and `ailsa skill install ailsa --link`; every text describing the reference DB carries the Nuzillard credit sentence from CONTEXT.md. `docs/BENCHMARK.md` gets the FREEZE-01 section between "How a benchmark run executes" and "How blindness is enforced"; `docs/SKILLS.md` loses the "byte-identical when the tags were set" sentence.

## Shared Patterns

### Frontmatter parsing without YAML
**Source:** `tests/test_skill_lite.py` lines 23-32 and `src/ailsa/cli/skill.py` lines 35-37
**Apply to:** installer index reader, `test_skill_frontier.py`, `skill_rule_inventory.py` if it reads headers
```python
match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
for line in match.group(1).splitlines():
    if re.match(r"^[a-z]+:", line):
        key, _, value = line.partition(":")
        fields[key] = value.strip()
```

### Repo-root-relative paths in tests
**Source:** `tests/test_skill_files_unchanged.py` line 62 (`Path(__file__).resolve().parents[1]`) and `tests/test_skill_lite.py` line 18
**Apply to:** every new or migrated test (the old `test_case_md_wv07.py` used a cwd-relative path; do not copy that).

### Command-contract check
**Source:** `tests/test_skill_lite.py` `_commands()` and `test_commands_exist` (lines 70-82, 122-139)
**Apply to:** the frontier lint, so every `ailsa ...` the skill shows exists in the click tree after the `lucy` to `ailsa` rename.

### Hash-guard update rule
**Source:** `tests/test_skill_files_unchanged.py` docstring (lines 26-35): change the baseline in the same commit as the text, as an explicit reviewed act, never loosen.
**Apply to:** every plan that edits skill text; the last step of each such task regenerates `tests/skill_files.sha256`.

### Symlink-safe file operations
**Source:** none existing; rule from 106-RESEARCH.md Pattern 3 (`is_symlink()` before `exists()`, `unlink()` for links, never `rmtree` through a link, only remove known legacy names).
**Apply to:** installer, tests for the installer.

### Pinned-process kill idiom
**Source:** `scripts/uat_watchdog.py` lines 398-406 (`pkill -KILL -f '[c]laude --resume'`)
**Apply to:** any new ssh command that kills Sheldon processes (bracket on the first letter so the ssh line does not match itself).

### Privacy of inventory and answer key
**Source:** CONTEXT.md decisions and 106-RESEARCH.md Pattern 5 and "Rule inventory"
**Apply to:** `scripts/skill_rule_inventory.py` (contains no skill text; output goes to `AILSA_RULE_INVENTORY_DIR`, default outside the repo), the scan test (key only via environment or home default), the acceptance run (print case number, verdict and rank only).

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `scripts/skill_rule_inventory.py` | utility | transform (segment, fuzzy match, TSV) | No text-diff or rule-matching tool exists. Build from the spec in 106-RESEARCH.md ("Cheap format"); read old text through `git show <tag>:<path>`; follow the layout of other `scripts/*.py` (argparse main, no skill text inside). |
| `tests/test_cli_skill.py` | test | file-I/O | `skill.py` has no test today; only the CliRunner idiom is borrowed. |

## Metadata

**Analog search scope:** `src/ailsa/cli/`, `src/ailsa/skills/`, `tests/` (skill and benchmark tests), `tests/case-benchmark/`, `scripts/`, `.claude/commands/lucy-ng/`, `.claude/agents/`
**Files read in full or in targeted ranges:** `src/ailsa/cli/skill.py`, `tests/test_skill_lite.py`, `tests/test_skill_files_unchanged.py`, `tests/test_case_md_wv07.py` (head), `tests/case-benchmark/blind_case_run.sh` (head and greps), `scripts/uat_watchdog.py` (ranges), `src/ailsa/cli/database.py` (docstring range), `src/ailsa/skills/ailsa-lite/SKILL.md` and `CHANGELOG.md` (heads), frontmatter of `case.md` and the solution analyst agent
**Pattern extraction date:** 2026-11-27
