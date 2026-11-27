# ailsa changelog

Each entry says which skill it applies to (see docs/SKILLS.md) and, for a change of behaviour,
which measurement supports it.

## 0.1.0

Applies to: ailsa (frontier skill) only.

- Commands renamed to `/ailsa:*` and agents to `ailsa-*`.
- Packaged with the CLI and installed with `ailsa skill install ailsa`.
- Unused supervisor agent removed.
- CLI calls use `ailsa`.
- Restructured to the skill-authoring form: every file under 500 lines, a contents list in every
  file over 100 lines, and details in one-level reference files that a command or agent reads at
  a named step; a reference never sends the reader on to another reference. The LSD facts that
  the LSD engineer, the devil's advocate and the diagnostic specialist share are one reference,
  `references/lsd-reference.md`, instead of separate copies.
- Model check: each agent reports the model it runs on in its first message, and the coordinator
  records the reported models in the progress log. They are no longer compared with an intended
  model, and the spawn calls of the four specialists name no model.
- Rules are plain sentences with their reason where one is known, instead of capital-letter
  emphasis.
- Examples name no compound and no dataset number; usage examples use placeholders.
- Project history, dead references and model IDs removed; one term per role.
- The commands that describe the reference database credit the source of the COCONUT shifts.
- No chemistry rule was added, removed or changed.
- Measurement: a rule inventory maps every rule of the old files to its new place (counts to
  follow), and one blind acceptance run checks the renamed chain (result to follow).
