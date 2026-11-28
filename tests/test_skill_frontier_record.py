"""Grep-contract tests for how the frontier coordinator and its agents write the run record.

They pin the coordinator text (src/ailsa/skills/ailsa/commands/case.md): the record is created
first, before any team, task or spawn; every spawn prompt carries the absolute work folder; prose
goes into notes; every exit declares the result or closes the run; CASE-PROGRESS.md and
final_results.md are renderings, never hand-written. They replace the old web-view contract test.
They also pin the agent texts (src/ailsa/skills/ailsa/agents/): the solution analyst reports the
ranking id and a declaration draft instead of writing a report, and the devil's advocate's name
gate reads the coordinator's message before the result is declared. Finally they pin the
references (src/ailsa/skills/ailsa/references/): the procedures read history from the generated
progress log, open every phase with a note and point into the run's work folder, never the dataset.
Two whole-skill tests cover every skill file at once: none brings back a legacy write, and the
frontier skill names the same record commands as the lean skill.

All file reads use repo-relative paths (src/ailsa/skills/ailsa/...), so the tests work from any
checkout without touching ~/.claude.

Run with::

    pytest tests/test_skill_frontier_record.py -v
"""

from __future__ import annotations

import re
from pathlib import Path

# Resolved from this file, so pytest can run from any folder.
SKILL_DIR = Path(__file__).resolve().parents[1] / "src/ailsa/skills/ailsa"
CASE_MD = SKILL_DIR / "commands/case.md"
RUN_RECORD_MD = SKILL_DIR / "references/run-record.md"
INDEX_MD = SKILL_DIR / "INDEX.md"
AGENTS_DIR = SKILL_DIR / "agents"
ANALYST_MD = AGENTS_DIR / "ailsa-solution-analyst.md"
DEVILS_ADVOCATE_MD = AGENTS_DIR / "ailsa-devils-advocate.md"
ENGINEER_MD = AGENTS_DIR / "ailsa-lsd-engineer.md"
DIAGNOSTIC_MD = AGENTS_DIR / "ailsa-diagnostic.md"
AGENT_FILES = (
    AGENTS_DIR / "ailsa-nmr-chemist.md",
    ENGINEER_MD,
    ANALYST_MD,
    DEVILS_ADVOCATE_MD,
    DIAGNOSTIC_MD,
)
REFERENCES_DIR = SKILL_DIR / "references"
MONITORING_MD = REFERENCES_DIR / "monitoring.md"
GATES_MD = REFERENCES_DIR / "coordinator-gates.md"
# The references the coordinator reads at named steps of the run.
COORDINATOR_REFERENCES = (
    MONITORING_MD,
    GATES_MD,
    REFERENCES_DIR / "advisory-templates.md",
    REFERENCES_DIR / "intervention.md",
    REFERENCES_DIR / "loop-patterns.md",
    REFERENCES_DIR / "multiplicity-ambiguity.md",
    REFERENCES_DIR / "smoke-test.md",
)

# The heading of the devil's advocate's name-gate section.
G_IDENT_HEADING = "## G-IDENT: name and structure cross-check"

# The marker that begins the terminate_team step in case.md.
TERMINATE_TEAM_MARKER = '<step name="terminate_team">'

# The first [BEGIN] peak-picking push (the SendMessage call of the kick-off), not the earlier
# mention in the nmr-chemist spawn prompt.
FIRST_PUSH_MARKER = 'content="[BEGIN] peak-picking'

INIT = "ailsa run init"


def _case_text() -> str:
    return CASE_MD.read_text()


def _step(text: str, name: str) -> str:
    """Text of one <step name="..."> block, from its opening tag to its closing </step>."""
    marker = f'<step name="{name}">'
    assert marker in text, f"case.md has no {marker}"
    after = text.split(marker, 1)[1]
    assert "</step>" in after, f"the {name} step has no closing </step>"
    return after.split("</step>", 1)[0]


