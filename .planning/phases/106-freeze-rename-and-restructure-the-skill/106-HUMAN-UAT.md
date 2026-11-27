---
status: complete
phase: 106-freeze-rename-and-restructure-the-skill
source: [106-15-SUMMARY.md]
started: 2026-11-27T11:08:21Z
updated: 2026-11-27T20:15:00Z
---

## Current Test

[awaiting the user's verdict on all eight items below; nothing has been approved on his behalf]

## Tests

### 1. One blind run of the renamed skill on the compute server

expected: A blind structure-elucidation run, started through the renamed command `/ailsa:case` with
the renamed agents, runs to its end on Sheldon and can be graded against the private answer key.
The rank of the true structure is reported; the phase does not fail on the rank alone, as agreed
beforehand.
result: accepted 2026-11-27 by the user (followed all recommendations)

**What was done.** On 2026-11-27 at 11:09 UTC, the normal benchmark runner started one blind run on
Sheldon on benchmark dataset CASE146. The runner opens a fresh headless Claude Code session that
receives only `/ailsa:case`, the dataset path and the molecular formula. The dataset was chosen
because it is blind (its identity never reached the skill or any prompt), because the old skill
solved it at rank 1 in the benchmark (one attempt, 1,763 s, three solver iterations), and because
with 19 heavy atoms it is big enough to need several iterations.

**Configuration.**
- Claude Code 2.1.332; model `claude-opus-5-5` for the coordinator and every specialist.
- Reference database on the host unchanged: the older schema-3 file (928,443 compounds), given to the
  run by its absolute path so no command depended on the working folder. With this schema the
  statistical detection commands return no data, exactly as in the benchmark.
- LSD 3.5.3; code at the phase head (skill files identical to the current state).
- The answer key is not on Sheldon; the runner's lockout found none of the former answer files.

**Outcome.** Finished in one attempt after 1,418 s (23 minutes; the old run took 29 minutes). Graded on vitus
against the private key: **solved, true structure at rank 1.** Three solver iterations narrowed the
candidates from 20,000 to 1,742 to 280 (old run: 21,223, 160, 37); the 280 solutions held 23
different structures, which the atom-by-atom comparison of predicted and measured shifts ranked.
The final report lists 11 candidates (old run: 4).

**Evidence that the renamed chain worked, from the run's own records.**
- Reference files read from `~/.claude/ailsa/references/`: 11 read calls covering 10 different
  files (among them the shared LSD reference, the constraint inventory, the validation checks and
  the progress-log format); **0 failed.**
- Command-line calls: 22 to `ailsa`, **0 to the old `lucy` command.**
- Specialists: six starts, all under the new names: NMR chemist 1, LSD engineer 1 (resumed by
  message for iterations 2 and 3; 4 messages, all delivered), devil's advocate 3, solution
  analyst 1. They worked one after another, as in the benchmark: a headless session forms no agent
  team, and the coordinator noted that in the log.
- Models: all 92 model replies in the session and its specialist records came from
  `claude-opus-5-5`. The progress log's "Team Models" block first names the coordinator and the NMR
  chemist (the others pending) and ends with a final line: all five roles on `claude-opus-5-5`.
- Errors: 4 small failures in the specialists' own helper commands (a parsing one-liner, a blocked
  long sleep, a cut-off wait, a failed self-check), each recovered in the next step. None involved
  a skill file or a failing `ailsa` command.
- The timing summary was written: peak picking 8.5 min, the three solver iterations 5.9, 3.1 and
  1.3 min, ranking 2.5 min, identity check 1.5 min.

**What the result can and cannot say.** The true structure is at rank 1, so no search for a
restructuring defect was needed. One run on one dataset cannot separate the restructuring from the
ranking change made after the benchmark (which decided the ranking here) or from run-to-run noise
(in an earlier repeat of 15 datasets, 11 gave the same verdict). It does show that the renamed
command, agents, references and CLI work together end to end and find the right answer on a
dataset the old skill solved.

**A small inconsistency, harmless here.** The coordinator wrote at the start that team messaging was
not available, and later used the message tool to resume the LSD engineer. How the agents
coordinate is decided in a later phase of this milestone; this run needs no change for it.

**Your decision.** (a) Accept the renamed chain as working. (b) Ask for a repeat run, on the same or
on a fallback dataset; it costs about 25 to 60 minutes on Sheldon and a share of the Claude quota,
and it would measure noise rather than the restructuring.

