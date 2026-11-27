"""`ailsa run start`: the launcher, with a fake `claude` shim on PATH (never the real one)."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from ailsa.cli.run import run
from ailsa.record import env as record_env
from ailsa.record import launcher
from ailsa.record.hooksettings import build_settings
from ailsa.record.launcher import build_argv, default_prompt
from ailsa.record.log import read_events

from .conftest import make_shim
from .test_spectra_export import make_1d

SHIM = f"""#!{sys.executable}
import json, os, signal, subprocess, sys, time
argv = sys.argv[1:]
if argv == ["--version"]:
    print("9.9.9 (fake)")
    sys.exit(0)
keep = ("AILSA", "CLAUDE", "PATH")
info = {{
    "argv": sys.argv[1:],
    "cwd": os.getcwd(),
    "pid": os.getpid(),
    "env": {{k: v for k, v in os.environ.items() if k.startswith(keep)}},
}}
with open(os.environ["FAKE_CLAUDE_OUT"], "w") as fh:
    json.dump(info, fh)
with open(os.environ["FAKE_CLAUDE_OUT"] + ".calls", "a") as fh:
    fh.write(json.dumps(info) + "\\n")
modes = os.environ.get("FAKE_CLAUDE_MODE", "").split(",")
sid = argv[argv.index("--session-id") + 1] if "--session-id" in argv else None
if "transcript" in modes and sid:
    folder = os.path.join(os.environ["AILSA_CLAUDE_PROJECTS"], "p")
    os.makedirs(folder, exist_ok=True)
    line = {{"type": "assistant", "message": {{"model": "claude-fake"}}, "requestedModel": "fake"}}
    with open(os.path.join(folder, sid + ".jsonl"), "w") as fh:
        fh.write(json.dumps(line) + "\\n")
if "hook" in modes and sid:
    payload = {{"hook_event_name": "SessionEnd", "session_id": sid, "reason": "other"}}
    subprocess.run(
        [sys.executable, "-m", "ailsa.record.hook"],
        input=json.dumps(payload).encode(),
        env=os.environ,
    )

def _cli(*args):
    subprocess.run([sys.executable, "-m", "ailsa.cli", "run", *args], env=os.environ)


if "declare_on_resume" in modes and "--resume" in argv:
    _cli("finalize", "--outcome", "insufficient_data", "--termination-reason", "test")
if "close_first" in modes and "--resume" not in argv:
    _cli("close", "--reason", "test")
if "grandchild" in modes:
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    with open(os.environ["FAKE_CLAUDE_OUT"] + ".child", "w") as fh:
        fh.write(str(child.pid))
if "ignore_term" in modes:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
if "sleep" in modes or "ignore_term" in modes:
    time.sleep(60)
