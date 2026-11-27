# ailsa changelog

Each entry says which skill it applies to (see docs/SKILLS.md) and, for a change of behaviour,
which measurement supports it.

## 0.2.0

Applies to: ailsa (frontier skill) only; the lean skill writes the record since its 0.3.0. Recording only: no chemistry rule changed.

- New reference `references/run-record.md`: what the coordinator notes and in which format (the
  field names loop detection reads are unchanged), how it reads the progress log that
  `ailsa run render` generates, how model self-reports are recorded, and how every exit path
  declares the result with `ailsa run finalize` or closes the run with `ailsa run close`.
- The coordinator creates the run record as its first step after the environment checks
  (`ailsa run init <compound_path> --formula <formula> --skill ailsa --mode team`), before any
  team, task or spawn; after a context compaction the same command reads the run back.
- Every spawn prompt and the first push carry the absolute work folder `{work_dir}`; agents write
  there, and the dataset folder stays read-only. The coordinator no longer creates `analysis/` in
  the dataset.
- The coordinator records one `ailsa run note` per validated structured message and a `--phase`
  note before every `[BEGIN]` push; it reads the progress log that `ailsa run render` generates
  instead of writing `CASE-PROGRESS.md` itself. The multiplicity coverage ledger is kept as
  `Multiplicity coverage:` notes.
- Every exit path declares the result with `ailsa run finalize` naming the ranking id from
  `[RANKING-COMPLETE]` explicitly (never the newest ranking, which is the analyst's cross-check),
  or closes the run with `ailsa run close`, then renders; `final_results.md` is a rendering.
  `[RANKING-COMPLETE]` now requires `Ranking id` and `Declaration draft`; the solution analyst
  writes no report file.
- Each specialist's `[MODEL]` line is recorded as a self-report note under the agent's frontmatter
  name; the coordinator records its own model the same way.
- The web-view launch, the wall-clock timing stamps and the run manifest written into the dataset
  are gone; the record's event times and the phase notes replace the timing.
- References `timing` and `progress-format` are replaced by `run-record`.
- The solution analyst writes no report file and no ranking file: it ranks from the absolute work
  folder, reports the `ranking_id` of the atom-by-atom ranking as `Ranking id:` (the cross-check
  ranking is recorded later and would otherwise count as the newest) and sends a
  `Declaration draft:` (outcome, candidate, confidence, caveats, open questions, next steps) in
  `[RANKING-COMPLETE]`. The verdict-keyed identity rules now govern the message's `Identity:`
  line instead of a report header.
- The devil's advocate's name gate runs after `[RANKING-COMPLETE]` and before the result is
  declared, on the reported name and top SMILES in the coordinator's `[BEGIN] G-IDENT` message;
  a flag becomes a caveat of the declaration. Its file paths are under the work folder.

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
  acceptance run, on a benchmark dataset that the paper skill had solved at rank 1, completed on
  its first attempt through `/ailsa:case` and placed the true structure at rank 1.
- Rules kept without a known reason: 18. They are marked for measurement before the workflow is
  rewritten (planning phase 109). The list is in the maintainer's private inventory folder
  `~/Dropbox/develop/data/skill-rule-inventory-106/` (files `reasons-*.tsv`, column
  `reason_known=no`). It quotes the old rule text, which names benchmark datasets, so it must
  never be added to this repository.
