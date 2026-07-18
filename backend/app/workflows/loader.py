from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.workflows.schemas import WorkflowDefinition


DEFAULT_DEFINITIONS_DIR = Path(__file__).resolve().parent / "definitions"
WORKFLOW_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class WorkflowLoadError(ValueError):
    pass


def load_workflow_file(path: str | Path) -> WorkflowDefinition:
    """Load and strictly validate one workflow YAML definition."""

    workflow_path = Path(path)
    try:
        raw_content = workflow_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise WorkflowLoadError(
            f"cannot read workflow definition {workflow_path}: {exc}"
        ) from exc

    try:
        payload = yaml.safe_load(raw_content)
    except yaml.YAMLError as exc:
        raise WorkflowLoadError(
            f"invalid YAML in workflow definition {workflow_path}: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise WorkflowLoadError(
            f"workflow definition {workflow_path} must contain a YAML mapping"
        )

    try:
        return WorkflowDefinition.model_validate(payload)
    except ValidationError as exc:
        raise WorkflowLoadError(
            f"invalid workflow definition {workflow_path}: {exc}"
        ) from exc


def available_workflows(
    definitions_dir: str | Path = DEFAULT_DEFINITIONS_DIR,
) -> tuple[str, ...]:
    root = Path(definitions_dir)
    if not root.is_dir():
        raise WorkflowLoadError(f"workflow directory does not exist: {root}")
    return tuple(sorted(path.stem for path in root.glob("*.yaml") if path.is_file()))


def get_workflow(
    workflow_id: str,
    definitions_dir: str | Path = DEFAULT_DEFINITIONS_DIR,
    *,
    expected_version: str | None = None,
) -> WorkflowDefinition:
    """Resolve a workflow by a safe ID and verify its internal identity."""

    if WORKFLOW_ID_PATTERN.fullmatch(workflow_id) is None:
        raise WorkflowLoadError(f"invalid workflow ID: {workflow_id!r}")

    root = Path(definitions_dir).resolve()
    workflow_path = (root / f"{workflow_id}.yaml").resolve()
    if workflow_path.parent != root:
        raise WorkflowLoadError("workflow path escapes the definitions directory")
    if not workflow_path.is_file():
        raise WorkflowLoadError(f"unknown workflow: {workflow_id}")

    workflow = load_workflow_file(workflow_path)
    if workflow.workflow_id != workflow_id:
        raise WorkflowLoadError(
            f"workflow ID mismatch: requested {workflow_id}, "
            f"file declares {workflow.workflow_id}"
        )
    if expected_version is not None and workflow.version != expected_version:
        raise WorkflowLoadError(
            f"workflow version mismatch: case requires {expected_version}, "
            f"definition declares {workflow.version}"
        )
    return workflow
