"""Workspace, config and run folder creation."""

from __future__ import annotations

import json
import re
import stat
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ailsa.record import workspace as wsp


def test_env_wins_and_folder_created(workspace: Path) -> None:
    root = wsp.workspace_root()
    assert root == workspace
    assert root.is_dir()
    assert stat.S_IMODE(root.stat().st_mode) == 0o700


def test_config_workspace_then_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, workspace: Path
) -> None:
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"workspace": str(tmp_path / "from-config")}))
    monkeypatch.delenv("AILSA_WORKSPACE")
    assert wsp.workspace_root() == tmp_path / "from-config"
    cfg.unlink()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert wsp.workspace_root(create=False) == Path(str(tmp_path / "home")) / "ailsa-runs"


def test_invalid_config_warns_once(tmp_path: Path, workspace: Path, capsys) -> None:
    (tmp_path / "config.json").write_text("{not json")
    assert wsp.load_config() == {}
    assert capsys.readouterr().err.count("warning") == 1


def test_missing_config_is_empty(workspace: Path) -> None:
    assert wsp.load_config() == {}


def test_dropbox_warning() -> None:
    assert wsp.workspace_warnings("/x/Dropbox/runs")
    assert not wsp.workspace_warnings("/x/runs")


def test_mint_run_id_form() -> None:
    now = datetime(2026, 11, 24, 14, 17, tzinfo=timezone.utc)
    assert re.match(r"^2026-11-24T1417Z_terpineol_[a-z0-9]{4}$", wsp.mint_run_id("terpineol", now))


def test_sanitize_label() -> None:
    out = wsp.sanitize_label("a b/c..d")
    assert re.fullmatch(r"[A-Za-z0-9._-]+", out)
    assert wsp.sanitize_label("") != ""
    assert wsp.sanitize_label("---..x")[0] not in ".-"
    assert len(wsp.sanitize_label("x" * 100)) <= 40
    assert wsp.sanitize_label("/../..") not in ("", ".", "..")


def test_create_run_dir_unique_under_threads(workspace: Path) -> None:
    now = datetime(2026, 11, 24, 14, 17, tzinfo=timezone.utc)
    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(lambda _: wsp.create_run_dir(workspace, "same", now), range(20)))
    assert len({rid for rid, _ in results}) == 20
    for rid, path in results:
        assert stat.S_IMODE(path.stat().st_mode) == 0o700
        assert (path / "agent").is_dir()
        marker = json.loads((path / ".ailsa-run").read_text())
        assert marker == {"run_id": rid, "schema_version": 1}


def test_find_run(workspace: Path, new_run: tuple[str, Path]) -> None:
    rid, path = new_run
    assert wsp.find_run(workspace, rid) == path
    assert wsp.find_run(workspace, str(path)) == path
    assert wsp.find_run(workspace, "../" + rid) is None
    assert wsp.find_run(workspace, ".sessions") is None
    assert wsp.find_run(workspace, "a/b") is None


def test_workspace_lock_times_out(workspace: Path) -> None:
    root = wsp.workspace_root()
    with wsp.workspace_lock(root):
        with pytest.raises(TimeoutError):
            with wsp.workspace_lock(root, timeout=0.1):
                pass
    with wsp.workspace_lock(root, timeout=0.5):
        pass


def test_host_alias_from_config(tmp_path: Path, workspace: Path) -> None:
    (tmp_path / "config.json").write_text(json.dumps({"host_alias": "Vitus Box"}))
    assert re.fullmatch(r"[a-z0-9._-]+", wsp.host_alias())
