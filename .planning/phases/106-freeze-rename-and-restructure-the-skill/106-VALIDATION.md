---
phase: 106
slug: freeze-rename-and-restructure-the-skill
status: planned
nyquist_compliant: true
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
| **Quick run command** | `~/.venvs/ailsa/bin/python -m pytest tests/test_skill_lite.py tests/test_skill_frontier.py tests/test_skill_files_unchanged.py tests/test_cli_skill.py tests/test_case_md_wv07.py tests/test_skill_answer_scan.py tests/test_skill_rule_inventory.py -q` (each plan runs the subset that exists at that point; from Plan 12 on add `tests/test_benchmark_scripts.py`, from Plan 13 on `tests/test_freeze.py tests/test_cli_database_help.py`) |
| **Full suite command** | on Sheldon only, in `/mnt/raid_drive/chris/ailsa-106.1/` (own venv, pinned hosegen, niced; code by git bundle): `run_gate_106.sh` (pytest with junit, `mypy src/ailsa`, `ruff check src tests`), compared with `pr-repo.junit.xml` via `junit_cmp.py` (Plan 14) |
| **Estimated runtime** | quick run ~3–10 s on vitus; full suite a few minutes on Sheldon (never on vitus or the laptop) |

---

## Sampling Rate

- **After every task commit:** quick run command plus `ruff check` on touched Python files
- **After every task that edits skill text:** the closing routine of Plans 05-10 (PENDING update, hash manifest, `scripts/skill_rule_inventory.py build` + `check --files <old paths>`, quick run including the local answer scan)
- **Before `/gsd:verify-work`:** full suite on Sheldon equal to or better than the recorded baseline failures (Plan 14); answer scan 0 hits (Plan 10); inventory `check --meaning` exits 0 (Plan 11); acceptance run graded (Plan 15)
- **Max feedback latency:** 10 seconds for the quick run

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 106-01-T1 | 01 | 1 | (D-06 baseline) | T-106-01-05 | local annotated tag `frontier-skill-pre-106` on the phase-start skill, not pushed | git | `git rev-parse --verify 'frontier-skill-pre-106^{commit}'` | n/a | ⬜ pending |
| 106-01-T2 | 01 | 1 | SKILL-01 | T-106-01-01..04 | installer writes only under the target root; legacy cleanup removes only symlinks; `--force` never follows a link; link mode refused from site-packages | unit (tmp_path) | `pytest tests/test_cli_skill.py -q` | created in 106-01-T1 | ⬜ pending |
| 106-02-T1 | 02 | 2 | SKILL-05 (D-06) | T-106-02-01 | inventory output refused inside the repo; no skill text in the tool | unit (synthetic trees) | `pytest tests/test_skill_rule_inventory.py -q` | created in 106-02-T1 | ⬜ pending |
| 106-02-T2 | 02 | 2 | SKILL-05 (D-06) | T-106-02-03 | positive control 0 LOST, negative control finds the deleted rule | script | `python scripts/skill_rule_inventory.py check --lost-only` | n/a | ⬜ pending |
| 106-03-T1 | 03 | 3 | SKILL-01, SKILL-02 | T-106-03-01, T-106-03-05 | skill moved once into the package; SHA-256 manifest guards every file; supervisor absent; frontier contract test not skipped | unit | `pytest tests/test_skill_lite.py tests/test_skill_files_unchanged.py tests/test_case_md_wv07.py -q` | migrated in 106-03-T1 | ⬜ pending |
| 106-03-T2 | 03 | 3 | SKILL-01, SKILL-02 | T-106-03-02, T-106-03-04 | vitus links point into the checkout; no legacy link left; move lost no rule | unit + script + ls | `pytest tests/test_cli_skill.py -q && python scripts/skill_rule_inventory.py check --lost-only` | exists | ⬜ pending |
| 106-04-T1 | 04 | 4 | SKILL-05, SKILL-06 (lint) | T-106-04-03, T-106-04-04 | lint proven to fail on known defects; pending files skipped visibly; strict xfail until PENDING is empty | unit | `pytest tests/test_skill_frontier.py -q` | created in 106-04-T1 | ⬜ pending |
| 106-04-T2 | 04 | 4 | SKILL-06 (scan) | T-106-04-01, T-106-04-02 | no benchmark compound by name or structure, no teaching-set name in restructured files; key never in repo | local unit | `pytest tests/test_skill_answer_scan.py -q` (skips without key) | created in 106-04-T2 | ⬜ pending |
| 106-05-T1, T2 | 05 | 5 | SKILL-05 | T-106-05-01, T-106-05-02 | NMR chemist and solution analyst lint-clean; multiplicity protocol shared | unit + script | `pytest tests/test_skill_frontier.py -q && python scripts/skill_rule_inventory.py check --files <old paths>` | exists | ⬜ pending |
| 106-06-T1, T2 | 06 | 6 | SKILL-05 | T-106-06-01, T-106-06-02 | one shared LSD reference; LSD engineer lint-clean; anti-stall rule kept | unit + script | same pattern | exists | ⬜ pending |
| 106-07-T1, T2 | 07 | 7 | SKILL-05 | T-106-07-01..03 | diagnostic split; no dead `skill/` pointers; inlined LSD facts merged before deletion | unit + script | same pattern | exists | ⬜ pending |
| 106-08-T1, T2 | 08 | 8 | SKILL-05, SKILL-06 | T-106-08-01..03 | devil's advocate lint-clean; benchmark example removed; gates kept | unit + script + local scan | same pattern + `pytest tests/test_skill_answer_scan.py -q` | exists | ⬜ pending |
| 106-09-T1, T2 | 09 | 9 | SKILL-05 | T-106-09-01..04 | coordinator under 500 lines; model reported not compared; both workflows and web-view launch intact | unit + script | same pattern + `pytest tests/test_case_md_wv07.py -q` | exists | ⬜ pending |
| 106-10-T1..T3 | 10 | 10 | SKILL-05, SKILL-06 | T-106-10-01, T-106-10-02 | PENDING empty; 0 skipped, 0 xfailed; answer scan clean for both skills; inventory clean over all old files | unit + script + local scan | `pytest tests/test_skill_frontier.py -q -rsx && python scripts/skill_rule_inventory.py check` | exists | ⬜ pending |
| 106-11-T1, T2 | 11 | 11 | SKILL-05 (D-06) | T-106-11-01..03 | every reworded rule judged; no meaning drift; private data untracked | script + reviewer | `python scripts/skill_rule_inventory.py check --meaning` | exists | ⬜ pending |
| 106-12-T1 | 12 | 12 | SKILL-04 | T-106-12-01, T-106-12-04 | runner and watchdog name `/ailsa:case`; existing CLAUDE_BIN >= 2.1.280; no dataset/compound pairing in comments | unit (grep) + help | `pytest tests/test_benchmark_scripts.py -q`; `python scripts/uat_watchdog.py --help` | created in 106-12-T1 | ⬜ pending |
| 106-12-T2 | 12 | 12 | SKILL-04 | T-106-12-02, T-106-12-03 | LaunchAgent removed; herdr pane documented; bootstrap installs packaged skill; watchdog not started | unit (grep) + `bash -n` | `pytest tests/test_benchmark_scripts.py -q` | exists | ⬜ pending |
| 106-13-T1 | 13 | 13 | FREEZE-01 | T-106-13-01, T-106-13-02 | tags resolve to f9aa7b3 / 6d2d126; BENCHMARK.md lists tags and environment; SKILLS.md corrected | unit | `pytest tests/test_freeze.py -q` | created in 106-13-T1 | ⬜ pending |
| 106-13-T2 | 13 | 13 | SKILL-01 (docs, D-05) | T-106-13-03 | no doc points at the old symlink layout | grep | see 106-13 Task 2 verify | n/a | ⬜ pending |
| 106-13-T3 | 13 | 13 | folded todo | T-106-13-04 | `ailsa database download --help` carries the COCONUT shift credit | unit | `pytest tests/test_cli_database_help.py -q` | created in 106-13-T3 | ⬜ pending |
| 106-14-T1 | 14 | 14 | phase gate | T-106-14-01, T-106-14-02 | full suite, mypy, ruff no worse than the 106.1 baseline; wheel ships the frontier skill | remote suite | `run_gate_106.sh` + `junit_cmp.py pr-repo.junit.xml p106-repo.junit.xml` on Sheldon | n/a | ⬜ pending |
| 106-14-T2 | 14 | 14 | SKILL-01, SKILL-02 (D-09) | T-106-14-03..05 | Sheldon main checkout at phase head, skill linked, no legacy link, headless `/ailsa:status` loads | remote checks | see 106-14 Task 2 verify | n/a | ⬜ pending |
| 106-15-T1, T2 | 15 | 15 | SKILL-03 | T-106-15-01..04 | one blind run completes and is graded; grading names stay in the scratchpad | manual (Sheldon run, vitus grading) | start batch with env vars; grade on vitus | manual | ⬜ pending |
| 106-15-T3 | 15 | 15 | SKILL-03 (D-07) | T-106-15-05 | evidence and open verdicts in 106-HUMAN-UAT.md; no auto-approval | file check | see 106-15 Task 3 verify | created in 106-15-T3 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Tests are created inside the plan that first needs them (test-first within the plan), before the
code or text they check:

