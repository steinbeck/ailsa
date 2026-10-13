---
phase: 105-documentation-and-outside-face
plan: 02
subsystem: docs
tags: [ailsa, cli, python-api, rename, user-guide]

# Dependency graph
requires:
  - phase: 104-package-and-cli
    provides: "the renamed ailsa package/CLI (src/ailsa, `ailsa` entry point) that this plan documents"
provides:
  - "docs/USER_GUIDE.md fully renamed to AILSA, with no MCP-server content"
  - "every CLI example in USER_GUIDE.md verified against the installed `ailsa --help` output"
  - "every Python import and API call in USER_GUIDE.md verified against the installed ailsa package via importlib/inspect"
affects: [105-documentation-and-outside-face, 106-skill-rebuild, 107-repo-rename]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Doc verification: resolve every CLI example and Python call against the live installed interpreter (`$(command -v ailsa)` shebang) rather than trusting the prior doc text"

key-files:
  created: []
  modified:
    - docs/USER_GUIDE.md

key-decisions:
  - "Retitled 'DEPT-Guided HSQC Picking' to 'HSQC Picking' and 'Guided HMBC Picking' to 'HMBC Picking' per D-14, since the CLI commands return raw peaks and guided filtering is agent/Python-side"
  - "Replaced the dead `ailsa lsd generate` command with a one-sentence explanation (agent-built in CASE runs, LSDInputGenerator in Python), keeping the heading 'LSD Input Files'"
  - "Fixed two Python API calls that referenced non-existent methods: LSDOutputParser.parse_solutions -> parse_smiles_file, and the manual HOSELookupTable-build loop (referencing a non-existent build_from_loader) -> HOSELookupTable.build_from_nmrshiftdb/build_from_coconut classmethods"

patterns-established:
  - "Pattern: before editing CLI/Python docs, enumerate real --help output and real class attributes via inspect/dataclasses/pydantic model_fields, rather than assuming the prior doc text was accurate"

requirements-completed: [DOC-02]

# Metrics
duration: 25min
completed: 2026-10-13
---

# Phase 105 Plan 02: USER_GUIDE AILSA rename and CLI/API correctness fix Summary

**Renamed docs/USER_GUIDE.md to AILSA, dropped the MCP interface, and fixed every command/API example that had drifted from the live CLI and Python package — including two Python calls to methods that do not exist.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-10-13T09:55:00+02:00 (approx.)
- **Completed:** 2026-10-13T10:05:26+02:00
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- CLI half (Overview through 13C Shift Prediction) fully renamed `lucy`/`lucy-ng`/MCP → `ailsa`/AILSA/two-interfaces, command-groups table rebuilt to list all 16 `ailsa --help` groups
- Every retained CLI example checked against `ailsa <group> <cmd> --help`: fixed `analyze symmetry` argument order, `dereplicate --top-n` → `--top`, removed dead `--dept135`/`--dept90`/`--c13`/`--hsqc` flags and the non-existent `lsd generate` command
- Python API half fully renamed `from lucy_ng` / `import lucy_ng` → `ailsa`; every import and every `Class.method()`/attribute access checked against the installed `ailsa` package (importlib, `inspect.signature`, `dataclasses.fields`/`__dataclass_fields__`, pydantic `model_fields`)
- Found and fixed two Python examples calling methods that do not exist: `LSDOutputParser.parse_solutions` (real name `parse_smiles_file`) and a manual HOSE-table-build loop referencing `HOSELookupTable.build_from_loader` (replaced with the real `build_from_nmrshiftdb`/`build_from_coconut` classmethods)

## Task Commits

Each task was committed atomically:

1. **Task 1: CLI half of USER_GUIDE (rename, two interfaces, fix every command example)** - `a9f3e01` (docs)
2. **Task 2: Python API and workflow half (rename imports, verify they resolve)** - `a8b726b` (docs)

_No TDD tasks in this plan; no separate plan-metadata commit (SUMMARY commit is the metadata commit)._

## Files Created/Modified
- `docs/USER_GUIDE.md` - CLI reference and Python API guide; fully renamed to AILSA, MCP-free, every example verified against the live CLI/package

## Decisions Made
- See `key-decisions` in frontmatter. Summary: retitle two picking sections to match what the raw CLI commands actually return; replace the dead `lsd generate` usage with an explanatory sentence instead of inventing a command; fix two Python calls to non-existent methods rather than leaving them plausible-but-wrong.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `LSDOutputParser.parse_solutions(Path("output/"))` does not exist**
- **Found during:** Task 2 (Python API verification)
- **Issue:** The "Solution Ranking" Python example called `LSDOutputParser.parse_solutions`, which is not a method on the real class (`parse_smiles_file`, `parse_summary_output`, `solutions_to_smiles_list` are). This predates the rename — it was already wrong under the old name.
- **Fix:** Replaced with `LSDOutputParser.parse_smiles_file(Path("outlsd.out"))`, matching the real signature `(smiles_path: Path | str) -> list[LSDSolution]` and its docstring ("standard output format from outlsd").
- **Files modified:** docs/USER_GUIDE.md
- **Verification:** `hasattr(LSDOutputParser, "parse_smiles_file")` is True; checked via `inspect.signature` against the installed package.
- **Committed in:** a8b726b (Task 2 commit)

**2. [Rule 1 - Bug] `HOSELookupTable.build_from_loader` does not exist**
- **Found during:** Task 2 (Python API verification)
- **Issue:** The "13C Shift Prediction" Python example built a HOSE table manually with a comment pointing to `HOSELookupTable.build_from_loader` "for full implementation" — that method does not exist, and the manual loop it stood in for (`generator.prepare_mol` + an empty `pass`) did not actually add anything to the table either.
- **Fix:** Replaced the entire manual loop with the real classmethods `HOSELookupTable.build_from_nmrshiftdb(Path(...), max_radius=6)` (and a commented alternative `build_from_coconut` for COCONUT SD files), matching their real signatures.
- **Files modified:** docs/USER_GUIDE.md
- **Verification:** `hasattr(HOSELookupTable, "build_from_nmrshiftdb")` and `build_from_coconut` both True (classmethods); checked via `inspect.signature`.
- **Committed in:** a8b726b (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - pre-existing bugs in the doc, unrelated to the rename itself, found while verifying every Python call per the task's instructions)
**Impact on plan:** Both fixes were required by the task's own acceptance criteria (every `Class.method()` call must satisfy `hasattr`). No scope creep — both methods are in files already being edited for this plan.

## Issues Encountered
None beyond the two deviations above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `docs/USER_GUIDE.md` is fully AILSA, MCP-free, and matches the installed CLI/package; no further work needed on this file for Phase 105.
- Other Phase 105 plans (README, ARCHITECTURE, BENCHMARK, INSTALLATION, NUS-PORTABILITY, SERVER_BOOTSTRAP, infographics, figshare, peripheral docs) are out of scope for this plan and proceed independently.

---
*Phase: 105-documentation-and-outside-face*
*Completed: 2026-10-13*

## Self-Check: PASSED

- FOUND: docs/USER_GUIDE.md
- FOUND: a9f3e01 (Task 1 commit)
- FOUND: a8b726b (Task 2 commit)
