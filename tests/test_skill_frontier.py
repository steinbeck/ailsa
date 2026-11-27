"""Lint for the frontier skill (src/ailsa/skills/ailsa).

Encodes the skill form (size, contents list, no history, no dataset numbers, no model IDs, no dead
references, one term per role, no capital-letter emphasis, database credit) as machine checks.
Files that are not yet restructured are listed in PENDING; their per-file checks are skipped with
a visible reason, and test_restructure_complete fails strictly (xfail) while PENDING is not empty.
Set AILSA_LINT_IGNORE_PENDING=1 to run every check on every file.
"""

from __future__ import annotations

import os
import re
import shlex
from pathlib import Path

import click
import pytest

from ailsa.cli import cli

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "src" / "ailsa" / "skills" / "ailsa"
FILES = sorted(SKILL_DIR.rglob("*.md"))
TEXT_FILES = [p for p in FILES if p.name != "CHANGELOG.md"]
COMMANDS = {"case", "dereplicate", "predict", "sanitise", "status", "help"}
AGENTS = {
    "ailsa-nmr-chemist",
    "ailsa-lsd-engineer",
    "ailsa-solution-analyst",
    "ailsa-devils-advocate",
    "ailsa-diagnostic",
}
REFS = {"advisory-templates", "loop-patterns", "nmr-basics", "progress-format"}
RUN_ARTEFACTS = {"CASE-PROGRESS.md", "final_results.md", "DIAGNOSTIC-REPORT.md"}
TEAMMATE_ADDRESSES = {"nmr-chemist", "lsd-engineer", "solution-analyst", "devils-advocate"}
CREDIT = (
    "COCONUT 13C shifts: from J.-M. Nuzillard, Zenodo, doi:10.5281/zenodo.6561449, CC BY 4.0"
)

# Paths relative to SKILL_DIR still awaiting restructure. Plan 10 empties this set.
PENDING: frozenset[str] = frozenset(
    {f"commands/{c}.md" for c in COMMANDS}
    | {f"agents/{a}.md" for a in AGENTS}
    | {f"references/{r}.md" for r in REFS}
) - {
    "agents/ailsa-nmr-chemist.md",
    "agents/ailsa-solution-analyst.md",
    "agents/ailsa-lsd-engineer.md",
    "agents/ailsa-diagnostic.md",
    "agents/ailsa-devils-advocate.md",
    "commands/case.md",
    "commands/sanitise.md",
    "commands/dereplicate.md",
    "commands/predict.md",
    "commands/status.md",
    "commands/help.md",
    "references/nmr-basics.md",
}
_ACTIVE_PENDING: frozenset[str] = (
    frozenset() if os.environ.get("AILSA_LINT_IGNORE_PENDING") == "1" else PENDING
)


def _rel(path: Path) -> str:
    return str(path.relative_to(SKILL_DIR))


def _frontmatter_text(text: str) -> str:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    return match.group(1) if match else ""


def _frontmatter(path: Path) -> dict[str, str]:
    """Top-level keys of the frontmatter; a folded `>` value is joined into one line."""
    fields: dict[str, str] = {}
    key = None
    for line in _frontmatter_text(path.read_text()).splitlines():
        m = re.match(r"^([a-z][a-z-]*):\s*(.*)$", line)
        if m:
            key = m.group(1)
            value = m.group(2).strip()
            fields[key] = "" if value in (">", "|") else value.strip("\"'")
        elif key and line.startswith(" ") and key in fields and not line.lstrip().startswith("-"):
            fields[key] = (fields[key] + " " + line.strip()).strip()
    return fields


def _indented_version(path: Path) -> bool:
    return bool(re.search(r"^\s+version:", _frontmatter_text(path.read_text()), re.MULTILINE))


def _prose(text: str) -> str:
    """Text without frontmatter, fenced code, inline code and [TAG] message tags."""
    text = re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.DOTALL)
    text = re.sub(r"^(```|~~~).*?^\1", "", text, flags=re.DOTALL | re.MULTILINE)
    text = re.sub(r"`[^`\n]*`", "", text)
    return re.sub(r"\[[A-Z][A-Z0-9 _/-]+\]", "", text)


