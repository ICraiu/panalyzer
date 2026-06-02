from __future__ import annotations

from pathlib import Path

from project_analyzer.app_config import (
    AppConfig,
    AppProjectConfig,
    AppServerConfig,
    ensure_app_config,
    load_app_config,
    resolve_server_config,
    save_app_config,
)


def test_save_and_load_app_config_round_trip(tmp_path: Path) -> None:
    config_path = tmp_path / "app.yaml"
    config = AppConfig(
        server=AppServerConfig(host="127.0.0.1", port=7010),
        projects=[AppProjectConfig(name="demo", path="/tmp/demo")],
    )

    save_app_config(config_path, config)

    loaded = load_app_config(config_path)
    assert loaded == config


def test_ensure_app_config_migrates_legacy_toml(tmp_path: Path) -> None:
    config_path = tmp_path / "app.yaml"
    legacy_path = tmp_path / "app.toml"
    legacy_path.write_text(
        """
[server]
host = "127.0.0.1"
port = 7011

[[projects]]
name = "legacy"
path = "/tmp/legacy"
""",
        encoding="utf-8",
    )

    config = ensure_app_config(config_path)

    assert config.server.host == "127.0.0.1"
    assert config.server.port == 7011
    assert config.projects[0].name == "legacy"
    assert config_path.exists()
    assert not legacy_path.exists()


def test_resolve_server_config_prefers_environment(monkeypatch) -> None:
    config = AppConfig(server=AppServerConfig(host="0.0.0.0", port=7000))
    monkeypatch.setenv("PORT", "8123")

    resolved = resolve_server_config(config)

    assert resolved.host == "0.0.0.0"
    assert resolved.port == 8123


def test_resolve_server_config_ignores_invalid_environment(monkeypatch) -> None:
    config = AppConfig(server=AppServerConfig(host="127.0.0.1", port=7000))
    monkeypatch.setenv("PANALYZER_PORT", "invalid")

    resolved = resolve_server_config(config)

    assert resolved == config.server
