"""Contract tests for the benchmark runner, watchdog and host scripts."""

import importlib.util
import re
from pathlib import Path

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
    version = tuple(int(x) for x in env["CLAUDE_BIN"].rsplit("/", 1)[1].split("."))
    assert version >= (2, 1, 280)
    assert env["CLAUDE_MODEL"] == "claude-opus-5-5"


def test_watchdog_abort_pattern():
    assert "[c]laude -p /ailsa:case" in _read("scripts/uat_watchdog.py")


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
