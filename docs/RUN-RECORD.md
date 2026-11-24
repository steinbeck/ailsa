# The AILSA run record

Every CASE run leaves a record: what the agent was given, what each tool did, which rankings
existed and which result the agent declared. The record lives in the `ailsa` package, so every
skill and every harness can use it. The lean skill writes it today ([SKILLS.md](SKILLS.md));
the frontier skill follows when it is wired to it.

## Contents

- [Idea](#idea)
- [Run folder](#run-folder)
- [Workspace and configuration](#workspace-and-configuration)
- [Environment variables](#environment-variables)
- [Starting a run](#starting-a-run)
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
| `agent/` | the agent's working corner: `setup.md`, `iterations.md`, the LSD files. Not verified by the record unless a tool registers them |
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

## Commands

```bash
ailsa run init DATASET --skill ailsa-lite        # create the run, print RUN: and WORK:
ailsa run note "13C list done, 11 carbons" --phase atoms
ailsa run status                                 # state of the run
ailsa run verify                                 # check the chain and the manifest
ailsa run render                                 # regenerate final_results.md and the progress log
ailsa run index --rebuild                        # rescan the workspace
ailsa run finalize --outcome proposal --ranking latest --candidate 1 --confidence medium
ailsa run close --reason "abandoned"             # close without a declared result
ailsa run start DATASET --model M                # launcher
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

## Transcripts

Harness transcripts are copied into the run folder and stay there. They leave the machine only on
an explicit request. `AILSA_NO_TRANSCRIPT=1` or `--no-transcript` turns the copy off.

## Batch commands not yet required

`ailsa peaks decide` and `ailsa model import` exist for decisions made in bulk. The skills do not
require them yet: their burden on a small model is measured first.

## Limits

Windows is not supported; the record relies on POSIX file locks. Use WSL2.
