"""init_run: create or reuse a run, blind refusal, binding, index, view child."""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from ailsa.record import env as record_env
from ailsa.record.fingerprint import dataset_fingerprint
from ailsa.record.log import read_events
from ailsa.record.runinit import (
    NOT_BLIND_REASON,
    InitRefused,
    init_run,
    rebuild_index,
)

from .test_spectra_export import make_1d


@pytest.fixture(autouse=True)
def _no_database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Never hash a real reference database during init tests."""
    monkeypatch.setattr(record_env, "resolve_database_path", lambda: None)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))


def _dataset(tmp_path: Path, name: str = "example") -> Path:
    ds = tmp_path / name
    make_1d(ds, "1")
    return ds


def _init(ds: Path, **kw: Any) -> dict[str, Any]:
    kw.setdefault("views", False)
    return init_run(ds, **kw)


def _types(run_dir: str | Path) -> list[str]:
    return [e["type"] for e in read_events(run_dir)["events"]]


def _created(run_dir: str | Path) -> dict[str, Any]:
    return read_events(run_dir)["events"][0]["payload"]


def test_init_creates_run(workspace: Path, tmp_path: Path) -> None:
    ds = _dataset(tmp_path)
    res = _init(ds, label="example")
    run = Path(res["run_dir"])
    assert res["created"] is True and res["views_pid"] is None
    assert run.parent == workspace.resolve()
    assert run.name.split("_")[1] == "example"
    assert oct(run.stat().st_mode & 0o777) == "0o700"
    assert (run / "agent").is_dir() and res["work_dir"] == str(run / "agent")
    assert _types(run)[:3] == ["run.created", "env.captured", "spectra.scanned"]
    assert (run / "spectra" / "inventory.json").is_file()
    payload = _created(run)
    assert payload["dataset"]["fingerprint"].startswith("sha256:")
    assert payload["dataset"]["label"] == "example"
    assert payload["class"] == "internal"
    scanned = read_events(run)["events"][2]["payload"]
    assert scanned["experiments"][0]["id"] and "readable" in scanned["experiments"][0]


def test_dataset_path_carries_no_home_folder(
    workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WR-13: home-relative dataset path; a public record names only the folder."""
    monkeypatch.setenv("HOME", str(tmp_path))
    ds = _dataset(tmp_path / "data")
    internal = _created(_init(ds, args=[str(ds), "--prompt", f"look at {ds}"])["run_dir"])
    assert internal["dataset"]["path"] == "~/data/example"
    assert internal["request"]["args"] == ["~/data/example", "--prompt", "look at ~/data/example"]
    public = _created(_init(ds, run_class="public")["run_dir"])
    assert public["dataset"]["path"] == "example"


def test_run_folder_outside_dataset_and_dataset_unchanged(workspace: Path, tmp_path: Path) -> None:
    ds = _dataset(tmp_path)
    before = dataset_fingerprint(ds)
    listing = sorted(p.name for p in ds.rglob("*"))
    res = _init(ds)
    assert ds.resolve() not in Path(res["run_dir"]).parents
    assert dataset_fingerprint(ds) == before
    assert sorted(p.name for p in ds.rglob("*")) == listing


def test_blind_uses_dataset_folder_name(workspace: Path, tmp_path: Path) -> None:
    ds = _dataset(tmp_path, "CASE999")
    res = _init(ds, blind=True, label="something-revealing")
    assert "CASE999" in res["run_id"] and "revealing" not in res["run_id"]
    manifest_label = _created(res["run_dir"])["dataset"]["label"]
    assert manifest_label == "CASE999"
    assert _created(res["run_dir"])["dataset"]["blind"] is True


def test_blind_refused_after_prior_run(workspace: Path, tmp_path: Path) -> None:
    ds = _dataset(tmp_path, "CASE1")
    first = _init(ds)
    renamed = tmp_path / "renamed"
    shutil.copytree(ds, renamed)
    before = sorted(p.name for p in workspace.iterdir())
    with pytest.raises(InitRefused) as info:
        _init(renamed, blind=True)
    assert info.value.code == "prior_runs"
    message = str(info.value)
    assert "1 earlier run" in message and first["run_id"] in message
    assert "--allow-prior-runs" in message
    assert sorted(p.name for p in workspace.iterdir()) == before


def test_blind_allowed_marks_not_blind(workspace: Path, tmp_path: Path) -> None:
    ds = _dataset(tmp_path, "CASE2")
    _init(ds)
    res = _init(ds, blind=True, allow_prior_runs=True)
    payload = _created(res["run_dir"])
    assert payload["prior_runs"]["allowed"] is True and payload["prior_runs"]["found"] == 1
    assert payload["not_blind_reason"] == NOT_BLIND_REASON
    assert payload["dataset"]["blind"] is False


