"""ailsa run: the run record (REC-06, REC-09, REC-16, REC-22).

Interface contract: Plans 14 and 17 add the subcommands (init, start, note,
finalize, render, verify) inside this file. Nothing heavy is imported at
module level.
"""

from __future__ import annotations

import click


@click.group()
def run() -> None:
    """Run record: create, note, finalize, render, verify."""
