"""ailsa model: atom model recorded in a run (REC-04).

Interface contract: Plan 12 adds the subcommands inside this file. Nothing
heavy is imported at module level.
"""

from __future__ import annotations

import click


@click.group()
def model() -> None:
    """Atom model recorded in a run."""
