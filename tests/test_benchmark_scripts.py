"""Contract tests for the benchmark runner, watchdog and host scripts."""

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_KEEP = [
    re.compile(r"/mnt/raid_drive/chris/lucy-ng"),
    re.compile(r"(?:~|\$HOME)/\.lucy\b"),
]


def _old_name_lines(text: str) -> list[str]:
    hits = []
    for line in text.splitlines():
        for pat in _KEEP:
            line = pat.sub("", line)
        if "lucy" in line:
            hits.append(line)
    return hits


def _read(rel: str) -> str:
    return (ROOT / rel).read_text()


def test_runner_files_have_no_old_name():
    for rel in (
        "tests/case-benchmark/blind_case_run.sh",
        "tests/case-benchmark/blind_case_batch.py",
        "tests/case-benchmark/README.md",
        "scripts/uat_watchdog.py",
    ):
        assert _old_name_lines(_read(rel)) == [], rel


def test_runner_calls_new_command():
    text = _read("tests/case-benchmark/blind_case_run.sh")
    assert '-p "/ailsa:case $CASE_DIR' in text
    assert not re.search(r"\bCASE\d+\b", text)


def _load_watchdog():
    spec = importlib.util.spec_from_file_location(
        "uat_watchdog", ROOT / "scripts" / "uat_watchdog.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_watchdog_pins():
    env = _load_watchdog().REMOTE_ENV
    binary = env["CLAUDE_BIN"]
    # Outside the auto-updater's folder, which prunes old versions.
    assert "/.local/share/claude/versions/" not in binary
    folder, name = binary.rsplit("/", 2)[-2:]
    assert name == "claude"
    version = tuple(int(x) for x in folder.removeprefix("claude-").split("."))
    assert version >= (2, 1, 280)
    assert env["CLAUDE_MODEL"] == "claude-opus-5-5"


def test_preflight_halts_with_copy_command_when_pin_missing(monkeypatch):
    mod = _load_watchdog()
    monkeypatch.setattr(mod, "ssh_run", lambda *a, **k: "NO_BINARY\n")
    with pytest.raises(mod.Halt) as exc:
        mod.preflight()
    assert f"cp {mod.PINNED_CLI_SOURCE} {mod.PINNED_CLI}" in str(exc.value)


def test_watchdog_abort_pattern():
    """The abort's pkill patterns must match the argv the runner really starts."""
    mod = _load_watchdog()
    patterns = re.findall(r"pkill -KILL -f -- '([^']+)'", mod._ABORT_SCRIPT)
    assert len(patterns) == 2
    run_sh = _read("tests/case-benchmark/blind_case_run.sh")
    assert '"$CLAUDE_BIN" -p "/ailsa:case $CASE_DIR $MF$SMOKE"' in run_sh
    assert '"$CLAUDE_BIN" --resume "$SID" -p "$NUDGE"' in run_sh
    assert run_sh.count("--dangerously-skip-permissions") == 2
    binary = mod.REMOTE_ENV["CLAUDE_BIN"]
    tail = ("--model claude-opus-5-5 --dangerously-skip-permissions "
            "--append-system-prompt BLIND CASE EVALUATION. --add-dir /data/CASE1")
    new_run = f"{binary} -p /ailsa:case /data/CASE1 C6H6 --session-id 1234-abcd {tail}"
    resume = f"{binary} --resume 1234-abcd -p Continue the in-progress CASE workflow {tail}"
    assert any(re.search(p, new_run) for p in patterns)
    assert any(re.search(p, resume) for p in patterns)
    # Never the abort script itself, nor an interactive session on the host.
    for innocent in (mod._ABORT_SCRIPT, "/home/chris/.local/bin/claude",
                     "claude --resume 1234-abcd", "claude -p hi"):
        assert not any(re.search(p, innocent) for p in patterns), innocent


def test_host_scripts_have_no_old_name():
    for rel in (
        "scripts/bootstrap_case_host.sh",
        "scripts/uat_run_remaining.sh",
        "scripts/uat_run_baseline_opus5.sh",
    ):
        assert _old_name_lines(_read(rel)) == [], rel


def test_launchagent_retired():
    plist = ROOT / "scripts/launchd/de.doktor-steinbeck.lucyng-uat-watchdog.plist"
    assert not plist.exists()


def test_watchdog_readme():
    text = _read("scripts/README.md")
    assert "herdr pane split" in text
    assert "externalUsageWritePath" in text


def test_bootstrap_installs_packaged_skill():
    text = _read("scripts/bootstrap_case_host.sh")
    assert "ailsa skill install ailsa" in text
    assert ".claude/commands" not in text


# --- result folders: no default, no paper arm, no model mixing -----------------------------


@pytest.fixture
def watchdog(monkeypatch: pytest.MonkeyPatch):
    mod = _load_watchdog()

    def no_ssh(*args, **kwargs):
        raise AssertionError("the test reached Sheldon")

    monkeypatch.setattr(mod, "ssh_run", no_ssh)
    return mod


def _main(mod, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *args: str):
    argv = ["uat_watchdog.py", "--once", "--dry-run", "--snapshot", str(tmp_path / "none.json")]
    monkeypatch.setattr(sys, "argv", argv + list(args))
    return mod.main()


def test_watchdog_results_dir_required(watchdog, monkeypatch, tmp_path):
    with pytest.raises(SystemExit) as exc:
        _main(watchdog, monkeypatch, tmp_path)
    assert exc.value.code == 2


@pytest.mark.parametrize("arm", sorted(_load_watchdog().PAPER_RESULT_DIRS))
def test_watchdog_refuses_paper_arms(watchdog, monkeypatch, tmp_path, arm, capsys):
    assert _main(watchdog, monkeypatch, tmp_path, "--results-dir", arm + "/") == 2
    assert "frozen" in capsys.readouterr().out


def test_paper_arms_cover_the_answer_scan_arms():
    arms = {p.rsplit("/", 1)[1] for p in _load_watchdog().PAPER_RESULT_DIRS}
    assert {"case-uat-results", "case-uat-results-opus5-rest",
            "case-uat-results-opus5-baseline"} <= arms


def test_check_results_dir_refuses_other_models():
    mod = _load_watchdog()
    model = mod.REMOTE_ENV["CLAUDE_MODEL"]
    new = "/mnt/raid_drive/chris/series-new"
    assert mod.check_results_dir(new, model, set()) is None
    assert mod.check_results_dir(new, model, {model}) is None
    assert "mix models" in mod.check_results_dir(new, model, {"<not recorded>"})
    assert "mix models" in mod.check_results_dir(new, model, {model, "claude-opus-5"})
    assert "absolute" in mod.check_results_dir("series-new", model, set())
    assert "CASE_RESULTS_DIR" not in mod.REMOTE_ENV


def _batch(tmp_path: Path, results: Path, model: str, claude_bin: str):
    data = tmp_path / "data"
    (data / "CASE1").mkdir(parents=True, exist_ok=True)
    (data / "CASE1" / "molecular-formula.txt").write_text("C6H6\n")
    env = dict(
        os.environ,
        CASE_DATA_DIR=str(data),
        CASE_STASH_DIR=str(tmp_path / "stash"),
        CLAUDE_MODEL=model,
        CLAUDE_BIN=claude_bin,
        CASE_RUN_MAX_ATTEMPTS="1",
        CASE_RUN_CALL_TIMEOUT="20",
        CASE_RUN_DEADLINE_S="20",
        TMPDIR=str(tmp_path),
    )
    env.pop("CASE_ANSWERKEY_PATHS", None)
    return subprocess.run(
        [sys.executable, str(ROOT / "tests/case-benchmark/blind_case_batch.py"), "CASE1",
         "-k", "1", "--results", str(results)],
        env=env, capture_output=True, text=True, timeout=50,
    )


@pytest.fixture
def fake_claude(tmp_path: Path) -> Path:
    fake = tmp_path / "bin" / "claude"
    fake.parent.mkdir()
    fake.write_text('#!/bin/sh\n[ "$1" = --version ] && { echo "9.9.9 (Claude Code)"; exit 0; }\n'
                    "exit 1\n")
    fake.chmod(0o755)
    return fake


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_meta_json_records_model_and_cli(tmp_path, fake_claude):
    results = tmp_path / "results"
    r = _batch(tmp_path, results, "claude-opus-5-5", str(fake_claude))
    assert r.returncode == 0, r.stdout + r.stderr
    meta = json.loads((results / "CASE1" / "meta.json").read_text())
    assert meta["model"] == "claude-opus-5-5"
    assert meta["claude_bin"] == str(fake_claude)
    assert meta["claude_version"] == "9.9.9 (Claude Code)"
    # The same series may resume in its own folder; another model may not add to it.
    assert _batch(tmp_path, results, "claude-opus-5-5", str(fake_claude)).returncode == 0
    r = _batch(tmp_path, results, "claude-opus-9", str(fake_claude))
    assert r.returncode != 0
    assert "mix models" in r.stderr


def test_batch_refuses_folder_without_recorded_model(tmp_path, fake_claude):
    results = tmp_path / "results"
    (results / "CASE2").mkdir(parents=True)
    (results / "CASE2" / "meta.json").write_text('{"case":"CASE2","runtime_s":5}')
    r = _batch(tmp_path, results, "claude-opus-5-5", str(fake_claude))
    assert r.returncode != 0
    assert "mix models" in r.stderr
    assert not (results / "CASE1").exists()


@pytest.mark.parametrize(
    "rel", ["scripts/uat_run_baseline_opus5.sh", "scripts/uat_run_remaining.sh"]
)
def test_paper_launchers_retired(rel):
    text = _read(rel)
    code = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    assert not [ln for ln in code if "case-uat-results" in ln or "ssh" in ln], rel
    assert code[-1] == "exit 2"
    if shutil.which("zsh"):
        r = subprocess.run(["zsh", str(ROOT / rel), "--dry-run"], capture_output=True,
                           text=True, timeout=20)
        assert r.returncode == 2
        assert "retired" in r.stderr
