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
and supervise it. Monitor progress through CASE-PROGRESS.md, which the coordinator writes as sole
author, and through TaskList; detect unproductive loop patterns, diagnose root causes, intervene
with advisory constraints via SendMessage, and escalate to the user after 10 failed intervention
cycles per pattern. The coordinator does not perform CASE work itself; it delegates to the team.

Do not attempt dereplication. Dereplication is a completely separate workflow; CASE starts from
scratch with the NMR spectra only.
</objective>

## Contents

The steps in run order; those marked "reference" read their procedure from a reference file.

- parse_arguments: compound path, formula, smoke-test mode
- validate_prerequisites: environment checks before any spawn
- spawn_case_team: coordination protocol, team and tasks, spawn calls, model disclosure, headless caveat, kick-off
- write_progress: CASE-PROGRESS.md as sole author, the multiplicity coverage ledger
- timing: wall-clock stamps (reference)
- validate_message: required fields of each structured message
- monitor_progress: the run loop, iterations, ranking, stall recovery (reference)
- detect_loops: loop patterns (reference)
- diagnose: root causes of a loop (reference)
- intervene: advisory per pattern (reference)
- track_and_decide: intervention counters and decision (reference)
- escalate: escalation report (reference)
- coverage_gate: multiplicity coverage before accept (reference)
- identity_gate: G-IDENT review before the results (reference)
- deliver_advisory_and_results: advisory and result templates (reference)
- smoke_test_report: smoke-test report (reference)
- terminate_team: timing finalize, shutdown, cleanup

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
               Write analysis/ directory structure.
               Send structured [SETUP-COMPLETE] message to coordinator via SendMessage with all peak assignments, detection results, and quality assessment.",
  activeForm="Picking NMR peaks"
)

TaskCreate(
  subject="lsd-iteration-01",
  description="Build initial LSD file from peak assignments. Use HSQC for MULT definitions,
               add first HMBC batch (3-5 high-confidence correlations). Run LSD from
               analysis/iteration_01/ directory. Send [ITERATION-COMPLETE] message to coordinator after LSD run.
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
          Act only on the coordinator's [BEGIN] lsd-iteration directives sent to you via SendMessage — do not poll or wait on the TaskList (idle agents are woken by messages, not by tasks).
          On each [BEGIN] lsd-iteration-NN directive: build the LSD file in analysis/iteration_NN/, run the LSD solver.
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
          Act only when the coordinator sends you a [BEGIN] ranking directive via SendMessage — do not poll or monitor the TaskList (idle agents are woken by messages, not by tasks).
          The [BEGIN] ranking directive embeds the full experimental 13C shift list and the solutions.smi path.
          Assess chemical plausibility of top candidates.
          Write analysis/final_results.md with ranked structures.
          Send [RANKING-COMPLETE] message to coordinator via SendMessage with ranking summary."
)

Task(
  name="devils-advocate",
  team_name="case-{compound_name}",
  subagent_type="ailsa-devils-advocate",
  prompt="You are the devil's advocate for CASE of {formula} at {compound_path}.
          Act only on requests received via SendMessage (from lsd-engineer or the coordinator) — do not poll the TaskList.
          On a pre-solver validation request:
          1. Diff current LSD file against previous iteration
          2. Check for dropped constraints (ring exclusion DEFF F/FEXP, COSY equivalence pairs, grouped notation)
          3. Verify sp2 count is even, H budget matches formula
          4. Send [VALIDATION-PASSED] or [VALIDATION-BLOCKED] to coordinator via SendMessage.
          On a post-solution [BEGIN] G-IDENT request (after analysis/final_results.md exists): run only your G-IDENT gate, the name and structure cross-check — read the reported trivial name + top SMILES, reason independently about whether the name matches the structure (do not call ailsa identify), apply the two G-IDENT triggers (an isomer name the data do not resolve; a recalled name whose ring linkage or symmetry does not match the drawn structure), and reply [G-IDENT-PASSED] or [G-IDENT-FLAGGED] with a one-line rationale.
          Report constraint persistence status after every validation."
)
```

**Step 4: Model disclosure.** Every teammate states its actual runtime model, so that the model
behind every agent is on record at the top of every run. Append this line to each of the four
`prompt=` strings above (it is identical for all four):
```
The first line of your very first SendMessage to the coordinator is exactly: [MODEL] <the exact model id shown in your system context> — copy the real id, do not guess or use an alias.
```
As each teammate's first message arrives, read its `[MODEL]` line and record it. After all four
have reported (or at the [SETUP-COMPLETE] boundary), write the Team Models block
(`### Team Models` under `## Setup`) into CASE-PROGRESS.md per progress-format.md: one line per
teammate with the model it reported, and one line for the coordinator with its own runtime model,
read from your environment or system context.

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
  completion in a loop. Read the `TaskList()` status and check the expected filesystem artefacts
  (`analysis/iteration_NN/solncounter` or `*.sol`, `analysis/final_results.md`), then proceed to
  the next stage yourself, without waiting for a wake-up.
