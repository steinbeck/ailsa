"""Local-only checks of the packaged skills against the private benchmark answer key.

The key and the scan script stay outside the repository and are read at test time only. Without
them (any machine but the maintainer's) the whole module is skipped. Failure messages carry
dataset numbers and file:line, never compound names.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_skill_frontier import PENDING

pytest.importorskip("rdkit")

REPO_ROOT = Path(__file__).resolve().parents[1]
KEY = Path(
    os.environ.get(
        "AILSA_ANSWER_KEY_DIR",
        Path.home() / "Dropbox/develop/data/nmrdata/benchmark-grading-2026-10-01",
    )
)
SCAN = Path(
    os.environ.get(
        "AILSA_ANSWER_SCAN",
        Path.home() / "Dropbox/develop/ailsa-paper/scripts/blindness/prompt_answer_scan.py",
    )
)
ARMS = ("case-uat-results-opus5-rest", "case-uat-results-opus5-baseline")
IDENTITIES = REPO_ROOT / ".planning" / "CASE-DATASET-IDENTITIES.md"

pytestmark = pytest.mark.skipif(
    not ((KEY / "truth.tsv").exists() and all((KEY / a).exists() for a in ARMS) and SCAN.exists()),
    reason="private answer key or scan script not available on this machine",
)

SKILLS = [
    REPO_ROOT / "src" / "ailsa" / "skills" / "ailsa",
    REPO_ROOT / "src" / "ailsa" / "skills" / "ailsa-lite",
]
FRONTIER = SKILLS[0]


def _is_pending(folder: Path, rel: str) -> bool:
    return folder == FRONTIER and rel in PENDING


@pytest.mark.parametrize("folder", SKILLS, ids=lambda p: p.name)
def test_no_benchmark_answer_in_skills(folder: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            str(SCAN),
            "--truth",
            str(KEY / "truth.tsv"),
            "--cases",
            *[str(KEY / a) for a in ARMS],
            "--skills",
            str(folder),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, "answer scan did not run"
    assert "skill files" in result.stdout, "answer scan printed no summary line"
    hits = []
    for line in result.stdout.splitlines():
        m = re.match(r"^(CASE\d+)\s+name at (.*?) \| constitution at (.*)$", line)
        if not m:
            continue
        for place in re.findall(r"'([^']+:\d+)'", m.group(2) + " " + m.group(3)):
            rel = place.rsplit(":", 1)[0]
            if not _is_pending(folder, rel):
                hits.append(f"{m.group(1)} {place}")
    assert not hits, f"benchmark answer in skill text: {sorted(set(hits))}"


def _teaching_names() -> dict[str, str]:
    """Dataset number -> bare compound name, from the git-ignored identities table."""
    names = {}
    for line in IDENTITIES.read_text().splitlines():
        m = re.match(r"^\|\s*(CASE\d+)\s*\|[^|]*\|\s*\*\*([^*]+)\*\*", line)
        if not m:
            continue
        name = re.sub(r"^\([^)]*\)-?\s*", "", m.group(2)).strip()
        if len(name) >= 5:
            names[m.group(1)] = name
    return names


@pytest.mark.skipif(not IDENTITIES.exists(), reason="identities table is maintainer-local")
def test_no_teaching_set_name_in_skills() -> None:
    names = _teaching_names()
    assert names, "identities table has no parsable rows"
    hits = []
    for folder in SKILLS:
        for path in sorted(folder.rglob("*.md")):
            if path.name == "CHANGELOG.md":
                continue
            rel = str(path.relative_to(folder))
            if _is_pending(folder, rel):
                continue
            for no, line in enumerate(path.read_text().splitlines(), 1):
                for case, name in names.items():
                    if re.search(rf"(?i)\b{re.escape(name)}\b", line):
                        hits.append(f"{case} {folder.name}/{rel}:{no}")
    assert not hits, f"teaching-set compound name in skill text: {sorted(set(hits))}"
