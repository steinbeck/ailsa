"""Tests for `ailsa skill install`: lean skill and command skill (copy and link mode).

All tests run on a synthetic package tree and a temporary root; nothing touches the
real home folder.
"""

from __future__ import annotations

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
    skills = tmp_path / "pkg" / "skills"
    _build_tree(skills)
    monkeypatch.setattr("ailsa.cli.skill._skills_root", lambda: skills)
    return skills


@pytest.fixture
def root(tmp_path: Path) -> Path:
    other = tmp_path / "home" / "other"
    other.mkdir(parents=True)
    (other / "keep.txt").write_text("keep\n")
    return tmp_path / "home" / ".claude"


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
    code, out = _run("install", "ailsa", "--root", str(root))
    assert code == 0, out
    for p in _paths(root):
        assert p.exists() and not p.is_symlink(), p
    assert (root / "commands" / "ailsa" / "case.md").read_text() == "case\n"
    assert (root / "ailsa" / "references" / "lsd-reference.md").is_file()
    assert "copy mode" in out


def test_link_install_layout(fake_pkg: Path, root: Path, tmp_path: Path) -> None:
    code, out = _run("install", "ailsa", "--link", "--root", str(root))
    assert code == 0, out
    for p in _paths(root):
        assert p.is_symlink(), p
        assert (tmp_path / "pkg") in p.resolve().parents
    assert "link mode" in out


def test_link_install_is_idempotent(fake_pkg: Path, root: Path) -> None:
    assert _run("install", "ailsa", "--link", "--root", str(root))[0] == 0
    assert _run("install", "ailsa", "--link", "--root", str(root))[0] == 0


def test_copy_refuses_existing_without_force(fake_pkg: Path, root: Path) -> None:
    assert _run("install", "ailsa", "--root", str(root))[0] == 0
    code, out = _run("install", "ailsa", "--root", str(root))
    assert code == 1
    assert "--force" in out


def test_force_over_symlink_never_touches_package(fake_pkg: Path, root: Path) -> None:
    assert _run("install", "ailsa", "--link", "--root", str(root))[0] == 0
    code, out = _run("install", "ailsa", "--force", "--root", str(root))
    assert code == 0, out
    assert (fake_pkg / "ailsa" / "commands" / "case.md").read_text() == "case\n"
    assert (fake_pkg / "ailsa" / "references" / "lsd-reference.md").read_text() == "lsd\n"
    assert (fake_pkg / "ailsa" / "agents" / "ailsa-nmr-chemist.md").read_text() == "chemist\n"
    assert (root / "commands" / "ailsa").is_dir()
    assert not (root / "commands" / "ailsa").is_symlink()


def test_legacy_cleanup_only_symlinks(fake_pkg: Path, root: Path, tmp_path: Path) -> None:
    (root / "commands").mkdir(parents=True)
    (root / "agents").mkdir()
    target = tmp_path / "somewhere"
    target.mkdir()
    (target / "f.md").write_text("x\n")
    (root / "commands" / "lucy-ng").symlink_to(target)
    (root / "agents" / "lucy-nmr-chemist.md").symlink_to(target / "f.md")
    (root / "agents" / "supervisor.md").symlink_to(target / "f.md")
    (root / "agents" / "lucy-diagnostic.md").write_text("regular\n")
    code, out = _run("install", "ailsa", "--root", str(root))
    assert code == 0, out
    assert not (root / "commands" / "lucy-ng").is_symlink()
    assert not (root / "agents" / "lucy-nmr-chemist.md").is_symlink()
    assert not (root / "agents" / "supervisor.md").is_symlink()
    assert (root / "agents" / "lucy-diagnostic.md").read_text() == "regular\n"
    assert "left alone (not a link)" in out
    assert (target / "f.md").read_text() == "x\n"


def test_link_refused_from_site_packages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, root: Path
) -> None:
    skills = tmp_path / "lib" / "python3.12" / "site-packages" / "ailsa" / "skills"
    _build_tree(skills)
    monkeypatch.setattr("ailsa.cli.skill._skills_root", lambda: skills)
    code, _ = _run("install", "ailsa", "--link", "--root", str(root))
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
    code, _ = _run("install", "ailsa", "--root", str(root), *extra)
    assert code == 1


def test_nothing_written_outside_root(fake_pkg: Path, root: Path, tmp_path: Path) -> None:
    def outside() -> set[Path]:
        return {p for p in (tmp_path / "home").rglob("*") if root not in (p, *p.parents)}

    before = outside()
    assert _run("install", "ailsa", "--link", "--root", str(root))[0] == 0
    assert outside() == before


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


def test_real_package_has_command_skill() -> None:
    from ailsa.cli.skill import available_skills

    skills = available_skills()
    assert skills["ailsa"]["kind"] == "commands"
    assert skills["ailsa"]["version"] == "0.1.0"
    assert "ailsa-lite" in skills


def test_real_copy_install(tmp_path: Path) -> None:
    from ailsa.cli.skill import available_skills

    root = tmp_path / "root"
    code, out = _run("install", "ailsa", "--root", str(root))
    assert code == 0, out
    package = Path(available_skills()["ailsa"]["path"]).parent
    assert len(list((root / "commands" / "ailsa").glob("*.md"))) == 6
    assert len(list((root / "agents").glob("ailsa-*.md"))) == 5
    for ref in (package / "references").glob("*.md"):
        assert (root / "ailsa" / "references" / ref.name).is_file()
