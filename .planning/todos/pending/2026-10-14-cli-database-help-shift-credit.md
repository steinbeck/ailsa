---
created: 2026-10-14
title: "`ailsa database download --help` describes the reference DB without the COCONUT shift source credit"
area: cli
files:
  - src/ailsa/cli/database.py
---

## Problem

The docstring of `download` in `src/ailsa/cli/database.py` (lines 219–220, shown by
`ailsa database download --help`) says the database holds "928K compounds (COCONUT + NMRShiftDB)
with 13C NMR shifts and 7.9M HOSE statistics". It does not say that the COCONUT 13C shifts are
predicted, nor credit their source.

Phase 105 (decision D-17, 2026-10-14) adds the credit to every document that describes the
database, but code was out of its scope (Phase 104, the package rename, is closed). The help text
ships inside the PyPI package, whose upload is deferred until after Phase 107 (D-05) — it should
carry the credit before that upload.

Recorded during the Phase 105 plan revision (plan check, 2026-10-14). The skill files that describe
the database are a separate note under Phase 106 in ROADMAP.md.

## Fix (quick task)

Add one sentence to the docstring, keeping "13C" in ASCII:
"The COCONUT 13C shifts are predicted, not measured; the NMRShiftDB shifts are experimental.
COCONUT 13C shifts: ACD/Labs predictions from J.-M. Nuzillard, Zenodo, doi:10.5281/zenodo.6561449,
CC BY 4.0." Update any test that snapshots this help text.

## Acceptance

- `ailsa database download --help | grep -c 'zenodo.6561449'` ≥ 1 and the output says the COCONUT
  shifts are predicted.
- Lands before the PyPI upload that follows Phase 107.
