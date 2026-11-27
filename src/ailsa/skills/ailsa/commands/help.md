---
description: Overview of the AILSA commands and when to use each. Use when: which AILSA command fits, what AILSA can do, list the commands
---

# AILSA: AI-Powered NMR Structure Elucidation

## What do you want to do?

**I have an unknown compound and want to determine its structure from NMR data**
→ `/ailsa:case <compound_path> <formula>` — Full autonomous CASE workflow with 4-agent team

**I have a known structure (SMILES) and want to predict its 13C shifts**
→ `/ailsa:predict "<smiles>"` — HOSE-code based 13C shift prediction

**I have a 13C spectrum and want to check if the compound is in the database**
→ `/ailsa:dereplicate <bruker_path> <formula>` — Match spectrum against 928K compounds

**I want to prepare an NMR dataset for blind CASE evaluation**
→ `/ailsa:sanitise <dataset_path>` — Remove compound names, CAS numbers, structure files

**I want to check if my environment is ready**
→ `/ailsa:status` — Verify ailsa CLI, LSD solver, and database are installed

## Available Sub-Commands

| Command | Description |
|---------|-------------|
| `/ailsa:status` | Check environment readiness (ailsa, LSD, database) |
| `/ailsa:dereplicate` | Match 13C spectrum against compound database |
| `/ailsa:predict` | Predict 13C chemical shifts for a SMILES structure |
| `/ailsa:sanitise` | Remove compound identifiers for blind CASE evaluation |
| `/ailsa:case` | Full CASE workflow - autonomous structure elucidation from NMR |

## Quick Start

Not sure which command? See the decision tree above.

1. Check your environment: `/ailsa:status`
2. Try dereplication: `/ailsa:dereplicate data/compound/2 C14H16`
3. Try prediction: `/ailsa:predict "CCO"`
4. Sanitise a dataset: `/ailsa:sanitise data/compound/Ibuprofen`
5. Run full CASE: `/ailsa:case data/compound/virgiline C16H21NO2`
