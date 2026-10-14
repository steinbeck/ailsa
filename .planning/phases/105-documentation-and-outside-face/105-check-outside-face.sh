#!/usr/bin/env bash
# Phase 105 gate: the outside face of the repository (DOC-01..04, D-05, D-13a, D-17).
#
# Run from anywhere; the script changes to the repository root itself.
# Prints one PASS/FAIL line per check (and per sub-check); exits 1 if any check fails.
# Network: one unauthenticated GET against the public figshare API (check 7).
# Side effect: check 6 rebuilds docs/infographics/deck.html from build.py; if the committed
# HTML was out of sync, the rebuilt file is left in the working tree for inspection.
set -u

ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)" || exit 2
cd "$ROOT" || exit 2

PHASE_DIR=".planning/phases/105-documentation-and-outside-face"
FAILS=0
pass() { printf 'PASS  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; FAILS=$((FAILS + 1)); }
detail() { sed 's/^/        /'; }

# Outside-facing files that must not contain the old name in any spelling (D-01, D-03).
IN_SCOPE=(
  README.md
  CLAUDE.md
  .gitignore
  rdmo-project-description.txt
  docs/ARCHITECTURE.md
  docs/BENCHMARK.md
  docs/INSTALLATION.md
  docs/NUS-PORTABILITY.md
  docs/SERVER_BOOTSTRAP.md
  docs/USER_GUIDE.md
  docs/nmr_shift_prediction_tools.md
  docs/infographics/build.py
  docs/infographics/README.md
  docs/infographics/deck.html
  scripts/faulon-bridge/README.md
  scripts/faulon-bridge/lsd2sml.py
  scripts/faulon-bridge/examples/CASE13.lsd
  scripts/faulon-bridge/examples/CASE13.sml
  scripts/figshare_upload.py
  scripts/zenodo_upload.py
)

# Files removed by plan 105-08 (git rm, user-approved); none of them is in IN_SCOPE, so no
# in-scope file may be missing.
REMOVED_BY_105_08=(
  analysis_ibuprofen/CASE_RESULTS.md
  docs/superpowers/specs/2026-07-02-case-webview-design.md
  docs/superpowers/specs/2026-08-10-case-forced-ranking-design.md
  background/sherlock-analysis.md
  background/wenk-thesis.txt
)

# Residue deliberately not renamed in Phase 105 (D-12): the deprecated console-script alias,
# the scripts that drive live hosts (renamed with the skill / evaluation phases) and one
# absolute local data path.
RESIDUE_ALLOW=(
  pyproject.toml
  scripts/bootstrap_case_host.sh
  scripts/launchd/README.md
  scripts/launchd/de.doktor-steinbeck.lucyng-uat-watchdog.plist
  scripts/uat_run_baseline_opus5.sh
  scripts/uat_watchdog.py
  scripts/render_jcamp_spectra.py
)

# Plus every file the user chose to keep (105-08-SUMMARY.md, "Old-name residue kept by user
# decision"; backticked paths in that section; "None." adds nothing).
KEPT=()
while IFS= read -r p; do
  [ -n "$p" ] && KEPT+=("$p")
done < <(sed -n '/^## Old-name residue kept by user decision/,/^## /p' "$PHASE_DIR/105-08-SUMMARY.md" \
           | grep -oE '`[^`]+`' | tr -d '`' | grep '/' || true)

in_list() {  # in_list <needle> <items...>
  local needle="$1"; shift
  local item
  for item in "$@"; do [ "$item" = "$needle" ] && return 0; done
  return 1
}

# D-13a section extracts (same sed ranges as the owning plans 105-01/03/06).
EX_DIR="$(mktemp -d)"
trap 'rm -rf "$EX_DIR"' EXIT
sed -n '/^## The CASE Agent Team/,/^## Running a CASE Elucidation/p' README.md > "$EX_DIR/readme_team"
sed -n '/^## Evaluation/,/^## Installation/p' README.md > "$EX_DIR/readme_eval"
sed -n '/^## The CASE agent layer/,/^## [^T]/p' docs/ARCHITECTURE.md > "$EX_DIR/arch_agents"
sed -n '/^## How a benchmark run executes/,/^## How blindness is enforced/p' docs/BENCHMARK.md > "$EX_DIR/bench_exec"
sed -n '/SLIDE 4 · AGENT TEAM/,/SLIDE 5/p' docs/infographics/build.py > "$EX_DIR/deck_team"
sed -n '/SLIDE 6 · BENCHMARK/,/SLIDE 7/p' docs/infographics/build.py > "$EX_DIR/deck_bench"

echo "== Phase 105 outside-face gate ($(git rev-parse --short HEAD))"

# ---------------------------------------------------------------------------------------
# 1. Positive control for the old-name grep: a planted "lucy-ng" must be reported.
# ---------------------------------------------------------------------------------------
PC="$(mktemp)"
cp README.md "$PC"
echo "lucy-ng" >> "$PC"
PC_HIT="$(grep -n -i lucy "$PC" | tail -1)"
rm -f "$PC"
if [ -n "$PC_HIT" ] && printf '%s' "$PC_HIT" | grep -q 'lucy-ng'; then
  pass "1  old-name grep positive control fires (planted line reported as '$PC_HIT')"
else
  fail "1  old-name grep positive control did NOT fire on the planted 'lucy-ng'"
fi

# ---------------------------------------------------------------------------------------
# 2. Old name in outside-facing files (plain substring, case-insensitive, deliberately
#    broader than a word-boundary match).
# ---------------------------------------------------------------------------------------
HITS=""
MISSING=""
for f in "${IN_SCOPE[@]}"; do
  if [ ! -f "$f" ]; then
    in_list "$f" "${REMOVED_BY_105_08[@]}" || MISSING="$MISSING $f"
    continue
  fi
  h="$(grep -n -i lucy "$f" | sed "s|^|$f:|")"
  [ -n "$h" ] && HITS="$HITS$h"$'\n'
done
if [ -n "$MISSING" ]; then
  fail "2  in-scope files missing from the tree:$MISSING"
elif [ -n "$HITS" ]; then
  fail "2  old name found in outside-facing files:"
  printf '%s' "$HITS" | detail
else
  pass "2  no old name in the ${#IN_SCOPE[@]} outside-facing files"
fi

# ---------------------------------------------------------------------------------------
# 3. Residue over the whole tracked tree outside .planning/ .claude/ src/ tests/ data/:
#    every file whose content or path contains the old name must be allow-listed.
# ---------------------------------------------------------------------------------------
RES_CONTENT="$(git ls-files -z | grep -z -v -E '^(\.planning/|\.claude/|src/|tests/|data/)' \
               | xargs -0 grep -l -i lucy 2>/dev/null || true)"
RES_PATHS="$(git ls-files | grep -v -E '^(\.planning/|\.claude/|src/|tests/|data/)' | grep -i lucy || true)"
UNEXPECTED=""
while IFS= read -r f; do
  [ -z "$f" ] && continue
  in_list "$f" "${RESIDUE_ALLOW[@]}" && continue
  [ "${#KEPT[@]}" -gt 0 ] && in_list "$f" "${KEPT[@]}" && continue
  UNEXPECTED="$UNEXPECTED $f"
done < <(printf '%s\n%s\n' "$RES_CONTENT" "$RES_PATHS" | sort -u)
if [ -n "$UNEXPECTED" ]; then
  fail "3  old-name residue outside the allow-list:$UNEXPECTED"
else
  n_res="$(printf '%s\n%s\n' "$RES_CONTENT" "$RES_PATHS" | sort -u | grep -c . || true)"
  pass "3  residue only in allow-listed files ($n_res file(s); ${#KEPT[@]} kept by user decision)"
fi

# ---------------------------------------------------------------------------------------
# 4. No MCP content in the user-facing docs (the MCP server was removed in v2.0).
# ---------------------------------------------------------------------------------------
MCP_BAD=""
for f in README.md docs/INSTALLATION.md docs/ARCHITECTURE.md docs/USER_GUIDE.md docs/SERVER_BOOTSTRAP.md; do
  c="$(grep -c -i mcp "$f" || true)"
  [ "$c" != "0" ] && MCP_BAD="$MCP_BAD $f($c)"
done
if [ -n "$MCP_BAD" ]; then fail "4  MCP mentioned in:$MCP_BAD"; else pass "4  no MCP mention in README and the four setup/user docs"; fi

# ---------------------------------------------------------------------------------------
# 5. Links.
#    5a README (the PyPI long description): only absolute https links or #anchors.
#    5b Other docs: every relative target exists relative to the linking file.
#    5c Anchors: #fragments of README-internal and relative links match a heading.
#    5d README links into this repository on GitHub name tracked paths.
# ---------------------------------------------------------------------------------------
LINK_OUT="$(python3 - <<'PY'
import os, re, subprocess, sys

FENCE = re.compile(r'^\s*(```|~~~)')
LINK = re.compile(r'\]\(([^)\s]+)(?:\s+"[^"]*")?\)')
HTML = re.compile(r'(?:href|src)="([^"]+)"')
SIBLING_REPO_ALLOW = {("scripts/faulon-bridge/README.md", "../../../faulon-ng")}
REPO_URL = re.compile(r'^https://github\.com/steinbeck/ailsa/(?:blob|tree)/master/([^#?]+)')

def lines_outside_fences(path):
    out, fenced = [], False
    with open(path, encoding="utf-8") as fh:
        for no, line in enumerate(fh, 1):
            if FENCE.match(line):
                fenced = not fenced
                continue
            if not fenced:
                out.append((no, line))
    return out

def slug(text):
    text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)   # [text](url) -> text
    text = text.replace('`', '').strip().lower()
    text = re.sub(r'[^\w\- ]', '', text)                    # GitHub drops punctuation
    return text.replace(' ', '-')

