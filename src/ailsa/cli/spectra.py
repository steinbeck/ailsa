"""ailsa spectra: spectra view products for display (REC-29).

Interface contract: Plan 10 adds the subcommands inside this file. Nothing
heavy is imported at module level.
"""

from __future__ import annotations

import click


@click.group()
def spectra() -> None:
    """Spectra view products for display."""
