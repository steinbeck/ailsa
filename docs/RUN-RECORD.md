# The AILSA run record

Every CASE run leaves a record: what the agent was given, what each tool did, which rankings
existed and which result the agent declared. The record lives in the `ailsa` package, so every
skill and every harness can use it. Both maintained skills write it, the lean skill `ailsa-lite`
and the frontier skill `ailsa` ([SKILLS.md](SKILLS.md)).

## Contents

- [Idea](#idea)
- [Run folder](#run-folder)
- [Workspace and configuration](#workspace-and-configuration)
- [Environment variables](#environment-variables)
- [Starting a run](#starting-a-run)
- [Team runs](#team-runs)
- [Commands](#commands)
- [Hooks for open sessions](#hooks-for-open-sessions)
- [Remote solves](#remote-solves)
- [Outcomes](#outcomes)
- [Blind mode](#blind-mode)
- [What the hash chain proves](#what-the-hash-chain-proves)
- [Transcripts](#transcripts)
- [Batch commands not yet required](#batch-commands-not-yet-required)
- [Limits](#limits)

## Idea

Agents decide, tools write. The tools (`ailsa lsd run`, `ailsa lsd rank`, the peak pickers) append
their own events to the record; the agent never edits it. The result of a run is declared by the
agent with `ailsa run finalize`, never inferred from files. Reports such as `final_results.md`
and the progress log are renderings of the record, regenerated on demand with `ailsa run render`.

## Run folder

One folder per run inside the workspace:

| Part | Content |
|---|---|
| record files | the event log (hash chained), the manifest of registered files, the run summary |
| `agent/` | the agents' working corner (the `WORK:` folder): the lean skill's `setup.md` and `iterations.md`, the LSD files in `iteration_NN/`, the frontier diagnostic specialist's report. Not verified by the record unless a tool registers them |
| `iterations/` | solver inputs and outputs written by `ailsa lsd run` |
| `rankings/` | every ranking `ailsa lsd rank` made, with an id |
| `peaks/` | picked peak lists |
| `spectra/` | inventory and view products of the spectra, for display |
| `transcript/` | copies of the harness transcripts (see below) |
| `renderings/` | generated reports |

The spectra are never modified and never copied into the record except as view products.

## Workspace and configuration

The workspace is resolved in this order:

1. `AILSA_WORKSPACE`
2. `workspace` in `~/.config/ailsa/config.json` (`AILSA_CONFIG` overrides the path of that file)
3. `~/ailsa-runs`

Do not put the workspace in a synchronised folder such as Dropbox: the record is append-only and
file locks do not survive synchronisation. The user config can also hold per-host settings for
remote solves (below).

## Environment variables

| Variable | Meaning |
|---|---|
| `AILSA_WORKSPACE` | workspace folder |
| `AILSA_CONFIG` | path of the user config file |
| `AILSA_RUN_DIR` | the run a command belongs to; set by the launcher and by `run init` in hooks |
| `AILSA_REQUIRE_RUN` | tools refuse to run outside a run when set to `1` |
| `AILSA_HARNESS` | name of the harness that drives the agent |
| `AILSA_AGENT_ROLE` | default sender of notes |
| `AILSA_NO_TRANSCRIPT` | do not copy harness transcripts |
| `AILSA_HOOKS_VIA_SETTINGS` | set by the launcher; hooks started from skill frontmatter then do nothing, so no event is recorded twice |
| `LUCY_DATABASE` | path of the reference database |

## Starting a run

Two ways, one record:

- **Launcher.** `ailsa run start DATASET --model M` creates the run, starts the harness with the
  skill, sets the variables and finalises the run when the harness ends. Use it for headless runs
  and benchmarks.
- **From the skill.** In an open session the skill's first step is `ailsa run init DATASET`. It
  prints `RUN:` and `WORK:`; the agent works in the WORK folder. Calling it again while a run is
  active prints the same folder.

Tools find their run through `AILSA_RUN_DIR`, or else through the run bound to the current work
folder. With `AILSA_REQUIRE_RUN=1` a tool that finds none stops.

Launcher options for the skill and for long runs:

| Option | Meaning |
|---|---|
| `--skill ailsa-lite\|ailsa` | which skill to run; default `ailsa-lite`. The lean skill is copied into the run's work folder. The frontier skill `ailsa` starts as `/ailsa:case DATASET [FORMULA]` and needs Claude Code and the global install (`ailsa skill install ailsa --target claude`); without either the launcher refuses before it creates a run folder. It sets `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` for the frontier skill. |
| `--resume-attempts N` | headless Claude Code only; default 1. When the harness ends before the run is settled, the launcher resumes the same session (`claude --resume`) with a short nudge to finish and declare, inside the same record. It stops when the run declares a result or is closed, when it is interrupted, when the deadline passes, or after N attempts in total. |
| `--deadline SECONDS` | total time over all attempts. Each attempt gets the smaller of `--time-limit` and the time left; a run stopped by the deadline is closed with the reason "deadline". |

Whatever happens, the launcher closes the run once at the end (unless the agent already closed
it), copies the transcripts and renders the reports.

## Team runs

The frontier skill runs a coordinator with specialists (NMR chemist, LSD engineer, solution
analyst, devil's advocate, a diagnostic specialist on escalation). Its record follows the same
rule as a lean run, agents decide and tools write, with one declarant:

- **The coordinator creates the record first.** Started by slash command in an open session, its
  first step after the environment checks is
  `ailsa run init DATASET --formula F --skill ailsa --mode team`, before any team, task or spawn. Under the launcher the record already exists and `run init`
  returns the launcher's run. Every specialist gets the absolute `WORK:` folder in its prompt; the
  dataset stays read-only.
- **A note per specialist message.** The coordinator records each validated structured message as
  one `ailsa run note`, with the sending agent as sender, and keeps the fields that its loop
  detection reads. Every hand-over to a specialist starts a phase: a note with `--phase` precedes
  the push, so the record times each phase without separate stamps.
- **Specialists' tool calls record themselves.** Solver rounds, rankings, identity checks and peak
  lists are written by the tools a specialist calls, as in a lean run.
- **The coordinator alone declares.** It runs `ailsa run finalize` once, naming the ranking id the
  solution analyst reported (`--ranking rkNN`), because a team may make more than one ranking: the
  analyst's cross-check ranking comes after the decisive one, so the newest ranking is the wrong
  one. Every other exit closes the run with `ailsa run close`; both are followed by
  `ailsa run render`.
- **Messages, spawns and models come from the hooks.** Agent messages, spawns and the models the
  harness saw are recorded by the recording hooks (always under the launcher; in an open session
  after `ailsa run hooks install`). Without them the rendering says "not recorded by this
  harness"; the tool events are recorded either way.
- **Model evidence per agent.** For each agent the record keeps up to three statements of the
  model it ran on: what the harness saw, what the transcript shows and what the agent said itself
  (each specialist reports its model in its first message; the coordinator records it with
  `ailsa run note "model reported" --sender <agent name> --self-reported-model <model>`). The
  statements are joined by the agent's name, with or without the `ailsa-` prefix: a teammate the
  coordinator spawned as `nmr-chemist` and its self-report as `ailsa-nmr-chemist` are one agent.
  The self-report is marked provisional, because it is what the agent said, not what the harness
  saw.

**What the proof runs showed (November 2026).** Two runs of the frontier skill on the public
example dataset, with a Sonnet-class model under Claude Code 2.1.332 and both started by the
launcher, each left a valid record (`ailsa run verify`: chain clean, manifest and artefacts
matching, no unregistered file), a declared result and a byte-identical dataset.

- *Interactive team run* (`--interactive`, agent-teams variable set, in-process teammates). Four
  named teammates formed: they went idle and busy on their own and wrote to each other directly
  (46 agent messages, 9 of them between specialists). For each teammate the hooks recorded its
  spawns, turns, stops and messages and the model the harness and the transcript showed; its own
  model report joined the same entry. The teammates' shell commands landed in the record under
  their agent ids, and the steps of the `ailsa` tools were recorded too (four solver rounds, two
  rankings, one identity check, eight peak lists), but without an agent id (see
  [Limits](#limits)). The team-creation tools named in the coordinator's procedure were not offered
  by that Claude Code version, so the coordinator spawned the teammates directly by name.
- *Headless run* (`claude -p`). The session offered no team tools; the coordinator noted this and
  ran the specialists one after another, each reply returning as the result of its call. The
  record has the same parts: spawns, messages, model evidence from three sources per agent, every
  solver round and the declaration.

Neither run was started by typing the slash command in an open session, where the skill's own
`ailsa run init` creates the record; in both, that first step found the launcher's run.

## Commands

```bash
ailsa run init DATASET --skill ailsa-lite        # create the run, print RUN: and WORK:
ailsa run note "13C list done, 11 carbons" --phase atoms
ailsa run status                                 # state of the run
ailsa run verify                                 # check the chain and the manifest
ailsa run render                                 # regenerate final_results.md and the progress log
ailsa run index --rebuild                        # rescan the workspace
ailsa run finalize --outcome proposal --ranking latest --candidate 1 --confidence medium
ailsa run finalize --outcome proposal --ranking rk02 --candidate 1 --confidence medium  # a named ranking (team runs)
ailsa run close --reason "abandoned"             # close without a declared result
ailsa run start DATASET --model M                # launcher, lean skill
ailsa run start DATASET --model M --skill ailsa --formula F --resume-attempts 4 --deadline 9000
ailsa run hooks show                             # what `hooks install` would write
```

`finalize` refuses a ranking the agent wrote by hand and a ranking older than the last solver run.
`--withdraw --reason TEXT` withdraws a declaration; a later `finalize` replaces it.

## Hooks for open sessions

In a Claude Code session the transcript, the agent turns and the model in use are recorded by
hooks. `ailsa run hooks install` adds them to `~/.claude/settings.json`; `hooks uninstall` removes
them. The hooks do nothing outside a run. Claude Code applies hooks of a project only after its
folder is trusted, so open the work folder once in a trusted session. Skill frontmatter hooks are
not used: in tests only some events fired there.

A harness without hooks still gets the tool events, because the tools write them. Its transcript
and models are marked "not recorded by this harness".

## Remote solves

`ailsa lsd run FILE --host ALIAS` runs LSD on another machine over SSH and copies the result back.
The alias is an SSH alias. Per-host settings go in the user config:
`hosts.<alias>.lsd`, `hosts.<alias>.outlsd` and `hosts.<alias>.scratch` (paths of the programs and
of a scratch folder on that host).

## Outcomes

Solver outcomes: `not_run`, `blocked`, `solutions`, `no_solution`, `limit_reached`, `timeout`,
`error`.

Declared outcomes: `proposal`, `proposal_under_determined`, `inconclusive`, `no_structure_fits`,
`insufficient_data`, `handed_to_human`. The first two need a candidate; those and `inconclusive`
need a ranking.

## Blind mode

`ailsa run init --blind` (or the launcher with `--blind`) refuses to start when earlier runs or
results for the same data are readable from the workspace. `--allow-prior-runs` overrides the
refusal and marks the run as not blind. This protects against accident only: the workspace is
readable by the agent, and an agent that looks for earlier results can find them. In blind mode
`--label`, `--source` and `--licence` are neither used nor stored in the run folder (which the
agent can read): the folder is named after the dataset folder, source and licence are recorded
only as "withheld (blind)", and these options are removed from the recorded command line.

## What the hash chain proves

Each event contains the hash of the one before. Changing, removing or reordering an event breaks
the chain, and `ailsa run verify` reports "record changed or incomplete from here" at the first
break. The chain is tamper-evident, not tamper-proof: someone who rewrites the whole record and
recomputes every hash cannot be detected from the record alone. The same message appears for an
incomplete record, for example after a crash; the record does not say which of the two it was.

`ailsa run verify` also compares the stored `manifest.json` with a fresh fold of the event log by
the installed package. After a package update that changes the fold, an older record shows
`manifest_matches: false` until `ailsa run render` or `ailsa run status` rewrites the derived
manifest from the untouched event log; the hash chain (`clean`) is what proves integrity.

## Transcripts

Harness transcripts are copied into the run folder and stay there. They leave the machine only on
an explicit request. `AILSA_NO_TRANSCRIPT=1` or `--no-transcript` turns the copy off.

## Batch commands not yet required

`ailsa peaks decide` and `ailsa model import` exist for decisions made in bulk. The skills do not
require them yet: their burden on a small model is measured first.

## Limits

- Windows is not supported; the record relies on POSIX file locks. Use WSL2.
- **Tool steps name the tool, not the agent.** The events the `ailsa` tools write themselves
  (solver rounds, rankings, identity checks, peak lists, tool calls) carry no agent id. In a team
  run, which specialist ran a step can be read only from the hook's shell event recorded next to
  it, so the attribution needs the recording hooks. The steps themselves are recorded either way.
- **Team tools depend on the Claude Code version.** Claude Code 2.1.332 did not offer the
  team-creation tools even with the agent-teams variable set; the coordinator spawned named
  teammates directly, no team folder was created, and the shutdown went by message. The record is
  complete either way. How the team runs unattended is decided in a later phase.
- **Teammates in a run typed as a slash command are not yet measured.** Under the launcher the
  run is named in the environment (`AILSA_RUN_DIR`), and the teammates' tool steps reached the
  record. In an open session the tools rely on the session pointer or on the run marker above
  their working folder; whether every teammate's tool steps reach the record there has not been
  observed. A tool that finds no run stays silent unless a run was expected (for example
  `AILSA_REQUIRE_RUN=1`), so a missed step need not show up as a warning.
