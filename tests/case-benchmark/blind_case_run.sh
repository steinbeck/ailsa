#!/usr/bin/env bash
# blind_case_run.sh — run ONE blind ailsa:case elucidation on a sanitised
# dataset as an isolated headless run through `ailsa run start`.
#
# The launcher creates the run record OUTSIDE the dataset (per-case workspace
# $RESULTS_DIR/ailsa-runs), resumes the same session until the run declares its
# result, and always closes the record. Nothing is written into the dataset.
# Grading (correctness vs truth) happens SEPARATELY, later, in grade_blind.py —
# never inside the solving process. When the run declared a proposed candidate
# (outcome proposal or proposal_under_determined) this script copies the rendered
# final_results.md (and CASE-PROGRESS.md) to $RESULTS_DIR/analysis/ so graders and
# the watchdog read what they always read; meta.json records every declared outcome.
#
# Blindness: the fresh process gets ONLY the dataset path + the molecular formula
# (read from the dataset's own molecular-formula.txt / molecularformula.txt);
# `--blind` makes the launcher refuse when an earlier run of the same data is
# readable, and a system-prompt fence forbids reading answer-key locations.
#
# Usage: blind_case_run.sh <CASE_DIR> <RESULTS_DIR> [full|smoke]
#
# Env (see README.md):
#   CASE_PROJECT_DIR   ailsa repo root (for .venv/bin). Default: repo of this script.
#   CLAUDE_MODEL       model id. REQUIRED, no default.
#   CLAUDE_BIN         claude binary to use. Default: `claude` on PATH. The launcher
#                      starts the harness by the name `claude`, so the folder of a
#                      pinned binary is put first on PATH.
#   AILSA_BIN          ailsa CLI. Default: `ailsa` on PATH.
#   CASE_ANSWERKEY_DIR optional dir the fence explicitly forbids reading.
#   CASE_RUN_MAX_ATTEMPTS (default 8), CASE_RUN_CALL_TIMEOUT s (3600),
#   CASE_RUN_DEADLINE_S total per dataset (9000)
set -u
CASE_DIR="$1"; RESULTS_DIR="$2"; MODE="${3:-full}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CASE_PROJECT_DIR="${CASE_PROJECT_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
# Which `claude` binary runs the benchmark. The reason to pin is
# comparability: holding the CLI fixed within a series keeps a later
# difference attributable to the model rather than to the toolchain. The
# paper benchmark ran on Claude Code 2.1.205 (recorded in docs/BENCHMARK.md);
# Opus 5.5 needs 2.1.280 or later.
#
# "Execution error" in a run log is the per-attempt time limit ending
# `claude -p`, not a fault; the launcher resumes the same session.
CLAUDE_BIN="${CLAUDE_BIN:-claude}"
AILSA_BIN="${AILSA_BIN:-ailsa}"

# No silent default. A benchmark whose model is implicit is unreadable six
# months later, and the previous default (claude-opus-4-8) quietly kept
# producing 4.8 results long after Opus 5 had become the session default.
# Name the model or the run does not start.
if [ -z "${CLAUDE_MODEL:-}" ]; then
  echo "CLAUDE_MODEL is unset. Benchmark runs must name their model explicitly" >&2
  echo "  so results stay attributable, e.g. CLAUDE_MODEL=claude-opus-5-5" >&2
  exit 2
fi
# Provenance for meta.json: which model and which CLI produced the run, so a results folder
# that mixes series can be detected afterwards (blind_case_batch.py refuses to add to one).
CLAUDE_VERSION="$("$CLAUDE_BIN" --version 2>/dev/null | head -1 | tr -d '"\\')"
PROV="\"model\":\"${CLAUDE_MODEL//\"/}\",\"claude_bin\":\"${CLAUDE_BIN//\"/}\",\"claude_version\":\"${CLAUDE_VERSION}\""
CASE_ANSWERKEY_DIR="${CASE_ANSWERKEY_DIR:-}"
MAX_ATTEMPTS="${CASE_RUN_MAX_ATTEMPTS:-8}"
CALL_TIMEOUT="${CASE_RUN_CALL_TIMEOUT:-3600}"
DEADLINE_S="${CASE_RUN_DEADLINE_S:-9000}"

CASE_NAME="$(basename "$CASE_DIR")"
# molecular formula: accept either filename convention
MF_FILE=""
for f in molecular-formula.txt molecularformula.txt; do
  [ -f "$CASE_DIR/$f" ] && { MF_FILE="$CASE_DIR/$f"; break; }
done
mkdir -p "$RESULTS_DIR"
if [ -z "$MF_FILE" ]; then
  echo '{"case":"'"$CASE_NAME"'",'"$PROV"',"status":"error","reason":"no_MF_file"}' > "$RESULTS_DIR/meta.json"; exit 2
fi
MF="$(tr -d '[:space:]' < "$MF_FILE")"

# put ailsa on PATH if a repo venv exists
[ -d "$CASE_PROJECT_DIR/.venv/bin" ] && export PATH="$CASE_PROJECT_DIR/.venv/bin:$PATH"
# the launcher starts the harness by the name `claude`: put the pinned one first
case "$CLAUDE_BIN" in */*) export PATH="$(dirname "$CLAUDE_BIN"):$PATH";; esac

# The run's own record lies under the results root (per-case workspace), so the fence exempts
# exactly that run folder and keeps every other results folder off limits.
RESULTS_ROOT="$(cd "$RESULTS_DIR/.." && pwd)"
FENCE="BLIND CASE EVALUATION. Solve an unknown structure using ONLY the NMR data at the given dataset path plus the provided molecular formula. Do NOT read, list or grep any ground-truth / answer-key / benchmark-results location${CASE_ANSWERKEY_DIR:+ (in particular ${CASE_ANSWERKEY_DIR})} — using it invalidates the run. Your own run folder (the parent of your working folder) is not such a location: read its record and renderings as the workflow asks. Every other folder under ${RESULTS_ROOT} is one. Never attempt dereplication; never look the compound up by name.

HEADLESS EXECUTION: there is no event loop to wake you after you stop. Never background a teammate/solver and then end your turn to 'wait' — drive every stage to completion INLINE, and do not stop until the run is settled: \`ailsa run finalize\` with an outcome the evidence justifies, or \`ailsa run close --reason ...\` when no result can be declared (a smoke test, a failed prerequisite). Never declare an outcome only to end the run."

if [ "$MODE" = smoke ]; then
  PROMPT_ARGS=(--prompt "/ailsa:case $CASE_DIR $MF --smoke-test")
  ATTEMPTS_ARG=1
else
  PROMPT_ARGS=()
  ATTEMPTS_ARG="$MAX_ATTEMPTS"
fi

START=$(date +%s)
# The launcher runs in the background only so that its pid can be recorded: the watchdog's
# abort stops exactly this launcher (launcher.pid), never another `ailsa run start` of the
# same user on the shared host. Keep the argument order: the abort checks it.
AILSA_WORKSPACE="$RESULTS_DIR/ailsa-runs" "$AILSA_BIN" run start "$CASE_DIR" --skill ailsa --headless --blind \
  --model "$CLAUDE_MODEL" --formula "$MF" --time-limit "$CALL_TIMEOUT" \
  --resume-attempts "$ATTEMPTS_ARG" --deadline "$DEADLINE_S" --no-views --format json \
  ${PROMPT_ARGS[@]+"${PROMPT_ARGS[@]}"} \
  -- --append-system-prompt "$FENCE" \
  > "$RESULTS_DIR/launch.json" 2> "$RESULTS_DIR/launch.err" &
LPID=$!
echo "$LPID" > "$RESULTS_DIR/launcher.pid"
wait "$LPID"
RC=$?
END=$(date +%s); RUNTIME=$((END - START))

jfield () { # $1 key: value from launch.json, empty when missing or not JSON
  python3 -c 'import json,sys
try:
    v = json.load(open(sys.argv[1])).get(sys.argv[2], "")
except Exception:
    v = ""
print("" if v is None else v)' "$RESULTS_DIR/launch.json" "$1" 2>/dev/null
}
RUN_ID="$(jfield run_id)"; RUN_DIR="$(jfield run_dir)"; RUN_STATE="$(jfield state)"
ATTEMPTS="$(jfield attempts)"; [ -n "$ATTEMPTS" ] || ATTEMPTS=0
# Why the launcher stopped (a signal means the run was aborted, not exhausted), as JSON values.
jjson () { # $1 key: JSON-encoded value from launch.json, null when missing or not JSON
  python3 -c 'import json,sys
try:
    v = json.load(open(sys.argv[1])).get(sys.argv[2])
except Exception:
    v = None
print(json.dumps(v))' "$RESULTS_DIR/launch.json" "$1" 2>/dev/null || echo null
}
LREASON="$(jjson reason)"; LSIGNAL="$(jjson signal)"; LEXIT="$(jjson exit_code)"

# existing log readers keep their input
[ -n "$RUN_DIR" ] && [ -f "$RUN_DIR/transcript/harness-output.log" ] \
  && cat "$RUN_DIR/transcript/harness-output.log" >> "$RESULTS_DIR/run.log"

# The declared outcome (empty without a valid declaration), recorded in meta.json.
OUTCOME=""
if [ "$RUN_STATE" = result_declared ] && [ -n "$RUN_DIR" ]; then
  OUTCOME="$(AILSA_WORKSPACE="$RESULTS_DIR/ailsa-runs" "$AILSA_BIN" run status --run "$RUN_DIR" \
    --format json 2>/dev/null | python3 -c 'import json,sys
try:
    v = (json.load(sys.stdin).get("final") or {}).get("outcome") or ""
except Exception:
    v = ""
print(v)' 2>/dev/null)"
fi

# Compatibility copy for graders and watchdog: only when the run proposed a candidate. The
# other declared outcomes (inconclusive, handed_to_human, no_structure_fits,
# insufficient_data) propose no structure, so they leave nothing to grade; their rendering
# still lists the top candidates, which a grader would otherwise count as an answer.
FRR="$RESULTS_DIR/analysis/final_results.md"; FR_EXISTS=false; TOPSMI=""
case "$OUTCOME" in proposal|proposal_under_determined) PROPOSED=true;; *) PROPOSED=false;; esac
if [ "$PROPOSED" = true ] && [ -f "$RUN_DIR/renderings/final_results.md" ]; then
  mkdir -p "$RESULTS_DIR/analysis"
  cp -n "$RUN_DIR/renderings/final_results.md" "$RESULTS_DIR/analysis/final_results.md"
  [ -f "$RUN_DIR/renderings/CASE-PROGRESS.md" ] \
    && cp -n "$RUN_DIR/renderings/CASE-PROGRESS.md" "$RESULTS_DIR/analysis/CASE-PROGRESS.md"
  FR_EXISTS=true
  TOPSMI="$(grep -aoiE 'SMILES[^A-Za-z0-9]+[^ `|)]+' "$FRR" | head -1 | sed -E 's/.*SMILES[^A-Za-z0-9]+//I')"
  case "$TOPSMI" in *' '*|"") TOPSMI="";; esac
  echo "$TOPSMI" | grep -qE '[=#()1-9]|[cC][cC]' || TOPSMI=""
fi

STATUS=""
if [ "$RC" -eq 2 ] || [ -z "$RUN_ID" ]; then
  STATUS=',"status":"error","reason":"launcher exit '"$RC"'"'
fi
printf '{"case":"%s",%s,"mf":"%s","mode":"%s","attempts":%d,"runtime_s":%d,"final_results":%s,"top_smiles":"%s","run_id":"%s","run_state":"%s","run_dir":"%s","outcome":"%s","launcher_reason":%s,"signal":%s,"exit_code":%s,"launcher_rc":%d%s}\n' \
  "$CASE_NAME" "$PROV" "$MF" "$MODE" "$ATTEMPTS" "$RUNTIME" "$FR_EXISTS" "${TOPSMI//\"/}" \
  "${RUN_ID//\"/}" "${RUN_STATE//\"/}" "${RUN_DIR//\"/}" "${OUTCOME//\"/}" \
  "$LREASON" "$LSIGNAL" "$LEXIT" "$RC" "$STATUS" > "$RESULTS_DIR/meta.json"
echo "[$CASE_NAME] attempts=$ATTEMPTS runtime=${RUNTIME}s final_results=$FR_EXISTS"
