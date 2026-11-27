"""Entry point for ``python -m ailsa.cli``.

Allows the ailsa CLI to be invoked as::

    python -m ailsa.cli <command> [args...]

This lets tools and tests start the CLI with the current interpreter when
the ``ailsa`` script is not on PATH (e.g. in an editable/dev install).
"""

from ailsa.cli import cli

if __name__ == "__main__":
    cli()
