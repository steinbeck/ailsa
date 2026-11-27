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
Orchestrate the full Computer-Assisted Structure Elucidation (CASE) workflow by spawning a 4-agent specialist team (nmr-chemist, lsd-engineer, solution-analyst, devils-advocate), monitoring progress through CASE-PROGRESS.md (which this orchestrator writes as sole author) and TaskList, detecting unproductive loop patterns, diagnosing root causes, intervening with advisory constraints via SendMessage, and escalating to the user after 10 failed intervention cycles per pattern.

This orchestrator does NOT perform CASE work itself—it delegates to a specialist team and handles supervision as team lead.

**ABSOLUTE PROHIBITION:** This orchestrator NEVER attempts dereplication. Dereplication is a completely separate workflow. CASE starts from scratch with NMR spectra only.
</objective>

<process>

<step name="parse_arguments">
Extract compound path and molecular formula from user input.

**Arguments:** `<compound_path> <formula>` — both optional if inferable.

**Resolution logic:**

1. **If both provided:** Use them directly.

2. **If compound_path missing:** Check if cwd looks like a Bruker compound directory:
   ```bash
   ls -d [0-9]*/acqus 2>/dev/null | head -1
   ```
   If numbered subdirectories with `acqus` files exist, use `.` (current directory) as compound_path.

3. **If formula missing:** FIRST look for it on disk in `{compound_path}`, and only ask the
   user if nothing usable is found. Many compound directories ship the formula in a small
   sidecar text file — read it instead of prompting. Search generically (do NOT hard-code one
   filename); check, in order, common formula sidecars:
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
   file it came from (e.g. "Using formula C13H18O2 from molecular-formula.txt"). Only if no
   sidecar yields a valid formula, ask the user — just the formula, nothing else:
   ```
   What is the molecular formula? (e.g., C9H10O2)
   ```

4. **If neither provided and cwd is not a compound directory:** Show brief usage:
   ```
   cd into your compound directory, then: /ailsa:case <formula>
   ```

**Smoke test mode:** If the user's invocation includes `--smoke-test` or `smoke test`:
- Set SMOKE_TEST = true
- Default compound_path to `data/example_compound` if not provided
- Default formula to `C9H10O2` if not provided
- Print header:
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
Check environment readiness. Run via Bash — STOP on any failure, do NOT spawn team:

