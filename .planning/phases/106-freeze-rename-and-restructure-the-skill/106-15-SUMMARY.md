---
phase: 106-freeze-rename-and-restructure-the-skill
plan: 15
subsystem: acceptance
tags: [acceptance, blind-run, sheldon, grading, human-uat]
requires: ["106-14"]
provides:
  - "one blind /ailsa:case run on Sheldon, completed and graded (CASE146, rank 1)"
  - "106-HUMAN-UAT.md with the evidence and eight open verdicts"
  - "106-VALIDATION.md statuses from the evidence"
affects: [106 verification, 107]
key-files:
  created:
    - .planning/phases/106-freeze-rename-and-restructure-the-skill/106-HUMAN-UAT.md
  modified:
    - .planning/phases/106-freeze-rename-and-restructure-the-skill/106-VALIDATION.md
    - src/ailsa/skills/ailsa/CHANGELOG.md
decisions:
  - "The run got the schema-3 host DB through LUCY_DATABASE (absolute path), the finder's first tier; the August runs had found the same file through the ~/.lucy link."
  - "Started the batch directly with a launcher script in the new results folder, not through the watchdog (no quota snapshot on vitus, one dataset)."
  - "Every UAT item stays pending, including the two whose automated evidence is green; the verdicts are the user's."
requirements: [SKILL-03]
metrics:
  duration: 28min
  completed: 2026-11-27
  tasks: 3
---

# Phase 106 Plan 15: Blind acceptance run and HUMAN-UAT Summary

The renamed chain ran once end to end on Sheldon: `/ailsa:case` on CASE146 finished in one attempt
(1,418 s) and the grade on vitus is SOLVED_TOP1, truth at rank 1. Every verdict waits for the user
in `106-HUMAN-UAT.md`.

## Task 1: Preflight and start

- 106-14 recorded no login blocker; 106-12's model probe succeeded (`claude-opus-5-5` on 2.1.332).
- Local: `test_skill_answer_scan.py` + `test_skill_frontier.py` 321 passed, 0 skipped.
- Sheldon: load 39.7 of 80 threads; no batch running; CASE146 has `molecularformula.txt`, no
  `analysis/`; `case-uat-results-106` did not exist; none of the four answer files in
  `nmr-dataset-assembly/`. Main checkout at `f56327a` (skill files identical to the vitus head),
  skill links in place.
- DB carry-over from 106-14: the CLI finder reads `LUCY_DATABASE` first; without it the August
  runs found the file through `~/.lucy/lucy-ng-derep.db` -> the checkout's
  `data/reference/lucy-ng-derep.db`. From a neutral folder with
  `LUCY_DATABASE=/mnt/raid_drive/chris/lucy-ng/data/reference/lucy-ng-derep.db`:
  `ailsa predict c13 CCO` 2 of 2, `ailsa database info` schema 3 / 928,443 compounds,
  `ailsa lsd check` LSD and outlsd available.
- Start 2026-11-27T11:09:53Z via `launch-106.sh` (copied into the results folder; sets
  CASE_DATA_DIR, CASE_RESULTS_DIR=`/mnt/raid_drive/chris/case-uat-results-106`,
  CASE_ANSWERKEY_PATHS = the four `REMOTE_TRUTH_PATHS`, CASE_ANSWERKEY_DIR, CLAUDE_MODEL
  `claude-opus-5-5`, CLAUDE_BIN `.../versions/2.1.332`, LUCY_DATABASE, PATH), `setsid nohup`,
  `-k 1 --mode full`. `batch.log`: launch line, batch line, `[lockout] stashed 0`.
- First steps confirmed: `claude -p /ailsa:case ...` process up within seconds; progress log
  header at 11:10, `peaks/` at 11:11, the log grew past its header (48 lines) by 11:19, nine
  minutes after the start.

## Task 2: End, grading, records

- End 11:33 UTC. `meta.json`: attempts 1, runtime_s 1418, final_results true. No batch process left.
  `run.log` has the single attempt line, no timeout, no deadline.
- Copied with `rsync` to the vitus scratchpad (`acceptance-106/results/`); graded with
  `CASE_GROUNDTRUTH=.../truth.tsv grade_blind.py`; `grade.out` stays in the scratchpad, unprinted.
  `scorecard.tsv` columns 1-3: `CASE146 SOLVED_TOP1 1`.
- Iterations: 3 (20,000 -> 1,742 -> 280 solutions; old run 21,223 -> 160 -> 37); 23 distinct
  constitutions; decisive ranking "assigned (atom-by-atom)"; 11 candidates in the final report
  (old: 4). Old run: 1 attempt, 1,763 s, SOLVED_TOP1 rank 1.
