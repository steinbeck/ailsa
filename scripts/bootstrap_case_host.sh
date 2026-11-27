#!/usr/bin/env bash
#
# bootstrap_case_host.sh — provision a headless host (e.g. sheldon) to run the
# full autonomous CASE skill `/ailsa:case`. See docs/SERVER_BOOTSTRAP.md.
#
# Idempotent + fail-loud. Run from INSIDE a cloned ailsa checkout:
#   git clone https://github.com/steinbeck/ailsa.git && cd ailsa
#   bash scripts/bootstrap_case_host.sh
#
# The LSD solver (step 2) is an external download whose archive name/version
# changes; if it is not already on PATH this script stops and tells you what to
# do — `ailsa lsd check` is the authoritative gate either way.
#
set -euo pipefail

PY_VERSION="${LUCY_PY_VERSION:-3.12}"
LSD_URL="${LUCY_LSD_URL:-}"   # optional: full URL to an LSD-X.Y.Z.tar.gz to auto-fetch
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

say() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33mWARN: %s\033[0m\n' "$*" >&2; }
die() { printf '\033[1;31mFATAL: %s\033[0m\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------------------
say "1/6  Python ${PY_VERSION} + ailsa (uv, reproducible from uv.lock)"
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
uv python install "$PY_VERSION"
uv sync                                   # creates .venv from uv.lock
# shellcheck disable=SC1091
source .venv/bin/activate
say "1b   hose-code-generator (13C prediction; --no-deps avoids the 3.12 xmlrunner break)"
uv pip install "git+https://github.com/Ratsemaat/HOSE_code_generator.git" --no-deps

say "1c   expose ailsa on PATH for CASE runs (which start outside this repo)"
# A CASE run starts from an NMR data dir OUTSIDE this repo with the venv NOT
# activated, so `ailsa` must be reachable without activation. ~/.local/bin is on
# PATH by default on Linux, and the venv console-script has an absolute shebang,
# so a plain symlink works without sourcing the venv.
mkdir -p "$HOME/.local/bin"
ln -sfn "$REPO/.venv/bin/ailsa" "$HOME/.local/bin/ailsa"

# ---------------------------------------------------------------------------
say "2/6  LSD solver (LSD + outlsd on PATH)"
if ailsa lsd check 2>/dev/null | grep -qi "outlsd: available"; then
  echo "LSD + outlsd already available."
elif [ -n "$LSD_URL" ]; then
  mkdir -p "$HOME/opt"; ( cd "$HOME/opt"
    curl -fSL "$LSD_URL" -o lsd.tar.gz && tar -xzf lsd.tar.gz
    d="$(find . -maxdepth 1 -type d -iname 'LSD*' | head -1)"
    [ -n "$d" ] || die "extracted LSD dir not found"
    ( cd "$d" && make 2>/dev/null || true )
    bindir="$HOME/opt/$d/bin"; [ -d "$bindir" ] || bindir="$HOME/opt/$d"
    grep -q "$bindir" ~/.bashrc 2>/dev/null || echo "export PATH=\"$bindir:\$PATH\"" >> ~/.bashrc
    export PATH="$bindir:$PATH" )
else
  warn "LSD not on PATH and no LUCY_LSD_URL given."
  warn "Download from http://eos.univ-reims.fr/LSD/, extract, put LSD+outlsd on PATH,"
  warn "then re-run (or set LUCY_LSD_URL=<archive-url> and re-run). Continuing — the"
  warn "verify step will fail until LSD is present."
fi

# Mirror the LSD binaries into ~/.local/bin so they are found from any CASE
# data dir. The ~/.bashrc PATH entry above only applies to interactive shells;
# CASE runs in non-interactive ones where ~/.bashrc may early-return.
for b in lsd outlsd genpos mol2ab; do
  p="$(command -v "$b" 2>/dev/null || true)"
  [ -n "$p" ] && ln -sfn "$p" "$HOME/.local/bin/$b"
done

# ---------------------------------------------------------------------------
say "3/6  Reference database (pre-built SQLite from Figshare)"
DB="data/reference/ailsa-derep.db"
if [ -f "$DB" ]; then
  echo "DB already present: $DB"
else
  mkdir -p data/reference
  ailsa database download -o "$DB"
fi
ailsa database info "$DB" || warn "ailsa database info failed — verify the DB download."

# Make the DB discoverable from any CWD: DatabaseFinder checks ~/.lucy/ (step 3
# of its search order) regardless of the working directory. Without this, a CASE
# run from a data dir silently falls back to a tiny bundled HOSE table
# (~11 matches) instead of the full 928k-compound DB.
mkdir -p "$HOME/.lucy"
ln -sfn "$REPO/$DB" "$HOME/.lucy/ailsa-derep.db"

# ---------------------------------------------------------------------------
say "4/6  CASE skill: install the packaged skill (commands + team agents) into ~/.claude"
AILSA="$REPO/.venv/bin/ailsa"
"$AILSA" skill install ailsa --target claude --link   # ailsa skill install ailsa

# ---------------------------------------------------------------------------
say "5/6  Enable agent teams"
if ! grep -q "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1" ~/.bashrc 2>/dev/null; then
  echo 'export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1' >> ~/.bashrc
fi
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1

# ---------------------------------------------------------------------------
say "6/6  Verify the CASE prerequisite chain (the gates case.md checks)"
ok=1
[ "${CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS:-}" = "1" ] && echo "  [ok] AGENT_TEAMS=1" || { echo "  [FAIL] AGENT_TEAMS"; ok=0; }
ailsa --version >/dev/null 2>&1 && echo "  [ok] ailsa CLI" || { echo "  [FAIL] ailsa CLI"; ok=0; }
ailsa lsd check 2>/dev/null | grep -qi "outlsd: available" && echo "  [ok] LSD + outlsd" || { echo "  [FAIL] LSD/outlsd"; ok=0; }
ailsa predict c13 "CCO" --format json >/dev/null 2>&1 && echo "  [ok] predict c13 (DB + hosegen)" || { echo "  [FAIL] predict c13"; ok=0; }
# Discoverability from a data dir (CASE runs start outside this repo):
[ -e "$HOME/.local/bin/ailsa" ] && echo "  [ok] ailsa on ~/.local/bin" || { echo "  [FAIL] ~/.local/bin/ailsa missing"; ok=0; }
[ -e "$HOME/.local/bin/outlsd" ] && echo "  [ok] outlsd on ~/.local/bin" || { echo "  [FAIL] ~/.local/bin/outlsd missing"; ok=0; }
( cd /tmp && ailsa predict c13 "CCO" --format json >/dev/null 2>&1 ) && echo "  [ok] DB found from any dir (~/.lucy)" || { echo "  [FAIL] DB not found outside repo (~/.lucy/ailsa-derep.db)"; ok=0; }

if [ "$ok" = "1" ]; then
  say "DONE — host is CASE-capable. Next: a smoke CASE in a fresh Claude Code session:"
  echo "  cd data/Ibuprofen && claude   # then type:  /ailsa:case . C13H18O2"
else
  die "One or more prerequisites failed (see [FAIL] above). Fix and re-run — this script is idempotent."
fi
