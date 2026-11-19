# ailsa-lite changelog

Each entry says which skill it applies to (see docs/SKILLS.md) and, for a change of behaviour,
which measurement supports it.

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
