#!/usr/bin/env python3
"""Rule inventory for the skill restructure (phase 106, decision D-06).

Maps every rule unit of the old skill files (a git revision, default the tag
``frontier-skill-pre-106``) to its best match in the restructured skill tree and
reports rules that were lost, plus emphasis rules without a recorded rationale.

The inventory carries the OLD skill text, which may contain benchmark identities,
so it is written only OUTSIDE the work tree (``$AILSA_RULE_INVENTORY_DIR``, default
``~/Dropbox/develop/data/skill-rule-inventory-106``). The script refuses an output
folder inside the repository (exit 2). This file contains no skill text.

Commands:
  build  segment old and new files, match, write inventory.tsv and pairs.tsv
  todo   append a reasons template for the emphasis units of one old file
  check  print counts and unresolved items (ids, locations, hints; never text)
"""
# ruff: noqa: E501
from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BASELINE = "frontier-skill-pre-106"
DEFAULT_OUT = "~/Dropbox/develop/data/skill-rule-inventory-106"
OLD_ROOTS = (".claude/commands/lucy-ng", ".claude/agents")
EXCLUDED_OLD = ("supervisor.md",)
NEW_DEFAULT = "src/ailsa/skills/ailsa"

# Matching thresholds. A unit at or above SAME_AT is carried over (same); between
# REWORDED_AT and SAME_AT it is reworded; below REWORDED_AT it counts as LOST.
# CONTAIN_FACTOR discounts "old tokens all found in the new unit plus its two
# successors" (a rule split over several new lines) against plain Jaccard.
SAME_AT = 0.85
REWORDED_AT = 0.45
CONTAIN_FACTOR = 0.95

EMPHASIS_WORDS = (
    "must", "never", "always", "mandatory", "binding", "important", "required",
    "forbidden", "critical", "only", "exactly", "verbatim", "absolute",
)
NORMATIVE_WORDS = (
    "must", "never", "always", "do not", "only", "required", "mandatory",
    "binding", "critical", "stop", "before", "after", "if",
)
STOPWORDS = set(EMPHASIS_WORDS) | {
    "the", "and", "for", "are", "was", "with", "that", "this", "from", "have",
    "has", "can", "will", "its", "you", "your", "all", "any", "but", "than",
    "then", "into", "per", "via", "also", "each", "when", "which", "they",
    "them", "their", "off", "out", "use", "used", "using",
    "is", "it", "of", "to", "in", "on", "at", "as", "by", "be", "or", "an", "if",
}

EMPH_RE = re.compile(r"\b(" + "|".join(EMPHASIS_WORDS) + r")\b", re.I)
NORM_RE = re.compile(r"\b(" + "|".join(NORMATIVE_WORDS) + r")\b", re.I)
NEG_RE = re.compile(r"\b(never|not|no|without)\b|n't\b")
LIST_RE = re.compile(r"^(\s*)([-*]|\d+[.)])\s+")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
HEAD_RE = re.compile(r"^\s{0,3}#{1,6}\s")
SEP_RE = re.compile(r"^\s*\|?[\s:|-]*-[\s:|-]*\|?\s*$")

HINT_PATTERNS = (
    ("D01", re.compile(r"\bclaude-[a-z0-9][\w.\-\[\]]*|MODEL MISMATCH|\b(?:opus|sonnet|haiku)[ -]?\d", re.I)),
    ("D03", re.compile(r"CASE\d+")),
    ("history", re.compile(r"\bphase \d+|\b\d{4}-\d{2}-\d{2}\b|\b[A-Z]{2,}-\d+[a-z]?\b|\bbug \d|\bUAT\b", re.I)),
    ("deadref", re.compile(r"\bskill/|SKILL\.md")),
)
VERDICTS = {
    "found", "dropped-D01", "dropped-D03", "dropped-history", "dropped-deadref",
    "merged-duplicate", "restored",
}

RENAMES = (
    (r"~/\.claude/commands/lucy-ng/references/", "~/.claude/ailsa/references/"),
    (r"\blucy(?:-ng)?\b", "ailsa"),
    (r"\blucy-", "ailsa-"),
    (r"\borchestrator\b", "coordinator"),
    (r"\bdevils?[- ]advocate\b", "devil's advocate"),
    (r"\bnmr-chemist\b", "nmr chemist"),
    (r"\blsd-engineer\b", "lsd engineer"),
    (r"\bsolution-analyst\b", "solution analyst"),
)


@dataclass
class Unit:
    file: str
    start: int
    end: int
    kind: str  # list | table | sentence | code
    text: str
    norm: str = ""
    tokens: frozenset = frozenset()
    uid: str = ""


def normalise(text: str) -> str:
    t = text.lower().replace("`", "").replace("*", "")
    for pat, rep in RENAMES:
        t = re.sub(pat, rep, t)
    return re.sub(r"\s+", " ", t).strip()


