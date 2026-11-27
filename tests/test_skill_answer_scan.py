"""Local-only checks of the packaged skills against the private benchmark answer key.

The key and the scan script stay outside the repository and are read at test time only. On any
machine but the maintainer's they are absent and the module is skipped. On the maintainer's
checkout (recognised by the git-ignored identities table) a missing input fails instead, so the
check cannot go quiet when the date-stamped key folder is renamed; set
AILSA_REQUIRE_ANSWER_SCAN=0 to skip there on purpose, or =1 to require it anywhere. Failure
messages carry counts, dataset numbers and file:line, never compound names.
"""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_skill_frontier import PENDING

REPO_ROOT = Path(__file__).resolve().parents[1]
IDENTITIES = REPO_ROOT / ".planning" / "CASE-DATASET-IDENTITIES.md"
ARMS = ("case-uat-results-opus5-rest", "case-uat-results-opus5-baseline")
GRADING = Path.home() / "Dropbox/develop/data/nmrdata"
SCAN = Path(
    os.environ.get(
        "AILSA_ANSWER_SCAN",
        Path.home() / "Dropbox/develop/ailsa-paper/scripts/blindness/prompt_answer_scan.py",
    )
)
REQUIRED = os.environ.get("AILSA_REQUIRE_ANSWER_SCAN", "1" if IDENTITIES.exists() else "0") == "1"


def _key_dir() -> Path | None:
    """The answer key: $AILSA_ANSWER_KEY_DIR, else the newest benchmark-grading-* folder."""
    if os.environ.get("AILSA_ANSWER_KEY_DIR"):
        return Path(os.environ["AILSA_ANSWER_KEY_DIR"])
    found = sorted(p for p in GRADING.glob("benchmark-grading-*") if (p / "truth.tsv").is_file())
    return found[-1] if found else None


KEY = _key_dir()


@pytest.fixture(scope="module", autouse=True)
def _inputs() -> None:
    missing = []
    if KEY is None or not (KEY / "truth.tsv").is_file():
        missing.append("answer key (truth.tsv)")
    elif not all((KEY / a).is_dir() for a in ARMS):
        missing.append("arm folders next to the key")
    if not SCAN.is_file():
        missing.append("scan script")
    if importlib.util.find_spec("rdkit") is None:
        missing.append("rdkit")
    if missing:
        why = "answer scan inputs missing: " + ", ".join(missing)
        if REQUIRED:
            pytest.fail(f"{why} (maintainer checkout; AILSA_REQUIRE_ANSWER_SCAN=0 skips)")
        pytest.skip(why)


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
    # Plain locals in the asserts: pytest must never print the CompletedProcess (stdout/stderr).
    rc = result.returncode
    assert rc == 0, f"answer scan exited {rc}"
    summary = re.search(
        r"datasets (\d+), skill files (\d+), datasets with a hit (\d+)", result.stdout
    )
    has_summary = summary is not None
    assert has_summary, "answer scan printed no summary line"
    n_datasets, n_files, n_hit = (int(x) for x in summary.groups())
    assert n_datasets > 0, "answer scan saw no datasets"
    expected = len(list(folder.rglob("*.md")))
    assert expected > 0, f"no skill files under {folder.name}"
    assert n_files == expected, f"answer scan saw {n_files} files, the folder has {expected}"
    hits, hit_cases = [], set()
    for line in result.stdout.splitlines():
        m = re.match(r"^(CASE\d+)\s+name at (.*?) \| constitution at (.*)$", line)
        if not m:
            continue
        hit_cases.add(m.group(1))
        for place in re.findall(r"'([^']+:\d+)'", m.group(2) + " " + m.group(3)):
            rel = place.rsplit(":", 1)[0]
            if not _is_pending(folder, rel):
                hits.append(f"{m.group(1)} {place}")
    parsed = len(hit_cases)
    assert parsed == n_hit, f"{n_hit} datasets with a hit reported, {parsed} hit lines parsed"
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