def anchors(path):
    seen, result = {}, set()
    for _, line in lines_outside_fences(path):
        m = re.match(r'^#{1,6}\s+(.*?)\s*#*\s*$', line)
        if m:
            s = slug(m.group(1))
            n = seen.get(s, 0)
            result.add(s if n == 0 else f"{s}-{n}")
            seen[s] = n + 1
        for a in re.findall(r'<a\s+(?:name|id)="([^"]+)"', line):
            result.add(a)
    return result

def links(path):
    for no, line in lines_outside_fences(path):
        for t in LINK.findall(line) + HTML.findall(line):
            yield no, t.strip('<>')

tracked = set(subprocess.run(["git", "ls-files"], capture_output=True, text=True,
                             check=True).stdout.split("\n"))
tracked_dirs = {os.path.dirname(p) for p in tracked}
for p in list(tracked_dirs):
    while p:
        p = os.path.dirname(p)
        tracked_dirs.add(p)

problems = {"5a": [], "5b": [], "5c": [], "5d": []}
counts = {"5a": 0, "5b": 0, "5c": 0, "5d": 0}

# 5a + 5c (README-internal anchors) + 5d
readme_anchors = anchors("README.md")
for no, t in links("README.md"):
    counts["5a"] += 1
    if t.startswith("#"):
        counts["5c"] += 1
        if t[1:] not in readme_anchors:
            problems["5c"].append(f"README.md:{no}: {t} (no such heading)")
    elif not re.match(r'^https?://', t):
        problems["5a"].append(f"README.md:{no}: {t} (relative link breaks on PyPI)")
    m = REPO_URL.match(t)
    if m:
        counts["5d"] += 1
        p = m.group(1).rstrip("/")
        if p not in tracked and p not in tracked_dirs:
            problems["5d"].append(f"README.md:{no}: {t} ({p} is not a tracked path)")
        frag = t.split("#", 1)[1] if "#" in t else ""
        if frag and p.endswith(".md") and os.path.isfile(p):
            counts["5c"] += 1
            if frag not in anchors(p):
                problems["5c"].append(f"README.md:{no}: {t} (no heading #{frag} in {p})")