def tokenize(norm: str) -> frozenset:
    return frozenset(w for w in re.findall(r"\w+", norm) if len(w) >= 2 and w not in STOPWORDS)


def segment(rel: str, text: str) -> list[Unit]:
    lines = text.splitlines()
    i = 0
    if lines and lines[0].strip() == "---":
        j = 1
        while j < len(lines) and lines[j].strip() != "---":
            j += 1
        i = j + 1
    units: list[Unit] = []
    para: list[tuple[int, str]] = []

    def flush() -> None:
        nonlocal para
        if para:
            joined = ""
            offs = []
            for ln, s in para:
                offs.append((len(joined), ln))
                joined += s.strip() + " "
            pos = 0
            for sent in re.split(r"(?<=[.!?])\s+(?=[A-Z`*\"(\[])", joined):
                at = joined.find(sent, pos)
                pos = at + len(sent)
                if not sent.strip() or not NORM_RE.search(sent):
                    continue
                s_line = max((ln for off, ln in offs if off <= at), default=para[0][0])
                e_line = max((ln for off, ln in offs if off <= pos - 1), default=s_line)
                units.append(Unit(rel, s_line, e_line, "sentence", sent.strip()))
            para = []

    n = len(lines)
    while i < n:
        line = lines[i]
        if not line.strip():
            flush()
            i += 1
        elif FENCE_RE.match(line):
            flush()
            fence = FENCE_RE.match(line).group(1)
            j = i + 1
            while j < n and not lines[j].lstrip().startswith(fence):
                j += 1
            body = "\n".join(lines[i + 1 : j])
            if body.strip():
                units.append(Unit(rel, i + 1, min(j + 1, n), "code", body))
            i = j + 1
        elif HEAD_RE.match(line) or re.match(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$", line):
            flush()
            i += 1
        elif line.lstrip().startswith("|"):
            flush()
            if not SEP_RE.match(line):
                units.append(Unit(rel, i + 1, i + 1, "table", line.strip()))
            i += 1
        elif LIST_RE.match(line):
            flush()
            j = i + 1
            while (
                j < n and lines[j].strip() and lines[j][:1].isspace()
                and not LIST_RE.match(lines[j]) and not FENCE_RE.match(lines[j])
            ):
                j += 1
            body = " ".join(s.strip() for s in lines[i:j])
            units.append(Unit(rel, i + 1, j, "list", LIST_RE.sub("", body, count=1)))
            i = j
        else:
            para.append((i + 1, line.lstrip("> ").rstrip() if line.lstrip().startswith(">") else line))
            i += 1
    flush()
    return units


def assign_ids(units: list[Unit], key: str) -> None:
    seen: dict[str, int] = {}
    for u in units:
        u.norm = normalise(u.text)
        u.tokens = tokenize(u.norm)
        base = f"{key}:{hashlib.sha1(u.norm.encode()).hexdigest()[:10]}"
        seen[base] = seen.get(base, 0) + 1
        u.uid = base if seen[base] == 1 else f"{base}-{seen[base]}"


def hints(u: Unit) -> list[str]:
    out = [name for name, rx in HINT_PATTERNS if rx.search(u.text)]
    if u.kind != "code" and EMPH_RE.search(u.text):
        out.append("emphasis")
    return out


def match_all(old: list[Unit], new: list[Unit]):
    """Return {old uid: (score, new unit or None)}."""
    post: dict[str, list[int]] = {}
    by_file: dict[str, list[int]] = {}
    for idx, u in enumerate(new):
        by_file.setdefault(u.file, []).append(idx)
        for t in u.tokens:
            post.setdefault(t, []).append(idx)
    window: dict[int, frozenset] = {}
    for idxs in by_file.values():
        for pos, idx in enumerate(idxs):
            w = set(new[idx].tokens)
            for k in (1, 2):
                if pos + k < len(idxs):
                    w |= new[idxs[pos + k]].tokens
            window[idx] = frozenset(w)
    result = {}
    exact = {}
    for idx, u in enumerate(new):
        exact.setdefault((u.kind == "code", u.norm), idx)
    for o in old:
        best, best_idx = 0.0, None
        if not o.tokens:
            hit = exact.get((o.kind == "code", o.norm))
            result[o.uid] = (1.0, new[hit]) if hit is not None else (0.0, None)
            continue
        cands: set[int] = set()
        for t in o.tokens:
            for j in post.get(t, ()):
                cands.update((j - 2, j - 1, j))
        for i in cands:
            if i < 0 or i >= len(new):
                continue
            n = new[i]
            if o.kind == "code" and n.kind != "code":
                continue
            inter = len(o.tokens & n.tokens)
            jac = inter / len(o.tokens | n.tokens) if n.tokens else 0.0
            cont = CONTAIN_FACTOR * len(o.tokens & window[i]) / len(o.tokens)
            s = max(jac, cont)
            if s > best:
                best, best_idx = s, i
        result[o.uid] = (best, new[best_idx] if best_idx is not None else None)
    return result


def status_of(score: float, o: Unit, n: Unit | None) -> tuple[str, list[str]]:
    st = "same" if score >= SAME_AT else "reworded" if score >= REWORDED_AT else "LOST"
    extra: list[str] = []
    if st != "LOST" and n is not None and NEG_RE.search(o.norm) and not NEG_RE.search(n.norm):
        extra.append("negation?")
        st = "reworded"
    return st, extra


def repo_root() -> Path:
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    return Path(r.stdout.strip()) if r.returncode == 0 else Path.cwd()


def resolve_out(arg: str | None) -> Path:
    out = Path(arg or os.environ.get("AILSA_RULE_INVENTORY_DIR") or DEFAULT_OUT).expanduser().resolve()
    root = repo_root().resolve()
    if out == root or root in out.parents:
        print(f"refusing --out inside the work tree: {out}", file=sys.stderr)
        sys.exit(2)
    return out


def git(*args: str) -> str:
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"git {' '.join(args)} failed: {r.stderr.strip()}", file=sys.stderr)
        sys.exit(2)
    return r.stdout


