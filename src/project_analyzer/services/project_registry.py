from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path

from ..app_config import AppProjectConfig, load_app_config, save_app_config


@dataclass(frozen=True)
class RegisteredProject:
    id: str
    name: str
    path: str


class ProjectRegistry:
    """Persistence-backed registry for saved project roots."""

    def __init__(self, config_path: Path):
        self.config_path = config_path

    def list_projects(self) -> list[RegisteredProject]:
        config = load_app_config(self.config_path)
        return [self._registered_project(project) for project in config.projects]

    def get_project(self, project_id: str) -> RegisteredProject | None:
        for project in self.list_projects():
            if project.id == project_id:
                return project
        return None

    def add_project(self, raw_path: str, name: str | None = None) -> RegisteredProject:
        if not raw_path.strip():
            raise ValueError("path is required")
        project_path = Path(raw_path).expanduser().resolve()
        if not project_path.exists():
            raise ValueError(f"path does not exist: {project_path}")
        if not project_path.is_dir():
            raise ValueError(f"path is not a directory: {project_path}")

        _validate_project_root(project_path)

        config = load_app_config(self.config_path)
        normalized_path = str(project_path)

        for project in config.projects:
            if Path(project.path).resolve() == project_path:
                return self._registered_project(project)

        project_name = (name or project_path.name or normalized_path).strip()
        project_entry = AppProjectConfig(name=project_name, path=normalized_path)
        config.projects.append(project_entry)
        config.projects.sort(key=lambda item: item.name.lower())
        save_app_config(self.config_path, config)
        return self._registered_project(project_entry)

    def delete_project(self, project_id: str) -> bool:
        config = load_app_config(self.config_path)
        remaining_projects: list[AppProjectConfig] = []
        removed_project: AppProjectConfig | None = None

        for project in config.projects:
            registered = self._registered_project(project)
            if registered.id == project_id and removed_project is None:
                removed_project = project
                continue
            remaining_projects.append(project)

        if removed_project is None:
            return False

        config.projects = remaining_projects
        save_app_config(self.config_path, config)
        return True

    def _registered_project(self, project: AppProjectConfig) -> RegisteredProject:
        digest = sha1(project.path.encode("utf-8")).hexdigest()[:12]
        return RegisteredProject(
            id=digest,
            name=project.name,
            path=project.path,
        )


def _validate_project_root(project_path: Path) -> None:
    if project_path.parent == project_path:
        raise ValueError(f"refusing to scan filesystem root: {project_path}")
    if not _looks_like_python_project(project_path):
        raise ValueError(
            "path does not look like a Python project root: expected pyproject.toml, setup.py, "
            "setup.cfg, requirements.txt, Pipfile, manage.py, a top-level Python package, or a src/ layout"
        )


def _looks_like_python_project(project_path: Path) -> bool:
    markers = (
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "requirements.txt",
        "Pipfile",
        "environment.yml",
        "environment.yaml",
        "tox.ini",
        "manage.py",
    )
    if any((project_path / marker).exists() for marker in markers):
        return True

    if any(project_path.glob("*.py")):
        return True

    if _has_top_level_python_package(project_path):
        return True

    src_dir = project_path / "src"
    if src_dir.is_dir() and _has_top_level_python_package(src_dir):
        return True

    return False


def _has_top_level_python_package(base_dir: Path) -> bool:
    for child in base_dir.iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        init_file = child / "__init__.py"
        if not init_file.is_file():
            continue
        if any(py_file.name != "__init__.py" for py_file in child.glob("*.py")):
            return True
    return False