# 5b + 5c for relative links in the other docs
import glob
others = ["CLAUDE.md"] + sorted(glob.glob("docs/*.md")) + ["docs/infographics/README.md",
                                                            "scripts/faulon-bridge/README.md"]
for f in others:
    base = os.path.dirname(f)
    for no, t in links(f):
        if re.match(r'^(https?://|mailto:)', t):
            continue
        if t.startswith("#"):
            counts["5c"] += 1
            if t[1:] not in anchors(f):
                problems["5c"].append(f"{f}:{no}: {t} (no such heading)")
            continue
        counts["5b"] += 1
        if (f, t) in SIBLING_REPO_ALLOW:
            continue
        target, _, frag = t.partition("#")
        dest = os.path.normpath(os.path.join(base, target))
        if not os.path.exists(dest):
            problems["5b"].append(f"{f}:{no}: {t} ({dest} does not exist)")
            continue
        if frag and dest.endswith(".md"):
            counts["5c"] += 1
            if frag not in anchors(dest):
                problems["5c"].append(f"{f}:{no}: {t} (no heading #{frag} in {dest})")

labels = {
    "5a": "README links are absolute or #anchors",
    "5b": "relative links in CLAUDE.md, docs/, deck README and faulon-bridge README resolve",
    "5c": "#anchors match a heading in the target file",
    "5d": "README links into github.com/steinbeck/ailsa name tracked paths",
}
for k in ("5a", "5b", "5c", "5d"):
    status = "FAIL" if problems[k] else "PASS"
    print(f"{status}  {k} {labels[k]} ({counts[k]} checked)")
    for p in problems[k]:
        print(f"        {p}")
