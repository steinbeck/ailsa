"""Tests for scripts/skill_rule_inventory.py on synthetic old/new trees."""
# ruff: noqa: E501
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "skill_rule_inventory.py"

OLD = """---
name: demo
---

# Demo

- Never run the solver before validation.
- Write the report to the output folder.
- Always keep a copy of the input spectrum.

Stop and ask when the formula is missing.
"""


def run(*args: str, expect: int | None = 0):
    r = subprocess.run(
        [sys.executable, str(SCRIPT), *args], cwd=ROOT, capture_output=True, text=True
    )
    if expect is not None:
        assert r.returncode == expect, r.stdout + r.stderr
    return r


@pytest.fixture
def trees(tmp_path):
    old, new = tmp_path / "old", tmp_path / "new"
    old.mkdir()
    new.mkdir()
    (old / "a.md").write_text(OLD)
    return old, new, tmp_path / "out"


def build(old, new, out, expect=0):
    return run("build", "--old-dir", str(old), "--new-dir", str(new), "--out", str(out), expect=expect)


def rows(out):
    with (out / "inventory.tsv").open() as f:
        lines = [ln for ln in f if not ln.startswith("#")]
    return list(csv.DictReader(lines, delimiter="\t", quoting=csv.QUOTE_NONE))


def test_identical_text_all_same(trees):
    old, new, out = trees
    (new / "a.md").write_text(OLD)
    build(old, new, out)
    assert {r["status"] for r in rows(out)} == {"same"}
    assert len(rows(out)) == 4


def test_reworded_without_emphasis_not_lost(trees):
    old, new, out = trees
    (new / "a.md").write_text(OLD.replace("Always keep", "Keep").replace("Stop and ask when", "Ask if"))
    build(old, new, out)
    assert "LOST" not in {r["status"] for r in rows(out)}


def test_deleted_item_lost_then_verdict(trees):
    old, new, out = trees
    (new / "a.md").write_text(OLD.replace("- Write the report to the output folder.\n", ""))
    build(old, new, out)
    lost = [r for r in rows(out) if r["status"] == "LOST"]
    assert len(lost) == 1
    assert run("check", "--lost-only", "--out", str(out), expect=1).stdout.count(lost[0]["id"]) == 1
    (out / "verdicts.tsv").write_text(f"id\tverdict\tnote\n{lost[0]['id']}\tdropped-history\tx\n")
    run("check", "--lost-only", "--out", str(out))


def test_check_never_prints_unit_text(trees):
    old, new, out = trees
    (new / "a.md").write_text("")
    build(old, new, out)
    assert "output folder" not in run("check", "--out", str(out), expect=1).stdout


def test_moved_unit_same_in_other_file(trees):
    old, new, out = trees
    (new / "b.md").write_text(OLD)
    build(old, new, out)
    assert all(r["new_file"] == "b.md" and r["status"] == "same" for r in rows(out))


def test_negation_dropped_needs_review(tmp_path):
    old, new, out = tmp_path / "o", tmp_path / "n", tmp_path / "out"
    old.mkdir()
    new.mkdir()
    (old / "a.md").write_text("- NEVER poll the list.\n")
    (new / "a.md").write_text("- Poll the list.\n")
    build(old, new, out)
    r = rows(out)[0]
    assert r["status"] != "same"
    assert "negation?" in r["hint"]


def test_todo_idempotent_and_check_reasons(trees):
    old, new, out = trees
    (new / "a.md").write_text(OLD)
    build(old, new, out)
    emph = [r for r in rows(out) if r["emphasis"] == "yes"]
    assert len(emph) == 2  # the 'never' and 'always' items
    run("todo", "--file", "a.md", "--out", str(out))
    first = (out / "reasons-a.tsv").read_text()
    assert len(first.strip().splitlines()) == 1 + len(emph)
    run("todo", "--file", "a.md", "--out", str(out))
    assert (out / "reasons-a.tsv").read_text() == first
    run("check", "--lost-only", "--out", str(out))
    run("check", "--out", str(out), expect=1)
    lines = first.splitlines()
    filled = [lines[0]] + [ln.rsplit("\t", 2)[0] + "\tyes\tbecause" for ln in lines[1:]]
    (out / "reasons-a.tsv").write_text("\n".join(filled) + "\n")
    run("check", "--out", str(out))


def test_out_inside_repo_refused(trees):
    old, new, _ = trees
    (new / "a.md").write_text(OLD)
    r = build(old, new, ROOT / "_inventory_test_out_never_created", expect=2)
    assert not (ROOT / "_inventory_test_out_never_created").exists()
    assert "work tree" in r.stderr


def test_second_build_keeps_hand_files(trees):
    old, new, out = trees
    (new / "a.md").write_text(OLD)
    build(old, new, out)
    hand = {
        "verdicts.tsv": "id\tverdict\tnote\n",
        "reasons-a.tsv": "id\told_lines\tsummary\treason_known\treason\n",
        "meaning.tsv": "id\tverdict\tnote\n",
    }
    for name, content in hand.items():
        (out / name).write_text(content)
    build(old, new, out)
    for name, content in hand.items():
        assert (out / name).read_text() == content


def test_meaning_flag(trees):
    old, new, out = trees
    (new / "a.md").write_text(OLD.replace("Write the report to the output folder", "Report goes to the output folder"))
    build(old, new, out)
    rw = [r for r in rows(out) if r["status"] == "reworded"]
    assert rw
    run("check", "--lost-only", "--meaning", "--out", str(out), expect=1)


def test_help_lists_commands():
    out = run("--help").stdout
    for c in ("build", "todo", "check"):
        assert c in out


def test_scattered_tokens_never_same(tmp_path):
    old, new, out = tmp_path / "o", tmp_path / "n", tmp_path / "out"
    old.mkdir()
    new.mkdir()
    (old / "a.md").write_text("- Validate spectrum peaks against solver output.\n")
    (new / "a.md").write_text(
        "- Check the spectrum header.\n- Compare peaks with the table.\n- Read solver output.\n"
    )
    build(old, new, out)
    assert rows(out)[0]["status"] != "same"
