"""Tests for `ailsa skill install`: lean skill and command skill (copy and link mode).

All tests run on a synthetic package tree and a temporary root; nothing touches the
real home folder.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from ailsa.cli import cli

LITE = (
    "---\nname: ailsa-lite\ndescription: lean skill\nmetadata:\n"
    '  version: "0.3.0"\n---\nbody\n'
)
INDEX = (
    "---\nname: ailsa\ndescription: Use when running a CASE\nmetadata:\n"
    '  version: "0.1.0"\n---\nindex\n'
)


def _build_tree(skills: Path) -> None:
    (skills / "ailsa-lite").mkdir(parents=True)
    (skills / "ailsa-lite" / "SKILL.md").write_text(LITE)
    ailsa = skills / "ailsa"
    (ailsa / "commands").mkdir(parents=True)
    (ailsa / "agents").mkdir()
    (ailsa / "references").mkdir()
    (ailsa / "INDEX.md").write_text(INDEX)
    (ailsa / "commands" / "case.md").write_text("case\n")
    (ailsa / "commands" / "status.md").write_text("status\n")
    (ailsa / "agents" / "ailsa-nmr-chemist.md").write_text("chemist\n")
    (ailsa / "agents" / "ailsa-diagnostic.md").write_text("diag\n")
    (ailsa / "references" / "lsd-reference.md").write_text("lsd\n")


@pytest.fixture
def fake_pkg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # A source checkout: <checkout>/pyproject.toml next to <checkout>/src/ailsa/skills.
    checkout = tmp_path / "pkg"
    skills = checkout / "src" / "ailsa" / "skills"
    _build_tree(skills)
    (checkout / "pyproject.toml").write_text("[project]\nname = 'ailsa'\n")
    monkeypatch.setattr("ailsa.cli.skill._skills_root", lambda: skills)
    return skills


@pytest.fixture(autouse=True)
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Every test runs with a temporary home folder; the real ~/.claude is never touched."""
    fake = tmp_path / "home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake))
    return fake


@pytest.fixture
def root(home: Path) -> Path:
    other = home / "other"
    other.mkdir(parents=True)
    (other / "keep.txt").write_text("keep\n")
    return home / ".claude"


def _run(*args: str) -> tuple[int, str]:
    result = CliRunner().invoke(cli, ["skill", *args])
    return result.exit_code, result.output


def _paths(root: Path) -> list[Path]:
    return [
        root / "commands" / "ailsa",
        root / "agents" / "ailsa-nmr-chemist.md",
        root / "agents" / "ailsa-diagnostic.md",
        root / "ailsa" / "references",
        root / "ailsa" / "INDEX.md",
    ]


def test_list_shows_both_kinds(fake_pkg: Path) -> None:
    code, out = _run("list")
    assert code == 0
    assert "ailsa-lite" in out
    assert "ailsa 0.1.0" in out
    assert "commands" in out
    assert "skill" in out


def test_copy_install_layout(fake_pkg: Path, root: Path) -> None:
    code, out = _run("install", "ailsa")
    assert code == 0, out
    for p in _paths(root):
        assert p.exists() and not p.is_symlink(), p
    assert (root / "commands" / "ailsa" / "case.md").read_text() == "case\n"
    assert (root / "ailsa" / "references" / "lsd-reference.md").is_file()
    assert "copy mode" in out


def test_link_install_layout(fake_pkg: Path, root: Path, tmp_path: Path) -> None:
    code, out = _run("install", "ailsa", "--link")
    assert code == 0, out
    for p in _paths(root):
        assert p.is_symlink(), p
        assert (tmp_path / "pkg") in p.resolve().parents
    assert "link mode" in out


def test_link_install_is_idempotent(fake_pkg: Path, root: Path) -> None:
    assert _run("install", "ailsa", "--link")[0] == 0
    assert _run("install", "ailsa", "--link")[0] == 0


def test_copy_refuses_existing_without_force(fake_pkg: Path, root: Path) -> None:
    assert _run("install", "ailsa")[0] == 0
    code, out = _run("install", "ailsa")
    assert code == 1
    assert "--force" in out


def test_copy_over_own_links_never_touches_package(fake_pkg: Path, root: Path) -> None:
    before = _state(fake_pkg)
    assert _run("install", "ailsa", "--link")[0] == 0
    # Links into the package are this skill's own: copy mode replaces them without --force.
    code, out = _run("install", "ailsa")
    assert code == 0, out
    assert _state(fake_pkg) == before
    for p in _paths(root):
        assert p.exists() and not p.is_symlink(), p


def test_foreign_link_needs_force(fake_pkg: Path, root: Path, tmp_path: Path) -> None:
    (root / "agents").mkdir(parents=True)
    mine = tmp_path / "mine.md"
    mine.write_text("custom\n")
    agent = root / "agents" / "ailsa-nmr-chemist.md"
    agent.symlink_to(mine)
    for mode in (["--link"], []):
        code, out = _run("install", "ailsa", *mode)
        assert code == 1, out
        assert "--force" in out
        assert agent.is_symlink() and agent.resolve() == mine.resolve()
    code, out = _run("install", "ailsa", "--force")
    assert code == 0, out
    assert agent.is_file() and not agent.is_symlink()
    assert agent.read_text() == "chemist\n"
    assert mine.read_text() == "custom\n"