def load_old(args) -> tuple[dict[str, str], list[str]]:
    files: dict[str, str] = {}
    excluded: list[str] = []
    if args.old_dir:
        base = Path(args.old_dir)
        for p in sorted(base.rglob("*.md")):
            rel = p.relative_to(base).as_posix()
            if p.name in EXCLUDED_OLD:
                excluded.append(rel)
            else:
                files[rel] = p.read_text(encoding="utf-8")
    else:
        names = git("ls-tree", "-r", "--name-only", args.baseline, "--", *OLD_ROOTS).splitlines()
        for rel in sorted(names):
            if not rel.endswith(".md"):
                continue
            if Path(rel).name in EXCLUDED_OLD:
                excluded.append(rel)
                continue
            files[rel] = git("show", f"{args.baseline}:{rel}")
    return files, excluded


def load_new(new_dir: Path) -> list[Unit]:
    if not new_dir.is_dir():
        print(f"new tree not found: {new_dir}", file=sys.stderr)
        sys.exit(2)
    units: list[Unit] = []
    for p in sorted(new_dir.rglob("*.md")):
        if p.name == "CHANGELOG.md":
            continue
        units += segment(p.relative_to(new_dir).as_posix(), p.read_text(encoding="utf-8"))
    for u in units:
        u.norm = normalise(u.text)
        u.tokens = tokenize(u.norm)
    return units


def file_keys(rels: list[str]) -> dict[str, str]:
    stems: dict[str, list[str]] = {}
    for r in rels:
        stems.setdefault(Path(r).stem, []).append(r)
    return {
        r: (Path(r).stem if len(stems[Path(r).stem]) == 1 else r.replace("/", "-").removesuffix(".md"))
        for r in rels
    }


def flat(s: str) -> str:
    return s.replace("\t", " ").replace("\r", "").replace("\n", "\\n")


def lines_str(u: Unit) -> str:
    return str(u.start) if u.start == u.end else f"{u.start}-{u.end}"


def write_tsv(path: Path, header: list[str], rows: list[list[str]], comment: str = "") -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        if comment:
            f.write(comment + "\n")
        w = csv.writer(f, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_NONE, escapechar="\\")
        w.writerow(header)
        w.writerows(rows)


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        lines = [ln for ln in f if not ln.startswith("#")]
    return list(csv.DictReader(lines, delimiter="\t", quoting=csv.QUOTE_NONE, escapechar="\\"))


def cmd_build(args) -> int:
    out = resolve_out(args.out)
    new_dir = Path(args.new_dir or repo_root() / NEW_DEFAULT)
    files, excluded = load_old(args)
    keys = file_keys(list(files))
    old: list[Unit] = []
    for rel, text in files.items():
        us = segment(rel, text)
        assign_ids(us, keys[rel])
        old += us
    new = load_new(new_dir)
    res = match_all(old, new)
    out.mkdir(parents=True, exist_ok=True)
    inv, pairs = [], []
    for o in old:
        score, n = res[o.uid]
        st, extra = status_of(score, o, n)
        hs = ",".join(hints(o) + extra)
        emph = "yes" if o.kind != "code" and EMPH_RE.search(o.text) else "no"
        inv.append([
            o.uid, o.file, lines_str(o), o.kind, emph, hs,
            n.file if n else "", lines_str(n) if n else "", f"{score:.2f}", st,
        ])
        pairs.append([o.uid, st, flat(o.text), flat(n.text) if n else ""])
    write_tsv(
        out / "inventory.tsv",
        ["id", "old_file", "old_lines", "kind", "emphasis", "hint", "new_file", "new_lines", "score", "status"],
        inv,
        comment="# excluded old files: " + (", ".join(excluded) or "none"),
    )
    write_tsv(out / "pairs.tsv", ["id", "status", "old_text", "new_text"], pairs)
    counts: dict[str, int] = {}
    for r in inv:
        counts[r[-1]] = counts.get(r[-1], 0) + 1
    print(f"{len(old)} old units from {len(files)} files -> {out}")
    print("counts: " + ", ".join(f"{k} {counts.get(k, 0)}" for k in ("same", "reworded", "LOST")))
    return 0