**Recommendation:** (a), because the run finished on its first attempt, found the true structure at
rank 1, and every link of the renamed chain shows up in its records.

### 2. The rule inventory: did the restructuring lose or change any rule?

expected: Every rule of the old skill files is found again in the new files, either word for word,
reworded with the same meaning, or removed for one of the reasons this phase allowed (an example
that named a compound or dataset, project history, a fixed model name, a dead reference).
result: accepted 2026-11-27 by the user (followed all recommendations): comparison base = phase-start tag `frontier-skill-pre-106`, option (a)

**What was done.** The skill text was split into smaller files and rewritten in plainer language.
To show that no rule was lost on the way, a script cut the old files into single rules and looked
for each one in the new files (the rule inventory, in the plans as `D-06`). A second reviewer, who
had not done the rewriting, then read every reworded rule next to its old wording.

**Numbers.**

| What | Count |
|---|---|
| Rules in the old files (15 files) | 1642 |
| Found again almost word for word | 1029 |
| Reworded, and read by the reviewer one by one | 555 |
| No close match found by the script | 58 |
| ... of these: found at another place / merged with a duplicate | 19 / 8 |
| ... removed because they named a compound or a dataset | 18 |
| ... removed project history / fixed model names / a dead reference | 10 / 2 / 1 |
| Reworded rules whose meaning had changed (an obligation had become a plain statement) | 3, all restored |
| Rules that used capital-letter emphasis | 406 |
| ... now carrying the reason for the rule | 388 |
| ... with no known reason, kept unchanged and marked for a later measurement | 18 |

The full lists live only in the private folder `~/Dropbox/develop/data/skill-rule-inventory-106/`,
because they quote the old text, which names benchmark compounds. They must never enter the
repository.

**A deliberate deviation from what was agreed.** The agreed plan was to compare the new files with
the skill exactly as the paper benchmark ran it (the git tag `paper-skill-v2`). The inventory
instead compares them with the skill as it stood at the start of this work (the local git tag
`frontier-skill-pre-106`). The reason: after the benchmark, two deliberate changes went into the
skill files: candidates are now ranked by an atom-by-atom comparison of predicted and measured
shifts, and several facts about the LSD solver were corrected, each tested against LSD 3.4.9.
Measured against the benchmark state, these wanted changes would show up as lost or altered rules
and would drown the real question in noise.

**Consequence.** The inventory proves that the restructuring kept every rule of the skill as it was
just before the restructuring. It does not re-check the two earlier changes; those were reviewed
when they were made.

**Your decision.** (a) Accept the inventory with this comparison base. Nothing further to do.
(b) Ask for an additional comparison against the benchmark state. That costs a rebuild of the
inventory into a new private folder and a hand classification of the rows the two later changes
touch; no model runs, a few hours of agent work.

**Recommendation:** (a), because this phase asks whether the restructuring lost anything, and the
text at the start of this work is the text that was restructured.

### 3. Form checks on the skill files

expected: The automatic checks that enforce the new writing rules run on every skill file, none is
skipped, and the scan for benchmark answers finds nothing.
result: accepted 2026-11-27 by the user (followed all recommendations)

**What it is.** A test file checks every skill file for the agreed form: under 500 lines, a
contents list in files over 100 lines, no dead references, no dataset numbers or compound names,
no fixed model names, no capital-letter emphasis, no project history. A second, local-only test
compares the skill files with the private benchmark answer key (names and structures).

**Result (2026-11-27 on vitus).**
- Form checks plus answer scan: 321 tests passed, 0 skipped, 0 expected failures. All local skill
  and benchmark-script tests together: 412 passed, 0 skipped.
- Sizes: the largest files are the sanitise command (494 lines) and the coordinator (492 lines);
  every skill file except the changelog is under 500 lines.
- Answer scan: no benchmark compound by name or by structure in the frontier skill (31 files) or in
  the lean skill (6 files).
- The rule-inventory checks (completeness and meaning) both exit without findings.

**Your decision.** Accept, or name a check you want added. **Recommendation:** accept; these checks
now run on every change, so a later regression shows up at once.

### 4. Full test suite on the compute server

