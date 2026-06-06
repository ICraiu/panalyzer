from __future__ import annotations

from pathlib import Path

from project_analyzer.analyzer import PythonAnalyzer
from project_analyzer.config import AnalyzerConfig
from project_analyzer.models import ProposalDocument
from project_analyzer.services.proposal_service import ProposalService, ProposalStore, ProposalValidator


class FixedShaResolver:
    def __init__(self, sha: str):
        self.sha = sha

    def current_sha(self, project_root: Path) -> str:
        return self.sha


def test_validator_reports_missing_parent_declarations(sample_project: Path) -> None:
    project = PythonAnalyzer().analyze(sample_project, AnalyzerConfig())
    proposal = ProposalDocument.model_validate(
        {
            "id": "proposal_1",
            "name": "broken",
            "created_at": "2026-06-04T10:15:00Z",
            "author": "codex",
            "source_model": "gpt-5",
            "rationale": "test",
            "project_sha": "abc123",
            "packages": [],
            "files": [],
            "methods": [
                {
                    "qualname": "sample_pkg.module_b.use_imports",
                    "name": "use_imports",
                    "file_relative_path": "src/sample_pkg/module_b.py",
                    "iteration_state": "change",
                }
            ],
            "references": [],
        }
    )

    validation = ProposalValidator().validate(project, proposal)

    assert validation.valid is False
    assert any(issue.code == "missing_parent_file_declaration" for issue in validation.errors)


def test_validator_rejects_non_relative_and_parent_mismatched_paths(sample_project: Path) -> None:
    project = PythonAnalyzer().analyze(sample_project, AnalyzerConfig())
    proposal = ProposalDocument.model_validate(
        {
            "id": "proposal_2",
            "name": "broken-paths",
            "created_at": "2026-06-04T10:15:00Z",
            "author": "codex",
            "source_model": "gpt-5",
            "rationale": "test",
            "project_sha": "abc123",
            "packages": [
                {
                    "name": "sample_pkg",
                    "relative_path": "/abs/not/allowed",
                    "iteration_state": "change",
                }
            ],
            "files": [
                {
                    "relative_path": "src/sample_pkg/module_b.py",
                    "import_path": "sample_pkg.module_b",
                    "package_name": "wrong_pkg",
                    "iteration_state": "change",
                }
            ],
            "methods": [
                {
                    "qualname": "sample_pkg.module_b.use_imports",
                    "name": "use_imports",
                    "file_relative_path": "src/sample_pkg/module_a.py",
                    "iteration_state": "change",
                }
            ],
            "references": [],
        }
    )

    validation = ProposalValidator().validate(project, proposal)

    assert validation.valid is False
    assert any(issue.code == "absolute_path_not_allowed" for issue in validation.errors)
    assert any(issue.code == "file_package_mismatch" for issue in validation.errors)
    assert any(issue.code == "method_file_mismatch" for issue in validation.errors)


def test_proposal_service_saves_invalid_proposal_but_reports_sha_mismatch(sample_project: Path, tmp_path: Path) -> None:
    project = PythonAnalyzer().analyze(sample_project, AnalyzerConfig())
    service = ProposalService(
        ProposalStore(tmp_path / "proposals"),
        sha_resolver=FixedShaResolver("actualsha"),
    )

    result = service.save(
        project_id="demo",
        project_root=sample_project,
        project=project,
        payload={
            "id": "proposal_1",
            "name": "broken",
            "created_at": "2026-06-04T10:15:00Z",
            "author": "codex",
            "source_model": "gpt-5",
            "rationale": "test",
            "project_sha": "othersha",
            "packages": [],
            "files": [],
            "methods": [],
            "references": [],
        },
    )

    assert result.validation.valid is False
    assert any(issue.code == "project_sha_mismatch" for issue in result.validation.errors)
    assert result.validation.preview is not None
    assert result.validation.preview.applied is True
    assert result.validation.preview.graph["active_proposal"]["id"] == "proposal_1"
    stored = service.load_latest("demo")
    assert stored is not None
    assert stored.id == "proposal_1"


