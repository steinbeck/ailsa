"""ailsa skill: install the agent skills that ship with this version of ailsa.

A skill must match the CLI it calls, so the skills are package data and are installed
from the installed package, never from a separate download.
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


def _skills_root() -> Path:
    with as_file(files("ailsa") / "skills") as root:
        return Path(root)


def available_skills() -> dict[str, dict[str, str]]:
    """Name -> {description, version, path} of every skill in the package."""
    result: dict[str, dict[str, str]] = {}
    root = _skills_root()
    for skill_md in sorted(root.glob("*/SKILL.md")):
        text = skill_md.read_text()
        name = re.search(r"^name:\s*(\S+)", text, re.MULTILINE)
        version = re.search(r'^\s+version:\s*"?([^"\n]+)"?', text, re.MULTILINE)
        desc = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
        if name:
            result[name.group(1)] = {
                "description": desc.group(1).strip() if desc else "",
                "version": version.group(1).strip() if version else "",
                "path": str(skill_md.parent),
            }
    return result


@click.group()
def skill() -> None:
    """Agent skills shipped with ailsa (list, install)."""


@skill.command("list")
def list_cmd() -> None:
    """List the skills in this version of ailsa."""
    for name, info in available_skills().items():
        click.echo(f"{name} {info['version']}\n  {info['description']}\n  {info['path']}")


@skill.command("install")
@click.argument("name")
@click.option(
    "--target",
    type=click.Choice(sorted(TARGETS)),
    default="opencode",
    show_default=True,
    help="The harness to install for.",
)
@click.option("--project", is_flag=True, help="Install into the current folder, not globally.")
@click.option(
    "--dest",
    type=click.Path(file_okay=False),
    default=None,
    help="Install into this skills folder instead.",
)
@click.option("--force", is_flag=True, help="Replace an installed copy.")
def install_cmd(name: str, target: str, project: bool, dest: str | None, force: bool) -> None:
    """Copy skill NAME into the skills folder of a harness."""
    skills = available_skills()
    if name not in skills:
        click.echo(f"Error: no skill {name!r}. Available: {', '.join(skills) or 'none'}")
        raise SystemExit(1)
    folder = Path(dest) if dest else TARGETS[target][1 if project else 0]
    destination = folder / name
    if destination.exists():
        if not force:
            click.echo(f"Error: {destination} exists. Use --force to replace it.")
            raise SystemExit(1)
        shutil.rmtree(destination)
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copytree(skills[name]["path"], destination)
    click.echo(f"Installed {name} {skills[name]['version']} to {destination}")
