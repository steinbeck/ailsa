---
phase: 105-documentation-and-outside-face
plan: 07
subsystem: docs
tags: [figshare, zenodo, reference-database, rename]
requires:
  - phase: 105-documentation-and-outside-face
    provides: shift source credit in the paste text and upload metadata (plan 10)
provides:
  - Public figshare record of the reference database under the AILSA name (version 3, same DOI, same file)
  - Upload scripts for figshare and Zenodo with the AILSA title and description
key-files:
  modified:
    - scripts/figshare_upload.py
    - scripts/zenodo_upload.py
    - ~/Downloads/ailsa-figshare-record.txt (outside the repo)
requirements-completed: [DOC-03]
completed: 2026-10-14
---

# Phase 105 Plan 07: figshare record under the AILSA name Summary

**The public record 10.6084/m9.figshare.31073554 now carries the AILSA title and description as version 3; base DOI, file and licence are unchanged.**

## Task Commits

1. Task 1: AILSA title/description in `scripts/figshare_upload.py` and `scripts/zenodo_upload.py` - `0405447`
2. Task 2: browser edit and publish by the user from `~/Downloads/ailsa-figshare-record.txt` (no API token, D-09) - no commit
3. Task 3: public API check - this SUMMARY

## Public record after the edit (API check 2026-10-14)

| Field | Value |
|-------|-------|
| Title | AILSA reference database: 13C NMR shifts and HOSE statistics for natural-product dereplication and shift prediction (COCONUT + NMRShiftDB) |
| Version | 3 |
| DOI | 10.6084/m9.figshare.31073554.v3 (base DOI 10.6084/m9.figshare.31073554 unchanged) |
| File | ID 61078393, `lucy-ng-derep.db.zip`, 828,954,592 bytes (unchanged, D-10/D-16) |
| Licence, category, tags | CC BY 4.0; Computational chemistry; Cheminformatics, Natural products, dereplication (unchanged) |

The Task 3 check prints `FIGSHARE_OK`: title and description contain AILSA, the description credits LSD and
Jean-Marc Nuzillard, links https://github.com/steinbeck/ailsa, carries doi 10.5281/zenodo.6561449 for the
COCONUT shift source and no longer contains the old name. DataCite already serves the new title for the base
DOI.

## Deviations

- **Source line worded by the user.** The published description reads "COCONUT 13C shifts: from
  J.-M. Nuzillard, Zenodo, doi:10.5281/zenodo.6561449, CC BY 4.0" and does not name the prediction software;
  the user shortened the paste text in the browser. The Zenodo DOI is in the description; the "References"
  field of the record is empty.
- **DOI resolver status 202, not 200.** `doi.org` redirects (302) to the figshare landing page, which answers
  scripted requests with 202 (figshare's bot challenge), with and without a browser user agent. The record
  itself resolves: the versioned API URL returns 200 and DataCite holds the new title. The landing-page URL
  still carries the old title slug; figshare resolves articles by ID, so the slug does not matter.
- **GitHub link resolves.** The repository was renamed to `steinbeck/ailsa` on 2026-10-14 (pulled forward
  from Phase 111), so the links in the record are live; the old `steinbeck/lucy-ng` URLs redirect.