def _task_blocks(text: str) -> list[str]:
    """Every Task( block: from a line starting with 'Task(' to the next line that is exactly ')'."""
    blocks: list[str] = []
    current: list[str] | None = None
    for line in text.splitlines():
        if current is None:
            if line.startswith("Task("):
                current = [line]
        else:
            current.append(line)
            if line == ")":
                blocks.append("\n".join(current))
                current = None
    return blocks


def _section(text: str, heading: str) -> str:
    """Text of one '## ' section, from its heading line to the next '## ' heading."""
    assert heading in text, f"no section {heading!r}"
    after = text.split(heading, 1)[1]
    match = re.search(r"^## ", after, re.MULTILINE)
    return after[: match.start()] if match else after


def _first_task_line_index(text: str) -> int:
    match = re.search(r"^Task\(", text, re.MULTILINE)
    assert match, "case.md has no line starting with Task("
    return match.start()


def test_start_record_step_listed() -> None:
    """The record step exists and is listed, so a reader sees it as its own step in run order."""
    text = _case_text()
    assert '<step name="start_record">' in text, "case.md has no start_record step"
    lines = text.splitlines()
    assert "## Contents" in lines, "case.md has no ## Contents"
    start = lines.index("## Contents")
    entries = []
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        if line.startswith("- "):
            entries.append(line[2:])
    assert any(e.startswith("start_record") for e in entries), (
        f"## Contents has no entry beginning with start_record: {entries}"
    )


def test_init_before_first_spawn() -> None:
    """The record exists before any team, spawn or push, so every later tool step lands in it."""
    text = _case_text()
    assert INIT in text, f"case.md does not name {INIT!r}"
    init_idx = text.index(INIT)
    assert "TeamCreate(" in text, "case.md has no TeamCreate( call"
    assert FIRST_PUSH_MARKER in text, f"case.md has no push marker {FIRST_PUSH_MARKER!r}"
    team_idx = text.index("TeamCreate(")
    task_idx = _first_task_line_index(text)
    push_idx = text.index(FIRST_PUSH_MARKER)
    assert init_idx < team_idx, f"{INIT} at {init_idx} comes after TeamCreate( at {team_idx}"
    assert init_idx < task_idx, f"{INIT} at {init_idx} comes after the first Task( at {task_idx}"
    assert init_idx < push_idx, f"{INIT} at {init_idx} comes after the first push at {push_idx}"


def test_init_names_frontier_skill() -> None:
    """The record names the frontier skill and team mode, so the two skills' runs stay apart."""
    text = _case_text()
    assert INIT in text, f"case.md does not name {INIT!r}"
    idx = text.index(INIT)
    line_start = text.rfind("\n", 0, idx) + 1
    line_end = text.find("\n", idx)
    line = text[line_start : line_end if line_end != -1 else len(text)]
    assert "--skill ailsa" in line, f"the first {INIT} line lacks --skill ailsa: {line!r}"
    assert "--mode team" in line, f"the first {INIT} line lacks --mode team: {line!r}"


def test_work_dir_in_every_spawn_prompt() -> None:
    """Every specialist gets the absolute work folder, so no agent writes into the dataset."""
    blocks = _task_blocks(_case_text())
    assert len(blocks) == 4, f"expected four Task( blocks, found {len(blocks)}"
    missing = [b.splitlines()[1].strip() for b in blocks if "{work_dir}" not in b]
    assert not missing, f"Task( blocks without {{work_dir}}: {missing}"


def test_terminate_declares_or_closes() -> None:
    """Every exit declares the result or closes the run and renders it, so no record stays open."""
    block = _step(_case_text(), "terminate_team")
    for command in ("ailsa run finalize", "ailsa run close", "ailsa run render"):
        assert command in block, f"terminate_team does not name {command!r}"


def test_explicit_ranking_id() -> None:
    """The declaration names its ranking, because 'latest' is the analyst's cross-check ranking."""
    for path in (CASE_MD, RUN_RECORD_MD):
        assert path.exists(), f"{path.name} is missing"
        assert "--ranking latest" not in path.read_text(), f"{path.name} uses --ranking latest"