PY
)"
printf '%s\n' "$LINK_OUT"
n_link_fail="$(printf '%s\n' "$LINK_OUT" | grep -c '^FAIL' || true)"
FAILS=$((FAILS + n_link_fail))

# ---------------------------------------------------------------------------------------
# 6. Deck: deck.html is what build.py produces, 8 slides, counters 01/08..08/08, PDF present,
#    no old name in any deck file name.
# ---------------------------------------------------------------------------------------
if (cd docs/infographics && python3 build.py >/dev/null 2>"$EX_DIR/build.err"); then
  if git diff --quiet -- docs/infographics/deck.html; then
    pass "6a deck.html is in sync with build.py (rebuild changes nothing)"
  else
    fail "6a deck.html differs from a fresh build.py run (rebuilt file left in the working tree)"
    git diff --stat -- docs/infographics/deck.html | detail
  fi
else
  fail "6a build.py failed"
  detail < "$EX_DIR/build.err"
fi
n_slides="$(grep -c '<section class="slide' docs/infographics/deck.html || true)"
counters="$(grep -o '0[0-9] / 0[0-9]' docs/infographics/deck.html | sort -u | tr '\n' ',' )"
want="01 / 08,02 / 08,03 / 08,04 / 08,05 / 08,06 / 08,07 / 08,08 / 08,"
if [ "$n_slides" = "8" ] && [ "$counters" = "$want" ]; then
  pass "6b deck has 8 slides with counters 01/08..08/08"
else
  fail "6b deck: $n_slides slides, counters '$counters'"
fi
if [ -f docs/infographics/ailsa-infographics.pdf ] && git ls-files --error-unmatch docs/infographics/ailsa-infographics.pdf >/dev/null 2>&1; then
  pass "6c ailsa-infographics.pdf exists and is tracked"
