# AILSA skills: one paper skill, two maintained skills

AILSA is driven by instructions for a language-model agent (a "skill") on top of the `ailsa`
command line. There are three skill states. One is frozen, two are maintained side by side.

| Skill | For | Where | Status |
|---|---|---|---|
| **Paper skill** | the blind benchmark reported in the paper | git tags `paper-skill-v1`, `paper-skill-v2` | frozen, never edited |
| **`ailsa`** (frontier skill) | Anthropic's frontier models in Claude Code: large context, an agent team | `.claude/commands/`, `.claude/agents/` (moves with the skill rebuild) | maintained, the standard skill |
| **`ailsa-lite`** (lean skill) | small open-weight models (about 20–35 B parameters, 32–128 k context) in OpenCode or any harness that reads Agent Skills | `src/ailsa/skills/ailsa-lite/`, installed with `ailsa skill install` | maintained, new |

## Contents

- [The paper skill](#the-paper-skill)
- [Why two maintained skills](#why-two-maintained-skills)
- [Rule 1: share code, not prose](#rule-1-share-code-not-prose)
- [Rule 2: the command line is the contract](#rule-2-the-command-line-is-the-contract)
- [Rule 3: a skill ships with the CLI it calls](#rule-3-a-skill-ships-with-the-cli-it-calls)
- [Which skill does a change touch](#which-skill-does-a-change-touch)
- [Checks on every change](#checks-on-every-change)
- [Measuring both skills](#measuring-both-skills)
- [The lean skill, version 0.1](#the-lean-skill-version-01)

## The paper skill

The benchmark ran the CASE skill in two states, both headless (`claude -p`), which means without
an agent team: the coordinator called one specialist subagent at a time.

| Tag | Commit | Runs | Difference |
|---|---|---|---|
| `paper-skill-v1` | `f9aa7b3` | 45 (11–14 August 2026) | — |
| `paper-skill-v2` | `6d2d126` | 211 | adds one rule: an exchangeable OH/NH proton used in an HMBC line needs its own `HSQC` declaration (`d62d833`) |

The skill files on `master` were still byte-identical to `paper-skill-v2` when the tags were
set. To get the paper skill as it ran:

```bash
git worktree add ../ailsa-paper-skill paper-skill-v2
```

The skill files are `.claude/commands/lucy-ng/` and `.claude/agents/lucy-*.md` in that tree.
Never move these tags. A corrected or improved skill is a new skill, not a new paper skill.

## Why two maintained skills

The frontier skill spends context freely: about 75 000 tokens of instructions, a coordinator
plus four specialists, long reasoning between tool calls. That suits Opus-class models and is
the design the project wants to measure.

A 27 B model at 4-bit quantisation in a 24 GB card cannot use that skill. Before the first
spectrum is read, OpenCode's own prompt and one specialist file already take a large part of its
context, and its weakest point is exactly what the frontier skill asks of the model most often:
long, exact bookkeeping (atom indices, constraint inventories, LSD file syntax). The lean skill
moves that bookkeeping into the command line and leaves the model the chemical judgement.

## Rule 1: share code, not prose

Everything deterministic lives in the `ailsa` package and is tested there: peak cleanup,
matching 2D peaks to atoms, consistency checks, writing the LSD file, running the solver,
ranking, identity lookup. Both skills call it.

The two skills share **no** instruction text, and neither refers into the other. Each is written
for its model class. A rule that both need is encoded once in the code where possible, so that
neither skill has to state it. Example: "an OH proton used in an HMBC line needs its own HSQC
line" is a sentence in the frontier skill and simply a property of `ailsa case solve`, which
writes that line itself.

When a rule can only live in prose, it is written twice, in the words each model class needs,
and the change log records that both copies exist.

## Rule 2: the command line is the contract

- Every `ailsa …` invocation that either skill shows must exist with the flags shown. A test
  extracts them from both skills and checks them against `ailsa … --help`.
- Every JSON field a skill tells the model to read is covered by a test of that command.
- An interface change to a command that a skill names is made in the same commit as the change
  to every skill that names it. The test above makes a forgotten skill fail.
- The `ailsa case` commands are the lean skill's whole interface. The frontier skill may adopt
  them (the planned script versions of the devil's-advocate checks are `ailsa case check`).

## Rule 3: a skill ships with the CLI it calls

The lean skill is package data of `ailsa`. `ailsa skill install ailsa-lite --target opencode`
(or `--target claude`) copies the skill that belongs to the installed CLI version into the
harness's skill directory, so a user never combines a skill with a CLI it was not written for.
The skill states the package version it was written for, and `ailsa skill list` shows both.

The frontier skill is still symlinked from the repository into `~/.claude`. It moves to the same
mechanism when it is rebuilt.

## Which skill does a change touch

| Kind of change | Lean skill | Frontier skill |
|---|---|---|
| Bug fix or new capability inside a command | gets it through the command | gets it through the command |
| Change of a command's interface or JSON output | same commit | same commit |
| Chemistry rule (e.g. when a heteroatom bond may be fixed) | encode it in the command if possible; otherwise write it for this skill | the same; record "applies to both" in the change log |
| Harness feature (agent teams, hooks, OpenCode configuration) | only this skill | only this skill |
| Search strategy (e.g. HMBC in batches or all at once) | decided per skill, measured per skill | decided per skill, measured per skill |

Each skill keeps a `CHANGELOG.md` next to its files. Every entry says which skill it applies to
and, for a behaviour change, which measurement supports it.

## Checks on every change

Run by `pytest` (the answer scan only locally):

- **Format:** `name` matches `^[a-z0-9]+(-[a-z0-9]+)*$` and the directory name; `description`
  at most 1 024 characters, third person, says what the skill does and when to use it.
- **Size:** lean skill: `SKILL.md` at most 200 lines; everything a normal run loads at most about
  6 000 tokens. Frontier skill: every file under 500 lines, a table of contents in every file
  over 100 lines.
- **Hygiene:** no model IDs, no project history (phase numbers, dates, bug numbers), no dataset
  numbers, no dead file references, one name per role.
- **Commands:** the contract test from Rule 2.
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

## The lean skill, version 0.1

**What the model does:** it reads short reports, makes the judgement calls, and chains a fixed
sequence of commands. **What it never does:** write an LSD file, copy shift lists between
commands, keep a constraint inventory, or spawn other agents.

| Step | Command | Model's decision |
|---|---|---|
| 1 | `ailsa case scan <dataset>` | which experiments to use, if there is more than one of a kind |
| 2 | `ailsa case setup <dataset> --formula <MF>` | — |
| 3 | `ailsa case check` | resolve every reported issue with `ailsa case edit` (missing or surplus carbons, multiplicities, hybridisation, heteroatom hydrogens, doubtful correlations) |
| 4 | `ailsa case solve` | if there is no solution even after the solver may drop three correlations: find the contradiction (step 3 again) |
| 5 | `ailsa case rank` | is the best candidate chemically plausible? |
| 6 | `ailsa case report` | a two- to four-sentence assessment |

The state of a run lives in `analysis/problem.json`: every atom, every correlation with the
peak it came from, and every edit with its reason. The LSD file is generated from it for each
solver run and is never edited by hand. That makes constraint loss between iterations impossible
by construction, and it records for every constraint which observation it came from.

**Deliberate differences from the frontier skill** (to be measured, not assumed):

- All trusted HMBC correlations go into the first solver run, and the solver may drop up to
  three of them if no solution exists. The frontier skill adds three to five per iteration.
- No subagents, no messages, no progress log written by the model. The commands write the log.

**Not in version 0.1:** several multiplicity models searched side by side when DEPT and edited
HSQC are both missing; automatic search for the contradicting correlation; fragment search;
NUS and JCAMP-DX input (use `ailsa nus` or `ailsa jcamp` first).
