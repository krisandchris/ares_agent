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
from ares_agent.model_clients.http_clients import (
    Requester,
    Sam3FastApiClient,
    SglangVlmJudgeClient,
    SglangVlmPreliminaryClient,
)
from ares_agent.model_clients.mock_clients import (
    MockEvidenceJudgeClient,
    MockPreliminaryClient,
    MockSegmentationClient,
)
from ares_agent.plugins.http_callback import HttpCallbackPlugin, Sender
from ares_agent.prompts.scene_activation import ScenePolicyResolver
from ares_agent.prompts.builders import (
    ConfigurableInspectionPromptBuilder,
    PromptBuilder,
)
from ares_agent.workflows.inspection_event_workflow import (
    build_inspection_event_workflow,
    build_preliminary_only_workflow,
)


def _load_fixture_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_workflow_from_config(
    config: AppConfig,
    *,
    callback_sender: Sender | None = None,
    model_requesters: dict[str, Requester] | None = None,
) -> Workflow:
    model_requesters = model_requesters or {}
    if config.orchestrator.chain_mode == "vlm1_only":
        preliminary_client = _build_preliminary_client_from_config(
            config,
            model_requester=model_requesters.get("preliminary"),
        )
        return build_preliminary_only_workflow(
            preliminary_client=preliminary_client,
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

    preliminary_client, segmentation_client, evidence_judge_client = _build_model_clients_from_config(
        config,
        model_requesters=model_requesters,
    )
    return build_inspection_event_workflow(
        preliminary_client=preliminary_client,
        segmentation_client=segmentation_client,
        evidence_judge_client=evidence_judge_client,
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


def _build_preliminary_client_from_config(
    config: AppConfig,
    *,
    model_requester: Requester | None = None,
):
    if config.model_clients.mode == "http":
        prompt_builder = _build_prompt_builder_from_config(config)
        if config.model_clients.preliminary is None:
            raise ValueError("HTTP model client mode requires a preliminary endpoint")
        return SglangVlmPreliminaryClient(
            endpoint=_build_http_endpoint(
                str(config.model_clients.preliminary.base_url),
                config.model_clients.preliminary.endpoint,
            ),
            model_name=config.model_clients.preliminary.model_name or "inspection-vlm",
            timeout_ms=config.model_clients.preliminary.timeout_ms,
            temperature=config.model_clients.preliminary.temperature or 0.0,
            max_tokens=config.model_clients.preliminary.max_tokens,
            requester=model_requester,
            prompt_builder=prompt_builder,
        )
    return MockPreliminaryClient(fixture_path=config.mock_clients.preliminary_fixture)


def _build_prompt_builder_from_config(config: AppConfig) -> PromptBuilder:
    if config.prompts is None:
        raise ValueError("HTTP model client mode requires configured prompt templates")
    if config.scene_policies is None:
        raise ValueError("HTTP model client mode requires configured scene activation policies")

    return ConfigurableInspectionPromptBuilder(
        preliminary_role_block=config.prompts.preliminary.role_block,
        preliminary_scene_activation_block_template=config.prompts.preliminary.scene_activation_block_template,
        preliminary_category_focus_block_template=config.prompts.preliminary.category_focus_block_template,
        preliminary_reasoning_block=config.prompts.preliminary.reasoning_block,
        preliminary_output_contract_block=config.prompts.preliminary.output_contract_block,
        preliminary_user_template=config.prompts.preliminary.user,
        judge_system_template=config.prompts.judge.system,
        judge_user_template=config.prompts.judge.user,
        category_registry=config.category_registry,
        open_risk_guidance_default=config.open_risk_registry.guidance,
        scene_activation_resolver=ScenePolicyResolver(config.scene_policies),
    )


def _build_model_clients_from_config(
    config: AppConfig,
    *,
    model_requesters: dict[str, Requester] | None = None,
):
    model_requesters = model_requesters or {}
    if config.model_clients.mode == "http":
        if config.orchestrator.chain_mode == "vlm1_only":
            raise ValueError("_build_model_clients_from_config should not be used for vlm1_only mode")
        prompt_builder = _build_prompt_builder_from_config(config)
        if config.model_clients.preliminary is None or config.model_clients.judge is None or config.model_clients.sam3 is None:
            raise ValueError("HTTP model client mode requires preliminary, judge, and sam3 endpoints")
        return (
            SglangVlmPreliminaryClient(
                endpoint=_build_http_endpoint(
                    str(config.model_clients.preliminary.base_url),
                    config.model_clients.preliminary.endpoint,
                ),
                model_name=config.model_clients.preliminary.model_name or "inspection-vlm",
                timeout_ms=config.model_clients.preliminary.timeout_ms,
                temperature=config.model_clients.preliminary.temperature or 0.0,
                max_tokens=config.model_clients.preliminary.max_tokens,
                requester=model_requesters.get("preliminary"),
                prompt_builder=prompt_builder,
            ),
            Sam3FastApiClient(
                endpoint=_build_http_endpoint(
                    str(config.model_clients.sam3.base_url),
                    config.model_clients.sam3.endpoint,
                ),
                timeout_ms=config.model_clients.sam3.timeout_ms,
                requester=model_requesters.get("sam3"),
            ),
            SglangVlmJudgeClient(
                endpoint=_build_http_endpoint(
                    str(config.model_clients.judge.base_url),
                    config.model_clients.judge.endpoint,
                ),
                model_name=config.model_clients.judge.model_name or "inspection-vlm",
                timeout_ms=config.model_clients.judge.timeout_ms,
                temperature=config.model_clients.judge.temperature or 0.0,
                max_tokens=config.model_clients.judge.max_tokens,
                requester=model_requesters.get("judge"),
                prompt_builder=prompt_builder,
            ),
        )

    return (
        MockPreliminaryClient(fixture_path=config.mock_clients.preliminary_fixture),
        MockSegmentationClient(fixture_path=config.mock_clients.segmentation_fixture),
        MockEvidenceJudgeClient(fixture_path=config.mock_clients.evidence_judge_fixture),
    )


def _build_http_endpoint(base_url: str, endpoint: str) -> str:
    return f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"


def _build_default_workflow(*, callback_sender: Sender | None = None) -> Workflow:
    config = load_config(Path.cwd() / "config/agent_config.example.yaml")
    return _build_workflow_from_config(config, callback_sender=callback_sender)


def create_app(
    *,
    workflow: Workflow | None = None,
    config_path: str | Path | None = None,
    callback_sender: Sender | None = None,
    event_store: InMemoryEventStore | None = None,
    model_requesters: dict[str, Requester] | None = None,
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
            model_requesters=model_requesters,
        )
    else:
        app.state.inspection_workflow = _build_workflow_from_config(
            app.state.app_config,
            callback_sender=callback_sender,
            model_requesters=model_requesters,
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

    @app.post("/v1/inspection-items", response_model=None)
    async def ingest_inspection_item(
        request: InspectionIngestRequest,
    ) -> JSONResponse | dict[str, object]:
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
        camera_id=seed.camera_id,
        location=seed.location,
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