def test_dropped_agent_link_removed(fake_pkg: Path, root: Path, tmp_path: Path) -> None:
    assert _run("install", "ailsa", "--link")[0] == 0
    mine = tmp_path / "mine.md"
    mine.write_text("custom\n")
    (root / "agents" / "ailsa-my-variant.md").symlink_to(mine)
    (fake_pkg / "ailsa" / "agents" / "ailsa-diagnostic.md").unlink()
    code, out = _run("install", "ailsa", "--link")
    assert code == 0, out
    stale = root / "agents" / "ailsa-diagnostic.md"
    assert not stale.is_symlink() and not stale.exists()
    assert "removed stale agent link" in out
    assert (root / "agents" / "ailsa-my-variant.md").is_symlink()
    assert mine.read_text() == "custom\n"


def test_dropped_agent_copy_removed_with_force(fake_pkg: Path, root: Path) -> None:
    assert _run("install", "ailsa")[0] == 0
    (fake_pkg / "ailsa" / "agents" / "ailsa-diagnostic.md").unlink()
    code, out = _run("install", "ailsa", "--force")
    assert code == 0, out
    assert not (root / "agents" / "ailsa-diagnostic.md").exists()
    assert "removed stale agent copy" in out
    assert (root / "agents" / "ailsa-nmr-chemist.md").read_text() == "chemist\n"


def test_legacy_cleanup_only_lucy_links(fake_pkg: Path, root: Path, tmp_path: Path) -> None:
    (root / "commands").mkdir(parents=True)
    (root / "agents").mkdir()
    old = tmp_path / "lucy-ng" / ".claude"
    (old / "commands" / "lucy-ng").mkdir(parents=True)
    (old / "agents").mkdir()
    (old / "agents" / "lucy-nmr-chemist.md").write_text("x\n")
    (old / "agents" / "supervisor.md").write_text("x\n")
    other = tmp_path / "other-project"
    other.mkdir()
    (other / "supervisor.md").write_text("theirs\n")
    (root / "commands" / "lucy-ng").symlink_to(old / "commands" / "lucy-ng")
    (root / "agents" / "lucy-nmr-chemist.md").symlink_to(old / "agents" / "lucy-nmr-chemist.md")
    (root / "agents" / "supervisor.md").symlink_to(other / "supervisor.md")
    (root / "agents" / "lucy-diagnostic.md").write_text("regular\n")
    code, out = _run("install", "ailsa")
    assert code == 0, out
    assert not (root / "commands" / "lucy-ng").is_symlink()
    assert not (root / "agents" / "lucy-nmr-chemist.md").is_symlink()
    # A generic name linked into another project is not ours: reported and kept.
    assert (root / "agents" / "supervisor.md").is_symlink()
    assert "left alone (link not into lucy-ng)" in out
    assert (root / "agents" / "lucy-diagnostic.md").read_text() == "regular\n"
    assert "left alone (not a link)" in out
    assert (old / "agents" / "lucy-nmr-chemist.md").read_text() == "x\n"
    assert (other / "supervisor.md").read_text() == "theirs\n"


@pytest.mark.parametrize(
    "where",
    [("lib", "python3.12", "site-packages", "ailsa", "skills"), ("target", "ailsa", "skills")],
    ids=["site-packages", "pip-target"],
)
def test_link_refused_outside_a_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, root: Path, where: tuple[str, ...]
) -> None:
    skills = tmp_path.joinpath(*where)
    _build_tree(skills)
    monkeypatch.setattr("ailsa.cli.skill._skills_root", lambda: skills)
    code, _ = _run("install", "ailsa", "--link")
    assert code == 1
    assert not (root / "commands").exists()
    assert not (root / "agents").exists()
    assert not (root / "ailsa").exists()


@pytest.mark.parametrize(
    "extra",
    [["--target", "opencode"], ["--project"], ["--dest", "x"]],
)
def test_command_skill_rejects_other_targets(
    fake_pkg: Path, root: Path, extra: list[str]
) -> None:
    code, _ = _run("install", "ailsa", *extra)
    assert code == 1


def test_root_option_gone(fake_pkg: Path, root: Path, tmp_path: Path) -> None:
    # The skill text reads ~/.claude/ailsa/references, so an install elsewhere cannot work.
    code, _ = _run("install", "ailsa", "--root", str(tmp_path / "elsewhere"))
    assert code == 2
    assert not (tmp_path / "elsewhere").exists()


def test_nothing_written_outside_root(fake_pkg: Path, root: Path, tmp_path: Path) -> None:
    def outside() -> set[Path]:
        return {p for p in (tmp_path / "home").rglob("*") if root not in (p, *p.parents)}

    before = outside()
    assert _run("install", "ailsa", "--link")[0] == 0
    assert outside() == before


