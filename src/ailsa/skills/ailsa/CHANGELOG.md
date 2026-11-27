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
- Measurement: a rule inventory maps every rule of the old files to its new place. The old files
  hold 1642 rule units in 15 files: 1029 match their new text closely, 555 are reworded and 58
  have no close match. Every reworded rule was read against its old text by a reviewer that did
  not do the restructuring: 3 had turned an obligation into a plain statement and were restored,
  and all reworded rules now state the same rule. Each of the 58 without a match is accounted for:
  19 found at another place, 8 merged duplicates, 18 removed examples that named a compound or
  dataset, 10 project-history notes, 2 model IDs, 1 dead reference. Of the 406 rules that used
  capital-letter emphasis, 388 now carry their reason and 18 have no known reason. One blind
  acceptance run checks the renamed chain (result to follow).
- Rules kept without a known reason: 18. They are marked for measurement before the workflow is
  rewritten (planning phase 109). The list is in the maintainer's private inventory folder
  `~/Dropbox/develop/data/skill-rule-inventory-106/` (files `reasons-*.tsv`, column
  `reason_known=no`). It quotes the old rule text, which names benchmark datasets, so it must
  never be added to this repository.