sys.exit(int(os.environ.get("FAKE_CLAUDE_EXIT", "0")))
"""


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, workspace: Path) -> None:
    monkeypatch.setattr(record_env, "resolve_database_path", lambda: None)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("AILSA_CLAUDE_PROJECTS", str(tmp_path / "projects"))
    monkeypatch.setenv("FAKE_CLAUDE_OUT", str(tmp_path / "shim.json"))
    monkeypatch.delenv("FAKE_CLAUDE_MODE", raising=False)


@pytest.fixture
def claude(shim_path: Path) -> Path:
    return make_shim(shim_path, "claude", SHIM)


@pytest.fixture
def dataset(tmp_path: Path) -> Path:
    ds = tmp_path / "example"
    make_1d(ds, "1")
    return ds


def _start(dataset: Path, *args: str) -> Any:
    base = ["start", str(dataset), "--no-views", "--format", "json"]
    return CliRunner().invoke(run, [*base, *args])


def _result(res: Any) -> dict[str, Any]:
    assert res.exit_code == 0, res.output + str(res.exception)
    return json.loads(res.stdout)


def _events(run_dir: str | Path) -> list[dict[str, Any]]:
    return read_events(run_dir)["events"]


def _of(events: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [e for e in events if e["type"] == kind]


def _shim(tmp_path: Path) -> dict[str, Any]:
    return json.loads((tmp_path / "shim.json").read_text())


# ---------------------------------------------------------------------------- argv


def test_build_argv_headless(tmp_path: Path) -> None:
    argv = build_argv(
        harness="claude",
        model="haiku",
        prompt="P",
        headless=True,
        run_dir=tmp_path / "r",
        dataset=tmp_path / "d",
        session_id="sid",
    )
    assert argv == [
        "claude",
        "-p",
        "P",
        "--model",
        "haiku",
        "--session-id",
        "sid",
        "--settings",
        str(tmp_path / "r" / "hooks.json"),
        "--add-dir",
        str(tmp_path / "d"),
        "--dangerously-skip-permissions",
    ]


def test_build_argv_confidential_extra_interactive_opencode(tmp_path: Path) -> None:
    common: dict[str, Any] = {
        "model": "m",
        "prompt": "P",
        "run_dir": tmp_path / "r",
        "dataset": tmp_path / "d",
        "session_id": "sid",
    }
    conf = build_argv(headless=True, confidential=True, extra=["--x"], **common)
    assert conf[-4:] == ["--disallowedTools", "WebFetch", "WebSearch", "--x"][-4:]
    assert "--disallowedTools" in conf and conf.index("WebFetch") == conf.index("WebSearch") - 1
    inter = build_argv(headless=False, **common)
    assert "-p" not in inter and inter[1] == "P"
    oc = build_argv(harness="opencode", headless=True, **common)
    assert oc == ["opencode", "run", "--model", "m", "P"]


def test_default_prompt_follows_slash_answer() -> None:
    assert default_prompt("/data/x", True) == "/ailsa-lite /data/x"
    assert "ailsa-lite skill" in default_prompt("/data/x", False)
    assert launcher.SLASH_PROMPT_WORKS is True


# ------------------------------------------------------------------------- runs


def test_headless_start_end_to_end(
    claude: Path, dataset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "transcript")
    res = _result(
        _start(
            dataset,
            "--model",
            "haiku",
            "--headless",
            "--time-limit",
            "30",
            "--class",
            "public",
            "--label",
            "example",
        )
    )
    assert set(res) >= {"run_id", "run_dir", "exit_code", "state"}
    assert res["exit_code"] == 0
    run_dir = Path(res["run_dir"])
    ev = _events(run_dir)
    types = [e["type"] for e in ev]
    assert types.index("run.created") < types.index("env.captured")
    assert types.index("run.attempt.started") < types.index("run.attempt.ended")
    assert types[-1] == "run.finished"
    created = _of(ev, "run.created")[0]["payload"]
    assert created["request"]["mode"] == "headless"
    assert created["request"]["harness"] == "claude-code"
    assert created["request"]["options"]["time_limit_s"] == 30
    assert created["request"]["prompt"] == f"/ailsa-lite {dataset.resolve()}"
    env = _of(ev, "env.captured")[0]["payload"]
    assert env["web_tools"] == "enabled"
    assert env["harness"]["version"] == "9.9.9 (fake)"
    started = _of(ev, "run.attempt.started")[0]["payload"]
    assert started["attempt"] == 1 and started["time_limit_s"] == 30
    ended = _of(ev, "run.attempt.ended")[0]["payload"]
    assert ended["exit_code"] == 0 and ended["reason"] == "exited"
    reported = [e["payload"] for e in _of(ev, "agent.model_reported")]
    assert {"agent": "main", "requested": "haiku", "actual": None, "source": "launcher"} in reported
    assert any(p["source"] == "transcript" for p in reported)
    copied = _of(ev, "transcript.copied")
    assert copied and copied[0]["payload"]["via"] == "launcher"
    assert json.loads((run_dir / "hooks.json").read_text()) == build_settings(
        sys.executable, auto_memory=False
    )
    assert (run_dir / "agent" / ".claude" / "skills" / "ailsa-lite" / "SKILL.md").is_file()
    assert (run_dir / "finished.json").is_file()
    assert (run_dir / "renderings" / "final_results.md").is_file()
    assert res["state"] == "stopped_before_result"
    info = _shim(tmp_path)
    assert info["cwd"] == str((run_dir / "agent").resolve())
    assert info["env"]["AILSA_RUN_DIR"] == str(run_dir)
    assert info["env"]["AILSA_REQUIRE_RUN"] == "1"
    assert info["env"]["AILSA_HOOKS_VIA_SETTINGS"] == "1"
    assert info["env"]["CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS"] == "15000"
    assert info["env"]["PATH"].startswith(str(Path(sys.executable).parent))
    assert info["argv"][0] == "-p" and "--session-id" in info["argv"]
    assert "--disallowedTools" not in info["argv"]


def test_launcher_is_not_bound_to_a_session(
    claude: Path, dataset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "outer-session-12345")
    res = _result(_start(dataset, "--model", "haiku"))
    ev = _events(res["run_dir"])
    # Only the launched session is bound (CR-05: its late hook events may still land after
    # close); the outer session that ran `ailsa run start` never is.
    bound = [e["payload"] for e in _of(ev, "run.bound")]
    assert [b["via"] for b in bound] == ["launcher"]
    argv = _shim(tmp_path)["argv"]
    assert bound[0]["session_id"] == argv[argv.index("--session-id") + 1]
    assert bound[0]["session_id"] != "outer-session-12345"
    assert "CLAUDE_CODE_SESSION_ID" not in _shim(tmp_path)["env"]


def test_confidential_removes_web_tools(claude: Path, dataset: Path, tmp_path: Path) -> None:
    res = _result(_start(dataset, "--model", "haiku", "--class", "confidential"))
    ev = _events(res["run_dir"])
    assert _of(ev, "env.captured")[0]["payload"]["web_tools"] == "disabled"
    assert not [
        e for e in _of(ev, "warning.raised") if e["payload"]["code"] == "web_tools_unknown"
    ]
    argv = _shim(tmp_path)["argv"]
    i = argv.index("--disallowedTools")
    assert argv[i + 1 : i + 3] == ["WebFetch", "WebSearch"]


def test_opencode_run(shim_path: Path, dataset: Path, tmp_path: Path) -> None:
    make_shim(shim_path, "opencode", SHIM)
    res = _result(_start(dataset, "--harness", "opencode", "--model", "prov/model"))
    run_dir = Path(res["run_dir"])
    ev = _events(run_dir)
    assert _of(ev, "env.captured")[0]["payload"]["web_tools"] == "unknown"
    assert (run_dir / "agent" / ".opencode" / "skills" / "ailsa-lite" / "SKILL.md").is_file()
    assert not (run_dir / "hooks.json").exists()
    argv = _shim(tmp_path)["argv"]
    assert argv[:3] == ["run", "--model", "prov/model"]


def test_hook_in_the_child_reaches_the_run(
    claude: Path, dataset: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "hook")
    res = _result(_start(dataset, "--model", "haiku"))
    types = [e["type"] for e in _events(res["run_dir"])]
    assert "session.ended" in types
    assert types[-1] == "run.finished"


def test_time_limit_kills_the_process_group(
    claude: Path, dataset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "sleep")
    started = time.monotonic()
    res = _result(_start(dataset, "--model", "haiku", "--time-limit", "2"))
    assert time.monotonic() - started < 30
    ev = _events(res["run_dir"])
    ended = _of(ev, "run.attempt.ended")[0]["payload"]
    assert ended["reason"] == "time_limit"
    assert _of(ev, "run.finished")[0]["payload"]["reason"] == "time limit"
    pid = _shim(tmp_path)["pid"]
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_term_ignoring_child_is_killed(
    claude: Path, dataset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "ignore_term")
    monkeypatch.setattr(launcher, "KILL_GRACE_S", 1)
    res = _result(_start(dataset, "--model", "haiku", "--time-limit", "1"))
    assert _of(_events(res["run_dir"]), "run.attempt.ended")[0]["payload"]["reason"] == "time_limit"
    with pytest.raises(ProcessLookupError):
        os.kill(_shim(tmp_path)["pid"], 0)


def _gone(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


def test_interactive_time_limit_ends_the_whole_tree(
    claude: Path, dataset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WR-04: interactive harness stays in the terminal's group; its children die with it."""
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "grandchild,sleep")
    monkeypatch.setattr(launcher, "KILL_GRACE_S", 2)
    res = _result(_start(dataset, "--model", "haiku", "--interactive", "--time-limit", "3"))
    assert _of(_events(res["run_dir"]), "run.attempt.ended")[0]["payload"]["reason"] == "time_limit"
    child = int((tmp_path / "shim.json.child").read_text())
    deadline = time.monotonic() + 5
    while not _gone(child) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert _gone(child) and _gone(_shim(tmp_path)["pid"])