def _hits(text: str, pattern: str, flags: int = 0) -> list[str]:
    out = []
    for no, line in enumerate(text.splitlines(), 1):
        if re.search(pattern, line, flags):
            out.append(f"{no}: {line.strip()[:80]}")
    return out


def _command_argvs(paths: list[Path]) -> list[list[str]]:
    found = []
    for path in paths:
        for line in path.read_text().splitlines():
            for chunk in re.findall(r"`(ailsa [^`]+)`", line) + (
                [line.strip()]
                if re.match(r"ailsa [a-z][a-z0-9-]*(\s|$)", line.strip())
                else []
            ):
                chunk = chunk.replace("...", "").rstrip("\\ ")
                try:
                    found.append(shlex.split(chunk))
                except ValueError:
                    found.append(chunk.split())
    return found


def _unknown_in_click_tree(argv: list[str]) -> str | None:
    if any(w.startswith("<") for w in argv[1:2]):
        return None
    group: click.Command = cli
    words = argv[1:]
    while isinstance(group, click.Group) and words and words[0] in group.commands:
        group = group.commands[words.pop(0)]
    if isinstance(group, click.Group):
        options = {opt for p in group.params for opt in getattr(p, "opts", [])} | {"--help"}
        if not all(w in options for w in words):
            return f"unknown subcommand in: {' '.join(argv)}"
        return None
    known = {opt for p in group.params for opt in getattr(p, "opts", [])} | {"--help"}
    for word in words:
        if word.startswith("--") and word.split("=")[0] not in known:
            return f"unknown option {word} in: {' '.join(argv)}"
    return None


# --- patterns -------------------------------------------------------------------------------

HISTORY = [
    r"\bPhase \d+",
    r"\b20\d\d-\d\d-\d\d\b",
    r"\bUAT\b",
    r"\bBug \d",
    r"\bD-\d+\b",
    r"\b(?!DEPT-)[A-Z]{2,5}-\d{2}\b",
]
MODEL_IDS = [
    r"(?i)\b(claude|gpt|qwen|llama|gemini)-?\d",
    r"(?i)\b(opus|sonnet|haiku)-\d",
    r"MODEL MISMATCH",
]
TERMS = [
    r"(?i)\borchestrator\b",
    r"(?i)\bteam lead\b",
    r"(?i)\bsupervisor\b",
    r"Devils-Advocate",
    r"(?i)(?<!ailsa-)\bdevils[ -]advocate\b",
    r"NMR-Chemist",
    r"LSD-Engineer",
    r"Solution-Analyst",
]
EMPHASIS = (
    r"\b(MUST|NEVER|ALWAYS|MANDATORY|BINDING|IMPORTANT|REQUIRED|FORBIDDEN|CRITICAL|DO NOT"
    r"|NOT|ONLY|EXACTLY|VERBATIM|ABSOLUTE)\b"
)


def _pending_skip(path: Path) -> None:
    if _rel(path) in _ACTIVE_PENDING:
        pytest.skip("awaiting restructure")


def _ids(p: Path) -> str:
    return _rel(p)


# --- always-on checks -----------------------------------------------------------------------


def test_tree_shape() -> None:
    commands = {p.stem for p in (SKILL_DIR / "commands").glob("*.md")}
    agents = {p.stem for p in (SKILL_DIR / "agents").glob("*.md")}
    assert commands == COMMANDS
    assert agents == AGENTS
    assert list((SKILL_DIR / "references").glob("*.md")), "references/ is empty"
    assert not (SKILL_DIR / "commands" / "references").exists()
    allowed = {"INDEX.md", "CHANGELOG.md"}
    stray = [
        _rel(p)
        for p in FILES
        if p.parts[len(SKILL_DIR.parts)] not in {"commands", "agents", "references"}
        and p.name not in allowed
    ]
    assert not stray, f"markdown files outside commands/agents/references: {stray}"


