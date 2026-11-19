# ailsa-lite changelog

Each entry says which skill it applies to (see docs/SKILLS.md) and, for a change of behaviour,
which measurement supports it.

## 0.2.1

Applies to: both skills (frontier: LSD engineer, devil's advocate, diagnostic, solution analyst,
advisory templates; the lean skill already had most of these from 0.2.0).

- LSD facts corrected, each tested against LSD 3.4.9 on a small known molecule: one FEXP line
  per file (a second aborts with error 402; a fragment goodlist joins the ring filters as
  `FEXP "F3 AND NOT F1 AND NOT F2"`); one HSQC line per atom, also for a CH2 with two proton
  shifts (error 234); pyrrole N-H is `N 3 1` (`N 2 1` gives an odd sp2 count, error 390); PROP
  counts are exact (`+` at least, `-` at most, 0 all); `lsd analyze` reports 4J as
  `j_coupling` 4 = `path_length` 3; `DEFF NOT` and SYME abort LSD (errors 150, 102) and
  `lsd run` does not translate them; list names are `L1`-`L20` (error 114); grouped HMBC only on
  the carbon side (error 116 otherwise); the order of HSQC and HMBC lines is a convention, not an
  error.
- Lean skill: a heteroatom on one of several candidate carbons is written `PROP X 1 L1` on the
  heteroatom; `PROP L1 1 L2` forced an O onto every candidate.

## 0.2.0

Applies to: ailsa-lite only (content derived from the frontier skill).

- Same tools and rules as the frontier skill, condensed for one agent: the model builds the atom
  list, writes and checks every LSD file, diagnoses failures and ranks the candidates itself.
  Core instruction plus four reference files read on demand (NMR analysis, LSD input, checks and
  diagnosis, ranking). The `ailsa case` commands are no longer used.
- Atom-by-atom ranking (`ailsa lsd rank --assigned`), `DUPL 1` in every LSD file, and the
  measured shift first in each carbon's MULT comment. Applies to both skills (frontier: solution
  analyst, LSD engineer, devil's advocate, coordinator). Measured: on a blind dataset the
  nearest-line ranking had the right structure at rank 3, the atom-by-atom ranking at rank 1.
- Reason: with 0.1, a 27 B open-weight model found 2 of 40 blind benchmark structures, the same 2 the commands
  found without a model; the scripts set the limit and the evaluation measured them, not the model.

## 0.1.0

Applies to: ailsa-lite only.

- First version. One agent, six steps (`ailsa case scan`, `setup`, `check`/`edit`, `solve`,
  `rank`, `report`); the commands keep all state in `analysis/problem.json` and write the LSD
  input themselves.
- Measured so far only on the development datasets, driving the commands without a model.
  Not yet measured with a small model.
