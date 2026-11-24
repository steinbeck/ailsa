"""Fake LSD and outlsd programs for solver tests (no real solver is ever started).

``install_fake_lsd(bin_dir, mode, **params)`` writes executable ``LSD``, ``lsd`` and
``outlsd`` shims into ``bin_dir`` and a ``fake_lsd.json`` next to them. Put ``bin_dir`` on
PATH to use them. Modes:

- ``solutions`` (``count``): writes ``<stem>.sol`` with that many solutions and ``solncounter``.
- ``nosolution``: prints ``No solution found``; the ``.sol`` holds only the input echo.
- ``error`` (``code``): prints ``error <code> - 6 commands read`` and an explanation line.
- ``sleep`` (``seconds``, ``partial``): writes ``solncounter`` with ``partial``, then sleeps.
- ``maxs``: as ``solutions`` with the count taken from the input's ``MAXS`` line.

``outlsd`` writes one SMILES per solution, or fails (``outlsd="fail"``).
"""

from __future__ import annotations

import json
import stat
import sys
from pathlib import Path

CONFIG_NAME = "fake_lsd.json"

_LSD_SCRIPT = '''#!{python}
import json, os, sys, time
here = os.path.dirname(os.path.realpath(__file__))
cfg = json.load(open(os.path.join(here, "{config}")))
if len(sys.argv) < 2 or sys.argv[1].startswith("-"):
    print("LSD-3.4.9 (fake)")
    sys.exit(1)
src = sys.argv[1]
stem = os.path.splitext(os.path.basename(src))[0]
mode = cfg["mode"]
text = open(src).read()
def write(count):
    with open(stem + ".sol", "w") as fh:
        fh.write(text)
        for i in range(count):
            fh.write("SOLUTION %d\\n" % (i + 1))
    with open("solncounter", "w") as fh:
        fh.write("%d\\n" % count)
print("LSD-3.4.9 (fake)")
if mode == "error":
    print("error %s - 6 commands read" % cfg.get("code", 420))
    print("unknown command in input")
    sys.exit(1)
if mode == "nosolution":
    write(0)
    print("No solution found")
elif mode == "sleep":
    with open("solncounter", "w") as fh:
        fh.write("%d\\n" % cfg.get("partial", 12))
    sys.stdout.flush()
    time.sleep(cfg.get("seconds", 10))
elif mode == "maxs":
    limit = 1
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0].upper() == "MAXS":
            limit = int(parts[1])
    write(limit)
    print("%d solutions" % limit)
else:
    n = int(cfg.get("count", 3))
    write(n)
    print("%d solutions" % n)
'''

_OUTLSD_SCRIPT = '''#!{python}
import json, os, sys
here = os.path.dirname(os.path.realpath(__file__))
cfg = json.load(open(os.path.join(here, "{config}")))
data = sys.stdin.read()
if cfg.get("outlsd") == "fail":
    print("outlsd: usage: outlsd p")
    sys.exit(0)
for line in data.splitlines():
    if line.startswith("SOLUTION"):
        print("CCO")
'''


def _write_exec(path: Path, text: str) -> None:
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def install_fake_lsd(bin_dir: Path, mode: str = "solutions", **params: object) -> Path:
    """Write the shims and the mode file into ``bin_dir``; return ``bin_dir``."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / CONFIG_NAME).write_text(json.dumps({"mode": mode, **params}))
    lsd = _LSD_SCRIPT.format(python=sys.executable, config=CONFIG_NAME)
    for name in ("LSD", "lsd"):
        _write_exec(bin_dir / name, lsd)
    _write_exec(bin_dir / "outlsd", _OUTLSD_SCRIPT.format(python=sys.executable, config=CONFIG_NAME))
    return bin_dir