def test_index() -> None:
    index = SKILL_DIR / "INDEX.md"
    fm = _frontmatter(index)
    assert fm.get("name") == "ailsa"
    assert _indented_version(index), "INDEX.md frontmatter has no indented version"
    assert 0 < len(fm.get("description", "")) <= 1024
    assert "Use when" in fm["description"]
    text = index.read_text()
    links = re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", text)
    for target in links:
        if re.match(r"^[a-z]+://", target):
            continue
        assert (index.parent / target).exists(), f"INDEX.md links to missing {target}"
    for p in FILES:
        if _rel(p) in {"INDEX.md", "CHANGELOG.md"}:
            continue
        assert _rel(p) in links, f"INDEX.md does not link {_rel(p)}"


@pytest.mark.parametrize("path", sorted((SKILL_DIR / "commands").glob("*.md")), ids=_ids)
def test_command_frontmatter(path: Path) -> None:
    fm = _frontmatter(path)
    assert "name" not in fm, "command files carry no name: key"
    description = fm.get("description", "")
    assert 0 < len(description) <= 1024
    assert "Use when" in description


@pytest.mark.parametrize("path", sorted((SKILL_DIR / "agents").glob("*.md")), ids=_ids)
def test_agent_frontmatter(path: Path) -> None:
    fm = _frontmatter(path)
    assert fm.get("name") == path.stem
    assert re.fullmatch(r"ailsa-[a-z]+(-[a-z]+)*", fm["name"])
    assert fm.get("description"), "agent has no description"
    assert "model" not in fm, "agent pins a model"


@pytest.mark.parametrize("path", FILES, ids=_ids)
def test_old_name(path: Path) -> None:
    hits = _hits(path.read_text(), r"(?i)\blucy\b|lucy-ng|lucy_ng")
    assert not hits, f"{_rel(path)}: old name at {hits}"


def test_reference_paths_resolve() -> None:
    problems = []
    for path in FILES:
        text = path.read_text()
        for ref in re.findall(r"~/\.claude/ailsa/references/([\w.-]+\.md)", text):
            if not (SKILL_DIR / "references" / ref).exists():
                problems.append(f"{_rel(path)}: reference {ref}")
        for cmd in re.findall(r"/ailsa:([a-z][a-z-]*)", text):
            if not (SKILL_DIR / "commands" / f"{cmd}.md").exists():
                problems.append(f"{_rel(path)}: command /ailsa:{cmd}")
        for agent in re.findall(r"(?:subagent_type|agent_type)=\"([^\"]+)\"", text):
            if not (SKILL_DIR / "agents" / f"{agent}.md").exists():
                problems.append(f"{_rel(path)}: agent {agent}")
    assert not problems, problems


def test_frontier_commands_exist() -> None:
    argvs = _command_argvs(TEXT_FILES)
    assert argvs, "the skill names no ailsa command"
    problems = [m for m in (_unknown_in_click_tree(a) for a in argvs) if m]
    assert not problems, problems


def test_regex_self_checks() -> None:
    assert re.search(EMPHASIS, _prose("Do NOT poll"))
    assert not re.search(EMPHASIS, _prose("severity `CRITICAL` here"))
    assert not any(re.search(p, "DEPT-90 spectrum") for p in HISTORY)
    assert any(re.search(p, "see MULT-04") for p in HISTORY)
    assert re.search(r"\bCASE\d+\b", "CASE12")
    assert any(re.search(p, "claude-opus-4-8") for p in MODEL_IDS)
    assert any(re.search(p, "the orchestrator") for p in TERMS)
    assert not any(re.search(p, _prose("send to `devils-advocate`")) for p in TERMS)
    assert not re.search(EMPHASIS, _prose("```\nMUST\n```\n"))
    assert not re.search(EMPHASIS, _prose("[BEGIN] and [NOT READY] tags"))


@pytest.mark.xfail(
    condition=bool(PENDING), strict=True, reason="files awaiting restructure"
)
def test_restructure_complete() -> None:
    assert not PENDING, f"still pending: {sorted(PENDING)}"


# --- per-file checks ------------------------------------------------------------------------


@pytest.mark.parametrize("path", TEXT_FILES, ids=_ids)
def test_size(path: Path) -> None:
    _pending_skip(path)
    n = len(path.read_text().splitlines())
    assert n < 500, f"{_rel(path)} has {n} lines"