@pytest.mark.parametrize("start_handler", ["default", "ignored"])
def test_sigint_in_a_headless_run_closes_it(
    claude: Path,
    dataset: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    start_handler: str,
) -> None:
    """WR-04: Ctrl-C ends the harness group, records the attempt and closes the run.

    Afterwards the launcher restores the SIGINT handler it found: Python's default in a
    terminal, SIG_IGN when the process was started in the background by a non-interactive
    shell (``setsid nohup … &``). The starting handler is set explicitly so the test does not
    depend on how pytest itself was started.
    """
    import signal

    monkeypatch.setenv("FAKE_CLAUDE_MODE", "grandchild,sleep")
    monkeypatch.setattr(launcher, "KILL_GRACE_S", 2)
    before = signal.default_int_handler if start_handler == "default" else signal.SIG_IGN
    outer = signal.signal(signal.SIGINT, before)
    try:
        _sigint_run_closes(tmp_path, dataset, before)
    finally:
        signal.signal(signal.SIGINT, outer)


def _sigint_run_closes(tmp_path: Path, dataset: Path, before: Any) -> None:
    import signal
    import threading

    def interrupt() -> None:
        deadline = time.monotonic() + 20
        while not (tmp_path / "shim.json.child").exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        os.kill(os.getpid(), signal.SIGINT)

    threading.Thread(target=interrupt, daemon=True).start()
    res = _start(dataset, "--model", "haiku")
    assert res.exit_code == 128 + signal.SIGINT, res.output
    data = json.loads(res.stdout)
    ev = _events(data["run_dir"])
    assert _of(ev, "run.attempt.ended")[0]["payload"]["reason"] == "interrupted"
    assert ev[-1]["type"] == "run.finished"
    assert ev[-1]["payload"]["reason"].startswith("interrupted")
    assert _gone(_shim(tmp_path)["pid"])
    child = int((tmp_path / "shim.json.child").read_text())
    deadline = time.monotonic() + 5
    while not _gone(child) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert _gone(child)
    assert signal.getsignal(signal.SIGINT) is before


