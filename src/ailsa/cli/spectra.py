"""ailsa spectra: spectra view products for display (REC-29).

Nothing heavy is imported at module level.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click


@click.group()
def spectra() -> None:
    """Spectra view products for display."""


def _inventory_for_run(run_dir: Path, dataset: Path) -> dict[str, Any]:
    """Latest registered inventory of the run, or a fresh one that is registered first."""
    from ailsa.record.artefacts import find_artefacts, register_artefact
    from ailsa.record.fingerprint import dataset_fingerprint
    from ailsa.record.inventory import build_inventory, scanned_payload
    from ailsa.record.log import read_events

    events = read_events(run_dir)["events"]
    found = [a for a in find_artefacts(events, "experiment-inventory") if not a["superseded_by"]]
    if found:
        return json.loads((run_dir / found[-1]["path"]).read_text())  # type: ignore[no-any-return]
    blind = False
    if events:
        blind = bool(((events[0].get("payload") or {}).get("dataset") or {}).get("blind", False))
    inventory = build_inventory(
        dataset, blind=blind, fingerprint=dataset_fingerprint(dataset)["fingerprint"]
    )
    register_artefact(
        run_dir,
        kind="experiment-inventory",
        rel_path="spectra/inventory.json",
        data=json.dumps(inventory, indent=2, sort_keys=True).encode("utf-8"),
        event_type="spectra.scanned",
        payload=scanned_payload(inventory),  # same list form as ailsa run init writes
        actor={"kind": "tool", "name": "ailsa spectra export"},
    )
    return inventory


@spectra.command("export")
@click.argument("dataset", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option(
    "--experiment",
    "experiments",
    multiple=True,
    help="Limit the export to this experiment (expno or alias); repeatable.",
)
@click.option("--run", "run_ref", default=None, help="Run folder path or id to record into.")
@click.option(
    "--out",
    "out_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Write the view products here and record nothing (needed outside a run).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def export(
    dataset: Path,
    experiments: tuple[str, ...],
    run_ref: str | None,
    out_dir: Path | None,
    output_format: str,
) -> None:
    """Export display products (levels, projections, 1D data) of every experiment.

    Inside a run the products go to the run folder and are registered there. The dataset is
    never written to.
    """
    import time

    from ailsa.record.resolve import current_run_for_tool, find_active_run
    from ailsa.spectra.export import export_dataset, register_result

    started = time.perf_counter()
    run_dir: Path | None = None
    if out_dir is None:
        ref = find_active_run(run_ref) if run_ref else current_run_for_tool("spectra export")
        if ref is None and run_ref:
            raise click.ClickException(f"run not found: {run_ref}")
        if ref is None:
            raise click.ClickException("spectra export needs an active run or --out DIR")
        run_dir = ref.run_dir
    dataset = dataset.resolve()
    only = set(experiments) or None

    if run_dir is not None:
        from ailsa.record.artefacts import run_target

        try:
            out_root = run_target(run_dir, "spectra")
        except ValueError as exc:
            raise click.ClickException(f"refused to write into the run: {exc}") from exc
        inventory = _inventory_for_run(run_dir, dataset)
    else:
        from ailsa.record.inventory import build_inventory

        assert out_dir is not None
        out_root = out_dir
        inventory = build_inventory(dataset, blind=False, fingerprint="")
    results = export_dataset(dataset, inventory, out_root, only=only, overwrite=run_dir is None)

    if run_dir is not None:
        by_label = {str(e["id"]).split(":", 1)[-1]: e for e in inventory["experiments"]}
        for res in results:
            entry = by_label.get(res["experiment"], {})
            guess = "vendor" if entry.get("processed", True) else "rawproc"
            try:
                register_result(run_dir, res, state_guess=guess)
            except Exception as exc:
                res["status"] = "failed"
                res["reason"] = f"not recorded: {type(exc).__name__}: {exc}"[:300]

    summary = {
        "views": [r for r in results if r["status"] == "ok"],
        "skipped": [r for r in results if r["status"] == "skipped"],
        "failed": [r for r in results if r["status"] == "failed"],
        "seconds": round(time.perf_counter() - started, 3),
    }
    if output_format == "json":
        click.echo(json.dumps(summary, indent=2))
        return
    for res in results:
        line = f"{res['experiment']} {res.get('state') or '-'} {res['status']} {res['seconds']}s"
        if res.get("reason"):
            line += f" ({res['reason']})"
        click.echo(line)
