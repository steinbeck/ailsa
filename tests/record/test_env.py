"""Environment probe (REC-24)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from ailsa.record import env
from ailsa.record.events import REQUIRED_PAYLOAD
from tests.record.conftest import make_shim


def test_parse_lsd_banner() -> None:
    assert env.parse_lsd_banner("LSD-3.4.9\nusage ...") == "3.4.9"
    assert env.parse_lsd_banner("nothing here") is None


def test_probe_lsd_shim_nonzero_exit(shim_path: Path) -> None:
    shim = make_shim(shim_path, "LSD", "#!/bin/sh\necho 'LSD-3.4.9'\nexit 1\n")
    out = env.probe_lsd()
    assert out["version"] == "3.4.9"
    assert out["path"] == str(shim)
    assert len(out["sha256"]) == 64


def test_env_records_no_hostname_or_home_path(
    shim_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WR-13: host alias instead of the hostname, home-relative binary and database paths."""
    import json

    monkeypatch.setenv("HOME", str(tmp_path))
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"host_alias": "box"}))
    monkeypatch.setenv("AILSA_CONFIG", str(config))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    make_shim(shim_path, "LSD", "#!/bin/sh\necho 'LSD-3.4.9'\nexit 1\n")
    db = tmp_path / "data" / "x.db"
    db.parent.mkdir()
    _tiny_db(db)
    monkeypatch.setattr(env, "resolve_database_path", lambda: db)
    out = env.probe_environment(mode="headless", harness="other")
    assert out["host"]["node"] == "box"
    assert out["lsd"]["path"] == "~/bin/LSD"
    assert out["database"]["path"] == "~/data/x.db"
    assert str(tmp_path) not in json.dumps(out)


def test_probe_lsd_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    assert env.probe_lsd() == {"path": None, "version": None, "sha256": None}
    assert env.probe_outlsd()["version"] is None


def test_probe_outlsd_hash_without_version(shim_path: Path) -> None:
    make_shim(shim_path, "outlsd", "#!/bin/sh\nexit 0\n")
    out = env.probe_outlsd()
    assert out["version"] is None
    assert out["sha256"]


def _tiny_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE schema_meta (key TEXT, value TEXT)")
    conn.execute("INSERT INTO schema_meta VALUES ('schema_version', '5')")
    conn.execute("CREATE TABLE compounds (id INTEGER)")
    conn.executemany("INSERT INTO compounds VALUES (?)", [(1,), (2,), (3,)])
    conn.commit()
    conn.close()


def test_database_info_cached(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    db = tmp_path / "x.db"
    _tiny_db(db)
    calls = []
    real = env.sha256_file

    def counting(path):  # type: ignore[no-untyped-def]
        calls.append(path)
        return real(path)

    monkeypatch.setattr(env, "sha256_file", counting)
    first = env.database_info(db)
    second = env.database_info(db)
    assert first["doi"] == "10.6084/m9.figshare.31073554"
    assert first["schema_version"] == 5
    assert first["compound_count"] == 3
    assert first["sha256"] == second["sha256"]
    assert len(calls) == 1


def test_database_info_none() -> None:
    assert env.database_info(None)["path"] is None


def test_skill_file_hashes(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "SKILL.md").write_text('name: demo\n  version: "1.2"\n')
    (tmp_path / "sub" / "a.md").write_text("a")
    (tmp_path / "link.md").symlink_to(tmp_path / "SKILL.md")
    hashes = env.skill_file_hashes(tmp_path)
    assert set(hashes) == {"SKILL.md", "sub/a.md"}
    info = env.skill_info(tmp_path)
    assert info["name"] == "demo"
    assert info["version"] == "1.2"


def test_detect_harness() -> None:
    assert env.detect_harness({"CLAUDECODE": "1"}) == "claude-code"
    assert env.detect_harness({"AILSA_HARNESS": "opencode"}) == "opencode"
    assert env.detect_harness({}) == "other"


def test_probe_environment_keys(
    shim_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(env, "resolve_database_path", lambda: None)
    make_shim(shim_path, "LSD", "#!/bin/sh\necho 'LSD-3.4.9'\nexit 1\n")
    out = env.probe_environment(mode="blind", harness="other")
    for key in REQUIRED_PAYLOAD["env.captured"]:
        assert key in out
    assert "python" in out
    assert out["lsd"]["version"] == "3.4.9"
    assert "PATH" not in str(out)


def _packaged_frontier() -> Path:
    from ailsa.record.runinit import _packaged_skill

    path = _packaged_skill("ailsa")
    assert path is not None
    return path


def _index_version(skill: Path) -> str:
    import re

    text = (skill / "INDEX.md").read_text(encoding="utf-8")
    found = re.search(r'^\s+version:\s*"?([^"\n]+)"?', text, re.MULTILINE)
    assert found
    return found.group(1).strip()


def install_command_skill(root: Path, *, link: bool) -> None:
    import shutil

    pkg = _packaged_frontier()
    (root / "commands").mkdir(parents=True)
    (root / "agents").mkdir()
    (root / "ailsa").mkdir()

    def put(src: Path, dst: Path) -> None:
        if link:
            dst.symlink_to(src)
        elif src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

    put(pkg / "commands", root / "commands" / "ailsa")
    put(pkg / "references", root / "ailsa" / "references")
    put(pkg / "INDEX.md", root / "ailsa" / "INDEX.md")
    for agent in sorted((pkg / "agents").glob("*.md")):
        put(agent, root / "agents" / agent.name)


def _expected_packaged() -> dict[str, str]:
    hashes = env.skill_file_hashes(_packaged_frontier())
    return {k: v for k, v in hashes.items() if k != "CHANGELOG.md"}


def test_skill_info_reads_index_md() -> None:
    pkg = _packaged_frontier()
    info = env.skill_info(pkg)
    assert info["name"] == "ailsa"
    assert info["version"] == _index_version(pkg)
    assert info["files"] == env.skill_file_hashes(pkg)


def test_skill_info_lean_still_reads_skill_md(tmp_path: Path) -> None:
    (tmp_path / "SKILL.md").write_text('name: lean\n  version: "0.3"\n')
    (tmp_path / "INDEX.md").write_text('name: other\n  version: "9"\n')
    info = env.skill_info(tmp_path)
    assert (info["name"], info["version"]) == ("lean", "0.3")


@pytest.mark.parametrize("link", [True, False])
def test_command_skill_files_link_and_copy(tmp_path: Path, link: bool) -> None:
    root = tmp_path / ".claude"
    install_command_skill(root, link=link)
    got = env.command_skill_files(root)
    assert got == _expected_packaged()
    assert "INDEX.md" in got and any(k.startswith("agents/") for k in got)


def test_command_skill_files_none_when_not_installed(tmp_path: Path) -> None:
    assert env.command_skill_files(tmp_path / ".claude") is None
