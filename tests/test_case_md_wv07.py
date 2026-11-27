"""Grep-contract tests for the web-view launch in case.md and progress-format.md.

They check that case.md launches `ailsa webview serve`, mentions `ailsa webview stop` before
terminate_team, never stops the server in terminate_team and creates the CASE-PROGRESS.md header
at run start, and that progress-format.md has the **Dashboard:** field.

All file reads use repo-relative paths (src/ailsa/skills/ailsa/...) so tests
work from any checkout without touching ~/.claude.

Run with::

    pytest tests/test_case_md_wv07.py -v
"""

from __future__ import annotations

from pathlib import Path

# Resolved from this file, so pytest can run from any folder.
SKILL_DIR = Path(__file__).resolve().parents[1] / "src/ailsa/skills/ailsa"
CASE_MD = SKILL_DIR / "commands/case.md"
PROGRESS_FORMAT_MD = SKILL_DIR / "references/progress-format.md"

# The marker that begins the terminate_team step in case.md.
TERMINATE_TEAM_MARKER = '<step name="terminate_team">'

# The exact substring that identifies the first [BEGIN] peak-picking *push*
# (SendMessage call in spawn_case_team Step 5, not the earlier agent prompt mention).
# Using content="[BEGIN] peak-picking ensures we locate the SendMessage action
# at line ~224, not the earlier Task() prompt reference at line ~146.
FIRST_PUSH_MARKER = 'content="[BEGIN] peak-picking'


def test_webview_launch_present() -> None:
    """case.md contains 'ailsa webview serve' BEFORE the first '[BEGIN] peak-picking' push.

    Asserts:
    - 'ailsa webview serve' is present in case.md.
    - The first occurrence of 'ailsa webview serve' precedes the first occurrence
      of the SendMessage push marker ``content="[BEGIN] peak-picking`` — verifying
      that the WV-07 launch block is inserted before the team kick-off.

    Status: RED until Plan 92-02 inserts the webview launch block in
    spawn_case_team Step 5.
    """
    case_text = CASE_MD.read_text()

    assert "ailsa webview serve" in case_text, (
        "case.md does not contain 'ailsa webview serve' — "
        "Plan 92-02 must insert the webview launch block in spawn_case_team Step 5"
    )
    assert FIRST_PUSH_MARKER in case_text, (
        f"case.md does not contain the SendMessage push marker {FIRST_PUSH_MARKER!r} — "
        "unexpected structural change to spawn_case_team; update this test if the "
        "SendMessage format changed"
    )

    serve_idx = case_text.index("ailsa webview serve")
    push_idx = case_text.index(FIRST_PUSH_MARKER)

    assert serve_idx < push_idx, (
        f"'ailsa webview serve' appears at position {serve_idx}, but the first "
        f"SendMessage push marker appears at position {push_idx} — "
        "the webview launch block must be inserted BEFORE the '[BEGIN] peak-picking' "
        "SendMessage in spawn_case_team Step 5"
    )


def test_stop_hint_present() -> None:
    """The pre-terminate_team region of case.md contains 'ailsa webview stop'.

    The WV-07 launch block (in spawn_case_team Step 5) must output a stop hint
    so the user knows how to shut down the dashboard after the run.

    Status: RED until Plan 92-02 adds the stop hint to the WV-07 launch block.
    """
    case_text = CASE_MD.read_text()

    assert TERMINATE_TEAM_MARKER in case_text, (
        f"case.md does not contain the marker {TERMINATE_TEAM_MARKER!r} — "
        "the terminate_team step may have been renamed; update this test"
    )

    pre_marker = case_text.split(TERMINATE_TEAM_MARKER, 1)[0]

    assert "ailsa webview stop" in pre_marker, (
        "The run-start/spawn region of case.md (everything before terminate_team) "
        "does not contain 'ailsa webview stop' — "
        "Plan 92-02 must add the stop hint to the WV-07 webview launch block in "
        "spawn_case_team Step 5"
    )


def test_terminate_team_no_stop() -> None:
    """The terminate_team section of case.md does NOT contain 'ailsa webview stop'.

    This is a regression guard: the webview server must outlive the CASE run
    (SC #2).  The orchestrator must never call 'ailsa webview stop' in the
    shutdown step — the stop hint belongs only in the run-start launch block.

    Status: GREEN both before and after Plan 92-02 (regression guard).
    """
    case_text = CASE_MD.read_text()

    assert TERMINATE_TEAM_MARKER in case_text, (
        f"case.md does not contain the marker {TERMINATE_TEAM_MARKER!r} — "
        "the terminate_team step may have been renamed; update this test"
    )

    # Extract the terminate_team section: from the marker to its closing </step>.
    after_marker = case_text.split(TERMINATE_TEAM_MARKER, 1)[1]

    closing_tag = "</step>"
    assert closing_tag in after_marker, (
        f"The terminate_team section does not have a closing {closing_tag!r} — "
        "unexpected structural change to case.md; update this test"
    )

    terminate_section = after_marker.split(closing_tag, 1)[0]

    assert "ailsa webview stop" not in terminate_section, (
        "The terminate_team section of case.md contains 'ailsa webview stop' — "
        "this violates SC #2: the server must outlive the CASE run. "
        "The stop hint belongs ONLY in the WV-07 launch block (spawn_case_team), "
        "NOT in the shutdown step."
    )


def test_progress_header_created_at_run_start() -> None:
    """case.md creates the CASE-PROGRESS.md header at run-start, before the first push.

    Regression for the live-run finding: the dashboard Run Log showed
    "Waiting for log data…" for the whole peak-picking phase because case.md
    created CASE-PROGRESS.md only after [SETUP-COMPLETE]. The header (compound
    path, formula, dashboard URL) is known at run-start and must be written then
    so the dashboard is populated from t=0.

    Asserts a 'create the CASE-PROGRESS.md header' instruction appears BEFORE the
    first ``content="[BEGIN] peak-picking`` push.
    """
    case_text = CASE_MD.read_text()
    lowered = case_text.lower()

    marker = "create the case-progress.md header"
    assert marker in lowered, (
        "case.md does not instruct creating the CASE-PROGRESS.md header at run-start — "
        "the header (compound/formula/dashboard) must be written in spawn_case_team "
        "Step 5 so the dashboard Run Log is populated from t=0, not only after "
        "[SETUP-COMPLETE]"
    )
    assert FIRST_PUSH_MARKER in case_text, (
        f"case.md does not contain the SendMessage push marker {FIRST_PUSH_MARKER!r}"
    )

    header_idx = lowered.index(marker)
    push_idx = case_text.index(FIRST_PUSH_MARKER)

    assert header_idx < push_idx, (
        f"The CASE-PROGRESS.md header-creation instruction appears at position "
        f"{header_idx}, but the first '[BEGIN] peak-picking' push is at {push_idx} — "
        "the header must be created BEFORE the push (at run-start) so the dashboard "
        "log is not empty during peak-picking"
    )


def test_progress_format_dashboard_field() -> None:
    """progress-format.md contains a '**Dashboard:**' header field (OD-5).

    This field records the webview URL in the CASE-PROGRESS.md header so the
    URL is retrievable after the run without re-running 'ailsa webview status'.

    Status: RED until Plan 92-02 adds the Dashboard field to the CASE-PROGRESS.md
    header template in progress-format.md.
    """
    pf_text = PROGRESS_FORMAT_MD.read_text()

    assert "**Dashboard:**" in pf_text, (
        "progress-format.md does not contain '**Dashboard:**' — "
        "Plan 92-02 must add the OD-5 Dashboard field to the CASE-PROGRESS.md "
        "header template in progress-format.md"
    )
