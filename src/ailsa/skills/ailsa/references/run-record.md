# Run record

The coordinator keeps every run on record with the `ailsa run` commands: it creates the record
first, notes every validated message, reads the generated progress log, and declares or closes the
run at the end. Agents decide; tools write.

## Contents

- What the record is
- Run and work folder
- Notes
- Note formats
- Model reports
- Reading the progress log
- Declaring the result
- Hooks

## What the record is

The record is the run's hash-chained event log in a run folder outside the dataset. The `ailsa`
tools append their own events: every solver round (`ailsa lsd run`), every ranking
(`ailsa lsd rank`), every identity check (`ailsa identify`), every picked peak list. The
coordinator adds what only it knows, as notes, and declares the result once.

- The coordinator never writes `CASE-PROGRESS.md` or `final_results.md` by hand. Both are
  renderings that `ailsa run render` generates from the record, so they always show what the tools
  recorded and the result that was declared.
- A report written by hand is not the record: the record does not read it, and a result that
  exists only in such a file counts as no result.
- Never edit a rendering. The next `ailsa run render` overwrites it, and the change would not be in
  the record.

## Run and work folder

`ailsa run init` prints two lines: `RUN:` with the run id and `WORK:` with the absolute work folder,
the run's working corner for files the agents write. Keep the `WORK:` value as `{work_dir}`.

- Every file an agent writes goes under `{work_dir}`: the LSD files and solver output in
  `{work_dir}/iteration_NN/`, per-family searches in `{work_dir}/iteration_NN_<family>/`, the
  diagnostic specialist's `DIAGNOSTIC-REPORT.md`, any scratch file.
- The dataset folder `{compound_path}` stays read-only. A later blind run of the same data must not
  find earlier results there.
- Every path in a command is absolute. An agent's shell may start in the dataset folder, and a
  relative path would then write into the data.
- After a context compaction, run `ailsa run init` again with the same arguments: it prints the same
  run and the same work folder and creates nothing new.
- A run started by the launcher (`ailsa run start`) already has its record; `ailsa run init` then
  prints that run.

## Notes

A note is one line of prose in the record: `ailsa run note "<text>" --sender <name>`. The tool adds
the time and the sender; a note never fails a run.

On each validated structured message, in this order:

1. One note that summarises the message, in the format below, with the sending agent as sender.
2. A note that starts the next phase, `--phase <task>` with `--sender coordinator`, for example
   `--phase peak-picking`, `--phase lsd-iteration-01`, `--phase ranking`, `--phase identity-check`.
3. The `[BEGIN]` push of that task.

Rules:

- The sender is the agent's frontmatter name: `ailsa-nmr-chemist`, `ailsa-lsd-engineer`,
  `ailsa-solution-analyst`, `ailsa-devils-advocate`, `ailsa-diagnostic`. The coordinator's own
  decisions (the start of the run, an intervention, a gate verdict) carry `--sender coordinator`.
  The record joins notes with the other evidence about an agent by these names.
- A `--phase` note precedes every `[BEGIN]` push. A phase name different from the last one starts a
  new phase, so the record times each phase without separate stamps.
- Keep notes short; the limit is 4 000 characters. Long tables stay in the agents' messages and in
  their work files; the note carries a summary and the fields that loop detection reads.

## Note formats

Write fields as `Field: value; Field: value`, with the field names exactly as below, because loop
detection and the gates find the fields by these names. Placeholders in angle brackets stand for
the values from the message.

**Setup summary**, from `[SETUP-COMPLETE]`:

```bash
ailsa run note "Setup: DBE: <n>; Spectra found: <list>; Peak counts: <13C, HSQC, HMBC counts>; Multiplicities: <CH3/CH2/CH/C counts>; Symmetry: <verdict>; Quality assessment: <verdict>; Aromatic expectation: <verdict>; 13C shifts: <comma-separated ppm list>" --sender ailsa-nmr-chemist
```

**Iteration**, from `[ITERATION-COMPLETE]`:

```bash
ailsa run note "Iteration <NN>: LSD file: <absolute path>; Solution count: <n>; Constraints added: <list>; Constraints removed: <list>; HMBC correlations used: <X>/<Y>; Fragment search: <none or summary>; Fragment file: <none or path>; Confidence: <level>" --sender ailsa-lsd-engineer
```

**Validation**, from `[VALIDATION-PASSED]` or `[VALIDATION-BLOCKED]`:

```bash
ailsa run note "Validation: <PASSED or BLOCKED>; sp2 count: <n> (<even or odd>); H budget: <ok or mismatch>; Dropped constraints: <none or list>" --sender ailsa-devils-advocate
```

**Ranking**, from `[RANKING-COMPLETE]`:

```bash
ailsa run note "Ranking: Ranking id: <rkNN>; Top candidate: rank <n>, SMILES <smiles>, MAE <ppm>; Recommendation: <text>; Declaration draft: <outcome>, candidate <n>, confidence <level>" --sender ailsa-solution-analyst
```