def test_blind_refused_for_legacy_results(workspace: Path, tmp_path: Path) -> None:
    ds = _dataset(tmp_path, "CASE3")
    (ds / "analysis").mkdir()
    (ds / "analysis" / "final_results.md").write_text("earlier result\n")
    with pytest.raises(InitRefused) as info:
        _init(ds, blind=True)
    assert info.value.code == "legacy_results"
    assert "analysis" in str(info.value)
    assert not list(p for p in workspace.iterdir() if p.is_dir() and p.name[0].isdigit())
    res = _init(ds, blind=True, allow_prior_runs=True)
    assert _created(res["run_dir"])["not_blind_reason"] == NOT_BLIND_REASON


def test_non_blind_with_prior_runs_starts(workspace: Path, tmp_path: Path) -> None:
    ds = _dataset(tmp_path)
    _init(ds)
    res = _init(ds)
    payload = _created(res["run_dir"])
    assert payload["prior_runs"]["found"] == 1 and payload["not_blind_reason"] is None


_CONCURRENT = """
import sys
import ailsa.record.env as e
e.resolve_database_path = lambda: None
from ailsa.record.runinit import init_run, InitRefused
try:
    init_run(sys.argv[1], blind=True, views=False)
    print("OK")
except InitRefused as exc:
    print("REFUSED", exc.code)
"""


def test_concurrent_blind_starts_one_wins(workspace: Path, tmp_path: Path) -> None:
    ds = _dataset(tmp_path, "CASE4")
    env = {**os.environ, "AILSA_WORKSPACE": str(workspace), "XDG_CACHE_HOME": str(tmp_path / "c")}
    procs = [
        subprocess.Popen(
            [sys.executable, "-c", _CONCURRENT, str(ds)],
            stdout=subprocess.PIPE,
            text=True,
            env=env,
        )
        for _ in range(2)
    ]
    outs = [p.communicate(timeout=60)[0].strip() for p in procs]
    assert sorted(o.split()[0] for o in outs) == ["OK", "REFUSED"]
    runs = [p for p in workspace.iterdir() if p.is_dir() and (p / ".ailsa-run").exists()]
    assert len(runs) == 1


def test_session_reuse_is_idempotent(
    workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "session-abcdef123456")
    ds = _dataset(tmp_path)
    first = _init(ds)
    assert "run.bound" in _types(first["run_dir"])
    again = _init(ds)
    assert again["created"] is False
    assert again["run_id"] == first["run_id"] and again["work_dir"] == first["work_dir"]
    assert len([p for p in workspace.iterdir() if p.name.startswith("20")]) == 1


def test_session_bound_to_other_dataset_refused(
    workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "session-abcdef123456")
    first = _init(_dataset(tmp_path, "one"))
    other = tmp_path / "two"
    make_1d(other, "1")
    (other / "1" / "extra").write_text("different content\n")
    with pytest.raises(InitRefused) as info:
        _init(other)
    assert info.value.code == "bound_elsewhere"
    assert first["run_id"] in str(info.value) and "another dataset" in str(info.value)