- [ ] `tests/test_cli_skill.py` — installer: copy mode, link mode (tmp root), legacy cleanup touches only symlinks, refuses link mode from site-packages, `--force` (106-01-T1)
- [ ] `scripts/skill_rule_inventory.py` and `tests/test_skill_rule_inventory.py` on synthetic old/new trees (106-02-T1)
- [ ] `tests/skill_files.sha256` manifest and generator command in the test docstring (106-03-T1)
- [ ] `tests/test_skill_frontier.py` — SKILL-05/06 lint with PENDING set (106-04-T1)
- [ ] `tests/test_skill_answer_scan.py` — local-only scan wrapper and teaching-set name check (106-04-T2)
- [ ] `tests/test_benchmark_scripts.py` (106-12-T1), `tests/test_freeze.py` (106-13-T1), `tests/test_cli_database_help.py` (106-13-T3)
- [ ] Wheel-contents check: `uv build --wheel` on Sheldon and list `ailsa/skills/ailsa/**` (106-14-T1)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| One blind CASE run through `/ailsa:case` completes and is graded | SKILL-03 | needs an Opus 5.5 headless run on Sheldon (30–60 min, up to 2.5 h) and the private answer key on vitus | 106-15 Tasks 1-2: start `tests/case-benchmark/blind_case_batch.py` on Sheldon with all env vars set (CASE_DATA_DIR, CASE_RESULTS_DIR, CASE_ANSWERKEY_PATHS, CASE_ANSWERKEY_DIR, CLAUDE_MODEL, CLAUDE_BIN); confirm the first steps appear; poll to the end; grade on vitus; the acceptance verdict is the user's (106-HUMAN-UAT.md) |
| Link-mode install shows `/ailsa:*` in a fresh Claude Code session | SKILL-01 | slash-command registration is only visible in a new session | Sheldon: headless `/ailsa:status` (106-14-T2); vitus, laptop, caffeine: listed for the user in 106-HUMAN-UAT.md |
| Rule inventory meaning check | D-06 | changed meaning needs a reader | 106-11: a fresh executor judges every reworded pair (`meaning.tsv`, private) |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 10 s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending (execution)
