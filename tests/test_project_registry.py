from __future__ import annotations

from pathlib import Path

import pytest

from project_analyzer.app_config import load_app_config
from project_analyzer.services.project_registry import ProjectRegistry


def test_add_project_persists_and_deduplicates_local_paths(tmp_path: Path, local_python_project: Path) -> None:
    registry = ProjectRegistry(tmp_path / "app.yaml")

    added = registry.add_project(str(local_python_project))
    duplicated = registry.add_project(str(local_python_project.resolve()))

    assert added == duplicated
    config = load_app_config(tmp_path / "app.yaml")
    assert [project.name for project in config.projects] == [local_python_project.name]


def test_add_project_rejects_invalid_paths(tmp_path: Path) -> None:
    registry = ProjectRegistry(tmp_path / "app.yaml")

    with pytest.raises(ValueError, match="path is required"):
        registry.add_project("   ")
    with pytest.raises(ValueError, match="path does not exist"):
        registry.add_project(str(tmp_path / "missing"))
    with pytest.raises(ValueError, match="path is not a directory"):
        file_path = tmp_path / "plain.py"
        file_path.write_text("print('x')\n", encoding="utf-8")
        registry.add_project(str(file_path))


def test_add_project_rejects_non_python_project(tmp_path: Path) -> None:
    registry = ProjectRegistry(tmp_path / "app.yaml")
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    with pytest.raises(ValueError, match="does not look like a Python project root"):
        registry.add_project(str(empty_dir))


def test_delete_project_removes_config_entry_but_keeps_local_directory(
    tmp_path: Path,
    local_python_project: Path,
) -> None:
    registry = ProjectRegistry(tmp_path / "app.yaml")
    added = registry.add_project(str(local_python_project))

    deleted = registry.delete_project(added.id)

    assert deleted is True
    assert registry.list_projects() == []
    assert local_python_project.exists()