else
  fail "6c docs/infographics/ailsa-infographics.pdf missing or untracked"
fi
n_old_deck="$(git ls-files docs/infographics | grep -c -i lucy || true)"
if [ "$n_old_deck" = "0" ]; then pass "6d no deck file name carries the old name"; else fail "6d $n_old_deck deck file name(s) carry the old name"; fi

# ---------------------------------------------------------------------------------------
# 7. figshare record (public API, no credentials): AILSA title, shift-source DOI in the
#    description (D-17), the unchanged data file, the base DOI.
# ---------------------------------------------------------------------------------------
FS_JSON="$EX_DIR/figshare.json"
if curl -s -f -m 30 -o "$FS_JSON" https://api.figshare.com/v2/articles/31073554; then
  FS_OUT="$(python3 - "$FS_JSON" <<'PY'
import json, sys
a = json.load(open(sys.argv[1], encoding="utf-8"))
problems = []
if "AILSA" not in a.get("title", ""):
    problems.append(f"title lacks AILSA: {a.get('title')!r}")
if "10.5281/zenodo.6561449" not in a.get("description", ""):
    problems.append("description lacks the COCONUT shift-source DOI 10.5281/zenodo.6561449")
files = a.get("files") or []
if not files or files[0].get("id") != 61078393:
    problems.append(f"files[0].id is {files[0].get('id') if files else None}, expected 61078393")
if not str(a.get("doi", "")).startswith("10.6084/m9.figshare.31073554"):
    problems.append(f"doi is {a.get('doi')!r}")
if problems:
    print("FAIL|" + "; ".join(problems))
else:
    print(f"PASS|title {a['title']!r}, doi {a['doi']}, file {files[0]['id']} "
          f"({files[0].get('name')}), version {a.get('version')}")
PY
)"
  case "$FS_OUT" in
    PASS\|*) pass "7  figshare: ${FS_OUT#PASS|}" ;;
    *)       fail "7  figshare: ${FS_OUT#FAIL|}" ;;
  esac
else
  fail "7  figshare API not reachable (https://api.figshare.com/v2/articles/31073554)"
fi

# ---------------------------------------------------------------------------------------
# 8. D-05 bookkeeping: the PyPI upload is recorded as deferred until after the repository
#    phase. D-05 named it "Phase 107"; the milestone extension of 2026-10-12 renumbered the
#    repository phase to 111 (ROADMAP.md v11.0), so both records must name Phase 111 and
#    neither may still point at Phase 107.
# ---------------------------------------------------------------------------------------
PKG_LINE="$(grep -F '**PKG-01**' .planning/REQUIREMENTS.md || true)"
UAT=".planning/phases/104-package-and-cli/104-HUMAN-UAT.md"
D05_BAD=""
printf '%s' "$PKG_LINE" | grep -q -E 'after .*Phase 111|now Phase 111' || D05_BAD="$D05_BAD REQUIREMENTS.md PKG-01 does not name Phase 111;"
printf '%s' "$PKG_LINE" | grep -q -F 'after Phase 107' && D05_BAD="$D05_BAD REQUIREMENTS.md PKG-01 still says 'after Phase 107';"
grep -q -F 'after Phase 111' "$UAT" || D05_BAD="$D05_BAD 104-HUMAN-UAT.md does not say 'after Phase 111';"
grep -q -F 'after Phase 107' "$UAT" && D05_BAD="$D05_BAD 104-HUMAN-UAT.md still says 'after Phase 107';"
if [ -n "$D05_BAD" ]; then fail "8  D-05 PyPI deferral:$D05_BAD"; else pass "8  D-05 PyPI upload recorded as deferred until after Phase 111 (REQUIREMENTS.md, 104-HUMAN-UAT.md)"; fi

