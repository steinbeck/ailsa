---
phase: 105-documentation-and-outside-face
plan: 10
subsystem: docs
tags: [attribution, reference-database, deck, figshare, zenodo]
requires:
  - phase: 105-documentation-and-outside-face
    provides: README, docs, deck and record texts from plans 01-08
provides:
  - Source credit for the COCONUT 13C shifts in every text that describes the reference database
  - Predicted-vs-experimental statement (895,099 COCONUT predicted; 33,344 NMRShiftDB experimental)
  - Final figshare paste text with a References click-path step; upload scripts carry the link as metadata
key-files:
  modified:
    - README.md
    - CLAUDE.md
    - docs/INSTALLATION.md
    - docs/SERVER_BOOTSTRAP.md
    - docs/ARCHITECTURE.md
    - docs/USER_GUIDE.md
    - rdmo-project-description.txt
    - scripts/figshare_upload.py
    - scripts/zenodo_upload.py
    - docs/infographics/build.py
    - docs/infographics/deck.html
    - docs/infographics/README.md
    - docs/infographics/ailsa-infographics.pdf
    - ~/Downloads/ailsa-figshare-record.txt (outside the repo)
requirements-completed: [DOC-01, DOC-02, DOC-03, DOC-04]
completed: 2026-10-14
---

# Phase 105 Plan 10: Credit the COCONUT shift source Summary

**The D-17 credit and the predicted/experimental statement now appear in the README, CLAUDE.md, four docs, the rdmo text, the figshare paste text, both upload scripts and deck slide 8 (source, HTML, PDF).**

## Task Commits

1. Task 1: README, CLAUDE.md, INSTALLATION, SERVER_BOOTSTRAP, ARCHITECTURE, USER_GUIDE - `7205019`
2. Task 2: rdmo text, figshare and Zenodo upload scripts - `fd068f5` (the ~/Downloads record file is outside git)
3. Task 3: deck build.py, deck.html, README, PDF - `ca7d8bf`

## Verification (acceptance output)

Task 1 (per file: attr / doi / software name / pnm / exp / lucy / deletions vs 52583f1):
README 2/2/1/1/1/0/del 2; CLAUDE.md 1/1/1/1/1/0/del 1; INSTALLATION 1/1/1/1/1/0/del 1;
SERVER_BOOTSTRAP 1/1/1/1/1/0/del 0; ARCHITECTURE 1/1/1/1/1/0/del 0; USER_GUIDE 1/1/1/1/4/0/del 0
(USER_GUIDE already had other "experimental 13C shifts" hits). readme-found, ack, claude-row,
claude-rule, inst-row, inst-quote all 1; README reference-database attr 1; README relative links 0;
`tests/nus/test_portability_doc.py` 7 passed.

Task 2: attr/software name/exp >= 1 in rdmo, record file, figshare script, Zenodo script; no old name in any;
record click-path has the References step and 8 numbered steps; all six 105-07 Task 1 strings
still present in the record file (each 1, "Nuzillard" 2); deletions rdmo 0, figshare 0, Zenodo 2;
longest rdmo line 114; `DESC SAME`; `REFS ['https://doi.org/10.5281/zenodo.6561449']`;
`ZREL ['10.5281/zenodo.6561449']`; upload-logic diff filter empty; both scripts parse.

Task 3: build_attr 1, deck_attr 1, slide8_attr 1, tile 1, slides 8, lucy 0, readme8 1, build.py
deletions 2; PDF 8 pages; p8_doi 1, p8_footer 1, p7_doi 0; `DECK_SYNC`; tracked-lucy 0; commit
lists exactly the four deck files. Page-8 PNG viewed (scratchpad `slide8-8.png`, 60 dpi): the
credits box sits fully above the "08 / 08" footer, tile wraps to two lines, no overlap.

## Deliberately unchanged (reason)

- docs/BENCHMARK.md: mentions the reference DB only for its schema.
- Deck slide 3 ("928K compounds", "7.9M HOSE stats"): size only; the deck credit sits on slide 8.
- CLAUDE.md line 26 (download instruction): the credit sits in Database Reference.
- docs/nmr_shift_prediction_tools.md: NMRShiftDB as another tool's training data, not this DB.
- src/ailsa/cli/database.py: code; follow-up tracked in
  .planning/todos/pending/2026-10-14-cli-database-help-shift-credit.md, due before the PyPI upload.
- .claude/ skill files: Phase 106.
- scripts/bootstrap_case_host.sh and data/reference/*: D-12.

## Deviations from Plan

None in substance. One mechanical hiccup: the first edit script stopped on the USER_GUIDE
paragraph because the anchor string occurs in several sections; I inserted it by line position
after the Dereplication usage block instead. Result matches the plan.

## Issues Encountered

None. Chrome printed a harmless "Invalid mailbox" GPU message during PDF export; the PDF is 8 pages.

## Next

105-07 Task 2 (user edits the figshare record from ~/Downloads/ailsa-figshare-record.txt) may now
proceed. Nothing pushed; STATE.md and ROADMAP.md untouched.

## Self-Check: PASSED

Commits `7205019`, `fd068f5`, `ca7d8bf` found in git log; all listed files exist.

## Amendment (2026-10-14, after 105-07)

The user published the figshare record with a shorter source line that does not name the prediction
software: "COCONUT 13C shifts: from J.-M. Nuzillard, Zenodo, doi:10.5281/zenodo.6561449, CC BY 4.0".
All repository texts listed above, the deck (HTML and PDF) and `~/Downloads/ailsa-figshare-record.txt`
were aligned to that wording; the software name was removed from them. The CSP5 comparison scripts
were moved out of the repository into the private data folder. The verification figures above are
from the original execution; the phase gate re-checks the DOI in every file.