def test_no_legacy_writes_in_case_md() -> None:
    """The coordinator writes no dataset folder, manifest, timing file, dashboard or old log."""
    text = _case_text()
    legacy_tokens = (
        "analysis/",
        ".run_manifest",
        "timing.json",
        "**Dashboard:**",
        "progress-format",
    )
    for legacy in legacy_tokens:
        assert legacy not in text, f"case.md still contains {legacy!r}"
    assert "webview" not in text.lower(), "case.md still mentions the web view"


def test_model_self_report_recorded() -> None:
    """Each specialist's model statement is recorded as a self-report, which stays provisional."""
    assert "--self-reported-model" in _case_text(), "case.md records no model self-report"


def test_ranking_complete_requires_ranking_id() -> None:
    """[RANKING-COMPLETE] has to carry the ranking id, because the declaration names it."""
    block = _step(_case_text(), "validate_message")
    pattern = r"^- \[RANKING-COMPLETE\]:(.*?)(?=^- |^\s*$)"
    match = re.search(pattern, block, re.MULTILINE | re.DOTALL)
    assert match, "validate_message lists no [RANKING-COMPLETE] fields"
    assert "Ranking id" in match.group(1), (
        f"[RANKING-COMPLETE] fields lack 'Ranking id': {match.group(1).strip()!r}"
    )


def test_retired_references_gone() -> None:
    """The timing and progress-format references gave way to run-record, linked from the index."""
    assert not (SKILL_DIR / "references/timing.md").exists(), "references/timing.md still exists"
    assert not (SKILL_DIR / "references/progress-format.md").exists(), (
        "references/progress-format.md still exists"
    )
    assert RUN_RECORD_MD.exists(), "references/run-record.md is missing"
    assert "references/run-record.md" in INDEX_MD.read_text(), "INDEX.md does not link run-record"


def test_analyst_reports_ranking_id() -> None:
    """The analyst names the decisive ranking and drafts the declaration instead of a report file.

    The coordinator declares against the ranking id the analyst reports, because the later
    cross-check ranking would otherwise be the newest; a hand-written report is not the record.
    """
    text = ANALYST_MD.read_text()
    for field in ("Ranking id:", "Declaration draft:"):
        assert field in text, f"the solution analyst's file lacks {field!r}"
    assert "ranking_results.json" not in text, "the analyst still saves ranking_results.json"
    writes = [
        line.strip()
        for line in text.splitlines()
        if re.search(r"(?i)write[^\n]{0,40}final_results\.md", line)
    ]
    assert not writes, f"the solution analyst still writes final_results.md: {writes}"


def test_devils_advocate_gate_reads_message() -> None:
    """The name gate reads the coordinator's G-IDENT message after the ranking, not a report."""
    text = DEVILS_ADVOCATE_MD.read_text()
    assert "analysis/" not in text, "the devil's advocate's file still names analysis/"
    assert "[BEGIN] G-IDENT" in text, "the devil's advocate's file names no [BEGIN] G-IDENT message"
    gate = _section(text, G_IDENT_HEADING)
    assert "[RANKING-COMPLETE]" in gate, "the G-IDENT section does not name [RANKING-COMPLETE]"


def test_identity_check_targets_the_declared_candidate() -> None:
    """The declared candidate is not always rank 1, so identity and G-IDENT follow it.

    Otherwise the rendered result could show the verdict of rank 1 next to candidate 2.
    """
    analyst = ANALYST_MD.read_text()
    assert "rank-#1 SMILES" not in analyst, "the analyst still identifies rank 1 only"
    assert "the SMILES of the candidate you recommend" in analyst
    assert "Identity: rank <recommended rank>" in analyst
    gate = _section(GATES_MD.read_text(), "## Identity gate")
    assert "`Top solution:` line" not in gate, "G-IDENT still reviews the rank-1 SMILES"
    assert "candidate SMILES (rank <N>)" in gate
    assert "top SMILES" not in DEVILS_ADVOCATE_MD.read_text()