- Treat teammate replies as best-effort: if a `[*-COMPLETE]` has not arrived but the artefact is
  on disk, read the result from the filesystem (as in the stall recovery of monitor_progress) and
  continue.

This keeps the identical push logic and changes only how you await each reply, so headless runs do
not stall. In an interactive session, the normal message-wake path applies unchanged.

**Step 5: Kick off.** The team does not start on its own: the freshly spawned teammates are idle
and do nothing until messaged, so push the first directive immediately after spawning.

**First, stamp timing** (the timing step; read its reference before this first stamp): take the
`run_start` stamp (this one also runs `mkdir -p <compound_path>/analysis`), then a `phase_start`
stamp for `peak-picking`, both before the push below.

**Write the run manifest** (trusted local absolute path). The web view's spectra router reads it to
locate the raw Bruker dataset. Write it before the web-view launch below, so that the dashboard's
first poll can read it. Both come after the `run_start` stamp, because that stamp creates `analysis/`:
```bash
cat > "<compound_path>/analysis/.run_manifest.json" <<JSON
{"bruker_data_dir": "<compound_path (absolute)>", "formula": "<formula>"}
JSON
```

**Launch the web-view dashboard** (non-blocking, returns in about 0.5 s):
```bash
WEBVIEW_OUTPUT=$(ailsa webview serve "<compound_path>/analysis" 2>&1)
WEBVIEW_EXIT=$?
if [ $WEBVIEW_EXIT -eq 0 ]; then
  echo "$WEBVIEW_OUTPUT"
else
  echo "Note: Webview dashboard unavailable — $WEBVIEW_OUTPUT"
  echo "Install ailsa[webview] to enable the live dashboard."
fi
```

This call is foreground and non-blocking: `ailsa webview serve` launches a detached uvicorn
subprocess via `start_new_session=True`, waits about 0.5 s for a startup probe, then returns. The
server outlives this session, and the call is compatible with the headless caveat because it
returns at once. Do not append `&`, do not background and wait, do not pass `--port` or `--open`,
and do not abort the CASE run if the call fails: the dashboard is observability only.

When the server starts, its output already contains:
- `Webview server running at http://127.0.0.1:NNNNN`
- `Stop with: ailsa webview stop <compound_path>/analysis`

Store the URL from the output in a variable (e.g. `WEBVIEW_URL`) so it can be recorded in the
`**Dashboard:**` field of the CASE-PROGRESS.md header (see write_progress).