- Chain evidence (session transcript plus six subagent transcripts on Sheldon, deduplicated by
  call id):
  - reference read calls from `~/.claude/ailsa/references/`: 11 (10 files), failed: 0;
  - `ailsa` calls 22, `lucy` calls 0;
  - subagent types: `ailsa-nmr-chemist` 1, `ailsa-lsd-engineer` 1, `ailsa-devils-advocate` 3,
    `ailsa-solution-analyst` 1; foreground, one at a time (no agent team in a headless session);
    4 `SendMessage` calls resumed the LSD engineer for iterations 2 and 3, all delivered;
  - every assistant message (92) from `claude-opus-5-5`;
  - Team Models: first block `coordinator: claude-opus-5-5`, `nmr-chemist: claude-opus-5-5`, the
    other three `(pending)`, plus the note that team tools were unavailable headless; final block
    "coordinator, nmr-chemist, lsd-engineer, solution-analyst, devils-advocate: all
    claude-opus-5-5";
  - 4 tool errors, all in the specialists' own helper commands (agent's inline Python KeyError on
    the rank JSON, a blocked `sleep 200`, an exit 144 wait, an agent self-check assertion), each
    recovered; none from a skill file or an `ailsa` command;
  - timing summary present (23:05 wall clock; peak picking 8:31, LSD 5:52 / 3:06 / 1:18, ranking
    2:31, identity gate 1:27).
- Rank is 1, so no restructuring-cause analysis was needed; the UAT notes that one run cannot
  separate restructuring, the post-benchmark ranking change (decisive here) and noise.
- `git status` shows nothing from the scratchpad or the grading folder.

## Task 3: HUMAN-UAT and validation

- `106-HUMAN-UAT.md` (status partial): eight items, each with expected, result pending, the
  evidence in plain language, options with consequences and a recommendation: the acceptance run,
  the rule inventory with the comparison-base deviation (`frontier-skill-pre-106` instead of
  `paper-skill-v2`), form checks (321 and 412 passed, 0 skipped; largest file 494 lines; answer
  scan 0 hits in 31 + 6 files), the Sheldon suite against the 106.1 baseline, installation per
  machine (vitus and Sheldon linked; laptop command verbatim; caffeine re-checked today, reachable
  and empty, optional install commands), the fresh-session menu check, the push decision, and the
  global CLAUDE.md example.
- `106-VALIDATION.md`: all automated rows ✅, the manual acceptance row ⬜ pending the user's
  verdict, Wave 0 items ticked, `wave_0_complete: true` (`nyquist_compliant` was already true).
  Re-checked before setting: inventory `check`, `check --meaning`, `check --lost-only` exit 0; the
  pre-106 tag resolves to `2535715`; watchdog `--help` exits 0; local quick set 412 passed.
- Read through once; `grep -oE "CASE[0-9]+"` finds only CASE146; no vendor name; answer scan over
  both files: 0 hits.

## Commits

- `9ae7818` docs(106-15): acceptance evidence and open verdicts
- `d4acce9` docs(106-15): skill changelog records the acceptance run result

Tasks 1 and 2 changed no tracked file (their output is on Sheldon and in the vitus scratchpad), so
they have no commit of their own.

## Deviations from Plan

1. **[Rule 2] DB given explicitly.** Per the carry-over from 106-14 the launcher sets
   `LUCY_DATABASE` to the schema-3 host file; the plan's run_facts list did not have it. Same file
   the August runs used, so the recorded environment is unchanged.
2. **[Rule 2] Changelog placeholder filled.** Plans 10 and 11 left "result to follow" in the skill
   CHANGELOG for this plan; it now states the outcome without a dataset number (the CHANGELOG is
   outside the hash manifest; skill tests 366 passed afterwards). Not in the plan's file list.
3. **Extra evidence for the push item.** Every text file touched by the 50 unpushed commits (99
   files) was answer-scanned. The scanner's recursive glob skips hidden folders, so the files were
   copied to non-hidden scratch folders first. The only hits were one dataset label in the key that
   is a generic English word, already in the public docs; checked line by line.
4. **Observation added to the fresh-session item:** `/ailsa:status` asks `ailsa database info`
   for the fixed relative path `data/reference/ailsa-derep.db` and so reports the DB missing
   outside the checkout (behaviour inherited from the old skill). Recommended for the foundation
   phase rather than fixed here, because this phase changes no behaviour.
5. The first ssh launch returned only through its 30 s client timeout (as in 106-14); the detached
   batch was unaffected.

## For later phases

- The coordinator logged that team tools were unavailable, then used `SendMessage` (found through
  ToolSearch) to resume the LSD engineer. Relevant to Phase 107 (team vs headless route).
- The early Team Models block keeps "(pending)" lines because the log is append-only; the final
  block follows later. Phase 106.2's run record replaces this.

## Known Stubs

None. The CHANGELOG placeholder is resolved.

## Threat Flags

None. The run used the existing runner; no new endpoint, file access pattern or schema change.

## Self-Check: PASSED

- FOUND: 106-HUMAN-UAT.md, 106-VALIDATION.md (modified), CHANGELOG.md (modified).
- FOUND: commits `9ae7818`, `d4acce9`.
- FOUND on Sheldon: `case-uat-results-106/CASE146/meta.json`; no batch process.
- FOUND in the scratchpad: `acceptance-106/results/scorecard.tsv`.
- STATE.md and ROADMAP.md untouched; nothing pushed.
