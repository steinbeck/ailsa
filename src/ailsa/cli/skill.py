"""ailsa skill: install the agent skills that ship with this version of ailsa.

A skill must match the CLI it calls, so the skills are package data and are installed
from the installed package, never from a separate download.

Two kinds of skill exist: Agent Skills (a folder with ``SKILL.md``, copied into the skills
folder of a harness) and the command skill (a folder with ``INDEX.md``, ``commands/``,
``agents/`` and ``references/``, installed into ``~/.claude`` by copy or by symlink).
"""

from __future__ import annotations

import re
import shutil
from importlib.resources import as_file, files
from pathlib import Path

import click

# Where each harness looks for skills (global, then project-level).
TARGETS: dict[str, tuple[Path, Path]] = {
    "opencode": (Path.home() / ".config" / "opencode" / "skills", Path(".opencode") / "skills"),
    "claude": (Path.home() / ".claude" / "skills", Path(".claude") / "skills"),
    "agents": (Path.home() / ".agents" / "skills", Path(".agents") / "skills"),
}

# Old links from before the rename, relative to the install root. Only symlinks are removed.
LEGACY_LINKS: tuple[str, ...] = (
    "commands/lucy-ng",
    "agents/lucy-nmr-chemist.md",
    "agents/lucy-lsd-engineer.md",
    "agents/lucy-solution-analyst.md",
    "agents/lucy-devils-advocate.md",
    "agents/lucy-diagnostic.md",
    "agents/supervisor.md",
)


def _skills_root() -> Path:
    with as_file(files("ailsa") / "skills") as root:
        return Path(root)


def available_skills() -> dict[str, dict[str, str]]:
    """Name -> {description, version, path, kind} of every skill in the package."""
    result: dict[str, dict[str, str]] = {}
    root = _skills_root()
    entries = [(p, "skill") for p in sorted(root.glob("*/SKILL.md"))]
    entries += [(p, "commands") for p in sorted(root.glob("*/INDEX.md"))]
    for md, kind in entries:
        text = md.read_text()
        name = re.search(r"^name:\s*(\S+)", text, re.MULTILINE)
        version = re.search(r'^\s+version:\s*"?([^"\n]+)"?', text, re.MULTILINE)
        desc = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
        if name:
            result[name.group(1)] = {
                "description": desc.group(1).strip() if desc else "",
                "version": version.group(1).strip() if version else "",
                "path": str(md.parent),
                "kind": kind,
            }
    return result


def _is_site_packages(path: Path) -> bool:
    return any(part in ("site-packages", "dist-packages") for part in path.parts)


def _remove_owned(dst: Path) -> None:
    """Remove a regular file or directory at an owned path (never a symlink target)."""
    if dst.is_symlink():
        dst.unlink()
    elif dst.is_dir():
        shutil.rmtree(dst)
    else:
        dst.unlink()


def _inside(path: Path, base: Path) -> bool:
    return path == base or base in path.parents


def _destination_problem(dst: Path, root: Path, package: Path) -> str | None:
    """Return why dst must not be written, or None.

    Symlinks are resolved in every folder above dst, never in dst itself (an old link there
    is replaced, not followed). A folder that resolves outside root, or a destination that
    lands in the package's own skill files, would make the install delete or overwrite the
    files it is about to install.
    """
    root_r = root.resolve()
    parent_r = dst.parent.resolve()
    if not _inside(parent_r, root_r):
        return (
            f"{dst.parent} resolves to {parent_r}, outside {root} (a symlinked folder?). "
            "Refusing to write through it."
        )
    target = parent_r / dst.name
    package_r = package.resolve()
    if _inside(target, package_r) or _inside(package_r, target):
        return (
            f"{dst} resolves to {target}, inside the package's own skill files "
            f"({package_r}). Refusing to write there."
        )
    return None