expected: The whole test suite, the type checker and the linter are no worse at the end of this
phase than at the end of the previous one.
result: accepted 2026-11-27 by the user (followed all recommendations); the five web-view failures go with the old web view in Phase 106.2

**What it is.** The full suite takes too long for the work laptops, so it ran on Sheldon against
the recorded result of the previous phase (the run-record phase).

| Check | Previous phase | This phase |
|---|---|---|
| Tests | 5 failed, 1953 passed, 100 skipped | 5 failed, 2335 passed, 105 skipped |
| Failing tests that are new | | none |
| Linter findings | 273 | 273 |
| Type-checker errors | 151 in 40 files | 151 in 40 files |

The five failures are the same five tests of the old web view, which need an optional package that
the server's test environment does not have. The five extra skips are by design: checks that need
the git tags, the private answer key or a private identities table, none of which exist on Sheldon.
The built package contains all 31 skill files, identical to the source.

**Your decision.** Accept, or ask for the web-view failures to be looked at now. **Recommendation:**
accept; the old web view is removed in the next phase anyway, and with it those five tests.

### 5. Where the renamed skill is installed, machine by machine

expected: On every machine where CASE runs happen, `/ailsa:*` commands work and no `/lucy-ng:*`
leftovers remain.
result: accepted 2026-11-27 by the user (followed all recommendations); vitus and Sheldon linked; laptop command still to run on the laptop (not reachable from vitus); caffeine not installed (no CASE sessions there)

**Done.**
- **vitus**: linked into the checkout. `~/.claude/commands/ailsa` points to
  `~/Dropbox/develop/lucy-ng/src/ailsa/skills/ailsa/commands`; the five
  `~/.claude/agents/ailsa-*.md` point to `.../src/ailsa/skills/ailsa/agents/`;
  `~/.claude/ailsa/references` and `~/.claude/ailsa/INDEX.md` point to `.../src/ailsa/skills/ailsa/`.
  Edits in the checkout apply at the next session start.
- **Sheldon**: linked the same way into `/mnt/raid_drive/chris/lucy-ng/src/ailsa/skills/ailsa/`.
  No `lucy` entry remains in `~/.claude/commands` or `~/.claude/agents`.
- The installer left no old regular file behind on either machine.

**Not done, because no automated step can reach these machines.**

(a) **The laptop** shares the checkout with vitus through Dropbox. Its old links pointed at files
that the move deleted, so since Dropbox synced the move, `/lucy-ng:*` no longer works there and
`/ailsa:*` is not yet set up. The fix is one command on the laptop:

```
~/Dropbox/develop/lucy-ng/.venv/bin/ailsa skill install ailsa --target claude --link
```

The checkout's `.venv` is the laptop's own editable install, so link mode applies, and the
installer removes the dead old links. Then check `launchctl list | grep lucyng`. If the old
benchmark watchdog agent still shows up, run
`launchctl unload -w ~/Library/LaunchAgents/de.doktor-steinbeck.lucyng-uat-watchdog.plist` and
delete that file; the watchdog now runs by hand in a herdr pane on vitus when a measurement series
is due.

(b) **caffeine** has no Dropbox. Checked again on 2026-11-27: reachable, no
`~/.claude/commands` folder, no AILSA agents (only the GSD ones), no `ailsa` command and no
checkout. Nothing is broken there, because it never had the skill. If you want CASE sessions on
caffeine, after this phase is pushed:

```
git clone https://github.com/steinbeck/ailsa.git ~/work/ailsa
python3 -m venv ~/.venvs/ailsa
~/.venvs/ailsa/bin/pip install -e ~/work/ailsa
~/.venvs/ailsa/bin/ailsa skill install ailsa --target claude --link
```

Later updates with `git -C ~/work/ailsa pull`. Alternatively, once a PyPI release contains the
packaged skill: `pip install ailsa` and `ailsa skill install ailsa --target claude` (copy mode,
because link mode is refused for an installed package; repeat with `--force` after each upgrade).

**Your decision.** Run the laptop command; decide whether caffeine should get the skill.
**Recommendation:** run the laptop command now (a minute); install on caffeine only if you want CASE
sessions there, which it has never had.

### 6. Fresh-session check of the command menu

expected: In a new Claude Code session the `/ailsa:` menu shows six commands (case, dereplicate,
help, predict, sanitise, status) and no entries for the reference files.
result: accepted 2026-11-27 by the user (followed all recommendations); the vitus session listed exactly the six /ailsa:* commands after the link install (no reference entries); the status-path observation is option (a), todo `2026-11-27-ailsa-status-db-relative-path.md` for Phase 108