**Now create the CASE-PROGRESS.md header, before the `[BEGIN] peak-picking` push and not at
`[SETUP-COMPLETE]`.** Using the file-header trigger of write_progress (trigger 1 in
progress-format.md), write `<compound_path>/analysis/CASE-PROGRESS.md` with `**Compound:**` (the
data path), `**Formula:**` (the molecular formula; both are known at run start),
`**Started (UTC):**` (the `run_start` stamp), `**Team:**`, and `**Dashboard:**` (`WEBVIEW_URL`, or
the note "unavailable — [webview] extra not installed" if the launch warned). This fills the
dashboard's Run Log panel with the run context from the start instead of leaving it at "Waiting
for log data…" until peak picking finishes, so do not defer the header to `[SETUP-COMPLETE]`.
Then continue to the `phase_start` stamp and the `[BEGIN] peak-picking` push regardless of the
web-view outcome.
```
SendMessage(
  type="message",
  recipient="nmr-chemist",
  content="[BEGIN] peak-picking — start now. Pick 13C/HSQC/HMBC for {compound_path} (formula {formula}), run statistical detection, write the analysis/ structure, then send [SETUP-COMPLETE] with all peak assignments, detection results, and quality assessment. Prepend your first message with the [MODEL] line.",
  summary="Kick off nmr-chemist peak-picking"
)
```

Do not proceed to a passive wait. After this push, enter monitor_progress: each teammate reply
arrives as a turn that wakes you; on each reply, immediately push the next `[BEGIN]` directive.
Do not rely on the teammate to poll the TaskList.
</step>

<step name="write_progress">
Read the full CASE-PROGRESS.md format before writing any progress entry:

Read file: ~/.claude/ailsa/references/progress-format.md

The coordinator is the sole author of CASE-PROGRESS.md. It creates the header at run start, in
spawn_case_team step 5 right after the web-view launch (file-header trigger 1, with the
`**Dashboard:**` field), not at [SETUP-COMPLETE]. Then it appends the `## Setup` section after
[SETUP-COMPLETE] from the NMR chemist, and updates the file after every [ITERATION-COMPLETE],
[VALIDATION-PASSED/BLOCKED] and [RANKING-COMPLETE] message.

**The `## Multiplicity Coverage` ledger** (only when a `[MULTIPLICITY-AMBIGUOUS]` record exists).
When the NMR chemist has sent a `[MULTIPLICITY-AMBIGUOUS]` signal (see
`~/.claude/ailsa/references/multiplicity-ambiguity.md`), keep a `## Multiplicity Coverage` section
in CASE-PROGRESS.md as the single source of truth that the pre-accept coverage gate reads. Record
four things:

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

If no `[MULTIPLICITY-AMBIGUOUS]` record exists, omit this section; the single-family flow is
unaffected.
</step>

<step name="timing">
Real UTC stamps at every phase boundary and agent hand-back, turned into `analysis/timing.json`
and a `## Timing Summary` before shutdown. Read it before the first stamp (`run_start`, kick-off):
Read file: ~/.claude/ailsa/references/timing.md
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
  plausibility, Quality, Recommendation

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
Only with a `[MULTIPLICITY-AMBIGUOUS]` record, after the ranking and before identity_gate: accept
only if every viable family and every model the devil's advocate mandated was searched, else reopen.
Read file: ~/.claude/ailsa/references/coordinator-gates.md (section "Coverage gate")
A FAIL reopens the run with the multiplicity-coverage reopen advisory (the Multiplicity Coverage
Gap pattern in `loop-patterns.md`):
Read file: ~/.claude/ailsa/references/advisory-templates.md
</step>

<step name="identity_gate">
Once, after the ranking and a passed coverage_gate (where it applies), before the results: push the
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
Shut down all teammates gracefully and clean up the team resources. This step runs after
present_results (successful or failed CASE), escalate (user escalation) or smoke_test_report
(smoke-test mode).

**The web-view server stays running.** The server started at run start is intentionally left
running here, so that the user can review the dashboard after the CASE run ends. The manual stop
hint was printed at run start (spawn_case_team step 5). Do not add a stop call to this step.

**Step 0: Finalize timing (before shutdown).** Take the `run_end` stamp, then run the timing
finalize (timing step): it writes `analysis/timing.json` and prints the `## Timing Summary` block,
which you append to `analysis/CASE-PROGRESS.md` (and to `analysis/final_results.md` if it exists).
Do this on every exit path (success, escalation or smoke test), so that a wall-clock duration is
always on record.

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
