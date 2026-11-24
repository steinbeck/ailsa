"""Main CLI entry point for ailsa."""

import importlib
from collections.abc import Sequence
from typing import Any

import click

from ailsa._version import __version__

# Fixed registry: command name -> "module:attr". Only these names are ever
# imported (T-106.1-01); unknown names fall through to click's usual error.
_COMMANDS: dict[str, str] = {
    "analyze": "ailsa.cli.analyze:analyze",
    "case": "ailsa.cli.case:case",
    "database": "ailsa.cli.database:database",
    "dereplicate": "ailsa.cli.dereplicate:dereplicate",
    "detect": "ailsa.cli.detect:detect",
    "fetch": "ailsa.cli.fetch:fetch",
    "fragment": "ailsa.cli.fragment:fragment",
    "identify": "ailsa.cli.identify:identify",
    "jcamp": "ailsa.cli.jcamp:jcamp",
    "lsd": "ailsa.cli.lsd:lsd",
    "nus": "ailsa.cli.nus:nus",
    "pick": "ailsa.cli.pick:pick",
    "predict": "ailsa.cli.predict:predict",
    "pylsd": "ailsa.cli.pylsd:pylsd",
    "read": "ailsa.cli.read:read",
    "skill": "ailsa.cli.skill:skill",
    "visualize": "ailsa.cli.visualize:visualize",
    "webview": "ailsa.cli.webview:webview",
    "run": "ailsa.cli.run:run",
    "spectra": "ailsa.cli.spectra:spectra",
    "peaks": "ailsa.cli.peaks:peaks",
    "model": "ailsa.cli.model:model",
}


class LazyGroup(click.Group):
    """Click group that imports a command module only when it is used."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._loaded: dict[str, click.Command] = {}
        super().__init__(*args, **kwargs)

    @property  # type: ignore[override]
    def commands(self) -> dict[str, click.Command]:
        """All commands; loads every registry entry (used by contract tests)."""
        for name in _COMMANDS:
            self._load(name)
        return self._loaded

    @commands.setter
    def commands(self, value: dict[str, click.Command]) -> None:
        self._loaded = dict(value)

    def add_command(self, cmd: click.Command, name: str | None = None) -> None:
        key = name or cmd.name
        if not key:
            raise TypeError("Command has no name.")
        self._loaded[key] = cmd

    def _load(self, name: str) -> click.Command | None:
        if name in self._loaded:
            return self._loaded[name]
        target = _COMMANDS.get(name)
        if target is None:
            return None
        module_path, attr = target.split(":")
        cmd = getattr(importlib.import_module(module_path), attr)
        self._loaded[name] = cmd
        return cmd  # type: ignore[no-any-return]

    def list_commands(self, ctx: click.Context) -> list[str]:
        return sorted(set(_COMMANDS) | set(self._loaded))

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        return self._load(cmd_name)


@click.group(cls=LazyGroup)
@click.version_option(version=__version__, prog_name="ailsa")
def cli() -> None:
    """ailsa: AI-powered Computer-Assisted Structure Elucidation.

    A command-line interface for NMR processing and structure elucidation
    of organic natural products.

    Commands:

    \b
      case        Guided structure elucidation, one step per command
      read        Read NMR spectra (1D, 2D)
      pick        Peak picking from spectra
      analyze     Analysis tools (symmetry detection)
      dereplicate Match against reference databases
      identify    Derive + verify compound identity (SMILES -> InChIKey + DB name)
      predict     Predict NMR chemical shifts
      detect      Statistical detection (hybridisation)
      lsd         LSD structure elucidation
      visualize   Generate NMR correlation diagrams
      fetch       Fetch data from external sources
      database    Database management (build, info)
      fragment    Fragment library (build, search, info)
      webview     Dashboard server for live CASE runs
      nus         NUS (Non-Uniform Sampling) 2D reconstruction
      jcamp       JCAMP-DX ingestion (read -> pick -> QC -> write)
      skill       Install the agent skills that ship with ailsa
      run         Run record: create, note, finalize, render, verify
      spectra     Spectra view products for display
      peaks       Peak decisions recorded in a run
      model       Atom model recorded in a run
    """
    pass


LUCY_DEPRECATION_MESSAGE = (
    "Warning: `lucy` is deprecated and will be removed in the next release; "
    "use `ailsa` instead."
)


def lucy_deprecated(args: Sequence[str] | None = None) -> None:
    """Deprecated alias for the ``ailsa`` command.

    Exists for one release to give existing ``lucy`` callers (notably the
    CASE agent team and the benchmark harness, both of which parse
    ``--format json`` stdout as a machine-readable contract) time to switch
    to ``ailsa``. Prints exactly one warning line to STDERR -- never
    stdout -- and then delegates to the identical ``cli`` group, so stdout
    stays byte-identical to the ``ailsa`` entry point (D-04). Like the
    ``ailsa`` entry point, this raises ``SystemExit`` via ``cli.main``'s
    default standalone mode; it never returns before that call.
    """
    click.echo(LUCY_DEPRECATION_MESSAGE, err=True)
    cli.main(args=list(args) if args is not None else None, prog_name="lucy")