def test_setup_failure_after_init_closes_the_run(
    claude: Path, dataset: Path, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WR-04: an error after the run folder exists closes the run instead of leaving it open."""

    def boom(*_a: Any, **_k: Any) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(launcher.shutil, "copytree", boom)
    res = _start(dataset, "--model", "haiku")
    assert res.exit_code == 2
    assert "closed" in res.stderr
    runs = [p for p in workspace.iterdir() if (p / ".ailsa-run").is_file()]
    assert len(runs) == 1
    ev = _events(runs[0])
    assert ev[-1]["type"] == "run.finished"
    assert "launcher setup failed" in ev[-1]["payload"]["reason"]


def test_close_after_the_agent_closed_is_quiet(new_run: tuple[str, Path]) -> None:
    """WR-04: a run the agent already closed is reported, not a traceback."""
    from ailsa.record.closing import close_run

    _, run_dir = new_run
    close_run(run_dir, "agent closed it")
    out = launcher._close_quietly(run_dir, "harness exited")
    assert "state" in out
    assert len(_of(_events(run_dir), "run.finished")) == 1


def test_prompt_override_and_context_files(claude: Path, dataset: Path, tmp_path: Path) -> None:
    note = tmp_path / "hint.txt"
    note.write_text("the sample is a terpene\n")
    res = _result(
        _start(
            dataset,
            "--model",
            "haiku",
            "--prompt",
            "Do it your way.",
            "--context-file",
            str(note),
        )
    )
    run_dir = Path(res["run_dir"])
    created = _of(_events(run_dir), "run.created")[0]["payload"]["request"]
    assert created["prompt"] == "Do it your way."
    files = created["context_files"]
    assert files[0]["name"] == "hint.txt" and len(files[0]["sha256"]) == 64
    assert (run_dir / "agent" / "context" / "hint.txt").read_text() == note.read_text()
    assert _shim(tmp_path)["argv"][1] == "Do it your way."


def test_no_transcript_skips_both_copies(
    claude: Path, dataset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "transcript,hook")
    res = _result(_start(dataset, "--model", "haiku", "--no-transcript"))
    ev = _events(res["run_dir"])
    assert not _of(ev, "transcript.copied")
    assert _shim(tmp_path)["env"]["AILSA_NO_TRANSCRIPT"] == "1"


def test_spawn_failure_still_closes_the_run(
    dataset: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", "/nonexistent-dir")
    res = _result(_start(dataset, "--model", "haiku"))
    assert res["exit_code"] is None
    ev = _events(res["run_dir"])
    assert _of(ev, "run.attempt.ended")[0]["payload"]["reason"].startswith("spawn_failed")
    assert ev[-1]["type"] == "run.finished"


def test_nonzero_exit_is_recorded(
    claude: Path, dataset: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_EXIT", "3")
    res = _result(_start(dataset, "--model", "haiku"))
    assert res["exit_code"] == 3
    assert _of(_events(res["run_dir"]), "run.attempt.ended")[0]["payload"]["exit_code"] == 3


def test_blind_refusal_exits_2(claude: Path, dataset: Path) -> None:
    assert CliRunner().invoke(run, ["init", str(dataset), "--no-views"]).exit_code == 0
    res = _start(dataset, "--model", "haiku", "--blind")
    assert res.exit_code == 2 and "--allow-prior-runs" in res.stderr


def test_missing_context_file(claude: Path, dataset: Path, tmp_path: Path) -> None:
    res = _start(dataset, "--model", "haiku", "--context-file", str(tmp_path / "nope.txt"))
    assert res.exit_code == 2 and "context file not found" in res.stderr


def test_extra_args_go_to_the_harness(claude: Path, dataset: Path, tmp_path: Path) -> None:
    res = _start(dataset, "--model", "haiku", "--", "--max-turns", "7")
    _result(res)
    assert _shim(tmp_path)["argv"][-2:] == ["--max-turns", "7"]


# ------------------------------------------------------------------ frontier skill


@pytest.fixture
def frontier_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from .test_env import install_command_skill

    home = tmp_path / "home"
    install_command_skill(home / ".claude", link=True)
    monkeypatch.setenv("HOME", str(home))
    return home


def _run_folders(tmp_path: Path) -> list[Path]:
    ws = tmp_path / "ws"
    return [p for p in ws.iterdir() if p.is_dir()] if ws.is_dir() else []


def test_default_prompt_frontier() -> None:
    assert default_prompt("/d", skill="ailsa", formula="C6H6") == "/ailsa:case /d C6H6"
    assert default_prompt("/d", skill="ailsa") == "/ailsa:case /d"
    assert default_prompt("/d") == "/ailsa-lite /d"


def test_frontier_start(
    claude: Path, frontier_home: Path, dataset: Path, tmp_path: Path
) -> None:
    res = _result(
        _start(
            dataset, "--model", "m", "--skill", "ailsa", "--formula", "C6H6", "--time-limit", "30"
        )
    )
    run_dir = Path(res["run_dir"])
    info = _shim(tmp_path)
    argv = info["argv"]
    assert argv[0] == "-p" and argv[1] == f"/ailsa:case {dataset.resolve()} C6H6"
    assert info["env"]["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"] == "1"
    assert not (run_dir / "agent" / ".claude" / "skills").exists()
    ev = _events(run_dir)
    env = _of(ev, "env.captured")[0]["payload"]
    assert env["skill"]["name"] == "ailsa"
    assert env["skill_location"] == "global-claude-commands"
    assert env["skill_matches_packaged"] is True
    assert _of(ev, "run.created")[0]["payload"]["request"]["mode"] == "headless"


def test_lean_start_sets_no_teams_flag(
    claude: Path, dataset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS", raising=False)
    res = _result(_start(dataset, "--model", "m"))
    assert "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS" not in _shim(tmp_path)["env"]
    assert (Path(res["run_dir"]) / "agent" / ".claude" / "skills" / "ailsa-lite").is_dir()


def test_frontier_prompt_override(
    claude: Path, frontier_home: Path, dataset: Path, tmp_path: Path
) -> None:
    _result(_start(dataset, "--model", "m", "--skill", "ailsa", "--prompt", "custom"))
    assert _shim(tmp_path)["argv"][1] == "custom"


def test_frontier_missing_install_refused(
    claude: Path, dataset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "emptyhome"))
    res = _start(dataset, "--model", "m", "--skill", "ailsa")
    assert res.exit_code == 2
    assert "ailsa skill install ailsa --target claude" in res.output
    assert _run_folders(tmp_path) == []


def test_frontier_opencode_refused(
    shim_path: Path, frontier_home: Path, dataset: Path, tmp_path: Path
) -> None:
    make_shim(shim_path, "opencode", SHIM)
    res = _start(dataset, "--harness", "opencode", "--model", "m", "--skill", "ailsa")
    assert res.exit_code == 2
    assert _run_folders(tmp_path) == []


# ------------------------------------------------------------------ resume attempts


def _calls(tmp_path: Path) -> list[dict[str, Any]]:
    text = (tmp_path / "shim.json.calls").read_text()
    return [json.loads(line) for line in text.splitlines() if line]


def _attempts(run_dir: str | Path, kind: str) -> list[int]:
    return [e["payload"]["attempt"] for e in _of(_events(run_dir), kind)]


def test_build_resume_argv(tmp_path: Path) -> None:
    argv = launcher.build_resume_argv(
        model="m",
        nudge="N",
        session_id="sid",
        run_dir=tmp_path / "r",
        dataset=tmp_path / "d",
        extra=["--x", "y"],
    )
    assert argv == [
        "claude",
        "--resume",
        "sid",
        "-p",
        "N",
        "--model",
        "m",
        "--settings",
        str(tmp_path / "r" / "hooks.json"),
        "--add-dir",
        str(tmp_path / "d"),
        "--dangerously-skip-permissions",
        "--x",
        "y",
    ]
    conf = launcher.build_resume_argv(
        model="m",
        nudge="N",
        session_id="sid",
        run_dir=tmp_path / "r",
        dataset=tmp_path / "d",
        confidential=True,
    )
    assert conf[-3:] == ["--disallowedTools", "WebFetch", "WebSearch"]


def test_resume_until_declared(
    claude: Path, dataset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "declare_on_resume")
    res = _result(
        _start(dataset, "--model", "m", "--resume-attempts", "3", "--", "--fence", "blind")
    )
    assert res["attempts"] == 2
    assert res["state"] == "result_declared"
    calls = _calls(tmp_path)
    assert len(calls) == 2
    first, second = calls[0]["argv"], calls[1]["argv"]
    sid = first[first.index("--session-id") + 1]
    run_dir = Path(res["run_dir"])
    assert second == [
        "--resume",
        sid,
        "-p",
        launcher.RESUME_NUDGE,
        "--model",
        "m",
        "--settings",
        str(run_dir / "hooks.json"),
        "--add-dir",
        str(dataset.resolve()),
        "--dangerously-skip-permissions",
        "--fence",
        "blind",
    ]
    assert first[-2:] == ["--fence", "blind"]
    assert _attempts(run_dir, "run.attempt.started") == [1, 2]
    assert _attempts(run_dir, "run.attempt.ended") == [1, 2]
    reports = _of(_events(run_dir), "agent.model_reported")
    reported = [e for e in reports if e["payload"]["source"] == "launcher"]
    assert len(reported) == 1


def test_resume_limit(claude: Path, dataset: Path, tmp_path: Path) -> None:
    res = _result(_start(dataset, "--model", "m", "--resume-attempts", "3"))
    assert res["attempts"] == 3
    assert res["state"] == "stopped_before_result"
    assert len(_of(_events(res["run_dir"]), "run.finished")) == 1
    assert len(_calls(tmp_path)) == 3


def test_agent_closed_run_stops_loop(
    claude: Path, dataset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "close_first")
    res = _result(_start(dataset, "--model", "m", "--resume-attempts", "3"))
    assert res["attempts"] == 1
    assert len(_calls(tmp_path)) == 1


def test_deadline_bounds_attempts(
    claude: Path, dataset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "sleep")
    started = time.monotonic()
    res = _result(
        _start(
            dataset,
            "--model",
            "m",
            "--time-limit",
            "1",
            "--deadline",
            "3",
            "--resume-attempts",
            "5",
        )
    )
    assert time.monotonic() - started < 25
    assert 1 <= res["attempts"] <= 3
    ev = _events(res["run_dir"])
    for e in _of(ev, "run.attempt.started"):
        assert e["payload"]["time_limit_s"] <= 3
    reason = _of(ev, "run.finished")[0]["payload"]["reason"]
    assert reason in ("deadline", "time limit")


def test_signal_ends_resume_loop(
    claude: Path, dataset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import signal
    import threading

    monkeypatch.setenv("FAKE_CLAUDE_MODE", "sleep")
    threading.Timer(2.0, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()
    res = _start(dataset, "--model", "m", "--resume-attempts", "3", "--time-limit", "30")
    assert res.exit_code == 128 + int(signal.SIGTERM), res.output
    assert len(_calls(tmp_path)) == 1


def test_resume_refused_interactive_or_opencode(
    claude: Path, dataset: Path, tmp_path: Path
) -> None:
    res = _start(dataset, "--model", "m", "--interactive", "--resume-attempts", "2")
    assert res.exit_code == 2
    res = _start(dataset, "--harness", "opencode", "--model", "m", "--resume-attempts", "2")
    assert res.exit_code == 2
    res = _start(dataset, "--model", "m", "--resume-attempts", "0")
    assert res.exit_code == 2
    assert _run_folders(tmp_path) == []


def test_default_run_has_one_attempt(claude: Path, dataset: Path, tmp_path: Path) -> None:
    res = _result(_start(dataset, "--model", "m"))
    assert res["attempts"] == 1
    assert _attempts(res["run_dir"], "run.attempt.started") == [1]
    assert len(_calls(tmp_path)) == 1
