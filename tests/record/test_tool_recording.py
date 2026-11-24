"""Every tool call inside a run records itself; outside a run nothing changes."""

from __future__ import annotations

import fcntl
import hashlib
import os
from collections.abc import Iterator
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from ailsa.cli.main import cli
from ailsa.record import resolve, toolrec
from ailsa.record.events import EVENTS_LOCK
from ailsa.record.log import read_events

LINE = '{"ok": true}\n'


@click.command("rectest")
@click.argument("rest", nargs=-1)
@click.option("--code", type=int, default=0)
def _rectest(rest: tuple[str, ...], code: int) -> None:
    click.echo(LINE, nl=False)
    if code:
        raise SystemExit(code)


@click.command("run")
def _fake_run() -> None:
    click.echo("x")


@pytest.fixture(autouse=True)
def _commands() -> Iterator[None]:
    resolve._warned = False
    cli.add_command(_rectest, "rectest")
    saved = cli._loaded.get("run")
    cli._loaded["run"] = _fake_run
    yield
    cli._loaded.pop("rectest", None)
    if saved is not None:
        cli._loaded["run"] = saved
    else:
        cli._loaded.pop("run", None)


def _invoke(args: list[str], **kw):
    return CliRunner().invoke(cli, args, **kw)


def _tool_events(run_dir: Path) -> list[dict]:
    return [e for e in read_events(run_dir)["events"] if e["type"] == "tool.invoked"]


def test_outside_run_identical(workspace: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    direct = CliRunner().invoke(_rectest, [])
    result = _invoke(["rectest"])
    assert result.stdout == direct.stdout == LINE
    assert result.stderr == ""
    assert not list(workspace.glob("*/events.jsonl"))


def test_inside_run_records(workspace: Path, new_run, monkeypatch, tmp_path: Path) -> None:
    _, run_dir = new_run
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    result = _invoke(["rectest", "a", "b"])
    assert result.stdout == LINE and result.stderr == ""
    events = _tool_events(run_dir)
    assert len(events) == 1
    payload = events[0]["payload"]
    assert payload["argv"] == ["rectest", "a", "b"]
    assert payload["exit_code"] == 0 and payload["duration_s"] >= 0
    assert payload["stdout_bytes"] == len(LINE)
    assert payload["stdout_sha256"] == hashlib.sha256(LINE.encode()).hexdigest()
    assert payload["cwd"] == "outside run"
    assert events[0]["actor"]["name"] == "ailsa rectest a"


def test_exit_code_recorded_and_kept(workspace: Path, new_run, monkeypatch) -> None:
    _, run_dir = new_run
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    result = _invoke(["rectest", "--code", "3"])
    assert result.exit_code == 3
    assert _tool_events(run_dir)[0]["payload"]["exit_code"] == 3


def test_excluded_and_help_not_recorded(workspace: Path, new_run, monkeypatch) -> None:
    _, run_dir = new_run
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    assert _invoke(["run"]).stdout == "x\n"
    _invoke(["rectest", "--help"])
    _invoke(["--version"])
    assert _tool_events(run_dir) == []


def test_lock_held_command_still_works(workspace: Path, new_run, monkeypatch) -> None:
    _, run_dir = new_run
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    monkeypatch.setattr(toolrec, "LOCK_TIMEOUT", 0.2)
    fd = os.open(run_dir / EVENTS_LOCK, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        result = _invoke(["rectest"])
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    assert result.exit_code == 0 and result.stdout == LINE
    assert result.stderr.startswith("ailsa: record write failed:")
    assert result.stderr.count("\n") == 1


def test_require_run_without_run(workspace: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AILSA_REQUIRE_RUN", "1")
    result = _invoke(["rectest"])
    assert result.exit_code == 0 and result.stdout == LINE
    assert result.stderr.startswith("ailsa: not recorded: no active run")
    assert result.stderr.count("\n") == 1
