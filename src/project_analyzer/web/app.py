from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..services import ProjectAnalysisService, ProjectRegistry


@dataclass
class WebAppContext:
    base_dir: Path
    registry: ProjectRegistry
    analysis_service: ProjectAnalysisService
