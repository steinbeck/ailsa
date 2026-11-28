---
created: 2026-11-28
title: "Team runs: tool events carry no agent id, and the team formed without the team-creation tools"
area: record
files:
  - src/ailsa/record/toolrec.py
  - src/ailsa/record/fold.py
  - src/ailsa/record/hooksettings.py
  - src/ailsa/skills/ailsa/commands/case.md
---

## Context: found in the Phase 106.2 team proof run (106.2-11-SUMMARY.md)

One interactive team run of the frontier skill on the public example dataset (Sheldon, Claude Code
2.1.332, Sonnet-class model, started by `ailsa run start --skill ailsa --interactive` in tmux with
`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` and `--teammate-mode in-process`), run id
`2026-11-27T2225Z_terpineol-team_6dwm`. The record is valid: `ailsa run verify` clean, manifest
and artefacts matching, no unregistered file, dataset unchanged (69-file hash list identical), 335
events. The owner judged it valid at the checkpoint on 2026-11-28 ("approved-with-gap"): the
duplicate agent entries were fixed in Phase 106.2 (`f36a2ae`), the two gaps below go to Phase 107.

What the record shows for the team: four named in-process teammates; 46 agent messages
(coordinator to specialists 18, specialists to coordinator 17, specialist to specialist 9);
28 spawn events for 4 teammate ids; 16 model reports (harness, transcript, self-report and
launcher); 51 shell events (LSD engineer 14, NMR chemist 13, devil's advocate 4, solution analyst
2, coordinator 18 without agent id); 26 `tool.invoked`; 24 notes; four solver rounds with
matching start and finish.

## Gap A: the tools' own events carry no agent id

`tool.invoked`, `solver.started/finished`, `ranking.computed`, `identity.derived` and
`peaks.picked` are written by the `ailsa` tools with `actor.agent_id = null`, in the team run and
in the headless run alike (checked on the headless event log: 0 of 25 `tool.invoked`, 0 of 4
solver starts with an agent id; 29 of 49 shell events have one). Which specialist ran a solver
round or a ranking can be read only from the neighbouring `tool.shell` hook event, so attribution
depends on the recording hooks and on matching events by position.

Why it matters for unattended team runs: Phase 107's mechanics report ("tool outputs usable or
not", per specialist) and Phase 109's logged direct channels need per-agent tool steps. With the
hooks off, or in a harness without them, a team run's tool steps cannot be attributed at all.

## Gap B: the team formed without the team-creation tools

The coordinator's procedure (`commands/case.md`) spawns the team via `TeamCreate` and
`Task(team_name)`. Claude Code 2.1.332 offered neither, even with the agent-teams variable set. The
coordinator spawned the four specialists directly as named teammates; no team folder was created
and the shutdown handshake went by message. The record is complete either way, but the skill text
and the harness disagree, and in `claude -p` (the headless proof run, 106.2-10-SUMMARY.md) no
teammates form at all: the specialists ran one after another.

Why it matters: the unattended route (Phase 107 success criterion 4) has to work without an
interactive session, where named subagents in `claude -p` run as ordinary subagents.

## Not yet measured

A run typed as `/ailsa:case` in an open session, without the launcher. There the tools find the run
through the session pointer or the run marker above the working folder, not through
`AILSA_RUN_DIR`. Whether in-process teammates share the lead's session id is not documented; a tool
that finds no run stays silent unless a run was expected, so a teammate's missed step would leave
no trace.

## Candidate fixes (none chosen here)

Named in the research (106.2-RESEARCH.md, Pitfall 2 and the hook coverage notes):

- Run lookup for teammates: pass the run explicitly to the specialists (an explicit `--run` or the
  absolute work folder in every prompt, with a first tool call whose "not recorded" output they
  must report), so the lookup does not depend on the session id.
- Subscribe the team-specific hook events (`TeammateIdle`, `TaskCreated`, `TaskCompleted`), which
  the hook settings do not subscribe today, so team activity is recorded beyond spawns and
  messages.

Not in the research, noted for completeness: for gap A, the fold could attach the agent id of the
matching shell hook event to the tool event it caused (the per-agent join of Phase 106.2, extended
to tool events). It would still depend on the hooks.

Owned by Phase 107 (evaluation bench and team-mode spike), which decides the route for unattended
team runs; Phase 109 then writes that route into the coordinator's procedure.