0. `echo $CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` — must be "1". Fix: `export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
1. `ailsa --version` — must succeed. Fix: `pip install ailsa`
2. `ailsa lsd check` — LSD and outlsd must be available. Fix: download from http://eos.univ-reims.fr/LSD/ and add bin/ to PATH
3. `ailsa predict c13 "CCO" --format json 2>/dev/null | head -1` — must succeed. Fix: `ailsa database download`
4. `ls <compound_path>` — directory must exist.
</step>

<step name="spawn_case_team">
Spawn the 4-agent CASE specialist team via TeamCreate and Task(team_name).

**CRITICAL:** The orchestrator skill IS the team lead (coordinator). Do NOT spawn a coordinator agent -- the skill itself manages the team, creates tasks, delivers advisories, and handles lifecycle.

**COORDINATION PROTOCOL — PUSH, NEVER PULL (critical — prevents the stall):**
Background teammates go idle between turns and do **NOT** poll the TaskList on their own. A `TaskCreate` by itself will **never** wake an idle agent — the run simply stalls until a message arrives. Therefore the coordinator drives everything by message:
- After creating/assigning ANY task, the coordinator MUST immediately `SendMessage` the specific assignee an explicit `[BEGIN] <task>` directive. Do this right after each `TaskCreate`, and again immediately after the prerequisite agent reports.
- `TaskCreate` / `TaskList` / `TaskUpdate` are a STATUS LEDGER for visibility only — never a work queue that agents poll.
- Agents act ONLY on a received `SendMessage`. They must never "wait for", "monitor", or "claim from" the TaskList.
- A teammate's reply arrives as a conversation turn and wakes the coordinator, which then immediately pushes the next `[BEGIN]` directive. This message ping-pong is the ONLY thing that keeps the workflow moving — there is no autonomous polling. If you ever find yourself "waiting" after a `TaskCreate` without having sent a `[BEGIN]`, that is the bug: push the directive.

**⚠ EXECUTION-MODE CAVEAT — headless / non-interactive (`claude -p`, batch/UAT harness):**
The message ping-pong above assumes a teammate's reply arrives as a conversation turn that
WAKES you. **That wake-up only happens in an interactive session.** When you run
non-interactively/headless there is NO event loop to re-enter a finished turn — if you send a
`[BEGIN]` and then END YOUR TURN saying "I'll wait for [ITERATION-COMPLETE]", the process
simply exits mid-workflow. **This is the `NO_RESULT` failure mode.** Detect this mode from your
environment/system context (no interactive user; invoked via `claude -p` / a harness). In it:
- **Never end a turn expecting to be woken. "Background-and-wait" is forbidden.**
- Drive every stage **INLINE within one continuous turn**: after each `[BEGIN]`, actively POLL
  for completion in a loop — read `TaskList()` status AND check the expected filesystem
  artefacts (`analysis/iteration_NN/solncounter` or `*.sol`, `analysis/final_results.md`) — then
  proceed to the next stage yourself, without waiting for a wake-up.
- Treat teammate replies as best-effort: if a `[*-COMPLETE]` has not arrived but the artefact is
  on disk, read the result from the filesystem (as in the Stall recovery step) and continue.
This keeps the identical push logic; it only changes how you await each reply so headless runs
do not stall. In an interactive session, the normal message-wake path applies unchanged.

**Step 1: Initialize team namespace** ({compound_name} = last path component, e.g., "MyCompound")

```
TeamCreate(team_name="case-{compound_name}", description="CASE workflow for {compound_path} -- formula {formula}")
```

**Step 2: Create initial shared tasks**

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

**Step 3: Spawn 4 specialist teammates**

```
Task(
  name="nmr-chemist",
  team_name="case-{compound_name}",
  subagent_type="ailsa-nmr-chemist",
  model="claude-opus-4-8",
  prompt="You are the NMR chemist for CASE of {formula} at {compound_path}.
          Begin ONLY when the coordinator sends you a [BEGIN] peak-picking directive — do NOT poll or wait on the TaskList (idle agents are not woken by tasks, only by messages).
          Execute peak picking and statistical detection using the ailsa CLI.
          Send [SETUP-COMPLETE] message to coordinator via SendMessage with all peak assignments, detection results, and quality assessment.
          Mark the task completed (TaskUpdate, for the status ledger) and then wait for the coordinator's next [BEGIN] directive — never poll the TaskList for more work."
)

Task(
  name="lsd-engineer",
  team_name="case-{compound_name}",
  subagent_type="ailsa-lsd-engineer",
  model="claude-opus-4-8",
  prompt="You are the LSD engineer for CASE of {formula} at {compound_path}.
          Act ONLY on the coordinator's [BEGIN] lsd-iteration directives sent to you via SendMessage — do NOT poll or wait on the TaskList (idle agents are woken by messages, not by tasks).
          On each [BEGIN] lsd-iteration-NN directive: build the LSD file in analysis/iteration_NN/, run the LSD solver.
          Send [ITERATION-COMPLETE] message to coordinator via SendMessage after EVERY iteration.
          CRITICAL: Read previous LSD file, never reconstruct from memory.
          Follow incremental HMBC strategy: 3-5 correlations per iteration.
          After reporting, wait for the coordinator's next [BEGIN] directive — never poll the TaskList. You will receive a shutdown_request when CASE is complete."
)

Task(
  name="solution-analyst",
  team_name="case-{compound_name}",
  subagent_type="ailsa-solution-analyst",
  model="claude-opus-4-8",
  prompt="You are the solution analyst for CASE of {formula} at {compound_path}.
          Act ONLY when the coordinator sends you a [BEGIN] ranking directive via SendMessage — do NOT poll or monitor the TaskList (idle agents are woken by messages, not by tasks).
          The [BEGIN] ranking directive embeds the full experimental 13C shift list and the solutions.smi path.
          Assess chemical plausibility of top candidates.
          Write analysis/final_results.md with ranked structures.
          Send [RANKING-COMPLETE] message to coordinator via SendMessage with ranking summary."
)

