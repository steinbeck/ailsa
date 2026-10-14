#!/usr/bin/env python3
"""Phase 105 gate, part 2: audit every `ailsa ...` example in the docs against the live CLI (D-14).

For each `ailsa` invocation found in a fenced code block or an inline code span of
README.md, CLAUDE.md, docs/*.md and docs/infographics/README.md, the script

  1. walks the tokens down the command tree as far as they name real subcommands
     (`ailsa <path> --help`; a group's help lists its subcommands under "Commands:"),
  2. reports a token that sits where a subcommand is expected but is not one,
  3. reports every -x / --long option that the resolved command's --help does not list.

Usage:
  python3 105-check-cli-examples.py            # scan the default doc set
  python3 105-check-cli-examples.py FILE...    # scan only the given files (positive control)

Environment: AILSA_BIN overrides the `ailsa` executable found on PATH.
Stdlib only. Exits 1 if any problem is found or no invocation was checked, 2 on setup errors.
"""
from __future__ import annotations

import glob
import os
import re
import shlex
import shutil
import subprocess
import sys

ROOT = subprocess.run(
    ["git", "-C", os.path.dirname(os.path.abspath(__file__)), "rev-parse", "--show-toplevel"],
    capture_output=True, text=True, check=True,
).stdout.strip()

DEFAULT_FILES = (
    ["README.md", "CLAUDE.md"]
    + sorted(os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, "docs", "*.md")))
    + ["docs/infographics/README.md"]
)

FENCE = re.compile(r"^\s*(```|~~~)")
SPAN = re.compile(r"`([^`\n]+)`")
CONTROL = {"&&", "||", ";", "|", "(", ")", "&", "$("}
REDIRECT = {">", ">>", "<", "2>", "&>"}
# Tokens that stand for an argument in a synopsis or prose example, not a literal word.
PLACEHOLDER = re.compile(r"^(\[.*\]|<.*>|\.\.\.|…|[A-Z][A-Z0-9_]*)$|…")

AILSA = os.environ.get("AILSA_BIN") or shutil.which("ailsa")
if not AILSA:
    print("SETUP  no `ailsa` executable on PATH (set AILSA_BIN)", file=sys.stderr)
    sys.exit(2)

_help_cache: dict[tuple[str, ...], tuple[int, str]] = {}


def cli_help(path: tuple[str, ...]) -> tuple[int, str]:
    """Return (exit code, help text) of `ailsa <path> --help`, cached."""
    if path not in _help_cache:
        proc = subprocess.run(
            [AILSA, *path, "--help"], capture_output=True, text=True, cwd=ROOT, timeout=120,
        )
        _help_cache[path] = (proc.returncode, proc.stdout + proc.stderr)
    return _help_cache[path]


def subcommands(text: str) -> set[str] | None:
    """Subcommands listed in the Click-generated 'Commands:' section, or None for a leaf.

    The top-level docstring carries its own hand-written 'Commands:' list; the last
    section is the one Click generates from the registered commands.
    """
    lines = text.splitlines()
    starts = [i for i, ln in enumerate(lines) if ln.strip() == "Commands:"]
    if not starts:
        return None
    names = set()
    for ln in lines[starts[-1] + 1:]:
        if ln.strip() and not ln.startswith(" "):
            break
        m = re.match(r"^\s{2,}([a-z0-9][\w-]*)(\s|$)", ln)
        if m:
            names.add(m.group(1))
    return names


def tokenize(cmd: str) -> list[str]:
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    try:
        return list(lex)
    except ValueError:  # unbalanced quotes in a prose span
        return cmd.split()


def invocations(cmd: str) -> list[list[str]]:
    """Split a shell line into simple commands; return those that start with `ailsa`."""
    out, cur, skip_next = [], [], False
    for tok in tokenize(cmd):
        if skip_next:
            skip_next = False
            continue
        if tok in CONTROL:
            out.append(cur)
            cur = []
            continue
        if tok in REDIRECT or re.fullmatch(r"\d?>>?", tok):
            skip_next = True
            continue
        cur.append(tok)
    out.append(cur)
    result = []
    for seg in out:
        if seg and seg[0] == "$":
            seg = seg[1:]
        if seg and seg[0] == "ailsa":
            result.append(seg)
    return result


