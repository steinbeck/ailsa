---
created: 2026-11-24
title: "2D peak picker raises IndexError (from nmrglue) when no cross-peak lies above the threshold"
area: processing
files:
  - src/ailsa/processing/peak_picker_2d.py
---

## Problem

Found while executing Phase 106.1 plan 11 (recorded in `106.1-11-SUMMARY.md`): `ailsa pick 2d`
on a 2D spectrum with no peak above the picking threshold crashes with an `IndexError` raised
inside nmrglue instead of returning an empty peak list. The defect predates Phase 106.1; the
pickers were out of that phase's scope, so the tests there use synthetic 2D data with real
cross-peaks.

## Expected

An empty (or all-below-threshold) 2D spectrum yields zero peaks with an honest message, in text
and JSON output, and — inside a run — a peak-pick artefact with an empty peak list.

## Notes

Fail loud but not with a traceback: the agents must be able to tell "no peaks above threshold"
from a reader or file error.
