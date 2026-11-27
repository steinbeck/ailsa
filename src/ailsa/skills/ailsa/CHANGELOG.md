# ailsa changelog

Each entry says which skill it applies to (see docs/SKILLS.md) and, for a change of behaviour,
which measurement supports it.

## 0.1.0

Applies to: ailsa (frontier skill) only.

- Commands renamed to `/ailsa:*` and agents to `ailsa-*`.
- Packaged with the CLI and installed with `ailsa skill install ailsa`.
- Unused supervisor agent removed.
- CLI calls use `ailsa`.
- Measurement: rule inventory plus one blind acceptance run (filled in by later plans).
