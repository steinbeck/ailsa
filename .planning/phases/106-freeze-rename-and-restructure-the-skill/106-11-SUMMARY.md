---
phase: 106-freeze-rename-and-restructure-the-skill
plan: 11
subsystem: skill
tags: [skill, rule-inventory, meaning-review, d-06, changelog]
requires: ["106-10"]
provides:
  - "private meaning.tsv: a verdict for every reworded rule (556 ids, all same, 3 after a fix)"
  - "three restored obligations in the shared references (lsd-reference, constraint-inventory, timing)"
  - "CHANGELOG 0.1.0: Measurement counts and the pointer to the private list of rules without a known reason"
affects: [106-15, 109]
key-files:
  created: []
  modified:
    - src/ailsa/skills/ailsa/references/lsd-reference.md
    - src/ailsa/skills/ailsa/references/constraint-inventory.md
    - src/ailsa/skills/ailsa/references/timing.md
    - src/ailsa/skills/ailsa/CHANGELOG.md
    - tests/skill_files.sha256
decisions:
  - "A reworded rule counts as `different` when a capital-letter obligation (MUST, NEVER) became a plain present-tense statement that a reader could take as a description of automatic behaviour. Restored with a lowercase `must` or `do not`, which the emphasis lint allows."
  - "Where the obligation survives in the same place through an imperative, a checklist item or a prohibition elsewhere in the same step, the plain statement is judged `same` (examples: the inventory block every file you write contains, backed by checklist item 9; the fragment file location, backed by 'pass --output-dir explicitly'; the identity gate, backed by monitoring's 'do not go straight to present_results')."
  - "The old smoke-test defaults (an example dataset path and a fixed formula) are judged `same` although they are gone: the path never existed in the repository, so the default could only fail the directory check; restoring it would restore a dead reference."
  - "The diagnostic specialist now reads the heteroatom evidence rule through the shared LSD reference, which its old copy lacked. Judged `same`: in the old skill the devil's advocate enforced that rule on every LSD file, and the diagnostic's own ambiguous-position PROP advice is kept in the solution-explosion procedure."
requirements-completed: [SKILL-05]
duration: 12min
completed: 2026-11-27
---

# Phase 106 Plan 11: Rule inventory meaning review Summary

A reviewer that did not write the restructured text read every reworded rule pair of the old
skill against its new text: 393 pairs from the five agent files and 163 from the commands and
references. Three rules had lost their obligation (a capital MUST or NEVER had become a plain
statement) and are restored; every other reworded rule says the same thing as before, apart from
the changes D-01 to D-03 allow. `check --meaning` over the whole inventory exits 0.

## Commits

- `a1aa8aa` fix: restore rule meaning found by the inventory review (agents). In
  `references/lsd-reference.md` the filter-block lines "must persist across all iterations" (the
  restructured text said they "persist", which reads like automatic behaviour); in
  `references/constraint-inventory.md` the inventory counts "must match the actual commands" (it
  said they "match"). Manifest regenerated.
- `cac3604` fix: restore rule meaning found by the inventory review (commands). In
  `references/timing.md` "Do not let stamping gate the next directive" (it said "Stamping does not
  gate the next directive", which reads like a reassurance). Manifest regenerated.
- `b877c90` docs: rule inventory counts in the frontier changelog.

Fixed inventory ids (for the private files): `lucy-lsd-engineer:6c62b64715`,
`lucy-lsd-engineer:fa60656090`, `case:a000dc94c8`.

## D-06 report (counts)

| Quantity | Count |
|----------|-------|
| Old rule units (15 old files, supervisor excluded) | 1642 |
| Matched closely (`same`) | 1029 |
| Reworded | 555 |
| No close match (`LOST`) | 58 |
| LOST resolved: found elsewhere / merged duplicate / dropped D-03 / dropped history / dropped D-01 / dropped dead reference | 19 / 8 / 18 / 10 / 2 / 1 |
| Emphasis-bearing rules | 406 |
| ... with a known reason (`reason_known=yes`) | 388 |
| ... without a known reason (`reason_known=no`, the Phase 109 marker) | 18 |
| Meaning verdicts written | 556 (555 still reworded, 1 now `same` after its fix) |
| Meaning differences found / fixed | 3 / 3 |

The reworded rows were reviewed per old file: NMR chemist 20, LSD engineer 104, solution analyst
4, devil's advocate 109, diagnostic 156, coordinator 109, sanitise 27, advisory templates 12,
dereplicate 5, progress format 4, loop patterns 3, command index 3. The best match the tool
records is often the wrong unit (its weakness from plan 106-02), so each rule was checked by
comparing the whole old section with the whole new section, not the recorded pair alone. The 102
rows with the `negation?` hint all kept their polarity.

## Rules without a known reason (Phase 109)

18 rules kept from the old skill have no known reason. They stay as plain sentences and are
marked for measurement before the workflow is rewritten in Phase 109. The list is in the
maintainer's private inventory folder `~/Dropbox/develop/data/skill-rule-inventory-106/`, in the
`reasons-*.tsv` files, rows with `reason_known=no`. Per old file: LSD engineer 9, devil's advocate
3, NMR chemist 2, diagnostic 1, solution analyst 1, coordinator 1, progress format 1.

That list must never be tracked in this repository: it quotes the old rule text, which names
benchmark datasets and compounds. The same applies to `pairs.tsv`, `inventory.tsv`, `verdicts.tsv`
and `meaning.tsv` in that folder. The CHANGELOG 0.1.0 entry carries the same pointer and count.

## Verification

- `check` (no flags) after the final build: exit 0. `check --meaning --files` over the five old
  agent paths: exit 0. `check --meaning` over the whole inventory: exit 0.
- Quick tests after each fix (seven skill test files): 399 passed. After the CHANGELOG edit,
  `test_skill_frontier.py` and `test_skill_answer_scan.py`: 321 passed.
- The CHANGELOG has no `CASE<digit>` string, no rule text and no rule id.
- `git ls-files | grep -c skill-rule-inventory` prints 0; `git status` shows no private file.

## Deviations from Plan

**1. [Rule 1 - Bug] Three obligations lost in the restructuring, restored.** Found during Tasks 1
and 2; fixed in `a1aa8aa` and `cac3604` as the plan prescribes. Each fix changes one word group
back to an obligation and adds nothing else.

No other deviation. The id-keyed update of the private `meaning.tsv` after each rebuild is a
scratch helper outside the repository (a rebuild moved one fixed row from reworded to same, so
index-based verdict files could not be reused).

## Notes for Phase 109

- The pattern behind all three fixes (an obligation rewritten as a present-tense statement) is
  frequent in the restructured text. Most cases keep the obligation through a nearby imperative,
  and the review judged them `same`; a rewrite of the workflow should state each obligation as an
  instruction.
- The diagnostic specialist still describes the version 1 inventory (fields `deff_not_patterns`,
  `syme_pairs`, `elim_value`), as its old text did. Content preserved, but stale against the
  version 2 inventory the LSD engineer writes.

## Known Stubs

None. "result to follow" in the CHANGELOG 0.1.0 Measurement bullet is the placeholder for the
acceptance run of plan 106-15.

## Self-Check: PASSED

- FOUND: the three modified references, `CHANGELOG.md`, `tests/skill_files.sha256`, this file.
- FOUND: commits `a1aa8aa`, `cac3604`, `b877c90`.
- FOUND: private `meaning.tsv` with 556 verdicts (outside the repository).
- STATE.md and ROADMAP.md untouched.