def cmd_todo(args) -> int:
    out = resolve_out(args.out)
    inv = [r for r in read_tsv(out / "inventory.tsv") if r["old_file"] == args.file and r["emphasis"] == "yes"]
    if not inv:
        print(f"no emphasis units for {args.file} (run build first?)")
        return 0
    key = inv[0]["id"].split(":")[0]
    path = out / f"reasons-{key}.tsv"
    have = {r["id"] for r in read_tsv(path)}
    texts = {r["id"]: r["old_text"] for r in read_tsv(out / "pairs.tsv")}
    header = ["id", "old_lines", "summary", "reason_known", "reason"]
    new_rows = [
        [r["id"], r["old_lines"], flat(texts.get(r["id"], ""))[:100], "", ""]
        for r in inv if r["id"] not in have
    ]
    if not path.exists():
        write_tsv(path, header, new_rows)
    elif new_rows:
        with path.open("a", encoding="utf-8", newline="") as f:
            csv.writer(f, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_NONE, escapechar="\\").writerows(new_rows)
    print(f"{len(new_rows)} rows added to {path.name}")
    return 0


def cmd_check(args) -> int:
    out = resolve_out(args.out)
    inv = read_tsv(out / "inventory.tsv")
    if not inv:
        print("no inventory.tsv - run build first", file=sys.stderr)
        return 2
    if args.files:
        inv = [r for r in inv if r["old_file"] in set(args.files)]
    verdicts = {r["id"]: r["verdict"] for r in read_tsv(out / "verdicts.tsv")}
    meaning = {r["id"]: r["verdict"] for r in read_tsv(out / "meaning.tsv")}
    reasons: dict[str, str] = {}
    for p in out.glob("reasons-*.tsv"):
        for r in read_tsv(p):
            reasons[r["id"]] = (r.get("reason_known") or "").strip()
    st_counts: dict[str, int] = {}
    hint_counts: dict[str, int] = {}
    for r in inv:
        st_counts[r["status"]] = st_counts.get(r["status"], 0) + 1
        for h in filter(None, r["hint"].split(",")):
            hint_counts[h] = hint_counts.get(h, 0) + 1
    print("counts: " + ", ".join(f"{k} {st_counts.get(k, 0)}" for k in ("same", "reworded", "LOST")))
    print("hints: " + (", ".join(f"{k} {v}" for k, v in sorted(hint_counts.items())) or "none"))
    problems: list[tuple[str, dict[str, str]]] = []
    for r in inv:
        if r["status"] == "LOST" and verdicts.get(r["id"]) not in VERDICTS:
            problems.append(("LOST without verdict", r))
        if not args.lost_only and r["emphasis"] == "yes" and reasons.get(r["id"]) not in ("yes", "no"):
            problems.append(("emphasis without reasons entry", r))
        if args.meaning and r["status"] == "reworded" and meaning.get(r["id"]) != "same":
            why = "reworded with meaning verdict 'different'" if meaning.get(r["id"]) == "different" else "reworded without meaning verdict"
            problems.append((why, r))
    for why, r in problems:
        print(f"{why}: {r['id']} {r['old_file']}:{r['old_lines']} hint={r['hint'] or '-'} score={r['score']}")
    print(f"unresolved: {len(problems)}")
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="match old rules to the new tree")
    g = b.add_mutually_exclusive_group()
    g.add_argument("--baseline", default=DEFAULT_BASELINE)
    g.add_argument("--old-dir")
    b.add_argument("--new-dir")
    b.add_argument("--out")
    b.set_defaults(fn=cmd_build)
    t = sub.add_parser("todo", help="append reasons template rows for one old file")
    t.add_argument("--file", required=True)
    t.add_argument("--out")
    t.set_defaults(fn=cmd_todo)
    c = sub.add_parser("check", help="report unresolved items")
    c.add_argument("--files", nargs="*")
    c.add_argument("--lost-only", action="store_true")
    c.add_argument("--meaning", action="store_true")
    c.add_argument("--out")
    c.set_defaults(fn=cmd_check)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