Task(
  name="devils-advocate",
  team_name="case-{compound_name}",
  subagent_type="ailsa-devils-advocate",
  model="claude-opus-4-8",
  prompt="You are the devils advocate for CASE of {formula} at {compound_path}.
          Act ONLY on requests received via SendMessage (from lsd-engineer or the coordinator) — do NOT poll the TaskList.
          On a PRE-SOLVER validation request:
          1. Diff current LSD file against previous iteration
          2. Check for dropped constraints (ring exclusion DEFF F/FEXP, COSY equivalence pairs, grouped notation)
          3. Verify sp2 count is even, H budget matches formula
          4. Send [VALIDATION-PASSED] or [VALIDATION-BLOCKED] to coordinator via SendMessage.
          On a POST-SOLUTION [BEGIN] G-IDENT request (after analysis/final_results.md exists): run ONLY the G-IDENT gate — read the reported trivial name + top SMILES, reason INDEPENDENTLY about whether the name matches the structure (do NOT call ailsa identify), apply the CASE4/CASE5 triggers, and reply [G-IDENT-PASSED] or [G-IDENT-FLAGGED] with a one-line rationale.
          Report constraint persistence status after every validation."
)
```

**Step 4: Mandatory model disclosure (observability — catches silent model fallback).**

Every teammate MUST disclose its actual runtime model. Append this line VERBATIM to each of the four `prompt=` strings above (it is intentionally identical for all four):

```
FIRST LINE of your very first SendMessage to the coordinator MUST be exactly: [MODEL] <your exact runtime model id from your environment/system context, e.g. claude-opus-4-8> — copy the real id verbatim, do not guess or use an alias.
```

**Orchestrator capture + cross-check:** As each teammate's first message arrives, read its `[MODEL]` line and record it. After all four have reported (or at the [SETUP-COMPLETE] boundary), write the `## Team Models` block into CASE-PROGRESS.md per progress-format.md, listing each agent's reported runtime model alongside the INTENDED model (`claude-opus-4-8` — the spawn `model=` value). If ANY reported model differs from `claude-opus-4-8`, emit a prominent WARNING line in that block:

```
⚠ MODEL MISMATCH: <agent> requested claude-opus-4-8 but is running <reported> — the model pin did not take effect (silent fallback). Results may not reflect the intended reasoning model.
```

Also record the coordinator's OWN runtime model (read it from your environment/system context) on the `coordinator (orchestrator)` line — the orchestrator has no pin and inherits the session model, so this documents what drives diagnosis/interventions.

This makes the exact model + version of every agent auditable at the top of every run, and surfaces a fallback immediately instead of buried in a footer.

**Step 5: Kick off (mandatory — the team will NOT start on its own).**

Immediately after spawning, the coordinator MUST push the first directive. The freshly-spawned teammates are idle and will do nothing until messaged.

**First, stamp timing** (see the timing step): take the `run_start` stamp (this one also does `mkdir -p <compound_path>/analysis`), then a `phase_start` stamp for `peak-picking` — both BEFORE the push below.

<!-- Phase 95 (SP1-01/SP-02): write the run manifest so the webview's
     spectra.py router can locate the raw Bruker dataset. analysis/
     already exists (created by the run_start stamp above); this write
     must land BEFORE the webview launch below so the dashboard's first
     poll tick can read it. -->

**Write the run manifest (trusted-local absolute path, D-07):**

```bash
cat > "<compound_path>/analysis/.run_manifest.json" <<JSON
{"bruker_data_dir": "<compound_path (absolute)>", "formula": "<formula>"}
JSON
```