def test_latest_proposal_uses_save_order_not_client_created_at(sample_project: Path, tmp_path: Path) -> None:
    project = PythonAnalyzer().analyze(sample_project, AnalyzerConfig())
    service = ProposalService(
        ProposalStore(tmp_path / "proposals"),
        sha_resolver=FixedShaResolver("sha123"),
    )

    service.save(
        project_id="demo",
        project_root=sample_project,
        project=project,
        payload={
            "id": "proposal_old_timestamp",
            "name": "first saved",
            "created_at": "2026-06-04T12:00:00Z",
            "author": "codex",
            "source_model": "gpt-5",
            "rationale": "first",
            "project_sha": "sha123",
            "packages": [],
            "files": [],
            "methods": [],
            "references": [],
        },
    )
    service.save(
        project_id="demo",
        project_root=sample_project,
        project=project,
        payload={
            "id": "proposal_newer_save_but_older_client_time",
            "name": "second saved",
            "created_at": "2026-06-04T01:00:00Z",
            "author": "codex",
            "source_model": "gpt-5",
            "rationale": "second",
            "project_sha": "sha123",
            "packages": [],
            "files": [],
            "methods": [],
            "references": [],
        },
    )

    latest = service.load_latest("demo")

    assert latest is not None
    assert latest.id == "proposal_newer_save_but_older_client_time"


def test_analyze_with_latest_applies_states_to_graph_and_diagram(sample_project: Path, tmp_path: Path) -> None:
    project = PythonAnalyzer().analyze(sample_project, AnalyzerConfig())
    service = ProposalService(
        ProposalStore(tmp_path / "proposals"),
        sha_resolver=FixedShaResolver("sha123"),
    )
    proposal_payload = {
        "id": "proposal_1",
        "name": "adapt signature",
        "created_at": "2026-06-04T10:15:00Z",
        "author": "codex",
        "source_model": "gpt-5",
        "rationale": "Adapt one caller to signature changes.",
        "project_sha": "sha123",
        "packages": [
            {
                "name": "sample_pkg",
                "relative_path": "src/sample_pkg",
                "iteration_state": "change",
            }
        ],
        "files": [
            {
                "relative_path": "src/sample_pkg/module_a.py",
                "import_path": "sample_pkg.module_a",
                "package_name": "sample_pkg",
                "iteration_state": "change",
            },
            {
                "relative_path": "src/sample_pkg/module_b.py",
                "import_path": "sample_pkg.module_b",
                "package_name": "sample_pkg",
                "iteration_state": "change",
            },
        ],
        "methods": [
            {
                "qualname": "sample_pkg.module_a.format_name",
                "name": "format_name",
                "file_relative_path": "src/sample_pkg/module_a.py",
                "iteration_state": "change",
            },
            {
                "qualname": "sample_pkg.module_b.use_imports",
                "name": "use_imports",
                "file_relative_path": "src/sample_pkg/module_b.py",
                "iteration_state": "change",
            },
        ],
        "references": [
            {
                "source_method": "sample_pkg.module_b.use_imports",
                "target_method": "sample_pkg.module_a.format_name",
                "file_relative_path": "src/sample_pkg/module_b.py",
                "iteration_state": "change",
            }
        ],
    }
    save_result = service.save(
        project_id="demo",
        project_root=sample_project,
        project=project,
        payload=proposal_payload,
    )

    assert save_result.validation.valid is True
    graph, diagram = service.analyze_with_latest(
        project_id="demo",
        project_root=sample_project,
        project=project,
    )

    method_node = next(node for node in graph.nodes if getattr(node, "qualname", None) == "sample_pkg.module_b.use_imports")
    changed_edge = next(edge for edge in graph.edges if edge.source_id.endswith("use_imports") and edge.target_id.endswith("format_name"))
    diagram_file = next(item for item in diagram.files if item.import_path == "sample_pkg.module_b")
    transition = next(item for item in diagram.transitions if item.source_import_path == "sample_pkg.module_b" and item.target_import_path == "sample_pkg.module_a")

    assert method_node.iteration_state.value == "change"
    assert changed_edge.iteration_state.value == "change"
    assert diagram_file.iteration_state.value == "change"
    assert transition.iteration_state.value == "change"
    assert graph.active_proposal is not None
    assert graph.active_proposal.id == "proposal_1"
    assert any(warning.code == "reference_change_requires_signature_adaptation_confirmation" for warning in graph.warnings)


