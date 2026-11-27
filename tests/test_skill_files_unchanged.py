"""Byte-unchanged guard for the frontier skill (the CASE coordinator, the five agents, references).

The skill text is what autonomous agents execute, so a change must be a reviewed act: update
`tests/skill_files.sha256` in the SAME commit as the text change and never loosen this test.
The manifest covers every `*.md` under `src/ailsa/skills/ailsa` except `CHANGELOG.md`.
Regenerate it with:

    (cd src/ailsa/skills/ailsa && find . -name '*.md' ! -name CHANGELOG.md | LC_ALL=C sort \
        | xargs shasum -a 256) > tests/skill_files.sha256
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "src" / "ailsa" / "skills" / "ailsa"
MANIFEST = REPO_ROOT / "tests" / "skill_files.sha256"

EXPECTED_AGENT_FILES = (
    "ailsa-devils-advocate.md",
    "ailsa-diagnostic.md",
    "ailsa-lsd-engineer.md",
    "ailsa-nmr-chemist.md",
    "ailsa-solution-analyst.md",
)


def _manifest() -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in MANIFEST.read_text().splitlines():
        if not line.strip():
            continue
        digest, name = line.split(maxsplit=1)
        name = name.strip()
        if name.startswith("./"):
            name = name[2:]
        entries[name] = digest
    return entries


@pytest.mark.parametrize("relative_path,expected", sorted(_manifest().items()))
def test_skill_files_match_manifest(relative_path: str, expected: str) -> None:
    path = SKILL_DIR / relative_path
    assert path.is_file(), f"missing skill file: {relative_path}"
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    assert actual == expected, (
        f"{relative_path} changed (expected {expected}, got {actual}). Revert the edit, or "
        "update tests/skill_files.sha256 in the same commit as a reviewed change."
    )


def test_manifest_covers_tree() -> None:
    on_disk = {
        p.relative_to(SKILL_DIR).as_posix()
        for p in SKILL_DIR.rglob("*.md")
        if p.name != "CHANGELOG.md"
    }
    assert set(_manifest()) == on_disk


def test_agent_roster() -> None:
    found = sorted(p.name for p in (SKILL_DIR / "agents").glob("*.md"))
    assert found == list(EXPECTED_AGENT_FILES)
    assert not list(SKILL_DIR.rglob("supervisor.md"))
    listing = subprocess.run(
        ["git", "ls-files", ".claude/agents", ".claude/commands"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    if listing.returncode != 0:
        # Outside a git checkout the empty output would pass for "nothing tracked".
        pytest.skip("not a git checkout: cannot list tracked files")
    assert listing.stdout.split() == []


def test_case_md_is_a_regular_readable_file() -> None:
    path = SKILL_DIR / "commands" / "case.md"
    assert path.is_file(), "missing: commands/case.md"
    assert path.read_bytes(), "commands/case.md is empty"
