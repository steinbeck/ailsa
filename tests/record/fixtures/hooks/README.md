# Hook payload fixtures

Real Claude Code hook payloads, captured 2026-11-24 with Claude Code 2.1.331 (model `claude-haiku-5-5`,
launched as `--model haiku`).

## How they were captured

Three headless `claude -p` sessions (small model, `--dangerously-skip-permissions`, `timeout 300`)
on a compute host, each hook calling a stdlib dump script that wrote the stdin JSON to a file:

1. one turn: Bash `echo`, an Agent-tool subagent, a SendMessage to that subagent, reply (hooks registered
   via `--settings` in exec form, plus one shell-form handler on SessionStart);
2. `--resume <id>` with the prompt `/compact` (PreCompact, PostCompact, SessionEnd, resumed SessionStart);
3. a project skill invoked as `/spike-skill` with hooks declared in its YAML frontmatter.

## Scrubbing

Session ids became fixed UUIDs (`11111111-...` parent, `22222222-...` other), agent ids `agent-sub-0001`,
the working directory `/RUN`, transcript paths `/UHOME/.claude/projects/PROJECT/...`, the host and user name
`HOST` / `USER` wherever they occurred, temp paths `/TMP/PATH`. Long strings (`compact_summary`,
`last_assistant_message`, tool response bodies) are cut at 300 characters. All keys are kept, including
unknown ones. Transcripts are minimised to `type`, `requestedModel`, `message.model`, `message.role`,
`isSidechain`, `agentId` and the first 200 characters of text.

## Files

One representative payload per event: `session_start` (source `startup`), `user_prompt_submit`,
`post_tool_use_bash`, `post_tool_use_agent`, `send_message` (PostToolUse of SendMessage), `subagent_start`,
`subagent_stop`, `stop`, `pre_compact`, `post_compact`, `session_end`. The transcript fixtures are in
`../transcripts/`.

## Events that did NOT fire in `-p`

- `Notification` (so there is no `notification.json`)
- `PermissionRequest` (bypass mode), `StopFailure`, `PostModelSwitch` (nothing triggered them)

`SessionStart.model` is absent for `source: startup` and present for `source: compact`.
