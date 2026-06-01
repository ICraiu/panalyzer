from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path
import tomllib

from pydantic import BaseModel, Field


class AnalyzerConfig(BaseModel):
    """Runtime configuration for the analyzer."""

    source_roots: list[str] = Field(
        default_factory=list,
        description="Directories to treat as Python source roots, relative to the scan root",
    )
    include_external_references: bool = Field(
        default=False,
        description="Include calls that resolve outside the scanned project",
    )
    ignore_files: list[str] = Field(
        default_factory=list,
        description="Glob patterns for files to skip during analysis",
    )

    def should_ignore_file(self, root: Path, file_path: Path) -> bool:
        """Return whether *file_path* should be skipped."""

        relative_path = str(file_path.relative_to(root))
        file_name = file_path.name
        return any(
            fnmatch(file_name, pattern) or fnmatch(relative_path, pattern)
            for pattern in self.ignore_files
        )

    def resolved_source_roots(self, root: Path) -> list[Path]:
        """Return absolute source roots for analysis."""

        if self.source_roots:
            return [(root / source_root).resolve() for source_root in self.source_roots]

        default_src = (root / "src").resolve()
        if default_src.is_dir():
            return [default_src]
        return [root]


def load_config(root: Path) -> AnalyzerConfig:
    """Load `panalyzer.toml` from the project root when present."""

    config_path = root / "panalyzer.toml"
    if not config_path.exists():
        return AnalyzerConfig()

    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    analyzer_data = data.get("analyzer", {})
    return AnalyzerConfig.model_validate(analyzer_data)
