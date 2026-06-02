from __future__ import annotations

import os
from pathlib import Path
import tempfile
import tomllib

from pydantic import BaseModel, Field
import yaml


DEFAULT_APP_CONFIG_NAME = "app.yaml"
LEGACY_APP_CONFIG_NAME = "app.toml"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 7000


class AppServerConfig(BaseModel):
    host: str = Field(default=DEFAULT_HOST)
    port: int = Field(default=DEFAULT_PORT)


class AppProjectConfig(BaseModel):
    name: str
    path: str


class AppConfig(BaseModel):
    server: AppServerConfig = Field(default_factory=AppServerConfig)
    projects: list[AppProjectConfig] = Field(default_factory=list)


def default_app_config_path(base_dir: Path) -> Path:
    return base_dir / DEFAULT_APP_CONFIG_NAME


def load_app_config(config_path: Path) -> AppConfig:
    existing_path = _existing_app_config_path(config_path)
    if existing_path is None:
        return AppConfig()
    if existing_path.suffix == ".toml":
        data = tomllib.loads(existing_path.read_text(encoding="utf-8"))
    else:
        data = yaml.safe_load(existing_path.read_text(encoding="utf-8")) or {}
    return AppConfig.model_validate(data)


def save_app_config(config_path: Path, config: AppConfig) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = _render_app_yaml(config)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(config_path.parent),
        delete=False,
    ) as handle:
        handle.write(rendered)
        temp_path = Path(handle.name)
    temp_path.replace(config_path)


def ensure_app_config(config_path: Path) -> AppConfig:
    config = load_app_config(config_path)
    legacy_path = config_path.with_name(LEGACY_APP_CONFIG_NAME)
    if not config_path.exists() and legacy_path.exists():
        save_app_config(config_path, config)
        legacy_path.unlink()
    if not config_path.exists():
        save_app_config(config_path, config)
    return config


def resolve_server_config(config: AppConfig) -> AppServerConfig:
    port_value = os.environ.get("PANALYZER_PORT") or os.environ.get("PORT")
    if not port_value:
        return config.server
    try:
        port = int(port_value)
    except ValueError:
        return config.server
    return AppServerConfig(host=config.server.host, port=port)


def _existing_app_config_path(config_path: Path) -> Path | None:
    if config_path.exists():
        return config_path
    legacy_path = config_path.with_name(LEGACY_APP_CONFIG_NAME)
    if legacy_path.exists():
        return legacy_path
    return None


def _render_app_yaml(config: AppConfig) -> str:
    payload = config.model_dump(mode="json", exclude_none=True)
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)
