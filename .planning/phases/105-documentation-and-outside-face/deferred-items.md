# Phase 105 — deferred items (out of scope for a docs phase)

Found by the 105-09 gate; code under `src/` is not changed in Phase 105.

1. **`ailsa --help` prints its command list twice.** The top-level group's docstring carries a
   hand-written "Commands:" list (which omits `pylsd`) above the list Click generates. The CLI
   audit (`105-check-cli-examples.py`) parses only the Click-generated list. Fix in the CLI code:
   drop the hand-written list from the docstring.
2. **Nine leaf commands have no `--format json`:** `database build`, `database download`,
   `database generate-hose-stats`, `database info`, `fragment build`, `fragment info`,
   `lsd check`, `predict build-table`, `visualize correlations` (34 of 43 have it). The docs now
   name these exceptions (commit `71a94de`). If a later phase adds `--format json` to them
   (ARCHITECTURE decision 3 aims at structured output everywhere; `lsd check` and
   `database info` as JSON would help prerequisite checks), the exception sentences in README.md,
   CLAUDE.md, docs/ARCHITECTURE.md and deck slide 8 can be reverted to "every subcommand".
