# Scripts

## Quota watchdog for benchmark series

`uat_watchdog.py` drives a blind benchmark series on Sheldon in small chunks. Before each chunk
it checks the 5-hour and the 7-day quota of the Claude account and launches the next chunk only
while both are below their ceilings. It never kills a running chunk.

**Where it runs:** on vitus, in its own herdr pane in the lane's space. It is started by hand when
a measurement series is due and restarted by hand after a vitus reboot. There is no LaunchAgent
(the old one was retired in Phase 106); nothing persistent runs on the laptop.

**How to start it:**

```bash
herdr pane split --current --direction down --cwd "$PWD" --no-focus
herdr pane run <pane> "python3 -u scripts/uat_watchdog.py --cases ... --results-dir <new folder on Sheldon>"
```

The watchdog runs in the pane's own terminal. `--results-dir` is required and has no default.
The two launchers of the paper benchmark (`uat_run_baseline_opus5.sh`, `uat_run_remaining.sh`)
are retired: they wrote into its frozen result folders and now only exit with a message.

**What it needs on vitus:** a quota snapshot at `~/.claude/usage-snapshot.json`. claude-hud writes
it through `display.externalUsageWritePath` in `~/.claude/plugins/claude-hud/config.json`, but only
while an interactive Claude Code session renders its statusline. vitus has no such setting yet;
set it before the first series. Without it the watchdog halts after the snapshot age limit.

A new series uses a new results folder on Sheldon; the historical `case-uat-results*` folders stay
untouched. The watchdog refuses the paper benchmark's folders, and any folder that already holds a
run whose `meta.json` names another model or none; `blind_case_batch.py` refuses the same on
Sheldon. Every `meta.json` records `model`, `claude_bin` and `claude_version`. The watchdog pins Claude Code 2.1.332 and the model `claude-opus-5-5` on Sheldon. The
answer-file lockout it carries is a no-op today because the key is no longer on Sheldon.

## One blind run without the watchdog

Run `tests/case-benchmark/blind_case_batch.py` on Sheldon with the environment variables
described in `tests/case-benchmark/README.md` (`CASE_DATA_DIR`, `CASE_RESULTS_DIR`,
`CLAUDE_MODEL`, `CLAUDE_BIN`).
