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
    # what a run loads in the normal case: SKILL.md only; at most also the fixing guide
    total = sum(len(p.read_text()) for p in FILES if p.name != "CHANGELOG.md")
    assert total / 4 <= 6000, "more than about 6000 tokens of instructions"


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
                found.append(shlex.split(chunk.replace("...", "")))
    return found


def test_commands_exist() -> None:
    commands = _commands()
    assert commands, "the skill names no ailsa command"
    for argv in commands:
        group: click.Command = cli
        words = argv[1:]
        while isinstance(group, click.Group) and words and words[0] in group.commands:
            group = group.commands[words.pop(0)]
        if isinstance(group, click.Group):
            assert not words, f"unknown subcommand in: {' '.join(argv)}"
            continue  # prose naming a command group, e.g. "the `ailsa case` commands"
        known = {opt for p in group.params for opt in getattr(p, "opts", [])}
        for word in words:
            if word.startswith("--"):
                assert word.split("=")[0] in known, f"unknown option {word} in: {' '.join(argv)}"
