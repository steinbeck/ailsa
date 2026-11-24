"""Rendering tests: golden files, escaping, break marker, blind mode."""

from __future__ import annotations

from pathlib import Path

from ailsa.record.fold import fold
from ailsa.record.log import append_event, read_events
from ailsa.record.render import (
    BREAK_MARKER,
    NOT_RECORDED,
    md_escape,
    render_final,
    render_progress,
    render_run,
)

from ._fixture_record import build_fixture_record

GOLD = Path(__file__).parent / "fixtures" / "render"
NOW = "2026-01-01T12:00:00.000Z"


def _gold(name: str) -> str:
    return (GOLD / name).read_text(encoding="utf-8")


def test_golden_with_hooks(tmp_path: Path) -> None:
    run = build_fixture_record(tmp_path / "run-hooks")
    render_run(run, now=NOW)
    assert (run / "renderings" / "CASE-PROGRESS.md").read_text() == _gold("progress_hooks.md")
    assert (run / "renderings" / "final_results.md").read_text() == _gold("final_results.md")
    assert NOT_RECORDED not in _gold("progress_hooks.md")


def test_golden_hookless(tmp_path: Path) -> None:
    run = build_fixture_record(tmp_path / "run-hookless", hooks=False)
    render_run(run, now=NOW)
    text = (run / "renderings" / "CASE-PROGRESS.md").read_text()
    assert text == _gold("progress_hookless.md")
    assert NOT_RECORDED in text


def test_hand_ranking_shows_no_result(tmp_path: Path) -> None:
    run = build_fixture_record(tmp_path / "hand", hand_ranking=True)
    render_run(run, now=NOW)
    text = (run / "renderings" / "final_results.md").read_text()
    assert "## Result\n\nStopped before a result (inferred)" in text
    assert "CCCO" not in text


def test_break_marker(tmp_path: Path) -> None:
    run = build_fixture_record(tmp_path / "brk")
    path = run / "events.jsonl"
    lines = path.read_bytes().splitlines(keepends=True)
    lines[5] = lines[5].replace(b"ailsa", b"aiLsa", 1)
    path.write_bytes(b"".join(lines))
    render_run(run, now=NOW)
    text = (run / "renderings" / "CASE-PROGRESS.md").read_text()
    assert BREAK_MARKER in text
    rows = text.splitlines()
    marker_at = next(i for i, r in enumerate(rows) if BREAK_MARKER in r)
    assert rows[marker_at + 1].startswith("| 6 ")
    assert any(r.startswith("| 14 ") for r in rows)
    assert "changed or incomplete from event 6" in text


def test_escape() -> None:
    out = md_escape("a | b `c` <script>x</script>\n# no")
    assert "|" not in out.replace("\\|", "")
    assert "<" not in out and "&lt;script&gt;" in out
    assert "`" not in out.replace("\\`", "")
    assert "\n" not in out


def test_note_is_escaped_in_table(tmp_path: Path) -> None:
    run = build_fixture_record(tmp_path / "esc")
    append_event(
        run,
        "note.added",
        {"text": "x | y `z` <script>", "sender": "chemist"},
        actor={"kind": "agent"},
        utc="2026-01-01T11:00:00.000Z",
        host="testhost",
    )
    r = read_events(run)
    m = fold(r["events"], r["integrity"], now=NOW)
    text = render_progress(m, r["events"])
    assert "<script>" not in text
    assert "x \\| y" in text


def test_blind_hides_names() -> None:
    m = {
        "run_id": "r",
        "dataset": {"label": "example"},
        "blind": True,
        "status": {"state": "result_declared"},
        "final": {"outcome": "proposal", "candidate": 1, "confidence": "low"},
        "identity": [{"verdict": "match", "derived_name": "SecretName"}],
    }
    text = render_final(m, None, None)
    assert "hidden in blind mode" in text
    assert "SecretName" not in text


def test_changed_ranking_file_is_flagged(tmp_path: Path) -> None:
    run = build_fixture_record(tmp_path / "chg")
    (run / "rankings" / "rk01.json").write_text("{}", encoding="utf-8")
    render_run(run, now=NOW)
    text = (run / "renderings" / "final_results.md").read_text()
    assert "ranking file changed after it was recorded" in text