# ---------------------------------------------------------------------------------------
# 9. Front page: Nuzillard in the first 30 lines, the name's expansion present.
# ---------------------------------------------------------------------------------------
n_nuz="$(head -30 README.md | grep -c Nuzillard || true)"
n_exp="$(grep -c 'AI + LSD + Agents' README.md || true)"
if [ "$n_nuz" -ge 1 ] && [ "$n_exp" -ge 1 ]; then
  pass "9  README front page credits Nuzillard (first 30 lines) and spells out 'AI + LSD + Agents'"
else
  fail "9  README front page: Nuzillard in first 30 lines=$n_nuz, 'AI + LSD + Agents'=$n_exp"
fi

# ---------------------------------------------------------------------------------------
# 10. D-13a wording (grep -F, case-sensitive, on the section extracts).
# ---------------------------------------------------------------------------------------
need_all() {  # need_all <file> <label> <phrase...>; echoes missing phrases
  local f="$1" label="$2"; shift 2
  local p miss=""
  if [ ! -s "$f" ]; then echo " [$label: section extract is empty]"; return; fi
  for p in "$@"; do grep -q -F "$p" "$f" || miss="$miss [$label: '$p']"; done
  printf '%s' "$miss"
}

# 10a Team as the design.
TEAM_PHRASES=("specialists that coordinate with each other" "direct review loop" "ask the NMR chemist")
M="$(need_all "$EX_DIR/readme_team" "README team section" "${TEAM_PHRASES[@]}")"
M="$M$(need_all "$EX_DIR/arch_agents" "ARCHITECTURE agent layer" "${TEAM_PHRASES[@]}")"
M="$M$(need_all "$EX_DIR/deck_team" "deck slide 4" "${TEAM_PHRASES[@]}")"
grep -q -F "specialists that coordinate with each other" CLAUDE.md || M="$M [CLAUDE.md: 'specialists that coordinate with each other']"
for p in "hub-and-spoke" "one at a time" "specialists the coordinator spawns"; do
  grep -q -i -F "$p" CLAUDE.md && M="$M [CLAUDE.md must not contain '$p']"
done
if [ -n "$M" ]; then fail "10a team as the design, missing/forbidden:$M"; else pass "10a team as the design: README team section, ARCHITECTURE agent layer, deck slide 4 and CLAUDE.md"; fi

