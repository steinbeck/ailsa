---
description: "Full CASE workflow — autonomous NMR structure elucidation. Use when: unknown compound, determine structure, identify molecule, what is this compound, structure determination from NMR"
argument-hint: "<compound_path> <formula>"
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
  - Task
  - TeamCreate
  - TeamDelete
  - TaskCreate
  - TaskList
  - TaskUpdate
  - SendMessage
---

<objective>
Coordinate the full Computer-Assisted Structure Elucidation (CASE) workflow: spawn a team of four
specialists (the NMR chemist, the LSD engineer, the solution analyst and the devil's advocate (DA))
and supervise it. Monitor progress through the run record (one note for every validated message,
and the progress log that `ailsa run render` generates from the record) and through TaskList;
detect unproductive loop patterns, diagnose root causes, intervene with advisory constraints via
SendMessage, and escalate to the user after 10 failed intervention cycles per pattern. The
coordinator does not perform CASE work itself; it delegates to the team.

Do not attempt dereplication. Dereplication is a completely separate workflow; CASE starts from
scratch with the NMR spectra only.
</objective>

## Contents

The steps in run order; those marked "reference" read their procedure from a reference file.

- parse_arguments: compound path, formula, smoke-test mode
- validate_prerequisites: environment checks before any spawn
- start_record: create the run record and the work folder, recovery after compaction
- spawn_case_team: coordination protocol, team and tasks, spawn calls, model disclosure, headless caveat, kick-off
- record_progress: notes for every validated message, multiplicity coverage notes, reading the generated log (reference)
- validate_message: required fields of each structured message
- monitor_progress: the run loop, iterations, ranking, stall recovery (reference)
- detect_loops: loop patterns (reference)
- diagnose: root causes of a loop (reference)
- intervene: advisory per pattern (reference)
- track_and_decide: intervention counters and decision (reference)
- escalate: escalation report (reference)
- coverage_gate: multiplicity coverage before accept (reference)
- identity_gate: G-IDENT review before the result is declared (reference)
- deliver_advisory_and_results: advisory and result templates (reference)
- smoke_test_report: smoke-test report (reference)
- terminate_team: declare or close the run, render, shutdown, cleanup

## Process

<process>

<step name="parse_arguments">
Extract the compound path and the molecular formula from the user input. **Arguments:**
`<compound_path> <formula>`, both optional if they can be inferred. **Resolution logic:**

1. **Both provided:** use them directly.
2. **compound_path missing:** check whether the current directory looks like a Bruker compound
   directory:
   ```bash
   ls -d [0-9]*/acqus 2>/dev/null | head -1
   ```
   If numbered subdirectories with `acqus` files exist, use `.` (the current directory) as
   compound_path.
3. **formula missing:** first look for it on disk in `{compound_path}`, and ask the user only if
   nothing usable is found. Many compound directories ship the formula in a small sidecar text
   file; read it instead of prompting. Search generically; do not hard-code one file name, because
   the conventions differ. Check these common formula sidecars in order:
   ```bash
   # look for a formula sidecar in the compound dir (case-insensitive, several conventions)
   for f in "$CP"/molecular-formula.txt "$CP"/molecular_formula.txt "$CP"/formula.txt \
            "$CP"/molform.txt "$CP"/*.formula; do
     [ -f "$f" ] || continue
     cand=$(tr -d ' \t\r\n' < "$f")
     # accept only a plausible molecular formula token (element symbols + counts)
     if printf '%s' "$cand" | grep -Eq '^([A-Z][a-z]?[0-9]*)+$'; then
       echo "FORMULA_FROM_FILE=$cand ($f)"; break
     fi
   done
   ```
   (`$CP` = `{compound_path}`.) If a plausible formula is found, use it and tell the user which
   file it came from (for example "Using formula <formula> from molecular-formula.txt"). Only if
   no sidecar yields a valid formula, ask the user, for the formula and nothing else:
   ```
   What is the molecular formula? (element symbols with counts)
   ```
4. **Neither provided and the current directory is not a compound directory:** show brief usage:
   ```
   cd into your compound directory, then: /ailsa:case <formula>
   ```

**Smoke test mode:** if the user's invocation includes `--smoke-test` or `smoke test`:
- Set SMOKE_TEST = true.
- Resolve `<compound_path> <formula>` as above; the skill ships no example dataset to default to.
- Print the header:
  ```
  ========================================
  SMOKE TEST — CASE Pipeline Validation
  ========================================
  Compound: {compound_path}
  Formula: {formula}
  Mode: 1-iteration validation (not full CASE)
  ```
</step>

<step name="validate_prerequisites">
Check that the environment is ready. Run each check via Bash; on any failure, stop and do not
spawn the team.

0. `echo $CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` must print "1". Fix: `export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
1. `ailsa --version` must succeed. Fix: `pip install ailsa`
2. `ailsa lsd check`: LSD and outlsd must be available. Fix: download from http://eos.univ-reims.fr/LSD/ and add bin/ to PATH
3. `ailsa predict c13 "CCO" --format json 2>/dev/null | head -1` must succeed. Fix: `ailsa database download`
4. `ls <compound_path>`: the directory must exist.
</step>

<step name="start_record">
Create the run record as the first step after the checks, before any team, task or spawn:
```bash
ailsa run init <compound_path> --formula <formula> --skill ailsa --mode team
```
It prints `RUN:` (the run id) and `WORK:` (the absolute work folder). Keep the `WORK:` value as
`{work_dir}` and the run id. The record has to exist before anything happens, so that every later
tool step lands in it. The work folder lies outside the dataset: `{compound_path}` stays read-only,
so a later blind run of the same data finds no earlier results there.

- If the command refuses (for example a blind refusal because earlier results are readable), stop,
  show its message and spawn nothing.
- After a context compaction, run the same command again to read the run and the work folder back;
  it creates nothing new.
- From here on every exit, a failure and the smoke test included, ends in terminate_team with
  `ailsa run close`, after `ailsa run finalize` when a result is declared, so no record is left
  open. A check that failed before this step needs no close.
</step>

<step name="spawn_case_team">
Spawn the four-agent CASE specialist team via TeamCreate and Task(team_name). The coordinator is
this command itself. Do not spawn a coordinator agent: the command manages the team, creates
tasks, delivers advisories and handles the lifecycle.

**Coordination protocol: push, never pull.** This protocol is what keeps a run from stalling.
Background teammates go idle between turns and do not poll the TaskList on their own. A
`TaskCreate` by itself never wakes an idle agent; the run simply stalls until a message arrives.
The coordinator therefore drives everything by message:
- After creating or assigning any task, immediately `SendMessage` the specific assignee an
  explicit `[BEGIN] <task>` directive. Do this right after each `TaskCreate`, and again
  immediately after the prerequisite agent reports.
- `TaskCreate` / `TaskList` / `TaskUpdate` are a status ledger for visibility only, never a work
  queue that agents poll.
- Agents act only on a received `SendMessage`. They do not "wait for", "monitor" or "claim from"
  the TaskList.
- A teammate's reply arrives as a conversation turn and wakes the coordinator, which then
  immediately pushes the next `[BEGIN]` directive. This message ping-pong is the only thing that
  keeps the workflow moving; there is no autonomous polling. If you find yourself waiting after a
  `TaskCreate` without having sent a `[BEGIN]`, that is the bug: push the directive.

**Step 1: Initialize the team namespace** ({compound_name} = last path component, e.g., "MyCompound")
```
TeamCreate(team_name="case-{compound_name}", description="CASE workflow for {compound_path} -- formula {formula}")
```

**Step 2: Create the initial shared tasks**
```
TaskCreate(
  subject="peak-picking",
  description="Pick 13C, HSQC, HMBC peaks for {compound_path} with formula {formula}.
               Run statistical detection (hybridisation, neighbours, hhb, grouping).
               Send structured [SETUP-COMPLETE] message to coordinator via SendMessage with all peak assignments, detection results, and quality assessment.",
  activeForm="Picking NMR peaks"
)

TaskCreate(
  subject="lsd-iteration-01",
  description="Build initial LSD file from peak assignments. Use HSQC for MULT definitions,
               add first HMBC batch (3-5 high-confidence correlations). Run LSD from
               {work_dir}/iteration_01/ directory. Send [ITERATION-COMPLETE] message to coordinator after LSD run.
               solutions.smi is produced automatically by ailsa lsd run (no manual outlsd step).",
  activeForm="Running LSD iteration 1"
)
```

**Step 3: Spawn the four specialist teammates.** The spawn calls carry no model argument.

```
Task(
  name="nmr-chemist",
  team_name="case-{compound_name}",
  subagent_type="ailsa-nmr-chemist",
  prompt="You are the NMR chemist for CASE of {formula} at {compound_path}.
          Work folder: {work_dir} (absolute). Write every file there and use absolute paths in every command; {compound_path} stays read-only.
          Begin only when the coordinator sends you a [BEGIN] peak-picking directive — do not poll or wait on the TaskList (idle agents are not woken by tasks, only by messages).
          Execute peak picking and statistical detection using the ailsa CLI.
          Send [SETUP-COMPLETE] message to coordinator via SendMessage with all peak assignments, detection results, and quality assessment.
          Mark the task completed (TaskUpdate, for the status ledger) and then wait for the coordinator's next [BEGIN] directive — never poll the TaskList for more work."
)

Task(
  name="lsd-engineer",
  team_name="case-{compound_name}",
  subagent_type="ailsa-lsd-engineer",
  prompt="You are the LSD engineer for CASE of {formula} at {compound_path}.
          Work folder: {work_dir} (absolute). Write every file there and use absolute paths in every command; {compound_path} stays read-only.
          Act only on the coordinator's [BEGIN] lsd-iteration directives sent to you via SendMessage — do not poll or wait on the TaskList (idle agents are woken by messages, not by tasks).
          On each [BEGIN] lsd-iteration-NN directive: build the LSD file in {work_dir}/iteration_NN/ and run the LSD solver there.
          Send [ITERATION-COMPLETE] message to coordinator via SendMessage after every iteration.
          Read the previous LSD file; never reconstruct it from memory, because constraints rebuilt from memory get dropped.
          Follow incremental HMBC strategy: 3-5 correlations per iteration.
          After reporting, wait for the coordinator's next [BEGIN] directive — never poll the TaskList. You will receive a shutdown_request when CASE is complete."
)

Task(
  name="solution-analyst",
  team_name="case-{compound_name}",
  subagent_type="ailsa-solution-analyst",
  prompt="You are the solution analyst for CASE of {formula} at {compound_path}.
          Work folder: {work_dir} (absolute). Write every file there and use absolute paths in every command; {compound_path} stays read-only.
          Act only when the coordinator sends you a [BEGIN] ranking directive via SendMessage — do not poll or monitor the TaskList (idle agents are woken by messages, not by tasks).
          The [BEGIN] ranking directive embeds the full experimental 13C shift list and the solutions.smi path.
          Assess chemical plausibility of top candidates.
          Write no report file: the record renders the results.
          Send [RANKING-COMPLETE] message to coordinator via SendMessage with ranking summary, the ranking id of the atom-by-atom ranking (the ranking_id field in the JSON output of the assigned ailsa lsd rank call) and a declaration draft (outcome, candidate rank, confidence, caveats, open questions, next steps)."
)

Task(
  name="devils-advocate",
  team_name="case-{compound_name}",
  subagent_type="ailsa-devils-advocate",
  prompt="You are the devil's advocate for CASE of {formula} at {compound_path}.
          Work folder: {work_dir} (absolute). Write every file there and use absolute paths in every command; {compound_path} stays read-only.
          Act only on requests received via SendMessage (from lsd-engineer or the coordinator) — do not poll the TaskList.
          On a pre-solver validation request:
          1. Diff current LSD file against previous iteration
          2. Check for dropped constraints (ring exclusion DEFF F/FEXP, COSY equivalence pairs, grouped notation)
          3. Verify sp2 count is even, H budget matches formula
          4. Send [VALIDATION-PASSED] or [VALIDATION-BLOCKED] to coordinator via SendMessage.
          On a post-solution [BEGIN] G-IDENT request (after [RANKING-COMPLETE], before the result is declared): run only your G-IDENT gate, the name and structure cross-check — read the reported trivial name + candidate SMILES from the coordinator's G-IDENT message, reason independently about whether the name matches the structure (do not call ailsa identify), apply the two G-IDENT triggers (an isomer name the data do not resolve; a recalled name whose ring linkage or symmetry does not match the drawn structure), and reply [G-IDENT-PASSED] or [G-IDENT-FLAGGED] with a one-line rationale.
          Report constraint persistence status after every validation."
)
```

**Step 4: Model disclosure.** Every teammate states its actual runtime model, so that the model
behind every agent is on record at the top of every run. Append this line to each of the four
`prompt=` strings above (it is identical for all four):
```
The first line of your very first SendMessage to the coordinator is exactly: [MODEL] <the exact model id shown in your system context> — copy the real id, do not guess or use an alias.
```
As each teammate's first message arrives, record its `[MODEL]` line as a self-report under the
agent's frontmatter name (`ailsa-nmr-chemist`, `ailsa-lsd-engineer`, `ailsa-solution-analyst`,
`ailsa-devils-advocate`):
```bash
ailsa run note "model reported" --sender <agent name> --self-reported-model <model id>
```
Record your own runtime model once the same way with `--sender coordinator`, read from your
environment or system context. The record joins these statements with the harness evidence by
agent name; a self-report stays provisional.

**Execution-mode caveat: headless, non-interactive runs (`claude -p`, batch or benchmark harness).**
It governs the kick-off below and every later wait for a reply. The message ping-pong of the
coordination protocol assumes that a teammate's reply arrives as a conversation turn that wakes
you. That wake-up happens only in an interactive session. A non-interactive (headless) run has no
event loop to re-enter a finished turn: if you send a `[BEGIN]` and then end your turn saying
"I'll wait for [ITERATION-COMPLETE]", the process simply exits mid-workflow. This is the
`NO_RESULT` failure mode. Detect this mode from your environment and system context (no
interactive user; invoked via `claude -p` or a harness). In it:
- Do not end a turn expecting to be woken. Do not background and wait.
- Drive every stage inline within one continuous turn: after each `[BEGIN]`, actively poll for
  completion in a loop. Read the `TaskList()` status and check the expected artefacts
  (`{work_dir}/iteration_NN/solncounter` or `*.sol`; `ailsa run status` for the iterations and the
  last solver outcome; the rankings the tool wrote under the run folder, `{work_dir}/../rankings/`),
  then proceed to the next stage yourself, without waiting for a wake-up.
- The run is done when you have declared the result yourself: do not stop before
  `ailsa run finalize` or `ailsa run close`.
- Treat teammate replies as best-effort: if a `[*-COMPLETE]` has not arrived but the artefact is
  on disk, read the result from the filesystem (as in the stall recovery of monitor_progress) and
  continue.

This keeps the identical push logic and changes only how you await each reply, so headless runs do
not stall. In an interactive session, the normal message-wake path applies unchanged.

**Step 5: Kick off.** The team does not start on its own: the freshly spawned teammates are idle
and do nothing until messaged, so push the first directive immediately after spawning.

Before the push, start the first phase, so the record times peak picking from here:
```bash
ailsa run note "start: formula <formula>" --phase peak-picking --sender coordinator
```
Then push:
```
SendMessage(
  type="message",
  recipient="nmr-chemist",
  content="[BEGIN] peak-picking — start now. Pick 13C/HSQC/HMBC for {compound_path} (formula {formula}; work folder {work_dir}), run statistical detection, then send [SETUP-COMPLETE] with all peak assignments, detection results, and quality assessment. Prepend your first message with the [MODEL] line.",
  summary="Kick off nmr-chemist peak-picking"
)
```

Do not proceed to a passive wait. After this push, enter monitor_progress: each teammate reply
arrives as a turn that wakes you; on each reply, immediately push the next `[BEGIN]` directive.
Do not rely on the teammate to poll the TaskList.
</step>

<step name="record_progress">
Read the note formats, the fields loop detection reads and the declaration table before the first
note:

Read file: ~/.claude/ailsa/references/run-record.md

The coordinator never writes CASE-PROGRESS.md or final_results.md: both are renderings that
`ailsa run render` generates from the record, and a hand-written copy is not the record. It records
one `ailsa run note` per validated structured message ([SETUP-COMPLETE], [ITERATION-COMPLETE],
[VALIDATION-PASSED/BLOCKED], [RANKING-COMPLETE]) with the sending agent as sender, and a note with
`--phase <task>` before every `[BEGIN]` push. Before each loop check it runs `ailsa run render` and
reads the progress log at the path that command prints.

**The multiplicity coverage ledger** (only when a `[MULTIPLICITY-AMBIGUOUS]` record exists).
When the NMR chemist has sent a `[MULTIPLICITY-AMBIGUOUS]` signal (see
`~/.claude/ailsa/references/multiplicity-ambiguity.md`), keep the ledger as notes whose text begins
with `Multiplicity coverage:` (format in run-record.md); the latest such note in the generated log
is the single source of truth that the pre-accept coverage gate reads. Record four things:

- **viable_families**: the numbered list from the NMR chemist's `[MULTIPLICITY-AMBIGUOUS]`
  signal, each family with its CH₃/CH₂/CH partition.
- **searched_families**: one entry per family that produced its own `iteration_NN_<family>/` run
  and a matching `[ITERATION-COMPLETE]`. Count a family as searched even if its `solutions.smi`
  conversion was skipped because the count was large (the searched-not-ranked rule). Do not
  require a ranked `solutions.smi` and do not key this off MAE or plausibility: searched means
  that the constrained LSD run ran and signalled, nothing more.
- **DA-mandated models**: every model X named in a DA `[MULT-EVIDENCE-FOR]` message (its
  multiplicity gate, G-MULT). These are binding mandatory-search items, closed only by an actual
  `iteration_NN_X/` search.
- **gate verdict**: PASS or FAIL, written by the coverage_gate step.

If no `[MULTIPLICITY-AMBIGUOUS]` record exists, write no coverage note; the single-family flow is
unaffected.
</step>

<step name="validate_message">
Validate incoming structured messages before processing them. Each message type has required
fields; if any are missing, request a resend via SendMessage.

**Required fields by message type:**
- [SETUP-COMPLETE]: DBE, Spectra found, Peak counts, Symmetry, Multiplicities, Quality assessment;
  Statistical detection, Grouping, HHB, Aromatic expectation; Conflicts with NMR evidence, Key
  observations
- [ITERATION-COMPLETE]: LSD file, Solution count, Constraints added, Constraints removed;
  Constraint inventory delta, sp2 count, H budget; HMBC correlations used, Why, Constraint
  effectiveness, Confidence; Fragment search, Fragment file
- [RANKING-COMPLETE]: Solutions, Top solution, Strained rings, Aromatic warning; Chemical
  plausibility, Quality, Recommendation; Ranking id, Declaration draft

**Validation procedure.** On receiving any structured message (identified by its `[TAG]` prefix),
identify the message type from the tag and check the message text for each required field label
(case-insensitive substring match of the field name followed by `:`). If any required field label
is missing, do not process the message. Send it back to the originating agent, and log "Message
validation failed for [{TAG}] from {agent}: missing {fields}":
```
SendMessage(
  type="message",
  recipient="{agent_name}",
  content="[RESEND-REQUIRED] Your [{TAG}] message is missing required fields: {list}.
           Please resend the complete message with all required fields.
           See your agent definition for the full template.",
  summary="Requesting resend of [{TAG}] — missing fields"
)
```
If all required fields are present, process the message in monitor_progress. "None detected",
"N/A", "None" and "0" are all valid values; only a truly missing field label triggers a resend.
</step>

<step name="monitor_progress">
From the kick-off until the results are ready: react to every reply, push the next `[BEGIN]`,
decide whether to iterate, rank or stop, and recover a stalled iteration. Read both files before
the first reply:
Read file: ~/.claude/ailsa/references/monitoring.md
Read file: ~/.claude/ailsa/references/loop-patterns.md
</step>

<step name="detect_loops">
After every iteration, and when the devil's advocate flags an issue: compare the history with the
five loop patterns, then continue, stop (converged or safety cap) or diagnose. The criteria are in
the section "Detect loops" of `monitoring.md`, the pattern definitions in:
Read file: ~/.claude/ailsa/references/loop-patterns.md
</step>

<step name="diagnose">
When detect_loops finds a pattern: find its root cause and document the findings for intervene.
Read file: ~/.claude/ailsa/references/monitoring.md (section "Diagnose")
</step>

<step name="intervene">
After diagnose: write an advisory that tells the agent what to fix, not how.
Read file: ~/.claude/ailsa/references/intervention.md (section "Intervene")
</step>

<step name="track_and_decide">
After each intervention: count it for its pattern and choose a basic advisory, the diagnostic
specialist, a specialist-informed advisory, honest termination or escalation.
Read file: ~/.claude/ailsa/references/intervention.md (section "Track and decide")
</step>

<step name="escalate">
After 10 failed intervention cycles for the same pattern: report to the user and stop.
Read file: ~/.claude/ailsa/references/intervention.md (section "Escalate")
</step>

<step name="coverage_gate">
Only with a `[MULTIPLICITY-AMBIGUOUS]` record, after the ranking and before identity_gate and before
the result is declared: accept only if every viable family and every model the devil's advocate
mandated was searched, else reopen.
Read file: ~/.claude/ailsa/references/coordinator-gates.md (section "Coverage gate")
A FAIL reopens the run with the multiplicity-coverage reopen advisory (the Multiplicity Coverage
Gap pattern in `loop-patterns.md`):
Read file: ~/.claude/ailsa/references/advisory-templates.md
</step>

<step name="identity_gate">
Once, after the ranking and a passed coverage_gate (where it applies), before the result is
declared: push the
devil's advocate's G-IDENT review of name and structure. A flag downgrades the name, never blocks.
Read file: ~/.claude/ailsa/references/coordinator-gates.md (section "Identity gate")
</step>

<step name="deliver_advisory_and_results">
Advisory delivery and formatting, result presentation (success, incomplete, failed), delegation to
the diagnostic specialist, extraction of its findings, and the anti-patterns to avoid:
Read file: ~/.claude/ailsa/references/advisory-templates.md
</step>

<step name="smoke_test_report">
Only in smoke-test mode, after the smoke test early exit: print the pass/fail table of the four
checkpoints, then go to terminate_team.
Read file: ~/.claude/ailsa/references/smoke-test.md
</step>

<step name="terminate_team">
Declare or close the run, then shut down all teammates gracefully and clean up the team
resources. This step runs after present_results (successful or failed CASE), escalate (user
escalation), smoke_test_report (smoke-test mode) or any failure after start_record.

**Step 0: Declare or close the run (before shutdown).** Pick the command from the exit-path table
in run-record.md. After an accepted ranking, declare against the ranking id rkNN from
`[RANKING-COMPLETE]`, not the newest ranking, because the analyst's cross-check ranking comes after
the decisive atom-by-atom one:
```bash
ailsa run finalize --outcome proposal --ranking rkNN --candidate N --confidence <level> --caveat "..." --open-question "..." --next-step "..."
```
- `--outcome proposal_under_determined` with the same options when the confidence is low or
  ambiguity remains; `--outcome inconclusive --ranking rkNN` when the ranking exists but no
  candidate is trusted.
- `--outcome handed_to_human --termination-reason "..."` after escalate;
  `--outcome no_structure_fits` when no solution remains after every diagnosis;
  `--outcome insufficient_data` when the spectra are unusable. These need no ranking.
- A devil's advocate flag from identity_gate becomes a `--caveat`; it never blocks the declaration.
- Smoke test: `ailsa run close --reason "smoke test"`. Any failure after start_record:
  `ailsa run close --reason "<failure>"`.
- If `finalize` refuses because a solver ran after the ranking, ask the solution analyst to rank
  again and declare against the new id.
- After a successful `finalize`, close the record: `ailsa run close --reason "result declared"`.
  The declared result stays; the close releases the session, so a later `/ailsa:case` starts a new
  run, and no tool step during the shutdown can make the declaration stale.

Then run `ailsa run render` and present the `final_results.md` whose path it prints. Do this on
every exit path, so that every record ends closed and rendered, with its result declared where
there is one.

**Step 1: Send shutdown requests to all four teammates:**
```
SendMessage(type="shutdown_request", recipient="nmr-chemist",
            content="CASE workflow complete. Shutting down team.")
SendMessage(type="shutdown_request", recipient="lsd-engineer",
            content="CASE workflow complete. Shutting down team.")
SendMessage(type="shutdown_request", recipient="solution-analyst",
            content="CASE workflow complete. Shutting down team.")
SendMessage(type="shutdown_request", recipient="devils-advocate",
            content="CASE workflow complete. Shutting down team.")
```

**Step 2: Wait for the shutdown confirmations.** Teammates approve shutdown automatically; they
have no reason to reject it after CASE completes.

**Step 3: Clean up the team resources** with `TeamDelete()`. This removes
`~/.claude/teams/case-{compound_name}/` and `~/.claude/tasks/case-{compound_name}/`.

**If TeamDelete fails (teammates still active):** wait 30 seconds and retry. If it still fails,
report: "Team cleanup incomplete. Manual cleanup may be needed: rm -rf ~/.claude/teams/case-{compound_name} ~/.claude/tasks/case-{compound_name}"
</step>

</process>
