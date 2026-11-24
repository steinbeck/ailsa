"""A fake ``ssh`` for remote-solve tests: runs the remote command locally inside a fake root.

``install_fake_ssh(bin_dir, fake_root)`` writes an executable ``ssh`` into ``bin_dir`` and sets up
``fake_root`` as the remote home: ``fake_root/bin`` holds the remote programs (put fake LSD there)
and is added to PATH only by the login-shell profile, so the remote PATH gap of a non-interactive
ssh is reproduced. Every call is appended to ``fake_root/ssh-calls.log`` (argv as JSON lines).

The alias ``unreachable`` exits 255 like an unreachable host.
"""

from __future__ import annotations

import stat
import sys
from pathlib import Path

_SCRIPT = """#!{python}
import json, os, subprocess, sys
root = {root!r}
args = sys.argv[1:]
with open(os.path.join(root, "ssh-calls.log"), "a") as log:
    log.write(json.dumps(args) + "\\n")
opts = []
i = 0
while i < len(args):
    if args[i] == "-o":
        opts.append(args[i + 1])
        i += 2
    elif args[i] == "--":
        i += 1
        break
    else:
        break
alias, command = args[i], " ".join(args[i + 1:])
if alias == "unreachable":
    sys.stderr.write("ssh: connect to host unreachable: no route\\n")
    sys.exit(255)
env = {{
    "HOME": root,
    "PATH": "/usr/bin:/bin",
    "TMPDIR": os.path.join(root, "tmp"),
}}
proc = subprocess.run(["bash", "-c", command], env=env, stdin=sys.stdin.buffer)
sys.exit(proc.returncode)
"""


def install_fake_ssh(bin_dir: Path, fake_root: Path) -> Path:
    bin_dir.mkdir(parents=True, exist_ok=True)
    fake_root.mkdir(parents=True, exist_ok=True)
    (fake_root / "bin").mkdir(exist_ok=True)
    (fake_root / "tmp").mkdir(exist_ok=True)
    (fake_root / ".bash_profile").write_text(f'export PATH="{fake_root}/bin:$PATH"\n')
    ssh = bin_dir / "ssh"
    ssh.write_text(_SCRIPT.format(python=sys.executable, root=str(fake_root)))
    ssh.chmod(ssh.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return bin_dir
