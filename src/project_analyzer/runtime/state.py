from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from pydantic import BaseModel, Field


RUNTIME_STATE_FILENAME = ".panalyzer-runtime.json"


class RuntimeState(BaseModel):
    pid: int | None = Field(default=None)
    host: str | None = Field(default=None)
    port: int | None = Field(default=None)
    config_path: str | None = Field(default=None)


class WebAppStatus(BaseModel):
    running: bool = Field(default=False)
    pid: int | None = Field(default=None)
    host: str | None = Field(default=None)
    port: int | None = Field(default=None)
    config_path: str | None = Field(default=None)


def default_runtime_state_path(base_dir: Path) -> Path:
    return base_dir / RUNTIME_STATE_FILENAME


def load_runtime_state(state_path: Path) -> RuntimeState:
    if not state_path.exists():
        return RuntimeState()
    return RuntimeState.model_validate_json(state_path.read_text(encoding="utf-8"))


def save_runtime_state(state_path: Path, state: RuntimeState) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(state_path.parent),
        delete=False,
    ) as handle:
        handle.write(json.dumps(state.model_dump(mode="json"), indent=2))
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(state_path)


def clear_runtime_state(state_path: Path) -> None:
    if state_path.exists():
        state_path.unlink()


def is_process_running(pid: int | None) -> bool:
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
