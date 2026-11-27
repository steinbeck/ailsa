# Aliphatic multiplicity ambiguity

Shared protocol for the case where the multiplicity of aliphatic CH, CH₂ and CH₃ carbons cannot be
determined from the spectra. Four readers use it: the NMR chemist detects the ambiguity and sends
the record, the coordinator records it and closes it, the LSD engineer searches every family, and
the devil's advocate (DA) checks that no model with spectral evidence is left out.

## Contents

- Why every family is searched
- Trigger
- Enumerate the viable families
- Cap of three families
- The [MULTIPLICITY-AMBIGUOUS] record
- Who uses the record

## Why every family is searched

When aliphatic CH/CH₂/CH₃ multiplicity cannot be determined from the spectra, the search covers
every viable whole-molecule multiplicity family. Otherwise the correct constitution is excluded
from the solution set before LSD runs: with a single hard-coded multiplicity model, a correct
structure from another family is never searched.

## Trigger

The NMR chemist decides from the program output, not by looking at the spectrum. Declare the
aliphatic block multiplicity-ambiguous when:

- **(a) HSQC is not multiplicity-edited.** Run `ailsa pick hsqc <hsqc_path> --format json` and
  read the `multiplicity_edited` field, the boolean the picker sets. Do not judge the editing by
  eye; read this field. `multiplicity_edited: false` (no negative cross-peaks) means that the
  CH/CH₂/CH₃ sign cannot be determined from HSQC.

  and/or

- **(b) APT/DEPT is phase-unreliable or inconsistent** by the NMR chemist's reliability
  assessment (phase varies across the range, signs inconsistent with the shift regions,
  distortion that makes the negative=CH₂ rule untrustworthy).

`multiplicity_edited: false` is necessary but not sufficient on its own. The decision combines
the HSQC boolean with the APT/DEPT reliability verdict. An edited HSQC
(`multiplicity_edited: true`) with a clean, phase-consistent DEPT-135 is not ambiguous: the
high-confidence sign evidence (the DEPT-135 sign, the highest evidence priority, trusted at 100 %)
determines multiplicity and no enumeration is needed. Declare ambiguous only when the
high-confidence sign signals are absent (non-edited HSQC) or unreliable (phase-distorted
APT/DEPT).

There is no numeric threshold for this decision in the skill text. The negative-cross-peak
detector that produces `multiplicity_edited` is part of `ailsa pick hsqc`; read its boolean.

## Enumerate the viable families

On the ambiguous condition, enumerate the viable families: the chemically sensible whole-molecule
CH₃/CH₂/CH integer partitions of the ambiguous aliphatic carbons and their attached protons that
are consistent with the molecular formula, the H count and the DBE. Use the DBE formula
DBE = (2C + 2 + N − H) / 2 and the H budget from the NMR chemist's DBE self-check.

Enumerate at the whole-molecule level, not as a per-centre cross-product: the cross-product
explodes and is harder to justify chemically.

Two partitions that satisfy the same formula, H count and DBE on the same skeleton are both
viable; list both.

## Cap of three families

Cap the viable families at 3. If more than 3 partitions are formally valid, rank them by prior
chemical plausibility, list the top 3, and state the truncation explicitly so that the
coordinator records it in CASE-PROGRESS.md. Do not drop a valid family silently; a truncation is
always documented.

## The [MULTIPLICITY-AMBIGUOUS] record

When the block is ambiguous, the NMR chemist sends a structured `[MULTIPLICITY-AMBIGUOUS]`
message to the coordinator in addition to `[SETUP-COMPLETE]`; the coordinator records both. The
record carries the ambiguity basis (the `multiplicity_edited` value and the APT/DEPT verdict) and
an explicit numbered `viable_families:` list, each family naming the per-atom multiplicity. The
LSD engineer consumes this list deterministically: one fully constrained LSD run per family.

```
[MULTIPLICITY-AMBIGUOUS]
Basis: HSQC multiplicity_edited=<true|false> (from ailsa pick hsqc --format json); APT/DEPT verdict=<reliable|phase-unreliable: reason>
Ambiguous aliphatic carbons: <atom# list with shifts>
viable_families:
  1. <family name>: <per-atom multiplicity, e.g. C11/C12/C13 = CH3, C14 = CH>
  2. <family name>: <per-atom multiplicity, e.g. C11/C12 = CH3, C13/C14 = CH2>
  3. <...>  (only if a 3rd valid partition exists)
Cap/truncation: <"none — N ≤ 3 families" or "N valid; top 3 by plausibility searched, dropped: <list>">
```

If the aliphatic block is not ambiguous (edited HSQC and/or clean DEPT-135), the NMR chemist does
not send this record and assigns multiplicities normally from the sign evidence.

## Who uses the record

- **Coordinator:** records the message and keeps a `## Multiplicity Coverage` ledger in
  CASE-PROGRESS.md. Its pre-accept coverage gate closes the record: the run does not accept until
  every viable family, and every model the DA has mandated, has been searched in its own LSD run.
- **LSD engineer:** runs each viable family as a separate, fully constrained LSD run in its own
  `iteration_NN_<family>/` directory.
- **DA:** the multiplicity gate (G-MULT). Positive spectral evidence for a whole-molecule model
  that the searched families cannot explain becomes a mandatory search item
  (`[MULT-EVIDENCE-FOR] model=X`).
