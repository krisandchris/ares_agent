"""FastAPI entrypoint for the Ares agent service."""

from __future__ import annotations

from pathlib import Path
import json

from agno.workflow import Workflow
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from ares_agent.api.schemas import EventFailureResponse, EventQueryResponse, InspectionIngestRequest
from ares_agent.domain.events import EventSeed, generate_event_id
from ares_agent.infra.config import AppConfig, load_config
from ares_agent.infra.event_store import InMemoryEventStore
from ares_agent.model_clients.mock_clients import (
    MockEvidenceJudgeClient,
    MockPreliminaryClient,
    MockSegmentationClient,
)
from ares_agent.plugins.http_callback import HttpCallbackPlugin, Sender
from ares_agent.workflows.inspection_event_workflow import build_inspection_event_workflow


def _load_fixture_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_workflow_from_config(
    config: AppConfig,
    *,
    callback_sender: Sender | None = None,
) -> Workflow:
    return build_inspection_event_workflow(
        preliminary_client=MockPreliminaryClient(
            fixture_path=config.mock_clients.preliminary_fixture
        ),
        segmentation_client=MockSegmentationClient(
            fixture_path=config.mock_clients.segmentation_fixture
        ),
        evidence_judge_client=MockEvidenceJudgeClient(
            fixture_path=config.mock_clients.evidence_judge_fixture
        ),
        sink_plugin=HttpCallbackPlugin(
            endpoint=str(config.callback.endpoint),
            auth_token=config.callback.auth_token,
            timeout_ms=config.callback.timeout_ms,
            max_attempts=config.callback.retry.max_attempts,
            backoff_ms=config.callback.retry.backoff_ms,
            sender=callback_sender,
        ),
        runtime_config={
            "callback": {
                "send_preliminary": config.callback.send_preliminary,
                "send_refined": config.callback.send_refined,
            }
        },
    )


def _build_default_workflow(*, callback_sender: Sender | None = None) -> Workflow:
    config = load_config(Path.cwd() / "config/agent_config.example.yaml")
    return _build_workflow_from_config(config, callback_sender=callback_sender)


def create_app(
    *,
    workflow: Workflow | None = None,
    config_path: str | Path | None = None,
    callback_sender: Sender | None = None,
    event_store: InMemoryEventStore | None = None,
) -> FastAPI:
    """Create the API app with the minimal service endpoints."""
    app = FastAPI(title="Ares Street Inspection Agent")
    if config_path is not None:
        app.state.app_config = load_config(config_path)
    else:
        app.state.app_config = load_config(Path.cwd() / "config/agent_config.example.yaml")
    app.state.event_store = event_store or InMemoryEventStore()
    if workflow is not None:
        app.state.inspection_workflow = workflow
    elif config_path is not None:
        app.state.inspection_workflow = _build_workflow_from_config(
            app.state.app_config,
            callback_sender=callback_sender,
        )
    else:
        app.state.inspection_workflow = _build_workflow_from_config(
            app.state.app_config,
            callback_sender=callback_sender,
        )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/mock/vlm/preliminary")
    async def mock_vlm_preliminary(_: dict[str, object]) -> dict[str, object]:
        payload = _load_fixture_json(app.state.app_config.mock_clients.preliminary_fixture)
        return {
            "id": "chatcmpl-preliminary",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(payload, ensure_ascii=True),
                    },
                    "finish_reason": "stop",
                }
            ],
        }

    @app.post("/mock/vlm/judge")
    async def mock_vlm_judge(_: dict[str, object]) -> dict[str, object]:
        payload = _load_fixture_json(app.state.app_config.mock_clients.evidence_judge_fixture)
        return {
            "id": "chatcmpl-judge",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(payload, ensure_ascii=True),
                    },
                    "finish_reason": "stop",
                }
            ],
        }

    @app.post("/mock/sam3/segment")
    async def mock_sam3_segment(_: dict[str, object]) -> dict[str, object]:
        return _load_fixture_json(app.state.app_config.mock_clients.segmentation_fixture)

    @app.post("/v1/inspection-items")
    async def ingest_inspection_item(request: InspectionIngestRequest) -> dict[str, object]:
        seed = EventSeed.model_validate(request.model_dump())
        workflow_output = app.state.inspection_workflow.run(input=seed)
        if not _workflow_succeeded(workflow_output):
            failure_payload = _build_failure_payload(seed, workflow_output)
            app.state.event_store.save(failure_payload["event_id"], failure_payload)
            status_code = 500 if failure_payload["error_type"] == "FileNotFoundError" else 502
            return JSONResponse(status_code=status_code, content=failure_payload)
        payload = dict(workflow_output.content)
        app.state.event_store.save(payload["event_id"], payload)
        return payload

    @app.get("/v1/events/{event_id}")
    async def get_event(event_id: str) -> JSONResponse:
        payload = app.state.event_store.get(event_id)
        if payload is None:
            response = EventQueryResponse(event_id=event_id, found=False, result=None)
            return JSONResponse(status_code=404, content=response.model_dump(mode="json"))
        response = EventQueryResponse(event_id=event_id, found=True, result=payload)
        return JSONResponse(status_code=200, content=response.model_dump(mode="json"))

    return app


def _workflow_succeeded(workflow_output: object) -> bool:
    step_results = getattr(workflow_output, "step_results", None) or []
    return bool(step_results) and all(getattr(step_result, "success", False) for step_result in step_results)


def _build_failure_payload(seed: EventSeed, workflow_output: object) -> dict[str, object]:
    step_results = getattr(workflow_output, "step_results", None) or []
    first_failed = next((step for step in step_results if not getattr(step, "success", False)), None)
    error_text = getattr(first_failed, "error", None) or "Workflow execution failed"
    error_type, error_message = _parse_error(error_text)
    return EventFailureResponse(
        event_id=generate_event_id(seed),
        frame_id=seed.frame_id,
        stage="failed",
        failed_step=getattr(first_failed, "step_name", None),
        error_type=error_type,
        error_message=error_message,
    ).model_dump(mode="json")


def _parse_error(error_text: str) -> tuple[str, str]:
    if ": " not in error_text:
        return "WorkflowError", error_text
    error_type, error_message = error_text.split(": ", 1)
    return error_type, error_message


app = create_app()
