"""ailsa peaks: peak decisions recorded in a run (REC-04, REC-17).

Interface contract: Plan 12 adds the subcommands inside this file. Nothing
heavy is imported at module level.
"""

from __future__ import annotations

import click


@click.group()
def peaks() -> None:
    """Peak decisions recorded in a run."""