def test_analyze_with_latest_ignores_invalid_latest_proposal(sample_project: Path, tmp_path: Path) -> None:
    project = PythonAnalyzer().analyze(sample_project, AnalyzerConfig())
    service = ProposalService(
        ProposalStore(tmp_path / "proposals"),
        sha_resolver=FixedShaResolver("sha123"),
    )

    service.save(
        project_id="demo",
        project_root=sample_project,
        project=project,
        payload={
            "id": "proposal_invalid",
            "name": "invalid",
            "created_at": "2026-06-04T10:15:00Z",
            "author": "codex",
            "source_model": "gpt-5",
            "rationale": "missing file declaration",
            "project_sha": "sha123",
            "packages": [],
            "files": [],
            "methods": [
                {
                    "qualname": "sample_pkg.module_b.use_imports",
                    "name": "use_imports",
                    "file_relative_path": "src/sample_pkg/module_b.py",
                    "iteration_state": "change",
                }
            ],
            "references": [],
        },
    )

    graph, diagram = service.analyze_with_latest(
        project_id="demo",
        project_root=sample_project,
        project=project,
    )

    assert graph.active_proposal is None
    assert any(warning.code == "ignored_invalid_latest_proposal" for warning in graph.warnings)
    assert graph.summary.file_count > 0
    assert diagram.summary.file_count > 0


def test_analyze_with_latest_ignores_unloadable_latest_proposal(sample_project: Path, tmp_path: Path) -> None:
    project = PythonAnalyzer().analyze(sample_project, AnalyzerConfig())
    store = ProposalStore(tmp_path / "proposals")
    service = ProposalService(
        store,
        sha_resolver=FixedShaResolver("sha123"),
    )
    project_dir = store.root / "demo"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "99999999999999999999__broken__proposal.json").write_text("{not json", encoding="utf-8")

    graph, diagram = service.analyze_with_latest(
        project_id="demo",
        project_root=sample_project,
        project=project,
    )

    assert graph.active_proposal is None
    assert any(warning.code == "ignored_unloadable_latest_proposal" for warning in graph.warnings)
    assert graph.summary.method_count > 0
    assert diagram.summary.transition_count >= 0


def test_analyze_with_latest_ignores_sha_mismatched_latest_proposal(sample_project: Path, tmp_path: Path) -> None:
    project = PythonAnalyzer().analyze(sample_project, AnalyzerConfig())
    service = ProposalService(
        ProposalStore(tmp_path / "proposals"),
        sha_resolver=FixedShaResolver("actualsha"),
    )

    service.save(
        project_id="demo",
        project_root=sample_project,
        project=project,
        payload={
            "id": "proposal_old_sha",
            "name": "stale proposal",
            "created_at": "2026-06-04T10:15:00Z",
            "author": "codex",
            "source_model": "gpt-5",
            "rationale": "stale sha",
            "project_sha": "oldsha",
            "packages": [],
            "files": [],
            "methods": [],
            "references": [],
        },
    )

    graph, diagram = service.analyze_with_latest(
        project_id="demo",
        project_root=sample_project,
        project=project,
    )

    assert graph.active_proposal is None
    assert any(warning.code == "ignored_sha_mismatched_latest_proposal" for warning in graph.warnings)
    assert any(warning.message == "Proposal SHAs do not match anymore." for warning in graph.warnings)
    assert graph.summary.method_count > 0
    assert diagram.summary.transition_count >= 0


def test_validate_returns_fallback_preview_when_merge_cannot_be_built(sample_project: Path, tmp_path: Path) -> None:
    project = PythonAnalyzer().analyze(sample_project, AnalyzerConfig())
    service = ProposalService(
        ProposalStore(tmp_path / "proposals"),
        sha_resolver=FixedShaResolver("sha123"),
    )

    result = service.validate(
        project_root=sample_project,
        project=project,
        payload={
            "id": "proposal_preview_failure",
            "name": "preview failure",
            "created_at": "2026-06-04T10:15:00Z",
            "author": "codex",
            "source_model": "gpt-5",
            "rationale": "missing file declaration for new method",
            "project_sha": "sha123",
            "packages": [],
            "files": [],
            "methods": [
                {
                    "qualname": "sample_pkg.module_new.added_method",
                    "name": "added_method",
                    "file_relative_path": "src/sample_pkg/module_new.py",
                    "iteration_state": "add",
                }
            ],
            "references": [],
        },
    )

    assert result.validation.preview is not None
    assert result.validation.preview.applied is False
    assert result.validation.preview.issues[0].code == "preview_generation_failed"
    assert result.validation.preview.graph["active_proposal"] is None


