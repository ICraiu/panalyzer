from __future__ import annotations

from io import BytesIO
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    project_root = tmp_path / "sample-project"
    package_dir = project_root / "src" / "sample_pkg"
    package_dir.mkdir(parents=True)

    (project_root / "pyproject.toml").write_text(
        "[project]\nname = 'sample-project'\nversion = '0.1.0'\n",
        encoding="utf-8",
    )
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "module_a.py").write_text(
        """class Greeter:
    def __init__(self):
        self.helper()

    def helper(self):
        return format_name("a")


def format_name(value):
    return value.strip()


def module_entry():
    Greeter()
    format_name("x")
    print("hi")
""",
        encoding="utf-8",
    )
    (package_dir / "module_b.py").write_text(
        """from sample_pkg.module_a import Greeter, format_name


def use_imports():
    Greeter().helper()
    return format_name("b")
""",
        encoding="utf-8",
    )
    (package_dir / "module_c.py").write_text(
        """from sample_pkg.module_a import format_name

format_name("root")
""",
        encoding="utf-8",
    )
    (package_dir / "broken.py").write_text(
        "def bad(:\n    pass\n",
        encoding="utf-8",
    )
    return project_root


@pytest.fixture
def local_python_project(tmp_path: Path) -> Path:
    project_root = tmp_path / "local-project"
    package_dir = project_root / "demo_pkg"
    package_dir.mkdir(parents=True)
    (project_root / "pyproject.toml").write_text(
        "[project]\nname = 'demo-project'\nversion = '0.1.0'\n",
        encoding="utf-8",
    )
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "worker.py").write_text("def run():\n    return 'ok'\n", encoding="utf-8")
    return project_root


def make_fake_request(path: str, body: bytes = b"") -> SimpleNamespace:
    return SimpleNamespace(
        path=path,
        headers={"Content-Length": str(len(body))},
        rfile=BytesIO(body),
        sent=None,
        _send=lambda *args, **kwargs: None,
    )
