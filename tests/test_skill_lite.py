"""Checks on the lean skill (ailsa-lite) that ships with the package.

Format and size follow the Agent Skills conventions; the command check makes sure the
skill only names commands and options that exist (docs/SKILLS.md, rule 2).
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import click
import pytest

from ailsa.cli import cli

SKILL_DIR = Path(__file__).resolve().parents[1] / "src" / "ailsa" / "skills" / "ailsa-lite"
SKILL_MD = SKILL_DIR / "SKILL.md"
FILES = sorted(SKILL_DIR.rglob("*.md"))


def _frontmatter() -> dict[str, str]:
    text = SKILL_MD.read_text()
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, "SKILL.md has no frontmatter"
    fields = {}
    for line in match.group(1).splitlines():
        if re.match(r"^[a-z]+:", line):
            key, _, value = line.partition(":")
            fields[key] = value.strip()
    return fields


def test_name_matches_directory() -> None:
    name = _frontmatter()["name"]
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name)
    assert name == SKILL_DIR.name


def test_description() -> None:
    description = _frontmatter()["description"]
    assert 0 < len(description) <= 1024
    assert "Use when" in description


def test_size_budget() -> None:
    assert len(SKILL_MD.read_text().splitlines()) <= 200
    # SKILL.md plus every reference file must fit next to the harness prompt (about 10k) and
    # a run's working context in a 64k window (about 3.5 characters per token for this text)
    total = sum(len(p.read_text()) for p in FILES if p.name != "CHANGELOG.md")
    assert total / 3.5 <= 20000, "more than about 20000 tokens of instructions"


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_hygiene(path: Path) -> None:
    text = path.read_text()
    assert not re.search(r"\b(claude|gpt|qwen|llama|gemini)-?\d", text, re.IGNORECASE)
    if path.name != "CHANGELOG.md":
        assert not re.search(r"\bCASE\d+\b|\bPhase \d+", text)
        assert not re.search(r"\b20\d\d-\d\d-\d\d\b", text)


def test_links_resolve() -> None:
    for path in FILES:
        for target in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", path.read_text()):
            assert (path.parent / target).exists(), f"{path.name} links to missing {target}"


def _commands() -> list[list[str]]:
    found = []
    for path in FILES:
        for line in path.read_text().splitlines():
            for chunk in re.findall(r"`(ailsa [^`]+)`", line) + (
                [line.strip()] if line.strip().startswith("ailsa ") else []
            ):
                chunk = chunk.replace("...", "").rstrip("\\ ")  # a line continued with "\"
                try:
                    found.append(shlex.split(chunk))
                except ValueError:  # unbalanced quotes in a shortened example
                    found.append(chunk.split())
    return found


FRONTIER = [
    *sorted((SKILL_DIR.parents[3] / ".claude" / "commands" / "lucy-ng").rglob("*.md")),
    *sorted((SKILL_DIR.parents[3] / ".claude" / "agents").glob("lucy-*.md")),
]


# Run-record commands only the lean skill names for now. The frontier skill adopts them when it
# is wired to the run record; this allow-list is removed then.
RECORD_COMMANDS = {"run init", "run note", "run finalize"}


def _command_names(paths: list[Path], prefixes: str) -> set[str]:
    """First two words of every command a skill names, e.g. "lsd run" or "identify"."""
    names = set()
    pattern = re.compile(rf"\b(?:{prefixes}) ([a-z][a-z0-9-]*)(?: ([a-z0-9][a-z0-9-]*))?")
    for path in paths:
        for m in pattern.finditer(path.read_text()):
            group = cli.commands.get(m.group(1))
            if group is None:
                continue
            is_sub = isinstance(group, click.Group) and m.group(2) in group.commands
            names.add(f"{m.group(1)} {m.group(2) if is_sub else ''}".strip())
    return names


@pytest.mark.skipif(not FRONTIER, reason="frontier skill not in this checkout")
def test_same_tools_as_frontier_skill() -> None:
    """The lean skill names only commands the frontier skill uses (docs/SKILLS.md, rule 1)."""
    lean = _command_names([p for p in FILES if p.name != "CHANGELOG.md"], "ailsa")
    frontier = _command_names(FRONTIER, "ailsa|lucy")
    assert lean, "the lean skill names no ailsa command"
    # a bare group name ("the `ailsa analyze ...` tools") counts if the frontier uses the group
    missing = {n for n in lean - frontier if not any(f.startswith(n + " ") for f in frontier)}
    missing -= RECORD_COMMANDS
    assert not missing, f"not used by the frontier skill: {sorted(missing)}"


def test_commands_exist() -> None:
    commands = _commands()
    assert commands, "the skill names no ailsa command"
    for argv in commands:
        if any(w.startswith("<") for w in argv[1:2]):
            continue  # a template such as "ailsa <command> --help"
        group: click.Command = cli
        words = argv[1:]
        while isinstance(group, click.Group) and words and words[0] in group.commands:
            group = group.commands[words.pop(0)]
        if isinstance(group, click.Group):
            options = {opt for p in group.params for opt in getattr(p, "opts", [])} | {"--help"}
            assert all(w in options for w in words), f"unknown subcommand in: {' '.join(argv)}"
            continue  # prose naming a command group, or a group option such as --version
        known = {opt for p in group.params for opt in getattr(p, "opts", [])}
        for word in words:
            if word.startswith("--"):
                assert word.split("=")[0] in known, f"unknown option {word} in: {' '.join(argv)}"
