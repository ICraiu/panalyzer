from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from project_analyzer.app_config import AppConfig, AppServerConfig, save_app_config
from project_analyzer.runtime.state import (
    RuntimeState,
    clear_runtime_state,
    load_runtime_state,
    save_runtime_state,
)
from project_analyzer.runtime.webapp import WebAppRuntime


def test_runtime_state_round_trip(tmp_path: Path) -> None:
    state_path = tmp_path / ".panalyzer-runtime.json"
    state = RuntimeState(pid=123, host="127.0.0.1", port=7000, config_path="/tmp/app.yaml")

    save_runtime_state(state_path, state)
    loaded = load_runtime_state(state_path)
    clear_runtime_state(state_path)

    assert loaded == state
    assert not state_path.exists()


def test_runtime_start_writes_state_and_reports_running(tmp_path: Path, monkeypatch) -> None:
    save_app_config(tmp_path / "app.yaml", AppConfig(server=AppServerConfig(host="127.0.0.1", port=7010)))
    runtime = WebAppRuntime(tmp_path)

    monkeypatch.setattr("project_analyzer.runtime.webapp.subprocess.Popen", lambda *args, **kwargs: SimpleNamespace(pid=4321))
    monkeypatch.setattr("project_analyzer.runtime.webapp.is_process_running", lambda pid: pid == 4321)
    monkeypatch.setattr("project_analyzer.runtime.webapp.time.sleep", lambda seconds: None)

    status = runtime.start()

    assert status.running is True
    assert status.pid == 4321
    assert load_runtime_state(runtime.state_path).pid == 4321


def test_runtime_stop_clears_live_state_after_termination(tmp_path: Path, monkeypatch) -> None:
    save_app_config(tmp_path / "app.yaml", AppConfig())
    runtime = WebAppRuntime(tmp_path)
    save_runtime_state(runtime.state_path, RuntimeState(pid=111, host="127.0.0.1", port=7000))

    calls = iter([True, False])
    monkeypatch.setattr("project_analyzer.runtime.webapp.is_process_running", lambda pid: next(calls))
    monkeypatch.setattr("project_analyzer.runtime.webapp.os.kill", lambda pid, sig: None)
    monkeypatch.setattr("project_analyzer.runtime.webapp.time.sleep", lambda seconds: None)

    status = runtime.stop()

    assert status.running is False
    assert not runtime.state_path.exists()


def test_runtime_status_clears_stale_pid_and_falls_back_to_config(tmp_path: Path, monkeypatch) -> None:
    save_app_config(tmp_path / "app.yaml", AppConfig(server=AppServerConfig(host="0.0.0.0", port=7000)))
    runtime = WebAppRuntime(tmp_path)
    save_runtime_state(runtime.state_path, RuntimeState(pid=999))
    monkeypatch.setattr("project_analyzer.runtime.webapp.is_process_running", lambda pid: False)

    status = runtime.status()

    assert status.running is False
    assert status.host == "0.0.0.0"
    assert status.port == 7000
    assert not runtime.state_path.exists()


def test_runtime_restart_starts_when_stopped(tmp_path: Path, monkeypatch) -> None:
    save_app_config(tmp_path / "app.yaml", AppConfig())
    runtime = WebAppRuntime(tmp_path)
    calls: list[str] = []

    monkeypatch.setattr(runtime, "status", lambda: SimpleNamespace(running=False))
    monkeypatch.setattr(runtime, "start", lambda: calls.append("start") or SimpleNamespace(running=True, host="127.0.0.1", port=7000))

    status = runtime.restart()

    assert calls == ["start"]
    assert status.running is True


def test_runtime_restart_stops_then_starts_when_running(tmp_path: Path, monkeypatch) -> None:
    save_app_config(tmp_path / "app.yaml", AppConfig())
    runtime = WebAppRuntime(tmp_path)
    calls: list[str] = []

    monkeypatch.setattr(runtime, "status", lambda: SimpleNamespace(running=True))
    monkeypatch.setattr(runtime, "stop", lambda: calls.append("stop") or SimpleNamespace(running=False, port=7000))
    monkeypatch.setattr(runtime, "start", lambda: calls.append("start") or SimpleNamespace(running=True, host="127.0.0.1", port=7000))

    status = runtime.restart()

    assert calls == ["stop", "start"]
    assert status.running is True