**Intervention**, when the coordinator sends an advisory:

```bash
ailsa run note "Intervention: Pattern: <loop pattern>; Counter: <n>/10; Advisory sent: <one line>" --sender coordinator
```

**Multiplicity coverage**, only with a `[MULTIPLICITY-AMBIGUOUS]` record, whenever one of its four
items changes:

```bash
ailsa run note "Multiplicity coverage: viable_families: <list>; searched_families: <list>; DA-mandated models: <list>; gate verdict: <pending, PASS or FAIL with the missing list>" --sender coordinator
```

The coverage note carries no `--phase`, because coverage is a ledger, not a phase. The latest note
that begins with `Multiplicity coverage:` is the current ledger; the `DA-mandated models` are the
models the devil's advocate (DA) named in its multiplicity evidence.

## Model reports

Each specialist opens its first message with a `[MODEL]` line naming the model it runs on. As each
first message arrives, record that line as a self-report:

```bash
ailsa run note "model reported" --sender ailsa-nmr-chemist --self-reported-model <model id>
```

Use the agent's frontmatter name as the sender, and record the coordinator's own runtime model once
with `--sender coordinator`. The record joins these statements by agent name with what the harness
and the transcripts show about the same agent. A self-report stays provisional: it is what the
agent said, not what the harness saw.

## Reading the progress log

Before each loop check and before each gate, run `ailsa run render` and read the `CASE-PROGRESS.md`
path it prints (in the run folder's `renderings/`). The log is a table of every event in time
order:

- notes appear as "Note from <sender>: <text>";
- solver rounds appear as "Solver round N: X possible structures (outcome)" without any note,
  because `ailsa lsd run` records them itself;
- phases appear as "Phase started: <name>"; rankings, identity checks and the declaration appear as
  the tools recorded them;
- agent messages appear as "Message <from> to <to>" without their text; the notes carry the fields.

Loop detection reads these fields from the notes and finds them by these names:

- `Solution count:` in the iteration notes (the solver rows give the same count)
- `Constraints added:` in the iteration notes
- `sp2 count:` in the validation notes
- `H budget:` in the validation notes
- `HMBC correlations used: X/Y` in the iteration notes
- `Fragment search:` in the iteration notes
- `Fragment file:` in the iteration notes

The coverage gate reads the latest note that begins with `Multiplicity coverage:`.

## Declaring the result

The coordinator declares the result once, after the coverage gate (where it applies) and the
identity gate, and before the shutdown. Every exit after `ailsa run init` ends in one of these
commands, followed by `ailsa run render`:

| Exit path | Command |
|---|---|
| ranking accepted, identity gate done | `ailsa run finalize --outcome proposal --ranking rkNN --candidate N --confidence <level> --caveat "..." --open-question "..." --next-step "..."` |
| as above, but confidence is low or the data leave several candidates | the same with `--outcome proposal_under_determined` |
| ranking done, no candidate trusted | `ailsa run finalize --outcome inconclusive --ranking rkNN` |
| escalation to the user after the intervention cap | `ailsa run finalize --outcome handed_to_human --termination-reason "..."` |
| no solution after every diagnosis | `ailsa run finalize --outcome no_structure_fits --termination-reason "..."` |
| spectra unusable | `ailsa run finalize --outcome insufficient_data --termination-reason "..."` |
| smoke test | `ailsa run close --reason "smoke test"` |
| any failure after the record exists | `ailsa run close --reason "<failure>"` |

Rules:

- Name the ranking id that the solution analyst reported in `[RANKING-COMPLETE]` for the atom-by-atom
  ranking (`ailsa lsd rank ... --assigned ...`), never `latest`. The analyst's later cross-check
  ranking is the newest one, so `latest` would declare against the wrong ranking.
- `--candidate N` is the rank the analyst chose, which is not always 1. Confidence, caveats, open
  questions and next steps come from the analyst's declaration draft; repeat an option for each
  item.
- A devil's advocate flag from the identity gate becomes a `--caveat`, for example
  `--caveat "reported name tentative: <rationale>"`. It never blocks the declaration.
- If `finalize` refuses because a solver ran after the ranking (the ranking is stale), ask the
  solution analyst to rank again and declare against the new id. The same holds after the coverage
  gate reopened the run.
- `finalize` also refuses a ranking the tool did not record; a ranking typed into a message or a
  file is not one.
- After the declaration, `ailsa run render` prints the path of `final_results.md`; present that
  file. Never edit a rendering.

## Hooks

The tools record their own steps in every session. Agent messages, spawns and the models the harness
saw are recorded only by the recording hooks: in an open session after `ailsa run hooks install`
(reversible with `ailsa run hooks uninstall`), and always under the launcher. If `ailsa run status`
shows `hooks_recorded: False` after the first specialist turn, tell the user once that agent
messages are not being recorded and that `ailsa run hooks install` turns the recording on for the
next session. It is not a gate: the run continues.