def test_coverage_reopen_ranks_through_the_analyst() -> None:
    """After a coverage reopen a new [RANKING-COMPLETE] is requested; the coordinator ranks nothing.

    Otherwise the identity gate and the declaration draft would read the stale ranking message.
    """
    gate = _section(GATES_MD.read_text(), "## Coverage gate")
    fail = gate.split("- **FAIL**", 1)[1]
    assert "re-run the deduplicated union rank" not in fail
    assert '--phase ranking' in fail and 'recipient="solution-analyst"' in fail
    assert "[BEGIN] ranking" in fail
    assert "Wait for the new `[RANKING-COMPLETE]`" in fail
    for ref in ("advisory-templates.md", "loop-patterns.md"):
        assert "re-run the deduped union rank" not in (REFERENCES_DIR / ref).read_text(), ref
        assert "re-run the union rank" not in (REFERENCES_DIR / ref).read_text(), ref


def test_agents_use_work_dir() -> None:
    """No agent writes or reads the dataset's analysis folder, a manifest or a timing file.

    Every agent path lies under the absolute work folder, so the dataset stays read-only; the
    progress log is generated from the record, so no agent contributes to it by hand.
    """
    assert len(AGENT_FILES) == 5, f"expected five agent files, found {len(AGENT_FILES)}"
    for path in AGENT_FILES:
        assert path.exists(), f"{path.name} is missing"
        text = path.read_text()
        for legacy in ("analysis/", ".run_manifest", "timing.json", "Contribution Protocol"):
            assert legacy not in text, f"{path.name} still contains {legacy!r}"


def test_engineer_marks_family_runs() -> None:
    """The engineer runs the solver in the work folder and marks per-family runs as such.

    The record then tells the main search apart from the family searches.
    """
    text = ENGINEER_MD.read_text()
    assert "{work_dir}/iteration_" in text, "the engineer's file has no {work_dir}/iteration_ path"
    assert "--purpose family" in text, "the engineer's file does not mark family runs"


def test_diagnostic_writes_report_to_work_dir() -> None:
    """The diagnostic specialist writes its report into the work folder, not the dataset."""
    text = DIAGNOSTIC_MD.read_text()
    assert "{work_dir}" in text, "the diagnostic specialist's file names no {work_dir}"
    assert "DIAGNOSTIC-REPORT.md" in text, "the diagnostic specialist's file names no report"


def test_coordinator_references_use_record() -> None:
    """The coordinator's procedures read and write the record, not the dataset or a hand log.

    No path into the dataset's analysis folder, no header line or stamps of the hand-written log;
    history comes from the generated progress log, every push opens a phase, a name flag becomes a
    caveat of the declaration, and the ranking directive asks for no report file.
    """
    assert len(COORDINATOR_REFERENCES) == 7, "expected seven coordinator references"
    for path in COORDINATOR_REFERENCES:
        assert path.exists(), f"{path.name} is missing"
        text = path.read_text()
        for legacy in ("analysis/", "Started (UTC)", "timing"):
            assert legacy not in text, f"{path.name} still contains {legacy!r}"
    monitoring = MONITORING_MD.read_text()
    for token in ("ailsa run render", "--phase", "Ranking id"):
        assert token in monitoring, f"monitoring.md does not name {token!r}"
    writes = [
        line.strip()
        for line in monitoring.splitlines()
        if re.search(r"(?i)write[^\n]{0,40}final_results\.md", line)
    ]
    assert not writes, f"monitoring.md still asks for final_results.md: {writes}"
    assert "--caveat" in GATES_MD.read_text(), "coordinator-gates.md turns no flag into a caveat"