def _state(tree: Path) -> list[tuple[str, str, str]]:
    """Every entry under tree: (relative path, kind, content or link target)."""
    out = []
    for p in sorted(tree.rglob("*")):
        rel = p.relative_to(tree).as_posix()
        if p.is_symlink():
            out.append((rel, "link", os.readlink(p)))
        elif p.is_dir():
            out.append((rel, "dir", ""))
        else:
            out.append((rel, "file", p.read_text()))
    return out


@pytest.mark.parametrize("mode", [["--link"], []], ids=["link", "copy"])
def test_symlinked_folder_into_package_refused(
    fake_pkg: Path, root: Path, mode: list[str]
) -> None:
    # ~/.claude/ailsa linked by hand to the package's skill folder: the obvious manual setup.
    before = _state(fake_pkg)
    root.mkdir(parents=True)
    (root / "ailsa").symlink_to(fake_pkg / "ailsa", target_is_directory=True)
    code, out = _run("install", "ailsa", *mode, "--force")
    assert code == 1, out
    assert "symlinked folder" in out
    assert _state(fake_pkg) == before
    assert not (root / "commands").exists()
    assert not (root / "agents").exists()


def test_root_resolving_into_package_refused(
    fake_pkg: Path, root: Path, tmp_path: Path
) -> None:
    before = _state(fake_pkg)
    root.parent.mkdir(parents=True, exist_ok=True)
    root.symlink_to(fake_pkg / "ailsa", target_is_directory=True)
    code, out = _run("install", "ailsa", "--link", "--force")
    assert code == 1, out
    assert "package's own skill files" in out
    assert _state(fake_pkg) == before


def test_refused_install_changes_nothing(fake_pkg: Path, root: Path, tmp_path: Path) -> None:
    (root / "agents").mkdir(parents=True)
    (root / "agents" / "ailsa-nmr-chemist.md").write_text("mine\n")
    old = tmp_path / "lucy-ng" / ".claude" / "commands" / "lucy-ng"
    old.mkdir(parents=True)
    (root / "commands").mkdir()
    (root / "commands" / "lucy-ng").symlink_to(old, target_is_directory=True)
    before = _state(root)
    code, out = _run("install", "ailsa")
    assert code == 1
    assert "--force" in out
    assert "Nothing was changed" in out
    assert _state(root) == before


def test_lite_dest_inside_package_refused(fake_pkg: Path) -> None:
    before = _state(fake_pkg)
    code, out = _run("install", "ailsa-lite", "--dest", str(fake_pkg), "--force")
    assert code == 1, out
    assert _state(fake_pkg) == before


def test_lite_install_unchanged(fake_pkg: Path, tmp_path: Path) -> None:
    dest = tmp_path / "dest-skills"
    code, out = _run("install", "ailsa-lite", "--dest", str(dest))
    assert code == 0, out
    assert (dest / "ailsa-lite" / "SKILL.md").read_text() == LITE


def test_lite_force_over_symlink_unlinks(fake_pkg: Path, tmp_path: Path) -> None:
    dest = tmp_path / "dest-skills"
    dest.mkdir()
    old = tmp_path / "old"
    old.mkdir()
    (old / "marker.txt").write_text("m\n")
    (dest / "ailsa-lite").symlink_to(old, target_is_directory=True)
    code, out = _run("install", "ailsa-lite", "--dest", str(dest), "--force")
    assert code == 0, out
    assert not (dest / "ailsa-lite").is_symlink()
    assert (old / "marker.txt").read_text() == "m\n"


def test_lite_force_over_regular_file(fake_pkg: Path, tmp_path: Path) -> None:
    dest = tmp_path / "dest-skills"
    dest.mkdir()
    (dest / "ailsa-lite").write_text("file\n")
    code, out = _run("install", "ailsa-lite", "--dest", str(dest), "--force")
    assert code == 0, out
    assert (dest / "ailsa-lite" / "SKILL.md").read_text() == LITE


def test_real_package_has_command_skill() -> None:
    from ailsa.cli.skill import available_skills

    skills = available_skills()
    assert skills["ailsa"]["kind"] == "commands"
    assert skills["ailsa"]["version"] == "0.2.0"
    assert "ailsa-lite" in skills


def test_real_copy_install(root: Path) -> None:
    from ailsa.cli.skill import available_skills

    code, out = _run("install", "ailsa")
    assert code == 0, out
    package = Path(available_skills()["ailsa"]["path"])
    assert len(list((root / "commands" / "ailsa").glob("*.md"))) == 6
    assert len(list((root / "agents").glob("ailsa-*.md"))) == 5
    refs = sorted((package / "references").glob("*.md"))
    assert refs, f"no reference files found under {package / 'references'}"
    for ref in refs:
        assert (root / "ailsa" / "references" / ref.name).is_file()
    assert (root / "ailsa" / "INDEX.md").is_file()