**Why manual.** Slash commands are registered when a session starts, and only a person sees the
menu. Headless on Sheldon, `/ailsa:status` was recognised and reported the `ailsa` command, LSD and
outlsd as available, and the acceptance run in item 1 started through `/ailsa:case`.

**How.** Open a new Claude Code session on vitus (or on the laptop after the command in item 5),
type `/ailsa:` and look at the list, then run `/ailsa:status`.

**One observation.** `/ailsa:status` reports the reference database as missing whenever the
session does not start in the checkout folder, because it asks for the fixed relative path
`data/reference/ailsa-derep.db`. The analysis commands themselves find the database through the
usual search (environment variable, then standard locations), as the acceptance run shows. This
behaviour is inherited from the old skill, not caused by the rename. Options: (a) leave it for the
foundation phase, where the CLI and its checks are revised; (b) fix it now by letting the status
command call `ailsa database info` without a path, which uses the same search as the analysis
commands (a one-line change to a skill file, plus the file's checksum). **Recommendation:** (a),
because this phase changes no behaviour, and a false "missing" in a status report misleads but
blocks nothing.

### 7. Pushing the phase to the public repository

expected: The phase's work reaches GitHub only after your decision, because the repository is
public.
result: decided 2026-11-27 by the user — option (a): commits pushed (52e5ab3..1ea7253), tag `frontier-skill-pre-106` kept local

**State.** All commits of this phase are local only (50 before this last plan, all from this
phase). The local tag `frontier-skill-pre-106` marks the skill as it stood at the start of the
phase; it exists only on vitus. Before you decide, every text file these commits touch (99 files)
was scanned against the private answer key: no benchmark compound by name or by structure. The only
hits were a generic English word that the key uses as one dataset's label; that word already
appears in the public documentation.

**Options.**
- (a) Push the commits, keep the tag local. The renamed, restructured skill becomes public and can
  be installed from GitHub (caffeine, pip from git). The tag stays a private bookmark for the rule
  inventory; the documentation cites the phase-start commit by its hash, which resolves publicly
  once the commits are pushed.
- (b) Push both. Content-wise harmless, the tag marks a commit that is public anyway. But a public
  tag is hard to take back once others have fetched it, and a third skill tag next to the two paper
  tags invites the misreading that it is a benchmark state.
- (c) Hold back. Laptop and Sheldon do not need the push (Dropbox and git bundle), but GitHub keeps
  showing the old `lucy-ng` skill layout, the caffeine install above is not possible, and the gap
  grows with every later phase.

**Recommendation:** (a): it publishes the work, which passed the answer scan, and keeps an internal
bookmark internal.

### 8. Not done here on purpose: the global CLAUDE.md example

expected: Your global `~/.claude/CLAUDE.md` names commands that exist.
result: accepted 2026-11-27 by the user (followed all recommendations): template changed to `/ailsa:case`, `/ailsa:dereplicate` and copied to vitus and caffeine (backups `CLAUDE.md.bak-2026-11-27`); laptop copy follows with `./claude-md-verteilen.sh` on the laptop

**What it is about.** The global instructions on all three herdr machines cite `/lucy-ng:case` and
`/lucy-ng:dereplicate` as examples of plugin commands that keep the colon form. Those commands no
longer exist. The file is generated from the template in the session-manager project
(`Claude-Code Session-Manager/claude-global/CLAUDE.md`, distributed with `claude-md-verteilen.sh`),
so this repository cannot change it.

**Options.** (a) Replace the examples with `/ailsa:case` and `/ailsa:dereplicate` in the template
and redistribute (a few minutes in the herdr admin lane on the laptop). (b) Leave it: the rule it
illustrates still reads correctly, but a session may try to run the old command names.
**Recommendation:** (a), together with the laptop command from item 5.

## Summary

total: 8
passed: 8
issues: 0
pending: 0
skipped: 0
blocked: 0

All eight accepted on 2026-11-27. Remaining manual steps on the laptop only: the skill install
command (item 5) and `./claude-md-verteilen.sh` (item 8).

## Gaps

None blocking. Open choices are listed inside items 1, 2, 6, 7 and 8.