def test_references_use_work_dir() -> None:
    """Every reference names work-folder paths, so no snippet writes or reads in the dataset.

    Per-family solver runs are marked as such, so the record tells them from the main search, and
    the diagnostic report lands in the work folder, where the coordinator looks for it.
    """
    references = sorted(REFERENCES_DIR.glob("*.md"))
    assert references, "references/ is empty"
    legacy = [path.name for path in references if "analysis/" in path.read_text()]
    assert not legacy, f"references still naming analysis/: {legacy}"
    search = (REFERENCES_DIR / "lsd-search.md").read_text()
    for token in ("--purpose family", "{work_dir}/union_solutions.smi"):
        assert token in search, f"lsd-search.md does not name {token!r}"
    report = (REFERENCES_DIR / "diagnostic-report.md").read_text()
    assert "{work_dir}/DIAGNOSTIC-REPORT.md" in report, (
        "diagnostic-report.md does not place the report in the work folder"
    )


def _skill_files() -> list[Path]:
    """Every frontier skill text except the changelog, which describes old behaviour on purpose."""
    return sorted(p for p in SKILL_DIR.rglob("*.md") if p.name != "CHANGELOG.md")


# Substrings no skill file may contain: the dataset's analysis folder, the dataset manifest, the
# timing file, the explicit "newest ranking" shortcut and the old dashboard header line.
LEGACY_SUBSTRINGS = (
    "analysis/",
    ".run_manifest",
    "timing.json",
    "--ranking latest",
    "**Dashboard:**",
)

# A hand-written progress log; allowed only on a line that says it must not happen.
PROGRESS_WRITE = re.compile(r"(?i)\bwrite[^\n]{0,40}CASE-PROGRESS\.md")
NEGATION = re.compile(r"(?i)\b(?:never|not)\b|\bno ")

# The record commands the frontier skill names: the lean skill's three (init, note, finalize) and
# the two its coordinator needs on every exit path (close without a result, render the reports).
RECORD_COMMANDS = (
    "ailsa run init",
    "ailsa run note",
    "ailsa run finalize",
    "ailsa run close",
    "ailsa run render",
)
LEAN_DIR = SKILL_DIR.parent / "ailsa-lite"
RECORD_COMMAND = re.compile(r"\bailsa run [a-z][a-z-]*")


def test_whole_skill_has_no_legacy_writes() -> None:
    """No frontier file writes into the dataset, a manifest, a timing log or the old web view.

    The per-file tests above pin the coordinator, the agents and the references one by one; this
    test covers every skill file at once, so a new or overlooked file cannot bring the old flow
    back. The progress log and the results are renderings of the record, never written by hand.
    """
    files = _skill_files()
    assert files, "the frontier skill has no markdown files"
    hits: list[str] = []
    for path in files:
        rel = path.relative_to(SKILL_DIR)
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            for legacy in LEGACY_SUBSTRINGS:
                if legacy in line:
                    hits.append(f"{rel}:{number}: {legacy!r}")
            if "webview" in line.lower():
                hits.append(f"{rel}:{number}: 'webview'")
            if PROGRESS_WRITE.search(line) and not NEGATION.search(line):
                hits.append(f"{rel}:{number}: writes CASE-PROGRESS.md")
    assert not hits, "legacy writes in the frontier skill:\n" + "\n".join(hits)


def test_both_skills_name_record_commands() -> None:
    """The frontier skill names every record command, including each one the lean skill names.

    A new recording command changes both skills in the same commit (docs/SKILLS.md); the lean
    skill's contract test then needs no exception for commands only it would name.
    """
    text = "\n".join(path.read_text() for path in _skill_files())
    missing = [command for command in RECORD_COMMANDS if command not in text]
    assert not missing, f"the frontier skill does not name: {missing}"
    lean_files = sorted(p for p in LEAN_DIR.rglob("*.md") if p.name != "CHANGELOG.md")
    assert lean_files, "the lean skill has no markdown files"
    lean = {m for p in lean_files for m in RECORD_COMMAND.findall(p.read_text())}
    assert lean, "the lean skill names no record command"
    only_lean = sorted(lean - set(RECORD_COMMAND.findall(text)))
    assert not only_lean, f"record commands only the lean skill names: {only_lean}"
