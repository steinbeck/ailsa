"""`ailsa run init|note|status|verify|render|index`."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from ailsa.cli.run import run
from ailsa.record import env as record_env
from ailsa.record.log import read_events

from ._fixture_record import build_fixture_record
from .test_spectra_export import make_1d


@pytest.fixture(autouse=True)
def _no_database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(record_env, "resolve_database_path", lambda: None)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))


def _invoke(args: list[str]) -> Any:
    return CliRunner().invoke(run, args)


def _dataset(tmp_path: Path, name: str = "example") -> Path:
    ds = tmp_path / name
    make_1d(ds, "1")
    return ds


# ----------------------------------------------------------------------------- init


def test_init_text_prints_two_lines(workspace: Path, tmp_path: Path) -> None:
    res = _invoke(["init", str(_dataset(tmp_path)), "--no-views"])
    assert res.exit_code == 0, res.output
    lines = res.stdout.strip().splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("RUN: ") and lines[1].startswith("WORK: ")
    assert lines[1].endswith(f"{lines[0][5:]}/agent")
    assert Path(lines[1][6:]).is_dir()


def test_init_json(workspace: Path, tmp_path: Path) -> None:
    res = _invoke(["init", str(_dataset(tmp_path)), "--no-views", "--format", "json"])
    assert res.exit_code == 0, res.output
    data = json.loads(res.stdout)
    assert set(data) == {"run_id", "run_dir", "work_dir", "created", "warnings", "views_pid"}
    assert data["created"] is True and data["views_pid"] is None


def test_init_blind_refusal_exits_2(workspace: Path, tmp_path: Path) -> None:
    ds = _dataset(tmp_path, "CASE5")
    assert _invoke(["init", str(ds), "--no-views"]).exit_code == 0
    before = sorted(p.name for p in workspace.iterdir())
    res = CliRunner().invoke(run, ["init", str(ds), "--blind", "--no-views"])
    assert res.exit_code == 2
    assert "--allow-prior-runs" in res.stderr and res.stdout == ""
    assert sorted(p.name for p in workspace.iterdir()) == before
    ok = _invoke(["init", str(ds), "--blind", "--allow-prior-runs", "--no-views"])
    assert ok.exit_code == 0, ok.output


def test_init_options_recorded(workspace: Path, tmp_path: Path) -> None:
    res = _invoke(
        [
            "init",
            str(_dataset(tmp_path)),
            "--no-views",
            "--class",
            "public",
            "--label",
            "example",
            "--formula",
            "C2H6O",
            "--source",
            "synthetic",
            "--licence",
            "none",
            "--skill",
            "ailsa-lite",
            "--mode",
            "lean",
            "--format",
            "json",
        ]
    )
    assert res.exit_code == 0, res.output
    first = read_events(json.loads(res.stdout)["run_dir"])["events"][0]["payload"]
    assert first["class"] == "public"
    assert first["dataset"]["formula"] == "C2H6O"
    assert first["dataset"]["source"] == "synthetic" and first["dataset"]["licence"] == "none"
    assert first["request"]["skill"] == "ailsa-lite" and first["request"]["mode"] == "lean"


def test_blind_run_stores_no_label_source_or_licence(
    workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CR-06: the agent can read the run folder, so nothing that could name the compound."""
    canary = "CANARY-NAME-7731"
    args = [
        "init",
        str(_dataset(tmp_path, "CASE9")),
        "--blind",
        "--no-views",
        "--label",
        f"{canary}-label",
        f"--source={canary}-source",
        "--licence",
        f"{canary}-licence",
        "--format",
        "json",
    ]
    monkeypatch.setattr("sys.argv", ["ailsa", "run", *args])
    res = _invoke(args)
    assert res.exit_code == 0, res.output
    run_dir = Path(json.loads(res.stdout)["run_dir"])
    _invoke(["status", "--run", str(run_dir)])  # writes manifest.json too
    for path in run_dir.rglob("*"):
        if path.is_file():
            assert canary not in path.read_text(errors="replace"), path
    created = read_events(run_dir)["events"][0]["payload"]
    assert created["dataset"]["label"] == "CASE9"
    assert created["dataset"]["source"] == created["dataset"]["licence"] == "withheld (blind)"
    recorded = created["request"]["args"]
    assert "--blind" in recorded and "--label" not in recorded and "--licence" not in recorded