# 10b Restricted configuration wherever the 69 % appear.
RC_PHRASES=("restricted configuration" "without the agent team" "without statistical detection")
M="$(need_all "$EX_DIR/readme_eval" "README Evaluation" "${RC_PHRASES[@]}")"
M="$M$(need_all "$EX_DIR/bench_exec" "BENCHMARK execution section" "${RC_PHRASES[@]}")"
M="$M$(need_all "$EX_DIR/deck_bench" "deck slide 6" "${RC_PHRASES[@]}")"
n_rc="$(grep -o -F 'restricted configuration' "$EX_DIR/deck_bench" | wc -l | tr -d ' ')"
[ "$n_rc" = "1" ] || M="$M [deck slide 6: 'restricted configuration' occurs $n_rc times, expected exactly 1]"
for f in README.md CLAUDE.md docs/*.md docs/infographics/build.py docs/infographics/README.md; do
  if grep -q -F '69.1' "$f" && ! grep -q -F 'restricted configuration' "$f"; then
    M="$M [$f quotes 69.1 without 'restricted configuration']"
  fi
done
if [ -n "$M" ]; then fail "10b restricted configuration next to the 69 %, missing:$M"; else pass "10b restricted configuration stated in README Evaluation, BENCHMARK execution section, deck slide 6 (once) and every file quoting 69.1"; fi

# 10c Setup docs.
M=""
for f in docs/INSTALLATION.md docs/SERVER_BOOTSTRAP.md; do
  M="$M$(need_all "$f" "$f" "do not form a team" "current schema")"
done
if [ -n "$M" ]; then fail "10c setup docs, missing:$M"; else pass "10c INSTALLATION and SERVER_BOOTSTRAP state 'do not form a team' and 'current schema'"; fi

# 10d Hub-and-spoke only as the description of how benchmark runs executed.
HS_FILES=""
for f in "${IN_SCOPE[@]}"; do
  [ -f "$f" ] && grep -q -i 'hub-and-spoke' "$f" && HS_FILES="$HS_FILES $f"
done
M=""
for f in $HS_FILES; do [ "$f" = "docs/BENCHMARK.md" ] || M="$M [$f]"; done
n_hs_all="$(grep -o -i 'hub-and-spoke' docs/BENCHMARK.md | wc -l | tr -d ' ')"
n_hs_sec="$(grep -o -i 'hub-and-spoke' "$EX_DIR/bench_exec" | wc -l | tr -d ' ')"
[ "$n_hs_all" = "$n_hs_sec" ] || M="$M [docs/BENCHMARK.md: $n_hs_all matches in the file, $n_hs_sec inside 'How a benchmark run executes']"
if [ -n "$M" ]; then fail "10d hub-and-spoke outside the benchmark execution section:$M"; else pass "10d hub-and-spoke confined to BENCHMARK 'How a benchmark run executes' ($n_hs_sec of $n_hs_all matches inside)"; fi

# ---------------------------------------------------------------------------------------
# 11. No claim that the full system performs better than the benchmark figure.
# ---------------------------------------------------------------------------------------
BETTER='(would|could|should|will|likely) (perform|score|do|solve)[a-z]* (even )?(better|higher|more)|perform(s|ed)? (even )?better|higher with the (agent )?team|(full|complete) (system|team|configuration) (achieves|scores|would|performs|solves)|better with the (agent )?team|lower bound|underestimat|conservative estimate'
PC="$(mktemp)"
cp README.md "$PC"
echo "With the agent team the full system achieves a higher rate." >> "$PC"
PC_HIT="$(grep -n -i -E "$BETTER" "$PC" | tail -1)"
rm -f "$PC"
if printf '%s' "$PC_HIT" | grep -q 'full system achieves'; then
  pass "11a no-better-claim positive control fires (planted line reported as '$PC_HIT')"
else
  fail "11a no-better-claim positive control did NOT fire on the planted sentence"
fi
BC_HITS="$(grep -n -i -E "$BETTER" README.md docs/BENCHMARK.md docs/ARCHITECTURE.md docs/infographics/build.py docs/infographics/deck.html || true)"
if [ -n "$BC_HITS" ]; then
  fail "11b better-than-benchmark claim found:"
  printf '%s\n' "$BC_HITS" | detail
else
  pass "11b no claim that the full system performs better (README, BENCHMARK, ARCHITECTURE, build.py, deck.html)"
fi

# ---------------------------------------------------------------------------------------
# 12. D-17: the COCONUT 13C shift-source DOI in every file that describes the reference DB.
# ---------------------------------------------------------------------------------------
D17_FILES=(
  README.md
  CLAUDE.md
  docs/INSTALLATION.md
  docs/ARCHITECTURE.md
  docs/USER_GUIDE.md
  docs/SERVER_BOOTSTRAP.md
  rdmo-project-description.txt
  scripts/figshare_upload.py
  scripts/zenodo_upload.py
  docs/infographics/build.py
  docs/infographics/deck.html
)
M=""
for f in "${D17_FILES[@]}"; do
  c="$(grep -c -F '10.5281/zenodo.6561449' "$f" 2>/dev/null || true)"
  [ "${c:-0}" -ge 1 ] || M="$M $f"
done
if [ -n "$M" ]; then fail "12 shift-source DOI 10.5281/zenodo.6561449 missing in:$M"; else pass "12 shift-source DOI 10.5281/zenodo.6561449 in all ${#D17_FILES[@]} files that describe the reference DB"; fi

echo "== $FAILS failing check(s)"
[ "$FAILS" -eq 0 ]
