"""Dataset fingerprint, prior-run scan and legacy-result scan (REC-06a, D-04)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from ailsa.record import fingerprint as fp
from ailsa.record.events import MARKER


def _tree(root: Path) -> Path:
    (root / "1" / "pdata" / "1").mkdir(parents=True)
    (root / "1" / "acqus").write_text("##$NS= 8\n")
    (root / "1" / "fid").write_bytes(b"\x00\x01\x02\x03" * 100)
    (root / "1" / "pdata" / "1" / "1r").write_bytes(b"abcd")
    return root


def test_rename_and_copy_keep_fingerprint(tmp_path: Path) -> None:
    a = _tree(tmp_path / "a")
    original = fp.dataset_fingerprint(a)
    assert original["fingerprint"].startswith("sha256:")
    assert len(original["fingerprint"]) == len("sha256:") + 64
    assert original["mode"] == "full"
    assert original["files"] == 3
    shutil.copytree(a, tmp_path / "other-name")
    assert fp.dataset_fingerprint(tmp_path / "other-name")["fingerprint"] == original["fingerprint"]
    a.rename(tmp_path / "renamed")
    assert fp.dataset_fingerprint(tmp_path / "renamed")["fingerprint"] == original["fingerprint"]


def test_changed_byte_changes_fingerprint(tmp_path: Path) -> None:
    a = _tree(tmp_path / "a")
    before = fp.dataset_fingerprint(a)["fingerprint"]
    (a / "1" / "fid").write_bytes(b"\x00\x01\x02\x04" * 100)
    assert fp.dataset_fingerprint(a)["fingerprint"] != before


def test_exclusions_and_symlinks(tmp_path: Path) -> None:
    a = _tree(tmp_path / "a")
    base = fp.dataset_fingerprint(a)["fingerprint"]
    (a / "analysis").mkdir()
    (a / "analysis" / "x.txt").write_text("result")
    (a / ".DS_Store").write_bytes(b"junk")
    (a / "__MACOSX").mkdir()
    (a / "__MACOSX" / "y").write_text("junk")
    run = a / "someRun"
    run.mkdir()
    (run / MARKER).write_text("{}")
    (run / "events.jsonl").write_text("{}\n")
    (a / "link").symlink_to(tmp_path)
    (a / "filelink").symlink_to(a / "1" / "fid")
    assert fp.dataset_fingerprint(a)["fingerprint"] == base


def test_large_file_sampled(tmp_path: Path, monkeypatch) -> None:
    a = _tree(tmp_path / "a")
    monkeypatch.setattr(fp, "SAMPLE_ABOVE", 1000)
    (a / "1" / "ser").write_bytes(b"z" * 3 * 1024 * 1024)
    result = fp.dataset_fingerprint(a)
    assert result["mode"] == "sampled"


def test_find_prior_runs(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    hit = ws / "run-a"
    miss = ws / "run-b"
    nomarker = ws / "run-c"
    for d in (hit, miss, nomarker):
        d.mkdir(parents=True)
    for d, value in ((hit, "sha256:aaa"), (miss, "sha256:bbb"), (nomarker, "sha256:aaa")):
        (d / "events.jsonl").write_text(
            json.dumps({"type": "run.created", "payload": {"dataset": {"fingerprint": value}}})
            + "\n"
        )
    (hit / MARKER).write_text("{}")
    (miss / MARKER).write_text("{}")
    assert fp.find_prior_runs(ws, "sha256:aaa") == ["run-a"]
    assert fp.find_prior_runs(tmp_path / "missing", "sha256:aaa") == []


def test_legacy_results(tmp_path: Path) -> None:
    a = _tree(tmp_path / "a")
    assert fp.legacy_results(a) == []
    (a / "analysis").mkdir()
    (a / "CASE-PROGRESS.md").write_text("x")
    (a / "1" / "final_results.md").write_text("x")
    (a / "1" / "out.sol").write_text("x")
    (a / "iteration_1").mkdir()
    found = fp.legacy_results(a)
    assert "analysis" in found
    assert "CASE-PROGRESS.md" in found
    assert "1/final_results.md" in found
    assert "1/out.sol" in found
    assert "iteration_1" in found


def test_workspace_overlap(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    assert fp.workspace_overlaps(tmp_path / "ws", data) is None
    assert fp.workspace_overlaps(data / "ws", data) is not None
    assert fp.workspace_overlaps(tmp_path, data) is not None
