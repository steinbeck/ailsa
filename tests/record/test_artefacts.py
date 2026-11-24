"""Artefact registration: atomic, hashed, never overwritten, supersession."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

from ailsa.record.artefacts import (
    artefact_index,
    copy_into_run,
    find_artefacts,
    register_artefact,
    register_existing,
    safe_relpath,
)
from ailsa.record.log import read_events

ACTOR = {"kind": "tool", "name": "ailsa pick"}


def _reg(run_dir: Path, rel: str, data: bytes = b"{}", **kw):
    return register_artefact(
        run_dir,
        kind="peak-pick",
        rel_path=rel,
        data=data,
        event_type="peaks.picked",
        payload={"pick_id": "p1"},
        actor=ACTOR,
        **kw,
    )


def test_register_writes_file_and_event(new_run) -> None:
    _, run_dir = new_run
    entry = _reg(run_dir, "peaks/5.1.json", b"hello")
    assert entry["id"] == "art:peak-pick:1"
    assert entry["sha256"] == hashlib.sha256(b"hello").hexdigest()
    assert entry["bytes"] == 5 and entry["path"] == "peaks/5.1.json"
    assert (run_dir / "peaks" / "5.1.json").read_bytes() == b"hello"
    events = read_events(run_dir)["events"]
    assert len(events) == 1 and events[0]["artefacts"][0] == entry
    assert events[0]["type"] == "peaks.picked"


def test_second_number(new_run) -> None:
    _, run_dir = new_run
    _reg(run_dir, "peaks/a.json")
    assert _reg(run_dir, "peaks/b.json")["id"] == "art:peak-pick:2"


def test_no_overwrite(new_run) -> None:
    _, run_dir = new_run
    _reg(run_dir, "peaks/a.json", b"one")
    with pytest.raises(FileExistsError):
        _reg(run_dir, "peaks/a.json", b"two")
    assert (run_dir / "peaks" / "a.json").read_bytes() == b"one"
    assert len(read_events(run_dir)["events"]) == 1


def test_supersession(new_run) -> None:
    _, run_dir = new_run
    first = _reg(run_dir, "peaks/a.json")
    second = _reg(run_dir, "peaks/b.json", supersedes=first["id"])
    assert second["supersedes"] == "art:peak-pick:1"
    events = read_events(run_dir)["events"]
    index = artefact_index(events)
    assert index["art:peak-pick:1"]["superseded_by"] == "art:peak-pick:2"
    assert index["art:peak-pick:2"]["superseded_by"] is None
    assert [a["id"] for a in find_artefacts(events, "peak-pick")] == [
        "art:peak-pick:1",
        "art:peak-pick:2",
    ]


def test_safe_relpath(new_run, tmp_path: Path) -> None:
    _, run_dir = new_run
    for bad in ("/etc/passwd", "../x", "a/../../x", ""):
        with pytest.raises(ValueError):
            safe_relpath(run_dir, bad)
    outside = tmp_path / "outside"
    outside.mkdir()
    (run_dir / "link").symlink_to(outside)
    with pytest.raises(ValueError):
        safe_relpath(run_dir, "link/file.json")
    assert safe_relpath(run_dir, "peaks/a.json") == "peaks/a.json"


def test_copy_into_run(new_run, tmp_path: Path) -> None:
    _, run_dir = new_run
    src = tmp_path / "src.bin"
    src.write_bytes(b"abc")
    rel, digest, size = copy_into_run(run_dir, src, "views/src.bin")
    assert (rel, size) == ("views/src.bin", 3)
    assert digest == hashlib.sha256(b"abc").hexdigest()
    link = tmp_path / "link.bin"
    link.symlink_to(src)
    with pytest.raises(ValueError):
        copy_into_run(run_dir, link, "views/link.bin")
    with pytest.raises(ValueError):
        copy_into_run(run_dir, src, "views/big.bin", max_bytes=2)


def test_register_existing(new_run) -> None:
    _, run_dir = new_run
    (run_dir / "out.txt").write_bytes(b"data")
    entry = register_existing(
        run_dir,
        kind="log",
        rel_path="out.txt",
        event_type="tool.invoked",
        payload={"argv": [], "exit_code": 0, "duration_s": 0.0},
        actor=ACTOR,
    )
    assert entry["id"] == "art:log:1" and entry["bytes"] == 4
    assert (run_dir / "out.txt").read_bytes() == b"data"


_WORKER = """
import sys
from ailsa.record.artefacts import register_artefact
run_dir, name = sys.argv[1], sys.argv[2]
e = register_artefact(run_dir, kind="peak-pick", rel_path="peaks/" + name + ".json",
    data=b"x", event_type="peaks.picked", payload={"pick_id": name},
    actor={"kind": "tool", "name": "w"})
print(e["id"])
"""


def test_concurrent_registers(new_run) -> None:
    _, run_dir = new_run
    procs = [
        subprocess.Popen(
            [sys.executable, "-c", _WORKER, str(run_dir), f"w{i}"],
            stdout=subprocess.PIPE,
            text=True,
        )
        for i in range(4)
    ]
    ids: list[str] = []
    try:
        for proc in procs:
            out, _ = proc.communicate(timeout=30)
            assert proc.returncode == 0
            ids.append(out.strip())
    finally:
        for proc in procs:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
    assert sorted(ids) == [f"art:peak-pick:{n}" for n in range(1, 5)]
    assert read_events(run_dir)["integrity"]["clean"]
