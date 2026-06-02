from __future__ import annotations

from pathlib import Path

from project_analyzer.config import AnalyzerConfig, load_config


def test_should_ignore_file_by_name_and_relative_path(tmp_path: Path) -> None:
    root = tmp_path / "project"
    nested = root / "src" / "pkg"
    nested.mkdir(parents=True)
    init_file = nested / "__init__.py"
    module_file = nested / "generated.py"
    init_file.write_text("", encoding="utf-8")
    module_file.write_text("", encoding="utf-8")
    config = AnalyzerConfig(ignore_files=["__init__.py", "src/pkg/generated.py"])

    assert config.should_ignore_file(root, init_file) is True
    assert config.should_ignore_file(root, module_file) is True


def test_resolved_source_roots_prefers_configured_values(tmp_path: Path) -> None:
    root = tmp_path / "project"
    (root / "lib").mkdir(parents=True)
    (root / "src").mkdir(parents=True)
    config = AnalyzerConfig(source_roots=["lib"])

    resolved = config.resolved_source_roots(root)

    assert resolved == [(root / "lib").resolve()]


def test_resolved_source_roots_defaults_to_src_directory(tmp_path: Path) -> None:
    root = tmp_path / "project"
    (root / "src").mkdir(parents=True)

    resolved = AnalyzerConfig().resolved_source_roots(root)

    assert resolved == [(root / "src").resolve()]


def test_load_config_reads_analyzer_section(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "panalyzer.toml").write_text(
        """
[analyzer]
source_roots = ["app"]
include_external_references = true
ignore_files = ["generated.py"]
""",
        encoding="utf-8",
    )

    config = load_config(root)

    assert config.source_roots == ["app"]
    assert config.include_external_references is True
    assert config.ignore_files == ["generated.py"]