def test_scrub_blind_args_forms() -> None:
    from ailsa.record.runinit import scrub_blind_args

    args = ["run", "start", "d", "--label", "x", "--prompt=y", "--source", "z", "--blind"]
    assert scrub_blind_args(args) == ["run", "start", "d", "--blind"]


def test_init_help_lists_options() -> None:
    text = _invoke(["init", "--help"]).output
    for flag in (
        "--blind",
        "--allow-prior-runs",
        "--class",
        "--label",
        "--formula",
        "--source",
        "--licence",
        "--skill",
        "--mode",
        "--no-views",
        "--format",
    ):
        assert flag in text


# ----------------------------------------------------------------------------- note


def _new_run(workspace: Path, tmp_path: Path) -> Path:
    res = _invoke(["init", str(_dataset(tmp_path)), "--no-views", "--format", "json"])
    return Path(json.loads(res.stdout)["run_dir"])


def _notes(run_dir: Path) -> list[dict[str, Any]]:
    return [e for e in read_events(run_dir)["events"] if e["type"] == "note.added"]


def test_note_records_sender_and_time(
    workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = _new_run(workspace, tmp_path)
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    monkeypatch.setenv("AILSA_AGENT_ROLE", "chemist")
    res = _invoke(["note", "Atoms set up; 10 carbons"])
    assert res.exit_code == 0 and res.stdout == ""
    note = _notes(run_dir)[-1]
    assert note["payload"] == {"text": "Atoms set up; 10 carbons", "sender": "chemist"}
    assert note["utc"].endswith("Z")


def test_note_default_sender_and_override(
    workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = _new_run(workspace, tmp_path)
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    monkeypatch.delenv("AILSA_AGENT_ROLE", raising=False)
    _invoke(["note", "one"])
    _invoke(["note", "two", "--sender", "devils-advocate"])
    senders = [n["payload"]["sender"] for n in _notes(run_dir)]
    assert senders == ["agent", "devils-advocate"]


def test_note_text_is_capped(
    workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ailsa.record.events import TEXT_CAP

    run_dir = _new_run(workspace, tmp_path)
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    _invoke(["note", "x" * (TEXT_CAP + 500)])
    assert len(_notes(run_dir)[-1]["payload"]["text"]) == TEXT_CAP


def test_note_phase_only_when_changed(
    workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = _new_run(workspace, tmp_path)
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    _invoke(["note", "a", "--phase", "lsd"])
    _invoke(["note", "b", "--phase", "lsd"])
    _invoke(["note", "c", "--phase", "rank"])
    phases = [
        e["payload"]["name"] for e in read_events(run_dir)["events"] if e["type"] == "phase.started"
    ]
    assert phases == ["lsd", "rank"]


def test_note_self_reported_model(
    workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = _new_run(workspace, tmp_path)
    monkeypatch.setenv("AILSA_RUN_DIR", str(run_dir))
    _invoke(["note", "hi", "--sender", "chemist", "--self-reported-model", "small-model"])
    event = [e for e in read_events(run_dir)["events"] if e["type"] == "agent.model_reported"][-1]
    assert event["payload"] == {
        "agent": "chemist",
        "requested": None,
        "actual": "small-model",
        "source": "self-report",
    }


def test_note_run_option(workspace: Path, tmp_path: Path) -> None:
    run_dir = _new_run(workspace, tmp_path)
    assert _invoke(["note", "via flag", "--run", str(run_dir)]).exit_code == 0
    assert _notes(run_dir)[-1]["payload"]["text"] == "via flag"


def test_note_without_run_warns_and_exits_0(workspace: Path, tmp_path: Path) -> None:
    res = CliRunner().invoke(run, ["note", "nobody listens"])
    assert res.exit_code == 0
    assert "not recorded: no active run" in res.stderr


def test_note_help_lists_options() -> None:
    text = _invoke(["note", "--help"]).output
    for flag in ("--phase", "--sender", "--self-reported-model", "--run", "--format"):
        assert flag in text


# ----------------------------------------------------------------------------- status


def _fixture(workspace: Path, **kw: Any) -> Path:
    return build_fixture_record(workspace / "2026-01-01T1000Z_example_fx01", **kw)


def test_status_json(workspace: Path) -> None:
    run_dir = _fixture(workspace)
    res = _invoke(["status", "--run", str(run_dir), "--format", "json"])
    assert res.exit_code == 0, res.output
    data = json.loads(res.stdout)
    assert set(data) == {
        "run_id",
        "state",
        "label",
        "inferred",
        "integrity",
        "events",
        "iterations",
        "last_solver_outcome",
        "final",
        "hooks_recorded",
        "heartbeat_utc",
    }
    assert data["state"] == "result_declared" and data["integrity"]["clean"] is True
    assert data["final"]["valid"] is True and data["hooks_recorded"] is True
    assert (run_dir / "manifest.json").is_file()


def test_status_text_one_line_per_field(workspace: Path) -> None:
    run_dir = _fixture(workspace)
    res = _invoke(["status", "--run", str(run_dir)])
    assert res.exit_code == 0
    assert any(line.startswith("state: ") for line in res.stdout.splitlines())


def test_status_by_id_and_without_run(workspace: Path) -> None:
    run_dir = _fixture(workspace)
    assert _invoke(["status", "--run", run_dir.name, "--format", "json"]).exit_code == 0
    res = CliRunner().invoke(run, ["status"])
    assert res.exit_code == 1
    assert "no run given and no active run" in res.stderr


# ----------------------------------------------------------------------------- verify


def test_verify_clean(workspace: Path) -> None:
    run_dir = _fixture(workspace)
    _invoke(["status", "--run", str(run_dir)])
    res = _invoke(["verify", "--run", str(run_dir), "--format", "json"])
    assert res.exit_code == 0, res.output
    data = json.loads(res.stdout)
    assert data["clean"] and data["manifest_matches"] and data["artefacts_ok"]
    assert data["unregistered"] == []
    assert _invoke(["verify", "--run", str(run_dir)]).stdout.strip() == "clean"


def test_verify_flipped_byte(workspace: Path) -> None:
    run_dir = _fixture(workspace)
    log = run_dir / "events.jsonl"
    raw = bytearray(log.read_bytes())
    pos = raw.index(b"example")
    raw[pos] = ord("E")
    log.write_bytes(bytes(raw))
    res = _invoke(["verify", "--run", str(run_dir), "--format", "json"])
    assert res.exit_code == 1
    data = json.loads(res.stdout)
    assert data["clean"] is False and data["first_bad_seq"] is not None


def test_verify_changed_artefact(workspace: Path) -> None:
    run_dir = _fixture(workspace)
    target = next((run_dir / "rankings").glob("*"))
    target.write_text(target.read_text() + " ")
    res = _invoke(["verify", "--run", str(run_dir), "--format", "json"])
    assert res.exit_code == 1
    data = json.loads(res.stdout)
    assert data["artefacts_ok"] is False
    assert data["bad_artefacts"][0]["path"].startswith("rankings/")


def test_verify_manifest_edited(workspace: Path) -> None:
    run_dir = _fixture(workspace)
    _invoke(["status", "--run", str(run_dir)])
    manifest = json.loads((run_dir / "manifest.json").read_text())
    manifest["final"]["outcome"] = "inconclusive"
    (run_dir / "manifest.json").write_text(json.dumps(manifest))
    res = _invoke(["verify", "--run", str(run_dir), "--format", "json"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["manifest_matches"] is False


def test_verify_lists_unregistered_but_exits_0(workspace: Path) -> None:
    run_dir = _fixture(workspace)
    (run_dir / "agent" / "scratch.txt").write_text("free area\n")
    (run_dir / "stray.txt").write_text("elsewhere\n")
    (run_dir / "iterations").mkdir(exist_ok=True)
    (run_dir / "iterations" / "loose.lsd").write_text("x\n")
    res = _invoke(["verify", "--run", str(run_dir), "--format", "json"])
    assert res.exit_code == 0, res.output
    assert json.loads(res.stdout)["unregistered"] == ["iterations/loose.lsd", "stray.txt"]
    text = _invoke(["verify", "--run", str(run_dir)]).stdout
    assert "warning: unregistered file stray.txt" in text


# ----------------------------------------------------------------------------- render, index


def test_render_writes_both_files(workspace: Path) -> None:
    run_dir = _fixture(workspace)
    res = _invoke(["render", "--run", str(run_dir), "--format", "json"])
    assert res.exit_code == 0, res.output
    files = json.loads(res.stdout)["files"]
    assert sorted(Path(f).name for f in files) == ["CASE-PROGRESS.md", "final_results.md"]
    assert all(Path(f).parent == run_dir / "renderings" for f in files)
    assert all(Path(f).is_file() for f in files)


def test_render_on_finished_run(workspace: Path) -> None:
    run_dir = _fixture(workspace)
    (run_dir / "finished.json").write_text("{}")
    assert _invoke(["render", "--run", str(run_dir)]).exit_code == 0


def test_index_lists_and_rebuilds(workspace: Path, tmp_path: Path) -> None:
    run_dir = _new_run(workspace, tmp_path)
    res = _invoke(["index", "--format", "json"])
    assert [r["run_id"] for r in json.loads(res.stdout)["runs"]] == [run_dir.name]
    (workspace / "runs.json").unlink()
    assert json.loads(_invoke(["index", "--format", "json"]).stdout)["runs"] == []
    rebuilt = _invoke(["index", "--rebuild", "--format", "json"])
    assert [r["run_id"] for r in json.loads(rebuilt.stdout)["runs"]] == [run_dir.name]
    assert run_dir.name in _invoke(["index"]).stdout


def test_run_help_lists_commands() -> None:
    text = _invoke(["--help"]).output
    for name in ("init", "note", "status", "verify", "render", "index"):
        assert name in text


_UNRESOLVED_RUN_COMMANDS = [
    ("run", ["close"]),
    ("run", ["finalize", "--outcome", "no_structure_fits"]),
    ("run", ["note", "into the wrong run?"]),
    ("run", ["status"]),
    ("run", ["render"]),
    ("run", ["verify"]),
    ("peaks", ["decide", "--from", "{table}"]),
    ("model", ["import", "{table}"]),
    ("spectra", ["export", "{dataset}"]),
]


@pytest.mark.parametrize(("group", "args"), _UNRESOLVED_RUN_COMMANDS)
def test_explicit_run_never_falls_back_to_active_run(
    workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, group: str, args: list[str]
) -> None:
    """CR-04: an explicit --run that does not resolve is an error, whatever run is active."""
    from ailsa.cli.model import model
    from ailsa.cli.peaks import peaks
    from ailsa.cli.spectra import spectra

    groups = {"run": run, "peaks": peaks, "model": model, "spectra": spectra}
    active = _new_run(workspace, tmp_path)
    monkeypatch.setenv("AILSA_RUN_DIR", str(active))
    monkeypatch.chdir(active / "agent")  # the cwd marker would resolve too
    table = tmp_path / "table.json"
    table.write_text('{"decisions": []}\n')
    filled = [a.format(table=table, dataset=tmp_path / "example") for a in args]
    before = (active / "events.jsonl").read_bytes()
    manifest_before = sorted(p.name for p in active.iterdir())
    res = CliRunner().invoke(groups[group], [*filled, "--run", "no-such-run-x1"])
    assert res.exit_code != 0, res.output
    assert "run not found: no-such-run-x1" in res.output
    assert (active / "events.jsonl").read_bytes() == before
    assert sorted(p.name for p in active.iterdir()) == manifest_before
    assert not (active / "finished.json").exists()


def test_walk_does_not_follow_symlinks(workspace: Path, tmp_path: Path) -> None:
    run_dir = _fixture(workspace)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("x")
    (run_dir / "link").symlink_to(outside)
    res = _invoke(["verify", "--run", str(run_dir), "--format", "json"])
    assert "secret.txt" not in res.stdout
    shutil.rmtree(outside)