@pytest.mark.parametrize("path", TEXT_FILES, ids=_ids)
def test_toc(path: Path) -> None:
    _pending_skip(path)
    lines = path.read_text().splitlines()
    if len(lines) <= 100:
        return
    head = lines[:60]
    starts = [i for i, ln in enumerate(head) if ln.strip() == "## Contents"]
    assert starts, f"{_rel(path)} has over 100 lines and no '## Contents' in the first 60"
    text = path.read_text()
    headings = {m.group(1).strip() for m in re.finditer(r"^#{2,3} (.+)$", text, re.MULTILINE)}
    headings |= set(re.findall(r'<step name="([^"]+)"', text))
    problems = []
    for ln in lines[starts[0] + 1 :]:
        if ln.startswith("#"):
            break
        m = re.match(r"^\s*[-*] (.+)$", ln)
        if not m:
            continue
        entry = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", m.group(1)).strip()
        entry = entry.strip("`")
        if not any(entry == h or entry in h or h in entry for h in headings):
            problems.append(entry[:60])
    assert not problems, f"{_rel(path)}: contents entries without a heading: {problems}"


@pytest.mark.parametrize("path", TEXT_FILES, ids=_ids)
def test_history(path: Path) -> None:
    _pending_skip(path)
    text = path.read_text()
    hits = []
    for pattern in HISTORY:
        hits += _hits(text, pattern)
    assert not hits, f"{_rel(path)}: history at {sorted(set(hits))}"


@pytest.mark.parametrize("path", TEXT_FILES, ids=_ids)
def test_datasets(path: Path) -> None:
    _pending_skip(path)
    text = path.read_text()
    hits = _hits(text, r"\bCASE\d+\b") + _hits(text, r"(?i)terpineol")
    assert not hits, f"{_rel(path)}: dataset reference at {sorted(set(hits))}"


@pytest.mark.parametrize("path", TEXT_FILES, ids=_ids)
def test_model_ids(path: Path) -> None:
    _pending_skip(path)
    text = path.read_text()
    hits = []
    for pattern in MODEL_IDS:
        hits += _hits(text, pattern)
    assert not hits, f"{_rel(path)}: model id at {sorted(set(hits))}"


@pytest.mark.parametrize("path", TEXT_FILES, ids=_ids)
def test_dead_refs(path: Path) -> None:
    _pending_skip(path)
    text = path.read_text()
    prose = text
    problems = _hits(prose, r"\bskill/|SKILL\.md")
    problems += _hits(_prose(text), r"\bSection \d|§\s?\d")
    packaged = {p.name for p in FILES} | RUN_ARTEFACTS
    for no, line in enumerate(text.splitlines(), 1):
        for token in re.findall(r"[\w.-]+\.md\b", line):
            if token not in packaged:
                problems.append(f"{no}: unknown file {token}")
    rel = _rel(path)
    if rel.startswith("agents/"):
        for other in AGENTS - {path.stem}:
            problems += _hits(text, re.escape(other) + r"\.md")
    if rel.startswith("references/"):
        problems += _hits(text, r"~/\.claude/ailsa/references/")
    assert not problems, f"{rel}: dead reference at {sorted(set(problems))}"


@pytest.mark.parametrize("path", TEXT_FILES, ids=_ids)
def test_terms(path: Path) -> None:
    _pending_skip(path)
    text = path.read_text()
    prose = _prose(text)
    hits = []
    for pattern in TERMS:
        hits += _hits(prose, pattern)
    if re.search(r"\bDA\b", prose) and "devil's advocate (DA)" not in text:
        hits += _hits(prose, r"\bDA\b")
    assert not hits, f"{_rel(path)}: term at {sorted(set(hits))}"


@pytest.mark.parametrize("path", TEXT_FILES, ids=_ids)
def test_emphasis(path: Path) -> None:
    _pending_skip(path)
    hits = _hits(_prose(path.read_text()), EMPHASIS)
    assert not hits, f"{_rel(path)}: capital-letter emphasis at {hits}"


@pytest.mark.parametrize("path", TEXT_FILES, ids=_ids)
def test_db_credit(path: Path) -> None:
    _pending_skip(path)
    text = path.read_text()
    if re.search(r"COCONUT|NMRShiftDB", _prose(text)):
        assert CREDIT in text, f"{_rel(path)} names the database without the source credit"