<!-- WV-07: Launch webview dashboard before the first [BEGIN] push.
     analysis/ was just created by the run_start timing stamp above.
     ailsa webview serve is non-blocking (~0.5 s startup probe) — it does NOT
     violate the headless/non-interactive rule. The spawned uvicorn process
     uses start_new_session=True and outlives this orchestrator session.
     Do NOT use & (background operator), --port, or --open. -->

**Launch the webview dashboard (non-blocking — exits in ~0.5 s):**

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

This call is foreground and non-blocking: `ailsa webview serve` launches a detached uvicorn subprocess via `start_new_session=True`, waits ~0.5 s for a startup probe, then returns. Do NOT append `&`, do NOT background-and-wait, do NOT pass `--port` or `--open`, and do NOT abort the CASE run if the call fails — the dashboard is observability only.

When the server starts successfully the output already contains:
- `Webview server running at http://127.0.0.1:NNNNN`
- `Stop with: ailsa webview stop <compound_path>/analysis`

Store the URL from the output in a variable (e.g. `WEBVIEW_URL`) so it can be recorded in the CASE-PROGRESS.md header `**Dashboard:**` field (see write_progress). The `analysis/` directory exists because the `run_start` stamp above created it — this is why the launch block sits after that stamp.

**Now create the CASE-PROGRESS.md header — BEFORE the `[BEGIN] peak-picking` push, not at `[SETUP-COMPLETE]`.** Using the `write_progress` File-header trigger (progress-format.md trigger 1), write `<compound_path>/analysis/CASE-PROGRESS.md` with `**Compound:**` (the data path), `**Formula:**` (the molecular formula — both are already known at run start), `**Started (UTC):**` (the `run_start` stamp), `**Team:**`, and `**Dashboard:**` (`WEBVIEW_URL`, or the "unavailable — [webview] extra not installed" note if the launch warned). This populates the dashboard **Run Log** panel with the run context from t=0 instead of leaving it "Waiting for log data…" until peak-picking finishes. Do NOT defer the header to `[SETUP-COMPLETE]`.

Continue to the `phase_start` stamp and the `[BEGIN] peak-picking` push regardless of webview outcome.

```
SendMessage(
  type="message",
  recipient="nmr-chemist",
  content="[BEGIN] peak-picking — start now. Pick 13C/HSQC/HMBC for {compound_path} (formula {formula}), run statistical detection, write the analysis/ structure, then send [SETUP-COMPLETE] with all peak assignments, detection results, and quality assessment. Prepend your first message with the [MODEL] line.",
  summary="Kick off nmr-chemist peak-picking"
)
```

Do NOT proceed to a passive wait. After this push, enter monitor_progress: each teammate reply arrives as a turn that wakes you; on each reply, immediately push the next `[BEGIN]` directive (never rely on the teammate to poll the TaskList).
</step>

<step name="write_progress">
Read the full CASE-PROGRESS.md format template before writing any progress entries:

Read file: ~/.claude/ailsa/references/progress-format.md

The orchestrator is the SOLE AUTHOR of CASE-PROGRESS.md. Create the file with its **header at run-start** — in spawn_case_team Step 5, right after the webview launch, using the File-header trigger (trigger 1 below). Do NOT wait for [SETUP-COMPLETE]: the header must exist from t=0 so the dashboard **Run Log** panel shows the run context (compound path, formula, dashboard URL) immediately rather than "Waiting for log data…". Then **append** the `## Setup` section after receiving [SETUP-COMPLETE] from nmr-chemist, and update after every [ITERATION-COMPLETE], [VALIDATION-PASSED/BLOCKED], and [RANKING-COMPLETE] message. When writing the file header, record the dashboard URL captured from the `ailsa webview serve` output (stored in `WEBVIEW_URL` from spawn_case_team Step 5) into the `**Dashboard:**` field — or write "unavailable — [webview] extra not installed" if the launch warned.

<!--
RELOAD NOTE: case.md is a repo `.claude/` skill prompt symlinked into `~/.claude`. Behavior
changes here are MARKDOWN PROMPT EDITS — a FRESH Claude Code session is REQUIRED to reload the
edited orchestrator. They are NOT unit-testable this session; functional validation is the blind
CASE4 re-run (UAT-01 / Phase 89).
-->

