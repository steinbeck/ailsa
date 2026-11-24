"""REC-31: remote solves over a fake ssh (no network, no real solver)."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest

from ailsa.record import remote
from ailsa.record.remote import RemoteUnreachable, solve_remote, stage_inputs, validate_alias

from ._fake_lsd import install_fake_lsd
from ._fake_ssh import install_fake_ssh

LSD_TEXT = """; tiny generic input
MULT 1 C 3 3
MULT 2 C 3 2
MULT 3 O 3 1
"""


@pytest.fixture
def fake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fake remote root with fake LSD in it; ssh on the local PATH, LSD not."""
    root = tmp_path / "remote"
    ssh_bin = install_fake_ssh(tmp_path / "sshbin", root)
    monkeypatch.setenv("PATH", f"{ssh_bin}:/usr/bin:/bin")
    monkeypatch.setenv("AILSA_REMOTE_POLL_S", "0.2")
    monkeypatch.setenv("AILSA_CONFIG", str(tmp_path / "config.json"))
    install_fake_lsd(root / "bin", "solutions", count=3)
    return root


@pytest.fixture
def work(tmp_path: Path) -> Path:
    d = tmp_path / "it"
    d.mkdir()
    (d / "compound.lsd").write_text(LSD_TEXT)
    return d


def _calls(root: Path) -> list[list[str]]:
    log = root / "ssh-calls.log"
    return [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []


def _scratch_dirs(root: Path) -> list[Path]:
    return sorted((root / "tmp").glob("ailsa-lsd.*"))


@pytest.mark.parametrize("alias", ["sheldon", "ara2", "host-1.lab"])
def test_alias_accepted(alias: str) -> None:
    assert validate_alias(alias) == alias


@pytest.mark.parametrize("alias", ["-oProxyCommand=x", "a b", "", "x;rm", "../h"])
def test_alias_rejected(alias: str) -> None:
    with pytest.raises(ValueError):
        validate_alias(alias)


def test_stage_inputs_copies_filters_and_deff(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "extra").write_text("filter")
    (src / "c.lsd").write_text('MULT 1 C 3 3\nDEFF F1 "ring3"\nDEFF F3 "extra"\n; DEFF F9 "../x"\n')
    stage = tmp_path / "stage"
    names = stage_inputs(src / "c.lsd", stage)
    assert names == ["c.lsd", "ring3", "ring4", "extra"]
    assert (stage / "extra").read_text() == "filter"


@pytest.mark.parametrize("bad", ["../secret", "/etc/passwd"])
def test_stage_inputs_refuses_traversal(tmp_path: Path, bad: str) -> None:
    src = tmp_path / "c.lsd"
    src.write_text(f'MULT 1 C 3 3\nDEFF F1 "{bad}"\n')
    with pytest.raises(ValueError):
        stage_inputs(src, tmp_path / "stage")


def test_solve_remote_solutions(fake: Path, work: Path) -> None:
    res = solve_remote("fakehost", work / "compound.lsd", work, timeout_s=30)
    assert res.host == "fakehost" and res.outcome == "solutions" and res.count == 3
    assert res.lsd["version"] == "3.4.9" and len(res.lsd["sha256"]) == 64
    assert res.outlsd["sha256"] and res.outlsd["version"] is None
    assert res.elapsed_s > 0 and res.scratch_dir is None
    for name in ("compound.sol", "solncounter", "lsd.out", "lsd.err", "solutions.smi"):
        assert (work / name).is_file(), name
    assert _scratch_dirs(fake) == []
    assert "path" in res.lsd and "/" not in (res.lsd["path"] or "")


def test_lowercase_binary_only(fake: Path, work: Path) -> None:
    (fake / "bin" / "LSD").unlink()
    if not (fake / "bin" / "lsd").exists():
        pytest.skip("case-insensitive file system: LSD and lsd are one file")
    probe = remote.probe_remote("fakehost", {})
    assert probe["lsd"]["version"] == "3.4.9"
    remote._cleanup("fakehost", probe["root"], probe["scratch"])


def test_config_override_wins(fake: Path, work: Path, tmp_path: Path) -> None:
    other = install_fake_lsd(tmp_path / "otherbin", "solutions", count=2)
    cfg = {"hosts": {"fakehost": {"lsd": str(other / "lsd"), "outlsd": str(other / "outlsd")}}}
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    res = solve_remote("fakehost", work / "compound.lsd", work, timeout_s=30)
    assert res.count == 2 and res.outcome == "solutions"


def test_timeout_kills_remote(tmp_path: Path, fake: Path, work: Path) -> None:
    install_fake_lsd(fake / "bin", "sleep", seconds=30, partial=12)
    t0 = time.monotonic()
    res = solve_remote("fakehost", work / "compound.lsd", work, timeout_s=1)
    assert time.monotonic() - t0 < 25
    assert res.outcome == "timeout" and res.timed_out and res.partial_count == 12
    time.sleep(0.5)
    left = subprocess.run(
        ["pgrep", "-f", str(fake / "bin" / "lsd")], capture_output=True, text=True
    )
    assert left.stdout.strip() == ""
    assert _scratch_dirs(fake) == []


def test_error_outcome(fake: Path, work: Path) -> None:
    install_fake_lsd(fake / "bin", "error", code=420)
    res = solve_remote("fakehost", work / "compound.lsd", work, timeout_s=30)
    assert res.outcome == "error" and "420" in (res.error_line or "")


def test_fetch_failure_keeps_scratch(fake: Path, work: Path, monkeypatch) -> None:
    def boom(*a, **k):
        raise remote.RemoteError("bad archive")

    monkeypatch.setattr(remote, "_extract_outputs", boom)
    res = solve_remote("fakehost", work / "compound.lsd", work, timeout_s=30)
    assert res.scratch_dir is not None and Path(res.scratch_dir).is_dir()
    assert res.outcome == "error"
    assert len(_scratch_dirs(fake)) == 1


def test_unreachable(fake: Path, work: Path) -> None:
    with pytest.raises(RemoteUnreachable):
        solve_remote("unreachable", work / "compound.lsd", work, timeout_s=5)


def test_ssh_argv_shape(fake: Path, work: Path) -> None:
    solve_remote("fakehost", work / "compound.lsd", work, timeout_s=30)
    calls = _calls(fake)
    assert calls
    for argv in calls:
        assert argv[:4] == ["-o", "BatchMode=yes", "-o", "ConnectTimeout=15"]
        assert argv[4:6] == ["--", "fakehost"]
        assert argv[6].startswith("bash -lc ")


def test_rm_only_for_mktemp_names() -> None:
    assert remote._scratch_ok("/var/t", "/var/t/ailsa-lsd.Ab12Cd")
    assert not remote._scratch_ok("/var/t", "/var/t/other")
    assert not remote._scratch_ok("/var/t", "/var/ailsa-lsd.Ab12Cd")
    assert not remote._scratch_ok("/var/t", "/var/t/../ailsa-lsd.Ab12Cd")
    assert not remote._cleanup("fakehost", "/var/t", "/")


def test_extract_refuses_traversal(tmp_path: Path) -> None:
    import io
    import tarfile

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        info = tarfile.TarInfo("../evil")
        info.size = 1
        tar.addfile(info, io.BytesIO(b"x"))
    with pytest.raises(remote.RemoteError):
        remote._extract_outputs(buf.getvalue(), tmp_path, {"lsd.out"})


# --- ailsa lsd run --host -------------------------------------------------------------------


@pytest.fixture
def run_env(new_run, fake: Path, monkeypatch: pytest.MonkeyPatch):
    _, run_dir = new_run
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    it = run_dir / "agent" / "iteration_01"
    it.mkdir(parents=True)
    (it / "compound.lsd").write_text(LSD_TEXT)
    monkeypatch.chdir(it)
    return run_dir, it


def _lsd_run(*args: str):
    from click.testing import CliRunner

    from ailsa.cli.lsd import lsd

    return CliRunner().invoke(lsd, ["run", *args])


def _events(run_dir: Path) -> list[dict]:
    from ailsa.record.log import read_events

    return read_events(run_dir)["events"]


def test_run_host_registers_locally(run_env, fake: Path) -> None:
    run_dir, it = run_env
    res = _lsd_run("compound.lsd", "--host", "fakehost", "--format", "json")
    assert res.exit_code == 0, res.output
    data = json.loads(res.stdout)
    assert data["host"] == "fakehost" and data["outcome"] == "solutions"
    assert data["iteration"] == "it01" and data["partial_count"] is None
    assert data["elapsed_s"] >= 0 and data["solution_count"] == 3
    for key in ("success", "return_code", "output_files", "stderr"):
        assert key in data
    events = _events(run_dir)
    started = next(e for e in events if e["type"] == "solver.started")["payload"]
    assert started["host"] == "fakehost" and started["remote"] is True
    fin = next(e for e in events if e["type"] == "solver.finished")["payload"]
    assert fin["host"] == "fakehost" and fin["outcome"] == "solutions" and fin["count"] == 3
    assert fin["provenance"] == "run"
    assert fin["lsd"]["version"] == "3.4.9" and len(fin["lsd"]["sha256"]) == 64
    solver = json.loads((run_dir / "iterations" / "it01" / "solver.json").read_text())
    assert solver["remote"] is True and solver["host"] == "fakehost"
    assert (it / "compound.sol").is_file() and (it / "solutions.smi").is_file()
    assert _scratch_dirs(fake) == []
    # the fake remote side only ever touched its own root
    assert not any(run_dir.rglob("ssh-calls.log"))


def test_run_host_outside_run(fake: Path, work: Path, monkeypatch) -> None:
    monkeypatch.delenv("AILSA_RUN_DIR", raising=False)
    monkeypatch.chdir(work)
    res = _lsd_run("compound.lsd", "--host", "fakehost", "--format", "json")
    assert res.exit_code == 0, res.output
    data = json.loads(res.stdout)
    assert data["host"] == "fakehost" and "iteration" not in data


def test_run_host_invalid_alias(run_env, fake: Path) -> None:
    res = _lsd_run("compound.lsd", "--host", "-oProxyCommand=x")
    assert res.exit_code == 1
    assert _calls(fake) == []
    assert not [e for e in _events(run_env[0]) if e["type"] == "solver.started"]


def test_run_host_unreachable_records_not_run(run_env) -> None:
    run_dir, _ = run_env
    res = _lsd_run("compound.lsd", "--host", "unreachable")
    assert res.exit_code == 1
    assert "Error: cannot reach host unreachable" in res.stderr
    fin = next(e for e in _events(run_dir) if e["type"] == "solver.finished")["payload"]
    assert fin["outcome"] == "not_run" and fin["host"] == "unreachable"
    assert fin["error_line"] == "cannot reach host unreachable"
