"""Close a run: ``run.finished`` with fsync, then the workspace index (REC-23).

Used by ``ailsa run close`` and by the launcher. A closed run takes no more material.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ailsa.record.events import FINISHED, MARKER, TEXT_CAP
from ailsa.record.log import append_event, read_events


class CloseRefused(Exception):
    """The run cannot be closed (already finished)."""


def close_run(
    run_dir: str | os.PathLike[str], reason: str, *, actor: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Append ``run.finished`` (fsync), update ``runs.json`` with state and chain head."""
    from ailsa.record.fold import fold
    from ailsa.record.runinit import _entry_from_log, update_index
    from ailsa.record.workspace import workspace_root

    run = Path(run_dir)
    if (run / FINISHED).exists():
        raise CloseRefused("run is already finished")
    result = read_events(run)
    manifest = fold(result["events"], result["integrity"])
    state = (manifest.get("status") or {}).get("state")
    append_event(
        run,
        "run.finished",
        {"state": state, "reason": reason[:TEXT_CAP]},
        actor=actor or {"kind": "human", "name": "ailsa run close"},
        fsync=True,
    )
    head: str | None = None
    try:
        head = json.loads((run / FINISHED).read_text(encoding="utf-8")).get("head")
    except (OSError, ValueError):
        pass
    try:
        run_id = str(json.loads((run / MARKER).read_text(encoding="utf-8"))["run_id"])
        entry = _entry_from_log(run, run_id)
        entry["head"] = head
        update_index(workspace_root(create=True), entry)
    except Exception:  # noqa: BLE001 - the index is derived; the log is the truth
        pass
    return {"state": state, "head": head}