def _place(src: Path, dst: Path, link: bool) -> str:
    """Link or copy src to dst; return one output line. Call only after _preflight."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_symlink() or dst.exists():
        _remove_owned(dst)
    if link:
        dst.symlink_to(src, target_is_directory=src.is_dir())
        return f"linked {dst} -> {src}"
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)
    return f"copied {src} -> {dst}"


def _drop_legacy(root: Path) -> list[str]:
    """Remove old lucy-ng symlinks; report anything else of that name and leave it."""
    lines: list[str] = []
    for rel in LEGACY_LINKS:
        path = root / rel
        if path.is_symlink():
            path.unlink()
            lines.append(f"removed legacy link {path}")
        elif path.exists():
            lines.append(f"left alone (not a link): {path}")
    return lines


def _plan(src_dir: Path, root: Path) -> list[tuple[Path, Path]]:
    """(source, destination) of every file or folder the command skill places under root."""
    pairs = [(src_dir / "commands", root / "commands" / "ailsa")]
    pairs += [(a, root / "agents" / a.name) for a in sorted((src_dir / "agents").glob("*.md"))]
    pairs.append((src_dir / "references", root / "ailsa" / "references"))
    pairs.append((src_dir / "INDEX.md", root / "ailsa" / "INDEX.md"))
    return pairs


def _preflight(
    pairs: list[tuple[Path, Path]], root: Path, package: Path, force: bool
) -> list[str]:
    """Every reason not to start, collected before anything on disk changes."""
    problems: list[str] = []
    legacy = [root / rel for rel in LEGACY_LINKS]
    legacy = [p for p in legacy if p.is_symlink() or p.exists()]
    for dst in [d for _, d in pairs] + legacy:
        why = _destination_problem(dst, root, package)
        if why:
            problems.append(why)
        elif dst not in legacy and not dst.is_symlink() and dst.exists() and not force:
            problems.append(f"{dst} exists. Use --force to replace it.")
    return problems


def _install_command_skill(src_dir: Path, root: Path, link: bool, force: bool) -> list[str]:
    """Install commands, agents and references of the command skill under root.

    Two passes: every destination is checked first, and only a clean check lets the install
    remove legacy links and place files. A refused install leaves the disk as it was.
    """
    pairs = _plan(src_dir, root)
    problems = _preflight(pairs, root, src_dir.parent, force)
    if problems:
        for why in problems:
            click.echo(f"Error: {why}")
        click.echo("Nothing was changed.")
        raise SystemExit(1)
    lines = _drop_legacy(root)
    lines += [_place(src, dst, link) for src, dst in pairs]
    return lines


@click.group()
def skill() -> None:
    """Agent skills shipped with ailsa (list, install)."""


@skill.command("list")
def list_cmd() -> None:
    """List the skills in this version of ailsa."""
    for name, info in available_skills().items():
        click.echo(
            f"{name} {info['version']} ({info['kind']})\n  {info['description']}\n  {info['path']}"
        )


@skill.command("install")
@click.argument("name")
@click.option(
    "--target",
    type=click.Choice(sorted(TARGETS)),
    default=None,
    help="The harness to install an Agent Skill for (default opencode; claude for the "
    "command skill).",
)
@click.option("--project", is_flag=True, help="Install into the current folder, not globally.")
@click.option(
    "--dest",
    type=click.Path(file_okay=False),
    default=None,
    help="Install into this skills folder instead.",
)
@click.option("--force", is_flag=True, help="Replace an installed copy.")
@click.option(
    "--link",
    is_flag=True,
    help="Command skill only: create symlinks into a source checkout instead of copies "
    "(for maintainers; refused for an installed wheel).",
)
@click.option(
    "--root",
    type=click.Path(file_okay=False),
    default=None,
    help="Command skill only: install under this folder (default ~/.claude).",
)
def install_cmd(
    name: str,
    target: str | None,
    project: bool,
    dest: str | None,
    force: bool,
    link: bool,
    root: str | None,
) -> None:
    """Install skill NAME: copy an Agent Skill, or copy/link the command skill."""
    skills = available_skills()
    if name not in skills:
        click.echo(f"Error: no skill {name!r}. Available: {', '.join(skills) or 'none'}")
        raise SystemExit(1)
    info = skills[name]
    if info["kind"] == "commands":
        if (target is not None and target != "claude") or project or dest:
            click.echo(
                "Error: the command skill installs only into ~/.claude; "
                "use --root to choose another folder."
            )
            raise SystemExit(1)
        src_dir = Path(info["path"])
        if link and _is_site_packages(src_dir):
            click.echo("Error: --link needs a source checkout; this install is a wheel.")
            raise SystemExit(1)
        root_dir = Path(root) if root else Path.home() / ".claude"
        for line in _install_command_skill(src_dir, root_dir, link, force):
            click.echo(line)
        mode = "link mode" if link else "copy mode"
        click.echo(f"Installed {name} {info['version']} into {root_dir} ({mode})")
        return
    if link or root:
        click.echo("Error: --link and --root apply to the command skill only.")
        raise SystemExit(1)
    folder = Path(dest) if dest else TARGETS[target or "opencode"][1 if project else 0]
    destination = folder / name
    why = _destination_problem(destination, folder, Path(info["path"]).parent)
    if why:
        click.echo(f"Error: {why}")
        raise SystemExit(1)
    if destination.is_symlink() or destination.exists():
        if not force:
            click.echo(f"Error: {destination} exists. Use --force to replace it.")
            raise SystemExit(1)
        if destination.is_symlink():
            destination.unlink()
        else:
            shutil.rmtree(destination)
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copytree(info["path"], destination)
    click.echo(f"Installed {name} {info['version']} to {destination}")