def candidates(path: str) -> list[tuple[int, str, list[str]]]:
    """(line number, source text, tokens) for every ailsa invocation in a markdown file."""
    found = []
    with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    fenced, pending, pending_no = False, "", 0
    for no, line in enumerate(lines, 1):
        if FENCE.match(line):
            fenced = not fenced
            pending = ""
            continue
        if fenced:
            text = line.strip()
            if pending:
                text, no_ = pending + " " + text, pending_no
            else:
                no_ = no
            if text.endswith("\\"):
                pending, pending_no = text[:-1], no_
                continue
            pending = ""
            for inv in invocations(text):
                found.append((no_, text, inv))
        else:
            for span in SPAN.findall(line):
                s = span.strip()
                if s.startswith("$ "):
                    s = s[2:].lstrip()
                if not s.startswith("ailsa "):
                    continue  # `ailsa`, `ailsa-*` agents, `/ailsa:*`, `src/ailsa`, imports
                for inv in invocations(s):
                    found.append((no, s, inv))
    return found


def is_option(tok: str) -> bool:
    return tok.startswith("-") and tok not in {"-", "--"} and not re.match(r"^-\d", tok)


def audit(path: str) -> tuple[int, list[str]]:
    checked, problems = 0, []
    for no, text, toks in candidates(path):
        checked += 1
        args = toks[1:]
        cmd: list[str] = []
        rc, text_help = cli_help(())
        if rc != 0:
            problems.append(f"{path}:{no}: `{text}` -> `ailsa --help` exits {rc}")
            continue
        i = 0
        while i < len(args):
            subs = subcommands(text_help)
            tok = args[i]
            if subs is None or is_option(tok):
                break
            if tok in subs:
                cmd.append(tok)
                rc, text_help = cli_help(tuple(cmd))
                if rc != 0:
                    problems.append(f"{path}:{no}: `{text}` -> `ailsa {' '.join(cmd)} --help` exits {rc}")
                    break
                i += 1
                continue
            if not PLACEHOLDER.search(tok):
                where = "ailsa " + " ".join(cmd) if cmd else "ailsa"
                problems.append(
                    f"{path}:{no}: `{text}` -> '{tok}' is not a subcommand of `{where.strip()}` "
                    f"(has: {', '.join(sorted(subs))})"
                )
            break
        resolved = "ailsa " + " ".join(cmd) if cmd else "ailsa"
        for tok in args:
            if not is_option(tok):
                continue
            opt = tok.split("=", 1)[0]
            if not re.search(r"(?<![\w-])" + re.escape(opt) + r"(?![\w-])", text_help):
                problems.append(
                    f"{path}:{no}: `{text}` -> option {opt} is not listed by `{resolved.strip()} --help`"
                )
    return checked, problems


def main(argv: list[str]) -> int:
    files = argv or DEFAULT_FILES
    total, all_problems = 0, []
    for f in files:
        rel = os.path.relpath(os.path.abspath(f), ROOT) if os.path.isabs(f) or os.path.exists(f) else f
        if not os.path.isfile(os.path.join(ROOT, rel)):
            print(f"SETUP  {f}: no such file", file=sys.stderr)
            return 2
        n, probs = audit(rel)
        total += n
        all_problems += probs
        print(f"       {rel}: {n} invocation(s)")
    for p in all_problems:
        print(f"PROBLEM {p}")
    print(f"== {total} ailsa invocation(s) checked against `{AILSA} ... --help` "
          f"({len(_help_cache)} help texts); {len(all_problems)} problem(s)")
    if total == 0:
        print("FAIL  no invocation found - the scanner is broken")
        return 1
    print("PASS" if not all_problems else "FAIL")
    return 0 if not all_problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
