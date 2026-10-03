"""The documented installer must work from a fresh checkout without overwriting skills."""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def checkout(tmp_path):
    root = tmp_path / "aea"
    (root / "tools").mkdir(parents=True)
    shutil.copyfile(ROOT / "tools" / "install_skills.py", root / "tools" / "install_skills.py")
    for skill_file in sorted((ROOT / "skills").glob("*/SKILL.md")):
        destination = root / "skills" / skill_file.parent.name
        destination.mkdir(parents=True)
        shutil.copyfile(skill_file, destination / "SKILL.md")
    return root


def run_installer(checkout, *args):
    # The caller's working directory is outside the checkout.
    return subprocess.run([sys.executable, str(checkout / "tools" / "install_skills.py"),
                           *args], cwd=checkout.parent, capture_output=True, text=True)


@pytest.mark.parametrize("agent,folders", [
    ("codex", (".agents",)),
    ("claude", (".claude",)),
    ("both", (".agents", ".claude")),
])
def test_installs_selected_clients_and_repeated_run_is_noop(checkout, agent, folders):
    sources = sorted((checkout / "skills").iterdir())
    result = run_installer(checkout, "--agent", agent)
    assert result.returncode == 0, result.stderr
    for folder in folders:
        installed = checkout / folder / "skills"
        assert sorted(p.name for p in installed.iterdir()) == [p.name for p in sources]
        for source in sources:
            link = installed / source.name
            assert link.is_symlink()
            assert not Path(os.readlink(link)).is_absolute()
            assert link.resolve() == source
            assert (link / "SKILL.md").read_bytes() == (source / "SKILL.md").read_bytes()
    for folder in set((".agents", ".claude")) - set(folders):
        assert not (checkout / folder).exists()

    result = run_installer(checkout, "--agent", agent)
    assert result.returncode == 0, result.stderr
    assert "created 0 link(s)" in result.stdout
    assert f"{len(sources) * len(folders)} already installed" in result.stdout


def test_links_reflect_updated_and_added_source_files(checkout):
    result = run_installer(checkout, "--agent", "both")
    assert result.returncode == 0, result.stderr
    skill = checkout / "skills" / "eeg-erp"
    (skill / "SKILL.md").write_text("Updated skill\n", encoding="utf-8")
    (skill / "helper.py").write_text("new helper\n", encoding="utf-8")
    for folder in (".agents", ".claude"):
        installed = checkout / folder / "skills" / skill.name
        assert (installed / "SKILL.md").read_text(encoding="utf-8-sig") == "Updated skill\n"
        assert (installed / "helper.py").read_text(encoding="utf-8-sig") == "new helper\n"


@pytest.mark.parametrize("kind", ("file", "directory", "symlink"))
def test_conflict_preserves_user_entry_and_creates_no_partial_install(checkout, kind):
    destination_dir = checkout / ".claude" / "skills"
    destination_dir.mkdir(parents=True)
    conflict = destination_dir / "eeg-tfr"
    if kind == "file":
        conflict.write_text("user file", encoding="utf-8")
    elif kind == "directory":
        conflict.mkdir()
        (conflict / "user.txt").write_text("user skill", encoding="utf-8")
    else:
        conflict.symlink_to("missing-user-skill", target_is_directory=True)
    unrelated = destination_dir / "my-skill"
    unrelated.mkdir()

    result = run_installer(checkout, "--agent", "both")
    assert result.returncode == 1
    assert str(conflict) in result.stderr
    assert "No links created" in result.stderr
    assert not (checkout / ".agents").exists()
    assert sorted(p.name for p in destination_dir.iterdir()) == ["eeg-tfr", "my-skill"]
    if kind == "file":
        assert conflict.read_text(encoding="utf-8-sig") == "user file"
    elif kind == "directory":
        assert (conflict / "user.txt").read_text(encoding="utf-8-sig") == "user skill"
    else:
        assert conflict.is_symlink()
        assert os.readlink(conflict) == "missing-user-skill"


def test_agent_is_required(checkout):
    result = run_installer(checkout)
    assert result.returncode == 2
    assert "--agent" in result.stderr
    assert not (checkout / ".agents").exists()
    assert not (checkout / ".claude").exists()


def test_windows_symlink_permission_error_is_actionable(checkout, monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location("aea_install_skills",
                                                checkout / "tools" / "install_skills.py")
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)

    def deny_symlink(*args, **kwargs):
        error = OSError("A required privilege is not held by the client")
        error.winerror = 1314
        raise error

    monkeypatch.setattr(installer.os, "symlink", deny_symlink)
    assert installer.main(["--agent", "codex"]) == 1
    error = capsys.readouterr().err
    assert "Developer Mode" in error
    assert "terminal with symlink privileges" in error
    assert "WSL" in error