**`## Multiplicity Coverage` ledger (only when a `[MULTIPLICITY-AMBIGUOUS]` record exists).**
When the nmr-chemist has emitted a `[MULTIPLICITY-AMBIGUOUS]` signal (see
`~/.claude/ailsa/references/multiplicity-ambiguity.md`), maintain a `## Multiplicity Coverage` section in CASE-PROGRESS.md as the single
source of truth the pre-accept coverage gate reads. Record four things:

- **viable_families** — the numbered list from the nmr-chemist's `[MULTIPLICITY-AMBIGUOUS]`
  signal (e.g. `iPr (3×CH₃+CH)`, `ethyl (2×CH₃+CH₂+CH₂)`).
- **searched_families** — one entry per family that produced **its own `iteration_NN_<family>/`
  run + a matching `[ITERATION-COMPLETE]`**. Count a family as SEARCHED **even if its
  `solutions.smi` conversion was skipped** because the count was large (the SEARCHED-not-RANKED
  rule from Plan 88-02). Do NOT require a ranked `solutions.smi` and do NOT key this off MAE or
  plausibility — searched means the constrained LSD run ran and signalled, nothing more.
- **DA-mandated models** — every model X from a Devils-Advocate `[MULT-EVIDENCE-FOR] model=X`
  message (G-MULT). These are binding mandatory-search items closeable ONLY by an actual
  `iteration_NN_X/` search.
- **gate verdict** — PASS / FAIL written by the coverage_gate step (see below).

If no `[MULTIPLICITY-AMBIGUOUS]` record exists, omit this section entirely — the single-family
flow is unaffected.
</step>

<step name="timing">
Take real UTC timestamps at every phase boundary and agent hand-back, and turn them into
`analysis/timing.json` and a `## Timing Summary` before the team shuts down. Read the protocol
before the first stamp, the `run_start` stamp at the kick-off:

Read file: ~/.claude/ailsa/references/timing.md
</step>

<step name="validate_message">
Validate incoming structured messages before processing. Each message type has required fields. If any are missing, request resend via SendMessage.

**Required fields by message type:**

[SETUP-COMPLETE]:
- DBE, Spectra found, Peak counts, Symmetry, Multiplicities, Quality assessment
- Statistical detection, Grouping, HHB, Aromatic expectation
- Conflicts with NMR evidence, Key observations

[ITERATION-COMPLETE]:
- LSD file, Solution count, Constraints added, Constraints removed
- Constraint inventory delta, sp2 count, H budget
- HMBC correlations used, Why, Constraint effectiveness, Confidence
- Fragment search, Fragment file

[RANKING-COMPLETE]:
- Solutions, Top solution, Strained rings, Aromatic warning
- Chemical plausibility, Quality, Recommendation

**Validation procedure:**

On receiving any structured message (identified by `[TAG]` prefix):
1. Identify message type from tag
2. Check message text for each required field label (case-insensitive substring match of the field name followed by `:`)
3. If any required field label is missing:
   - DO NOT process the message
   - Send back to originating agent:
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
   - Log: "Message validation failed for [{TAG}] from {agent}: missing {fields}"
4. If all required fields present: proceed to process in monitor_progress

**Important:** "None detected", "N/A", "None", and "0" are all VALID values. Only truly missing field labels trigger resend.
</step>

<step name="monitor_progress">
Runs from the kick-off until the results are ready: react to every teammate reply, push the next
`[BEGIN]` directive, decide whether to iterate, rank or stop, and recover a stalled iteration.
Read both files before processing the first reply:

Read file: ~/.claude/ailsa/references/monitoring.md
Read file: ~/.claude/ailsa/references/loop-patterns.md
</step>

<step name="detect_loops">
After every iteration, and whenever the devil's advocate flags an issue: compare the iteration
history with the five loop patterns and decide whether the run continues, stops (converged or
safety cap) or goes to diagnose. Section "Detect loops" of `monitoring.md`, with the pattern
definitions in:

Read file: ~/.claude/ailsa/references/loop-patterns.md
</step>