def test_launcher_run_dir_is_reused(
    workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ds = _dataset(tmp_path)
    first = _init(ds)
    monkeypatch.setenv("AILSA_RUN_DIR", first["run_dir"])
    before = sorted(p.name for p in workspace.iterdir())
    again = _init(ds)
    assert again["created"] is False and again["run_id"] == first["run_id"]
    assert sorted(p.name for p in workspace.iterdir()) == before


def test_overlap_refused(workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ds = _dataset(tmp_path)
    monkeypatch.setenv("AILSA_WORKSPACE", str(ds / "runs"))
    with pytest.raises(InitRefused) as info:
        _init(ds)
    assert info.value.code == "overlap"
    assert str(ds.resolve()) in str(info.value) and "runs" in str(info.value)
    monkeypatch.setenv("AILSA_WORKSPACE", str(tmp_path))
    with pytest.raises(InitRefused):
        _init(ds)


def test_not_a_dataset(workspace: Path, tmp_path: Path) -> None:
    with pytest.raises(InitRefused) as info:
        _init(tmp_path / "missing")
    assert info.value.code == "not_a_dataset"


def test_confidential_records_unknown_web_tools(workspace: Path, tmp_path: Path) -> None:
    res = _init(_dataset(tmp_path), run_class="confidential", web_tools="disabled")
    env_event = read_events(res["run_dir"])["events"][1]
    assert env_event["type"] == "env.captured"
    assert env_event["payload"]["web_tools"] == "unknown"
    assert any("ailsa run start" in w for w in res["warnings"])


def test_formula_sources(workspace: Path, tmp_path: Path) -> None:
    ds = _dataset(tmp_path)
    assert _created(_init(ds)["run_dir"])["dataset"]["formula"] is None
    given = _created(_init(ds, formula="C2H6O")["run_dir"])["dataset"]
    assert (given["formula"], given["formula_source"]) == ("C2H6O", "request")


def test_formula_sidecar(workspace: Path, tmp_path: Path) -> None:
    from ailsa.case.scan import FORMULA_FILES

    ds = _dataset(tmp_path)
    (ds / FORMULA_FILES[0]).write_text("C3H8O\n")
    dataset = _created(_init(ds)["run_dir"])["dataset"]
    assert dataset["formula"] == "C3H8O"
    assert dataset["formula_source"] == f"sidecar:{FORMULA_FILES[0]}"


def test_index_updated_and_rebuilt(workspace: Path, tmp_path: Path) -> None:
    ds = _dataset(tmp_path)
    one = _init(ds)
    two = _init(ds)
    data = json.loads((workspace / "runs.json").read_text())
    ids = [r["run_id"] for r in data["runs"]]
    assert sorted(ids) == sorted([one["run_id"], two["run_id"]])
    entry = data["runs"][0]
    assert set(entry) >= {"run_id", "label", "created_utc", "fingerprint", "blind", "state"}
    (workspace / "runs.json").unlink()
    rebuilt = rebuild_index(workspace)
    assert sorted(r["run_id"] for r in rebuilt) == sorted(ids)
    assert all(r["state"] == "running" for r in rebuilt)
    assert (workspace / "runs.json").is_file()


def test_view_export_child_finishes_and_leaves_events(
    workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ds = _dataset(tmp_path)
    # CR-01: the child inherits the caller's working folder; a module planted there must not run.
    project = tmp_path / "project"
    project.mkdir()
    marker = tmp_path / "planted-module-ran"
    (project / "json.py").write_text(f"open({str(marker)!r}, 'w').close()\n", encoding="utf-8")
    monkeypatch.chdir(project)
    res = init_run(ds, views=True)
    pid = res["views_pid"]
    assert isinstance(pid, int)
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            try:
                done, _ = os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                done = pid
            if done:
                break
            time.sleep(0.2)
        else:
            pytest.fail("view export child did not exit within 30 s")
    finally:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    assert not marker.exists()
    assert "spectrum.processed" in _types(res["run_dir"])


def _install_frontier(home: Path, *, link: bool) -> None:
    from .test_env import install_command_skill

    install_command_skill(home / ".claude", link=link)


def test_skill_location_link_install_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ailsa.record.runinit import _skill_location

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    _install_frontier(tmp_path / "home", link=True)
    _, label, same, installed = _skill_location("ailsa")
    assert (label, same) == ("global-claude-commands", True)
    assert installed and "CHANGELOG.md" not in installed


def test_skill_location_differing_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from ailsa.record.runinit import _skill_location

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    _install_frontier(tmp_path / "home", link=False)
    agent = next((tmp_path / "home" / ".claude" / "agents").glob("ailsa-*.md"))
    agent.write_text(agent.read_text() + "\nlocal edit\n")
    _, label, same, _ = _skill_location("ailsa")
    assert (label, same) == ("global-claude-commands", False)


def test_skill_location_absent_falls_back_to_packaged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ailsa.record.runinit import _packaged_skill, _skill_location

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    assert _skill_location("ailsa") == (_packaged_skill("ailsa"), "packaged", True, None)


def test_env_captured_for_frontier_skill(
    workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from .test_env import _index_version, _packaged_frontier

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    _install_frontier(tmp_path / "home", link=True)
    res = _init(_dataset(tmp_path), skill="ailsa")
    payload = read_events(res["run_dir"])["events"][1]["payload"]
    assert payload["skill"]["name"] == "ailsa"
    assert payload["skill"]["version"] == _index_version(_packaged_frontier())
    assert payload["skill_location"] == "global-claude-commands"
    assert payload["skill_matches_packaged"] is True
    assert "CHANGELOG.md" not in payload["skill"]["files"]


def test_env_captured_reports_the_installed_version(
    workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A copy install of another version: the record names the version that ran."""
    from .test_env import _index_version, _packaged_frontier

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    _install_frontier(tmp_path / "home", link=False)
    index = tmp_path / "home" / ".claude" / "ailsa" / "INDEX.md"
    packaged = _index_version(_packaged_frontier())
    index.write_text(index.read_text().replace(f'version: "{packaged}"', 'version: "0.0.1"'))
    res = _init(_dataset(tmp_path), skill="ailsa")
    payload = read_events(res["run_dir"])["events"][1]["payload"]
    assert payload["skill"]["version"] == "0.0.1"
    assert payload["skill"]["packaged_version"] == packaged
    assert payload["skill_matches_packaged"] is False


def test_skill_location_honours_claude_config_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ailsa.record.runinit import _skill_location

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    _install_frontier(tmp_path / "home", link=True)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cfg"))
    assert _skill_location("ailsa")[1] == "packaged"  # ~/.claude is not where Claude Code looks
    from .test_env import install_command_skill

    install_command_skill(tmp_path / "cfg", link=True)
    _, label, same, installed = _skill_location("ailsa")
    assert (label, same) == ("global-claude-commands", True)
    assert installed
