"""The frozen benchmark state is recorded: tags and documentation."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    ("tag", "prefix"),
    [("paper-skill-v1", "f9aa7b3"), ("paper-skill-v2", "6d2d126")],
)
def test_tag_resolves(tag: str, prefix: str) -> None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--verify", f"{tag}^{{commit}}"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        pytest.skip("git not available")
    if out.returncode != 0:
        pytest.skip(f"tag {tag} absent in this clone")
    assert out.stdout.strip().startswith(prefix)


def test_benchmark_doc_records_state() -> None:
    text = (ROOT / "docs" / "BENCHMARK.md").read_text(encoding="utf-8")
    for needle in (
        "paper-skill-v1",
        "paper-skill-v2",
        "f9aa7b3",
        "6d2d126",
        "2.1.205",
        "3.5.3",
        "schema 3",
        "ragment",
    ):
        assert needle in text, needle


def test_skills_doc_describes_packaged_skill() -> None:
    text = (ROOT / "docs" / "SKILLS.md").read_text(encoding="utf-8")
    assert "byte-identical" not in text
    assert "src/ailsa/skills/ailsa" in text
    assert "ailsa skill install ailsa" in text
