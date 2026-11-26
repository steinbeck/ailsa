# Phase 106: Freeze, rename and restructure the skill - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-26
**Phase:** 106-freeze-rename-and-restructure-the-skill
**Areas discussed:** How far the text may change, Where the skill lives and how it is installed, How we rule out a regression, Benchmark control after the move

Questions were asked in German; options are summarised here in English.

---

## How far the text may change

### What replaces the fixed model pin and the mismatch warning?

| Option | Description | Selected |
|--------|-------------|----------|
| Report only, no comparison | Pin and warning go; each specialist still names its actual model, the coordinator records it | ✓ |
| Remove entirely | No pin, no report; the model is only in the run record (frontier skill from 106.2) | |
| Alias instead of version | Pin "opus", keep the check; the skill stays tied to one model family | |

**User's choice:** Report only, no comparison.

### What happens to the ~180 capital-letter rules?

| Option | Description | Selected |
|--------|-------------|----------|
| Rationale instead of emphasis | Same rule as a plain sentence plus the failure it prevents where known; unknown-reason rules marked for Phase 109 | ✓ |
| Keep capitals for now | Only names and structure change now; every file touched again in 109; deviates from SKILL-05 | |

**User's choice:** Rationale instead of emphasis.

### What replaces worked examples that name datasets or compounds?

| Option | Description | Selected |
|--------|-------------|----------|
| Rule stays, molecule goes | No named compound; syntax examples with atom numbers and shifts only | ✓ |
| α-terpineol as example | Public and outside all pools, but the skill would then know the demo dataset | |
| Invented molecules | Cannot de-blind, but may be chemically inconsistent and mislead | |

**User's choice:** Rule stays, molecule goes.

### What does Phase 106 do with the double workflow (team flow plus headless caveat)?

| Option | Description | Selected |
|--------|-------------|----------|
| Leave as is, only reorder | No pre-emption of Phase 107; Phase 109 rewrites the flow anyway | ✓ |
| Split now into core plus two flow files | Cleaner, but needs mode detection: a behaviour change 109 may undo | |

**User's choice:** Leave as is, only reorder.

---

## Where the skill lives and how it is installed

| Option | Description | Selected |
|--------|-------------|----------|
| Into the package now | Package data plus `ailsa skill install ailsa`; link option on maintainer machines; each file moves once | ✓ |
| Stay in the repo, move later | New `.claude/commands/ailsa/` with symlinks; package move with PyPI (Phase 111); files move twice | |
| As a Claude Code plugin | Commands, agents and hooks in one bundle; OpenCode cannot read it; agent names change form | |

**User's choice:** Into the package now.

---

## How we rule out a regression

### How do we safeguard the restructuring before the comparison run?

| Option | Description | Selected |
|--------|-------------|----------|
| One run plus rule inventory | Map every old rule to its new place; report lost or changed rules; no quota | ✓ |
| Small before/after comparison | 5 datasets × old/new, ~10 runs, ~1/5 of a weekly quota; sees only gross breaks | |
| Only the one run | Cheapest; a lost rule surfaces only in Phase 110 | |

**User's choice:** One run plus rule inventory.

### When does the one blind acceptance run pass?

| Option | Description | Selected |
|--------|-------------|----------|
| Completes, result reported | Pass when it completes and is graded; rank reported; a miss is inspected and put to the user | ✓ |
| Must solve at rank 1 | Stricter; a noise failure would block the phase | |

**User's choice:** Completes, result reported.

---

## Benchmark control after the move

### Where does the quota watchdog run?

| Option | Description | Selected |
|--------|-------------|----------|
| vitus, herdr pane | Follows the 2026-11-14 rule; restarted by hand after a reboot; SKILL-04 reworded | ✓ |
| vitus, LaunchAgent | Survives reboots, but invisible and against the herdr-pane rule | |
| Laptop, rename only | As SKILL-04 says; stops when the laptop is closed | |

**User's choice:** vitus, herdr pane.

### Where does the restructured skill live on Sheldon?

| Option | Description | Selected |
|--------|-------------|----------|
| Update the main checkout | After the restructuring; paper skill via tags; result dirs untouched | ✓ |
| Separate area next to it | Runner and watchdog repointed; two states on one host | |

**User's choice:** Update the main checkout.

### Which configuration runs the acceptance run?

| Option | Description | Selected |
|--------|-------------|----------|
| Today's configuration | Opus 5.5, current Claude Code; watchdog's pinned binary updated | ✓ |
| Benchmark configuration | Opus 5, Claude Code 2.1.205; isolates the skill change if Opus 5 is still available | |

**User's choice:** Today's configuration.

---

## Folded todos

| Todo | Decision |
|------|----------|
| CLI database help lacks the COCONUT shift credit | Folded (recommended) |
| CASE4 azulene regiochemistry gap | Not folded — Phase 109 |
| 2D picker IndexError on empty spectrum | Not folded — Phase 108 |
| Ranking tests hard-fail without hosegen | Not folded — Phase 108 |

## Claude's Discretion

Package layout, installer details and link option, file splits and reference reading points, the
shared LSD reference, one term per role, lint implementation and answer-scan wiring, rule-inventory
format and meaning check, choice of the acceptance dataset within D-07.

## Deferred Ideas

- Update the global `~/.claude/CLAUDE.md` template (session-manager project) where it cites
  `/lucy-ng:case`, once `/ailsa:case` exists.
