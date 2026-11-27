---
phase: 106
slug: freeze-rename-and-restructure-the-skill
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-11-27
---

# Phase 106 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >= 7 (`pyproject.toml` `[tool.pytest.ini_options]`, `testpaths = ["tests"]`, `pythonpath = ["src"]`) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `~/.venvs/ailsa/bin/python -m pytest tests/test_skill_lite.py tests/test_skill_frontier.py tests/test_skill_files_unchanged.py tests/test_cli_skill.py tests/test_case_md_wv07.py -q` |
| **Full suite command** | on Sheldon only, in `/mnt/raid_drive/chris/ailsa-106.1/` (own venv, pinned hosegen, niced; code by git bundle): `python -m pytest -q`, plus `ruff check src tests` and `mypy src/ailsa` |
| **Estimated runtime** | quick run ~3–10 s on vitus; full suite several minutes on Sheldon (never on vitus or the laptop) |

---

## Sampling Rate

- **After every task commit:** quick run command plus `ruff check` on touched files
- **After every plan wave:** quick run plus `python scripts/skill_rule_inventory.py --check` (private output dir) and, locally, the answer scan (`tests/test_skill_answer_scan.py`)
- **Before `/gsd:verify-work`:** full suite on Sheldon equal to or better than the recorded baseline failures; answer scan 0 hits; acceptance run graded
- **Max feedback latency:** 10 seconds for the quick run

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 106-xx | tbd | 0 | FREEZE-01 | — | tags resolve to f9aa7b3 / 6d2d126; BENCHMARK.md lists tags and environment | unit | `pytest tests/test_freeze.py -q` | ❌ W0 | ⬜ pending |
| 106-xx | tbd | tbd | SKILL-01 | T-106 (installer) | installer writes only under the target root; legacy cleanup removes only symlinks; link mode refused from site-packages | unit (tmp_path) | `pytest tests/test_cli_skill.py -q` | ❌ W0 | ⬜ pending |
| 106-xx | tbd | tbd | SKILL-02 | T-106 (tamper) | SHA-256 manifest guards the new files; supervisor absent | unit | `pytest tests/test_skill_files_unchanged.py -q` | migrate | ⬜ pending |
| 106-xx | tbd | last | SKILL-03 | — | one blind run completes and is graded (manual, Sheldon) | manual | start batch with env vars; grade on vitus | manual | ⬜ pending |
| 106-xx | tbd | tbd | SKILL-04 | — | runner and watchdog name `/ailsa:case`; no `lucy-ng` in `scripts/` or `tests/case-benchmark/`; CLAUDE_BIN exists check | unit (grep) + dry-run | `pytest tests/test_benchmark_scripts.py -q`; `python scripts/uat_watchdog.py --help` | ❌ W0 | ⬜ pending |
| 106-xx | tbd | tbd | SKILL-05 | — | size, TOC, hygiene, dead refs, one term per role, emphasis, frontmatter | unit | `pytest tests/test_skill_frontier.py -q` | ❌ W0 | ⬜ pending |
| 106-xx | tbd | tbd | SKILL-06 | T-106 (blindness) | no benchmark compound by name or structure in any skill file (local only; key never in repo) | local unit | `pytest tests/test_skill_answer_scan.py -q` (skips without key) | ❌ W0 | ⬜ pending |
| 106-xx | tbd | tbd | Rule 2 contract | — | every `ailsa ...` command the frontier skill shows exists | unit | `pytest tests/test_skill_lite.py -q` (repointed) | exists | ⬜ pending |
| 106-xx | tbd | tbd | folded todo | — | `ailsa database download --help` carries the COCONUT shift credit | unit | `pytest tests/test_cli_database_help.py -q` | ❌ W0 | ⬜ pending |
| 106-xx | tbd | tbd | D-06 | T-106 (blindness) | rule inventory has no LOST rows; inventory data stays outside the repo | script + reviewer | `python scripts/skill_rule_inventory.py --check` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky* (task IDs filled in by the planner)

---

## Wave 0 Requirements

- [ ] `tests/test_skill_frontier.py` — SKILL-05/06 lint
- [ ] `tests/test_skill_answer_scan.py` — local-only scan wrapper (skips when the key is absent)
- [ ] `tests/test_cli_skill.py` — installer: copy mode, link mode (tmp root), legacy cleanup touches only symlinks, refuses link mode from site-packages, `--force`
- [ ] `tests/test_freeze.py`, `tests/test_benchmark_scripts.py` — small grep-style contract tests
- [ ] `scripts/skill_rule_inventory.py` and its tests on a synthetic old/new pair (no real text)
- [ ] `tests/skill_files.sha256` manifest and generator command in the test docstring
- [ ] Wheel-contents check: `uv build --wheel` and list `ailsa/skills/ailsa/**` (on Sheldon if it takes over a minute)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| One blind CASE run through `/ailsa:case` completes and is graded | SKILL-03 | needs an Opus 5.5 headless run on Sheldon (30–60 min) and the private answer key on vitus | start `tests/case-benchmark/blind_case_batch.py` on Sheldon with all env vars set (CASE_DATA_DIR, CASE_RESULTS_DIR, CASE_ANSWERKEY_PATHS, CLAUDE_MODEL, CLAUDE_BIN); confirm the run starts and the second step happens; grade on vitus; the acceptance verdict is the user's |
| Link-mode install on vitus and Sheldon shows `/ailsa:*` in a fresh Claude Code session | SKILL-01 | slash-command registration is only visible in a new session | `ailsa skill install ailsa --target claude --link`; list `~/.claude/commands/ailsa/` and `~/.claude/agents/ailsa-*.md`; in a fresh session, `/ailsa:status` |
| Rule inventory meaning check | D-06 | changed meaning needs a reader | a fresh reviewer instance compares old and new text per inventory row |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10 s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
