# AILSA skills: one paper skill, two maintained skills

AILSA is driven by instructions for a language-model agent (a "skill") on top of the `ailsa`
command line. There are three skill states. One is frozen, two are maintained side by side.

| Skill | For | Where | Status |
|---|---|---|---|
| **Paper skill** | the blind benchmark reported in the paper | git tags `paper-skill-v1`, `paper-skill-v2` | frozen, never edited |
| **`ailsa`** (frontier skill) | Anthropic's frontier models in Claude Code: large context, an agent team | `src/ailsa/skills/ailsa/`, installed with `ailsa skill install ailsa --target claude` (maintainers add `--link`) | maintained, the standard skill |
| **`ailsa-lite`** (lean skill) | small open-weight models (about 20–35 B parameters, 64–128 k context) in OpenCode or any harness that reads Agent Skills: the same tools and rules as the frontier skill, condensed for one agent | `src/ailsa/skills/ailsa-lite/`, installed with `ailsa skill install` | maintained, new |

## Contents

- [The paper skill](#the-paper-skill)
- [Why two maintained skills](#why-two-maintained-skills)
- [Rule 1: the same instruments, the agent decides](#rule-1-the-same-instruments-the-agent-decides)
- [Rule 2: the command line is the contract](#rule-2-the-command-line-is-the-contract)
- [Rule 3: a skill ships with the CLI it calls](#rule-3-a-skill-ships-with-the-cli-it-calls)
- [Which skill does a change touch](#which-skill-does-a-change-touch)
- [Checks on every change](#checks-on-every-change)
- [Measuring both skills](#measuring-both-skills)
- [The lean skill](#the-lean-skill)
- [Version 0.1, withdrawn](#version-01-withdrawn)

## The paper skill

The benchmark ran the CASE skill in two states, both headless (`claude -p`), which means without
an agent team: the coordinator called one specialist subagent at a time.

| Tag | Commit | Runs | Difference |
|---|---|---|---|
| `paper-skill-v1` | `f9aa7b3` | 45 (11–14 August 2026) | — |
| `paper-skill-v2` | `6d2d126` | 211 | adds one rule: an exchangeable OH/NH proton used in an HMBC line needs its own `HSQC` declaration (`d62d833`) |

At the start of Phase 106 the frontier skill on `master` (commit `2535715`) differed from
`paper-skill-v2` by two later commits: `9377d45` (atom-by-atom ranking) and `6a80d9e` (corrected
LSD facts). To get the paper skill as it ran:

```bash
git worktree add ../ailsa-paper-skill paper-skill-v2
```

The skill files are `.claude/commands/lucy-ng/` and `.claude/agents/lucy-*.md` in that tree.
Never move these tags. A corrected or improved skill is a new skill, not a new paper skill.

## Why two maintained skills

The frontier skill spends context freely: about 75 000 tokens of instructions, a coordinator
plus four specialists, long reasoning between tool calls. That suits Opus-class models and is
the design the project wants to measure.

A 27 B model at 4-bit quantisation in a 24 GB card cannot load that skill: its context is about
64 000 tokens, of which OpenCode's own prompt takes about 10 000, and a run needs room for peak
lists, LSD files and solver output.

The point of the project is to measure what language-model agents can do in CASE. The lean skill
therefore asks the small model for the same work as the frontier skill asks of Opus: read the
spectra, build the atom list, write the LSD input, judge the candidates. It differs only in how
the instructions are packaged: one agent instead of a team, and reference files that the model
loads when it needs them instead of everything at once.

## Rule 1: the same instruments, the agent decides

Both skills use the same `ailsa` commands, and only as instruments: reading and peak picking,
statistical hints, running LSD, ranking by predicted shifts, identity lookup. No command takes a
decision that the evaluation is about: which atoms and multiplicities the data support, which
correlations go into the solver, how the LSD file is written, which candidate is right. A
command that did so would measure the script instead of the model.

The lean skill's text is derived from the frontier skill: the same chemistry and the same rules,
condensed. Every rule in the lean skill must have its source in the frontier skill. A chemistry
change is made in the frontier skill first and then carried into the lean skill in the same
commit; the change log says so.

## Rule 2: the command line is the contract

- Every `ailsa …` invocation that either skill shows must exist with the flags shown. A test
  extracts them from both skills and checks them against `ailsa … --help`.
- Every JSON field a skill tells the model to read is covered by a test of that command.
- An interface change to a command that a skill names is made in the same commit as the change
  to every skill that names it. The test above makes a forgotten skill fail.
- The lean skill names only commands that the frontier skill also uses. A test compares the two
  sets.

## Rule 3: a skill ships with the CLI it calls

The lean skill is package data of `ailsa`. `ailsa skill install ailsa-lite --target opencode`
(or `--target claude`) copies the skill that belongs to the installed CLI version into the
harness's skill directory, so a user never combines a skill with a CLI it was not written for.
The skill states the package version it was written for, and `ailsa skill list` shows both.

The frontier skill is package data too: `ailsa skill install ailsa --target claude` copies it
(maintainers working from a source checkout add `--link` to get symlinks instead).

## Which skill does a change touch

| Kind of change | Lean skill | Frontier skill |
|---|---|---|
| Bug fix or new capability inside a command | gets it through the command | gets it through the command |
| Change of a command's interface or JSON output | same commit | same commit |
| Chemistry rule (e.g. when a heteroatom bond may be fixed) | carried over from the frontier skill in the same commit | written here first; record "applies to both" in the change log |
| Harness feature (agent teams, hooks, OpenCode configuration) | only this skill | only this skill |
| Search strategy (e.g. HMBC in batches or all at once) | decided per skill, measured per skill | decided per skill, measured per skill |

Each skill keeps a `CHANGELOG.md` next to its files. Every entry says which skill it applies to
and, for a behaviour change, which measurement supports it.

## Checks on every change

Run by `pytest` (the answer scan only locally). A pre-commit hook (`scripts/git-hooks/pre-commit`,
installed once per clone with `ln -s ../../scripts/git-hooks/pre-commit .git/hooks/pre-commit`) runs
the skill checks on every commit that touches `src/ailsa/skills/` or the skill tests:

- **Format:** `name` matches `^[a-z0-9]+(-[a-z0-9]+)*$` and the directory name; `description`
  at most 1 024 characters, third person, says what the skill does and when to use it.
- **Size:** lean skill: `SKILL.md` at most 200 lines; `SKILL.md` plus every reference file at
  most about 20 000 tokens (Qwen tokenizer; 19 000 in version 0.2), so that all of it fits next to OpenCode's prompt and
  a run's working context. Frontier skill: every file under 500 lines, a table of contents in every file
  over 100 lines.
- **Hygiene:** no model IDs, no project history (phase numbers, dates, bug numbers), no dataset
  numbers, no dead file references, one name per role.
- **Commands:** the contract test from Rule 2.
- **Frontier skill:** `tests/test_skill_frontier.py` (size, contents table, history, datasets,
  model IDs, dead references, terms, emphasis, DB credit).
- **Answer scan:** `tests/test_skill_answer_scan.py` (local, skipped without the key).
- **Blindness:** no compound of the evaluation set appears in a skill, by name or by structure.
  This scan runs against the private answer key on the maintainer's machine and before every
  benchmark, never in CI, because the key must not enter the repository.

## Measuring both skills

- Both skills run on the same fixed evaluation sample (about 25 datasets, stratified by size,
  blind only).
- The lean skill is measured three ways: with the partner lab's open-weight model in OpenCode;
  with a small Claude model in Claude Code, which is cheap enough to run after every change; and
  with a frontier model, which separates the effect of the skill from the effect of the model.
- Results are recorded per skill version in [BENCHMARK.md](BENCHMARK.md).
- A change is kept if rank-1 results do not get worse beyond run-to-run noise. On a sample of
  this size that is two or three datasets: a repeat of 15 datasets agreed on 11.

## The lean skill

One agent, three steps, the frontier skill's tools:

| Step | What the model does | Reference file it loads |
|---|---|---|
| 1 | picks peaks, runs the statistical detection, writes the atom list (`setup.md`) | `nmr-analysis.md` |
| 2 | writes the LSD file, checks it, runs LSD, adds HMBC correlations in batches, diagnoses failures | `lsd-input.md`, `checks-and-diagnosis.md` |
| 3 | ranks the candidates, checks identities, declares the result with `ailsa run finalize` | `ranking.md` |

What the frontier team spreads over five agents (coordinator, NMR chemist, LSD engineer, solution
analyst, devil's advocate, with a diagnostic specialist on escalation), the lean agent does in
turn; the devil's-advocate checks become a checklist it applies before every solver run. The
state of a run lives in files the agent writes (`setup.md`, `iterations.md`, one `compound.lsd`
per iteration), because a small model must not rely on what it remembers.

The lean skill writes the run record ([RUN-RECORD.md](RUN-RECORD.md)): `ailsa run init` is its
first step, `ailsa run note` records step summaries and `ailsa run finalize` declares the result.
Until the frontier skill is wired to the record, `run init`, `run note` and `run finalize` are the
only commands the lean skill names that the frontier skill does not (an explicit allow-list in
the contract test).

Left out on purpose: messages between agents, the dashboard, timing stamps,
model-disclosure gates.

## Version 0.1, withdrawn

Version 0.1 (commit `925bf89`) moved the agent's work into scripts (`ailsa case` commands that
built the atom list and wrote the LSD file) and left the model six commands in a fixed order. On
40 blind benchmark datasets, Qwen3.8-27B with that skill found 2 structures, exactly the two the
commands found without any model. The scripts set the limit and the model could not contribute;
such a skill measures the scripts, not the model. The `ailsa case` commands are no longer used by
any skill.
