from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from ..app_config import default_app_config_path, ensure_app_config, load_app_config, resolve_server_config
from .state import (
    RuntimeState,
    WebAppStatus,
    clear_runtime_state,
    default_runtime_state_path,
    is_process_running,
    load_runtime_state,
    save_runtime_state,
)


class WebAppRuntime:
    """Lifecycle management for the local web application."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir.resolve()
        self.config_path = default_app_config_path(self.base_dir)
        self.state_path = default_runtime_state_path(self.base_dir)

    def start(self) -> WebAppStatus:
        current = self.status()
        if current.running:
            return current

        config = ensure_app_config(self.config_path)
        server_config = resolve_server_config(config)
        log_path = self.base_dir / ".panalyzer-webapp.log"
        with log_path.open("a", encoding="utf-8") as log_handle:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "project_analyzer.web.server",
                    "--config",
                    str(self.config_path),
                ],
                cwd=str(self.base_dir),
                stdout=log_handle,
                stderr=log_handle,
                start_new_session=True,
            )

        state = RuntimeState(
            pid=process.pid,
            host=server_config.host,
            port=server_config.port,
            config_path=str(self.config_path),
        )
        save_runtime_state(self.state_path, state)
        time.sleep(0.4)
        return self.status()

    def stop(self) -> WebAppStatus:
        state = load_runtime_state(self.state_path)
        if not is_process_running(state.pid):
            clear_runtime_state(self.state_path)
            return WebAppStatus(
                running=False,
                host=state.host,
                port=state.port,
                config_path=state.config_path,
            )

        assert state.pid is not None
        try:
            os.kill(state.pid, signal.SIGTERM)
        except ProcessLookupError:
            clear_runtime_state(self.state_path)
            return WebAppStatus(
                running=False,
                host=state.host,
                port=state.port,
                config_path=state.config_path,
            )

        for _ in range(20):
            if not is_process_running(state.pid):
                clear_runtime_state(self.state_path)
                return WebAppStatus(
                    running=False,
                    host=state.host,
                    port=state.port,
                    config_path=state.config_path,
                )
            time.sleep(0.1)

        return self.status()

    def restart(self) -> WebAppStatus:
        current = self.status()
        if current.running:
            self.stop()
        return self.start()

    def status(self) -> WebAppStatus:
        ensure_app_config(self.config_path)
        state = load_runtime_state(self.state_path)
        if not is_process_running(state.pid):
            clear_runtime_state(self.state_path)
            config = load_app_config(self.config_path)
            server_config = resolve_server_config(config)
            return WebAppStatus(
                running=False,
                host=state.host or server_config.host,
                port=state.port or server_config.port,
                config_path=str(self.config_path),
            )
        return WebAppStatus(
            running=True,
            pid=state.pid,
            host=state.host,
            port=state.port,
            config_path=state.config_path,
        )
