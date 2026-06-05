from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..services import ProjectService, ProposalService


@dataclass
class WebAppContext:
    base_dir: Path
    project_service: ProjectService
    proposal_service: ProposalService
