---
quick_id: 261013-knr
slug: csp5-13c-comparison-on-coconut
status: complete
completed: 2026-10-13
---

# CSP5 vs the current COCONUT 13C predictions (sample comparison)

## What was done

The free 13C predictor CSP5 (Goodman group, MIT licence, trained on experimental shifts) was
compared with the predicted shifts that the reference DB holds for COCONUT (COCONUT 13C shifts:
from J.-M. Nuzillard, Zenodo, doi:10.5281/zenodo.6561449, CC BY 4.0):

- on a reproducible sample of 20,000 COCONUT records (CSP5 vs the current shifts, per carbon), and
- on 12,642 NMRShiftDB2 molecules held out from CSP5's training, against their experimental
  spectra (CSP5, the current shifts where available, and the current HOSE predictor).

The scripts, per-atom data, results, the report and an independent verification of the report
stay outside the repository in the private CSP5 data folder.

## Outcome in brief

- CSP5 is the strongest of the free options measured: on the same held-out carbons a HOSE table
  built only from experimental NMRShiftDB2 spectra reaches 3.48 ppm mean absolute error, CSP5
  1.76 ppm.
- Whether a reference DB built from CSP5 predictions over COCONUT should replace the current
  shifts is an open decision (ROADMAP.md v11.0, open decision 5).

## Technical findings worth keeping

- CSP5's own conformer embedding has no time limit; a handful of natural products blocked the
  first run for hours. The runner now embeds per molecule with a time limit (ETKDG, 3 attempts)
  and must add explicit hydrogens before embedding.
- The NMRShiftDB2 SD export sets the MDL atom valence field to the current bond-order sum, so RDKit
  reads many carbons as hydrogen-free; the runner clears it before parsing.
- 0.8 % of the COCONUT sample (153 of 20,000) could not be embedded within the time limit.