<step name="diagnose">
When detect_loops finds a pattern: check that pattern's typical root causes in the latest LSD file
and the iteration history, and document the findings for the intervention. Section "Diagnose" of:

Read file: ~/.claude/ailsa/references/monitoring.md
</step>

<step name="intervene">
After diagnose: write an advisory that tells the agent what to fix, not how. The templates per
pattern are in the section "Intervene" of:

Read file: ~/.claude/ailsa/references/intervention.md
</step>

<step name="track_and_decide">
After each intervention: count it for its pattern and decide between a basic advisory, delegation
to the diagnostic specialist, a specialist-informed advisory, honest termination and escalation.
Section "Track and decide" of:

Read file: ~/.claude/ailsa/references/intervention.md
</step>

<step name="escalate">
After 10 failed intervention cycles for the same pattern: present the structured escalation report
to the user and stop. Section "Escalate" of:

Read file: ~/.claude/ailsa/references/intervention.md
</step>

<step name="coverage_gate">
Only when a `[MULTIPLICITY-AMBIGUOUS]` record exists, after the ranking and before identity_gate:
the run accepts only if every viable multiplicity family and every model the devil's advocate
mandated has been searched; otherwise it reopens. Section "Coverage gate" of:

Read file: ~/.claude/ailsa/references/coordinator-gates.md

A FAIL reopens the run with the multiplicity-coverage reopen advisory in `advisory-templates.md`;
the reopen pattern is the Multiplicity Coverage Gap in `loop-patterns.md`.

Read file: ~/.claude/ailsa/references/advisory-templates.md
</step>

<step name="identity_gate">
Once, after the ranking (and after coverage_gate has passed, where it applies), before the
results: push the devil's advocate's independent G-IDENT cross-check of name and structure and
record its verdict. A flag downgrades the name and never blocks the report. Section
"Identity gate" of:

Read file: ~/.claude/ailsa/references/coordinator-gates.md
</step>

<step name="deliver_advisory_and_results">
Read advisory delivery, result presentation, diagnostic delegation, and anti-pattern templates:

Read file: ~/.claude/ailsa/references/advisory-templates.md

This reference covers: advisory message formatting, result presentation (success/incomplete/failed), diagnostic specialist delegation, diagnostic findings extraction, and anti-patterns to avoid.
</step>

<step name="smoke_test_report">
Only in smoke-test mode, after the smoke test early exit: print the pass/fail table of the four
checkpoints, then go to terminate_team.

Read file: ~/.claude/ailsa/references/smoke-test.md
</step>

<step name="terminate_team">
Gracefully shut down all teammates and clean up team resources.

**This step executes after:** present_results (successful or failed CASE), OR escalate (user escalation), OR smoke_test_report (smoke test mode).

**Note (WV-07):** The webview server started at run_start is intentionally left running here. It remains accessible so the user can review the dashboard after the CASE run ends. The manual stop hint was printed at run-start (spawn_case_team Step 5). Do NOT add a stop call to this step.

**Step 0: Finalize timing (before shutdown).** Take the `run_end` stamp, then run the timing finalize (see the timing step): it writes `analysis/timing.json` and prints the `## Timing Summary` block, which you append to `analysis/CASE-PROGRESS.md` (and to `analysis/final_results.md` if it exists). Do this on every exit path — success, escalation, or smoke test — so a wall-clock duration is always on record.

**Step 1: Send shutdown requests to all 4 teammates:**
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

**Step 2: Wait for shutdown confirmations.**
Teammates approve shutdown automatically (they have no reason to reject after CASE completes).

**Step 3: Clean up team resources:**
```
TeamDelete()
```

This removes:
- ~/.claude/teams/case-{compound_name}/
- ~/.claude/tasks/case-{compound_name}/

**If TeamDelete fails (teammates still active):** Wait 30 seconds and retry. If still failing, report: "Team cleanup incomplete. Manual cleanup may be needed: rm -rf ~/.claude/teams/case-{compound_name} ~/.claude/tasks/case-{compound_name}"
</step>

</process>
