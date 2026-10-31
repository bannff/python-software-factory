"""Layered skill store: built-ins win reads, the user root owns writes."""
from __future__ import annotations

from pathlib import Path

import pytest

from factory.agent.authoring.roots import AuthoringRootUnavailable
from factory.agent.runtime import skill_store
from factory.agent.runtime.execution_manifest.preparation_support import freeze_skills
from factory.agent.runtime.skill_store import BuiltinSkillError


@pytest.fixture
def user_root(monkeypatch, tmp_path) -> Path:
    root = tmp_path / "agent-skills"
    monkeypatch.setenv("FACTORY_AGENT_SKILLS_DIR", str(root))
    return root


def _write_skill(root: Path, skill_id: str, name: str, body: str) -> None:
    directory = root / skill_id
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: seeded\n---\n\n{body}\n", encoding="utf-8",
    )


def test_builtins_are_listed_from_the_packaged_root(user_root) -> None:
    ids = {skill.id for skill in skill_store.list_skills()}
    packaged = {p.name for p in skill_store.packaged_skills_root().iterdir() if p.is_dir()}
    assert packaged and packaged <= ids
    assert all(skill.builtin for skill in skill_store.list_skills() if skill.id in packaged)


def test_add_targets_the_user_root_and_refuses_builtin_ids(user_root) -> None:
    builtin = sorted(p.name for p in skill_store.packaged_skills_root().iterdir() if p.is_dir())[0]
    with pytest.raises(FileExistsError):
        skill_store.add_skill(builtin, "Shadow", "", "nope")
    assert not (skill_store.packaged_skills_root() / builtin).joinpath("SKILL.md").read_text().startswith(
        "---\nname: Shadow"
    )

    skill_store.add_skill("user-owned", "User Owned", "local", "body text")
    assert (user_root / "user-owned" / "SKILL.md").is_file()
    assert not (skill_store.packaged_skills_root() / "user-owned").exists()
    with pytest.raises(FileExistsError):
        skill_store.add_skill("user-owned", "Again", "", "body text")
    stored = skill_store.read_skill("user-owned")
    assert stored is not None and stored[0].builtin is False and stored[1] == "body text"


def test_builtins_win_a_read_collision(user_root) -> None:
    builtin = sorted(p.name for p in skill_store.packaged_skills_root().iterdir() if p.is_dir())[0]
    packaged_body = (skill_store.packaged_skills_root() / builtin / "SKILL.md").read_text()
    _write_skill(user_root, builtin, "Shadowed", "user body")
    stored = skill_store.read_skill(builtin)
    assert stored is not None
    assert stored[0].builtin is True
    assert stored[0].path == skill_store.packaged_skills_root() / builtin / "SKILL.md"
    assert packaged_body in stored[0].path.read_text()
    listed = [skill for skill in skill_store.list_skills() if skill.id == builtin]
    assert len(listed) == 1 and listed[0].builtin is True


def test_delete_cannot_remove_a_builtin_but_removes_a_user_skill(user_root) -> None:
    builtin = sorted(p.name for p in skill_store.packaged_skills_root().iterdir() if p.is_dir())[0]
    with pytest.raises(BuiltinSkillError):
        skill_store.delete_skill(builtin)
    assert (skill_store.packaged_skills_root() / builtin / "SKILL.md").is_file()

    skill_store.add_skill("throwaway", "Throwaway", "", "x")
    assert skill_store.delete_skill("throwaway") is True
    assert skill_store.delete_skill("throwaway") is False
    assert skill_store.read_skill("throwaway") is None


def test_skill_dir_layering_and_traversal_safety(user_root, tmp_path) -> None:
    skill_store.add_skill("layered", "Layered", "", "x")
    assert skill_store.skill_dir("layered") == (user_root / "layered").resolve()
    builtin = sorted(p.name for p in skill_store.packaged_skills_root().iterdir() if p.is_dir())[0]
    assert skill_store.skill_dir(builtin) == skill_store.packaged_skills_root() / builtin
    assert skill_store.skill_dir("../escape") is None
    outside = tmp_path / "outside"
    _write_skill(outside, "secret", "Secret", "s")
    (user_root / "linked").symlink_to(outside / "secret", target_is_directory=True)
    assert skill_store.skill_dir("linked") is None
    assert skill_store.read_skill("linked") is None


def test_symlinked_or_packaged_user_root_refuses_writes(monkeypatch, tmp_path) -> None:
    """Writes must never be redirected by a link, nor land in the package."""
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    monkeypatch.setenv("FACTORY_AGENT_SKILLS_DIR", str(link))
    with pytest.raises(AuthoringRootUnavailable):
        skill_store.add_skill("zzz-sym", "S", "", "b")
    assert list(target.iterdir()) == []

    monkeypatch.setenv("FACTORY_AGENT_SKILLS_DIR", str(skill_store.packaged_skills_root()))
    with pytest.raises(AuthoringRootUnavailable):
        skill_store.add_skill("zzz-pkg", "P", "", "b")
    assert not (skill_store.packaged_skills_root() / "zzz-pkg").exists()


def test_manifest_freeze_resolves_user_and_builtin_skills(user_root) -> None:
    skill_store.add_skill("frozen", "Frozen", "", "freeze me")
    builtin = sorted(p.name for p in skill_store.packaged_skills_root().iterdir() if p.is_dir())[0]
    bundle = freeze_skills(["frozen", builtin])
    assert bundle.names == ("frozen", builtin)
    assert {item.path for item in bundle.files} == {
        "frozen/SKILL.md", f"{builtin}/SKILL.md",
    }
    with pytest.raises(ValueError, match="unknown skill"):
        freeze_skills(["not-a-skill"])