def test_validator_rejects_changed_package_without_changed_file(sample_project: Path) -> None:
    project = PythonAnalyzer().analyze(sample_project, AnalyzerConfig())
    proposal = ProposalDocument.model_validate(
        {
            "id": "proposal_3",
            "name": "bad-package-change",
            "created_at": "2026-06-04T10:15:00Z",
            "author": "codex",
            "source_model": "gpt-5",
            "rationale": "test",
            "project_sha": "abc123",
            "packages": [
                {
                    "name": "sample_pkg",
                    "relative_path": "src/sample_pkg",
                    "iteration_state": "change",
                }
            ],
            "files": [
                {
                    "relative_path": "src/sample_pkg/module_a.py",
                    "import_path": "sample_pkg.module_a",
                    "package_name": "sample_pkg",
                    "iteration_state": "remove",
                }
            ],
            "methods": [
                {
                    "qualname": "sample_pkg.module_a.Greeter",
                    "name": "Greeter",
                    "file_relative_path": "src/sample_pkg/module_a.py",
                    "iteration_state": "remove",
                },
                {
                    "qualname": "sample_pkg.module_a.Greeter.__init__",
                    "name": "__init__",
                    "file_relative_path": "src/sample_pkg/module_a.py",
                    "iteration_state": "remove",
                },
                {
                    "qualname": "sample_pkg.module_a.Greeter.helper",
                    "name": "helper",
                    "file_relative_path": "src/sample_pkg/module_a.py",
                    "iteration_state": "remove",
                },
                {
                    "qualname": "sample_pkg.module_a.format_name",
                    "name": "format_name",
                    "file_relative_path": "src/sample_pkg/module_a.py",
                    "iteration_state": "remove",
                },
                {
                    "qualname": "sample_pkg.module_a.module_entry",
                    "name": "module_entry",
                    "file_relative_path": "src/sample_pkg/module_a.py",
                    "iteration_state": "remove",
                },
            ],
            "references": [
                {
                    "source_method": "sample_pkg.module_a.Greeter.__init__",
                    "target_method": "sample_pkg.module_a.Greeter.helper",
                    "file_relative_path": "src/sample_pkg/module_a.py",
                    "iteration_state": "remove",
                },
                {
                    "source_method": "sample_pkg.module_a.Greeter.helper",
                    "target_method": "sample_pkg.module_a.format_name",
                    "file_relative_path": "src/sample_pkg/module_a.py",
                    "iteration_state": "remove",
                },
                {
                    "source_method": "sample_pkg.module_a.module_entry",
                    "target_method": "sample_pkg.module_a.Greeter",
                    "file_relative_path": "src/sample_pkg/module_a.py",
                    "iteration_state": "remove",
                },
                {
                    "source_method": "sample_pkg.module_a.module_entry",
                    "target_method": "sample_pkg.module_a.format_name",
                    "file_relative_path": "src/sample_pkg/module_a.py",
                    "iteration_state": "remove",
                },
                {
                    "source_method": "sample_pkg.module_b.use_imports",
                    "target_method": "sample_pkg.module_a.Greeter.helper",
                    "file_relative_path": "src/sample_pkg/module_b.py",
                    "iteration_state": "remove",
                },
                {
                    "source_method": "sample_pkg.module_b.use_imports",
                    "target_method": "sample_pkg.module_a.format_name",
                    "file_relative_path": "src/sample_pkg/module_b.py",
                    "iteration_state": "remove",
                },
            ],
        }
    )

    validation = ProposalValidator().validate(project, proposal)

    assert validation.valid is False
    assert any(issue.code == "missing_changed_file_for_changed_package" for issue in validation.errors)
