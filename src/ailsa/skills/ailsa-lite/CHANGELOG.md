# ailsa-lite changelog

Each entry says which skill it applies to (see docs/SKILLS.md) and, for a change of behaviour,
which measurement supports it.

## 0.1.0

Applies to: ailsa-lite only.

- First version. One agent, six steps (`ailsa case scan`, `setup`, `check`/`edit`, `solve`,
  `rank`, `report`); the commands keep all state in `analysis/problem.json` and write the LSD
  input themselves.
- Measured so far only on the development datasets, driving the commands without a model.
  Not yet measured with a small model.
