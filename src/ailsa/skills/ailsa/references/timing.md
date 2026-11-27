# Wall-clock timing

The coordinator takes real UTC timestamps at every phase boundary and agent hand-back, so that the
total and per-phase duration of a run can be reported reproducibly (for example in a publication).
The steps that push a `[BEGIN]` directive or receive a completion reply take the stamps described
here; terminate_team runs the finalize script.

## Contents

- Two rules
- Mechanism: one append per event
- When to stamp
- Finalize

## Two rules

1. **Read the clock; do not infer a timestamp.** Do not take a timestamp from context or
   `currentDate`: that only knows the calendar day. Read the real clock with `date -u` every time.
   A timestamp filled in from context has no time of day, so durations computed from it are
   meaningless.
2. **All timing work happens in the coordinator**, not in the teammates. It therefore cannot delay
   the LSD engineer's rule to send `[ITERATION-COMPLETE]` the instant the solver exits, the rule
   that keeps a run from hanging. A `date` call is instantaneous; still, take the `phase_end` stamp
   for an arriving reply first, then write its CASE-PROGRESS.md section and push the next
   `[BEGIN]`. Stamping does not gate the next directive.

## Mechanism: one append per event

At each timing point, run exactly one Bash call that reads the clock and appends one JSON line to
the append-only log, which survives restarts:

```bash
printf '{"utc":"%s","epoch":%s,"event":"%s","phase":"%s","agent":"%s"}\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(date -u +%s)" "<event>" "<phase>" "<agent>" \
  >> <compound_path>/analysis/timing.jsonl
```

The very first call, `run_start`, creates the directory first: prefix it with
`mkdir -p <compound_path>/analysis && `.

## When to stamp

Stamp at phase boundaries and agent hand-backs: plenty, but not every message.

| event | phase value | when |
|-------|-------------|------|
| `run_start` | `run` | once, at team spawn, before the first `[BEGIN]` push |
| `phase_start` | the task name (`peak-picking`, `lsd-iteration-NN`, `hmbc-selection-NN`, `ranking`, `coverage_gate`, `identity_gate`) | immediately before you SendMessage each `[BEGIN]` directive |
| `phase_end` | same phase name | immediately as the matching `[*-COMPLETE]` / `[VALIDATION-*]` / `[G-IDENT-*]` reply arrives (before writing its section) |
| `run_end` | `run` | once, after the gates pass and results are ready, before terminate_team |

Rule of thumb: **every `[BEGIN]` you send gets one `phase_start`; every completion reply you
receive gets one `phase_end`.** That gives start and end for every phase and a stamp for every
agent hand-back, without stamping routine chatter. Also mirror the human-readable UTC value into
the matching field of CASE-PROGRESS.md (`**Started (UTC):**`, `**Phase start (UTC):**`,
`**Reported (UTC):**`).

## Finalize

Run once, right after the `run_end` stamp, before terminate_team shuts the team down. This also
runs on the escalate and smoke-test exits (any path into terminate_team), so a duration is always
recorded. The script converts the log into the machine-readable `timing.json` and a human table
deterministically: Python does the arithmetic, so do not compute durations by hand.

```bash
python3 - <<'PY' <compound_path>
import json, sys, pathlib
d = pathlib.Path(sys.argv[1]) / "analysis"
ev = [json.loads(l) for l in (d/"timing.jsonl").read_text().splitlines() if l.strip()]
def hms(s): return None if s is None else f"{s//3600:02d}:{s%3600//60:02d}:{s%60:02d}"
starts, phases = {}, []
for e in ev:
    if e["event"] == "phase_start":
        starts[e["phase"]] = e
    elif e["event"] == "phase_end" and e["phase"] in starts:
        s = starts.pop(e["phase"])
        phases.append({"phase": e["phase"], "agent": e.get("agent", ""),
                       "start_utc": s["utc"], "end_utc": e["utc"],
                       "duration_s": int(e["epoch"]) - int(s["epoch"])})
run = {x["event"]: x for x in ev if x["event"] in ("run_start", "run_end")}
total = (int(run["run_end"]["epoch"]) - int(run["run_start"]["epoch"])) if {"run_start","run_end"} <= run.keys() else None
out = {"run_start_utc": run.get("run_start", {}).get("utc"),
       "run_end_utc": run.get("run_end", {}).get("utc"),
       "total_duration_s": total, "total_duration_hms": hms(total), "phases": phases}
(d/"timing.json").write_text(json.dumps(out, indent=2))
rows = "\n".join(f"| {p['phase']} | {p['agent']} | {p['start_utc']} | {p['end_utc']} | {hms(p['duration_s'])} |" for p in phases)
print("\n## Timing Summary\n\n"
      f"**Run start (UTC):** {out['run_start_utc']}  \n"
      f"**Run end (UTC):** {out['run_end_utc']}  \n"
      f"**Total wall-clock:** {out['total_duration_hms']}\n\n"
      "| Phase | Agent | Start (UTC) | End (UTC) | Duration |\n"
      "|-------|-------|-------------|-----------|----------|\n" + rows + "\n")
PY
```

Append the printed `## Timing Summary` block to `analysis/CASE-PROGRESS.md`, and also to
`analysis/final_results.md` if it exists (it does not on the escalate and smoke-test exits).
`analysis/timing.json` is the machine-readable artefact for aggregating across many runs.
