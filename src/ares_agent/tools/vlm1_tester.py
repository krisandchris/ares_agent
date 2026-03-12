"""Standalone VLM-1 testing helpers and Gradio entrypoint."""

from __future__ import annotations

import argparse
import base64
import mimetypes
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ares_agent.api.app import _build_prompt_builder_from_config
from ares_agent.domain.events import EventSeed, generate_event_id
from ares_agent.infra.config import AppConfig, load_config
from ares_agent.model_clients.http_clients import Requester, SglangVlmPreliminaryClient
from ares_agent.model_clients.mock_clients import MockPreliminaryClient
from ares_agent.prompts.scene_activation import SceneActivationContext
from ares_agent.workflows.inspection_event_workflow import PreliminaryResult


@dataclass(frozen=True)
class Vlm1TesterOutput:
    event_id: str
    input_image_uri: str
    scene_activation: SceneActivationContext
    system_prompt: str
    user_prompt: str
    messages: list[dict[str, Any]]
    result: PreliminaryResult


def run_vlm1_preliminary_test(
    *,
    config_path: str | Path,
    image_uri: str,
    uploaded_image_path: str | Path | None = None,
    camera_id: str,
    location: str,
    device_id: str,
    task_id: str,
    occur_time: str,
    mode_override: str | None = None,
    preliminary_requester: Requester | None = None,
) -> Vlm1TesterOutput:
    config = load_config(config_path)
    if mode_override is not None:
        config = config.model_copy(
            update={
                "model_clients": config.model_clients.model_copy(
                    update={"mode": mode_override}
                )
            }
        )
    resolved_image_uri = _resolve_input_image_uri(
        image_uri=image_uri,
        uploaded_image_path=uploaded_image_path,
        mode=config.model_clients.mode,
    )
    prompt_builder = _build_prompt_builder_from_config(config)
    seed = EventSeed(
        image_uri=resolved_image_uri,
        camera_id=camera_id,
        location=location,
        device_id=device_id,
        task_id=task_id,
        occur_time=occur_time,
    )
    scene_activation = _resolve_scene_activation(prompt_builder, seed)
    messages = prompt_builder.build_preliminary_messages(
        seed,
        scene_activation_context=scene_activation,
    )
    client = _build_preliminary_client(
        config,
        prompt_builder=prompt_builder,
        preliminary_requester=preliminary_requester,
    )
    result = client.analyze(seed)
    return Vlm1TesterOutput(
        event_id=generate_event_id(seed),
        input_image_uri=resolved_image_uri,
        scene_activation=scene_activation,
        system_prompt=str(messages[0]["content"]),
        user_prompt=_extract_user_text(messages),
        messages=messages,
        result=result,
    )


def create_gradio_app(
    *,
    config_path: str | Path = Path.cwd() / "config/agent_config.example.yaml",
    preliminary_requester: Requester | None = None,
):
    import gradio as gr

    def _submit(
        image_uri: str,
        uploaded_image: str | None,
        mode: str,
        camera_id: str,
        location: str,
        device_id: str,
        task_id: str,
        occur_time: str,
    ) -> tuple[str, str, str, str, str]:
        output = run_vlm1_preliminary_test(
            config_path=config_path,
            image_uri=image_uri,
            uploaded_image_path=uploaded_image,
            camera_id=camera_id,
            location=location,
            device_id=device_id,
            task_id=task_id,
            occur_time=occur_time,
            mode_override=mode,
            preliminary_requester=preliminary_requester,
        )
        return (
            output.event_id,
            json.dumps(output.scene_activation.model_dump(), ensure_ascii=False, indent=2),
            output.system_prompt,
            json.dumps(output.messages, ensure_ascii=False, indent=2),
            json.dumps(output.result.model_dump(), ensure_ascii=False, indent=2),
        )

    with gr.Blocks(title="Ares VLM-1 Tester") as demo:
        gr.Markdown(
            """
            # Ares VLM-1 Tester
            独立测试 `camera_id + location -> scene policy -> VLM-1 preliminary` 链路。
            """
        )
        with gr.Row():
            image_uri = gr.Textbox(label="image_uri", value="s3://street/frame-001.jpg")
            uploaded_image = gr.File(label="uploaded_image", type="filepath")
            mode = gr.Radio(label="mode", choices=["mock", "http"], value="mock")
            camera_id = gr.Dropdown(label="camera_id", choices=["front", "left", "right"], value="front")
            location = gr.Textbox(label="location", value="南山路")
        with gr.Row():
            device_id = gr.Textbox(label="device_id", value="dog-17")
            task_id = gr.Textbox(label="task_id", value="patrol-sh-001")
            occur_time = gr.Textbox(label="occur_time", value="2026-03-09T10:00:00Z")
        submit = gr.Button("Run VLM-1")
        event_id = gr.Textbox(label="event_id")
        scene_activation = gr.Code(label="scene_activation_context", language="json")
        system_prompt = gr.Code(label="system_prompt", language="markdown")
        messages = gr.Code(label="messages", language="json")
        preliminary_result = gr.Code(label="preliminary_result", language="json")

        submit.click(
            _submit,
            inputs=[image_uri, uploaded_image, mode, camera_id, location, device_id, task_id, occur_time],
            outputs=[event_id, scene_activation, system_prompt, messages, preliminary_result],
        )
    return demo


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch the standalone Gradio VLM-1 tester.")
    parser.add_argument(
        "--config",
        default=str(Path.cwd() / "config/agent_config.example.yaml"),
        help="Path to the YAML config file used to build scene policy and VLM-1 client settings.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host address for the Gradio server.")
    parser.add_argument("--port", type=int, default=7860, help="Port for the Gradio server.")
    args = parser.parse_args()

    demo = create_gradio_app(config_path=args.config)
    demo.launch(server_name=args.host, server_port=args.port)


def _build_preliminary_client(
    config: AppConfig,
    *,
    prompt_builder: Any,
    preliminary_requester: Requester | None = None,
):
    if config.model_clients.mode == "http":
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
            requester=preliminary_requester,
            prompt_builder=prompt_builder,
        )
    return MockPreliminaryClient(fixture_path=config.mock_clients.preliminary_fixture)


def _resolve_scene_activation(prompt_builder: Any, seed: EventSeed) -> SceneActivationContext:
    if getattr(prompt_builder, "scene_activation_resolver", None) is not None:
        return prompt_builder.scene_activation_resolver.resolve(
            camera_id=seed.camera_id,
            location=seed.location,
        )
    return SceneActivationContext(
        camera_id=seed.camera_id,
        location=seed.location,
    )


def _extract_user_text(messages: list[dict[str, Any]]) -> str:
    content = messages[1]["content"]
    if isinstance(content, list):
        for item in content:
            if item.get("type") == "text":
                return str(item.get("text", ""))
    return ""


def _resolve_input_image_uri(
    *,
    image_uri: str,
    uploaded_image_path: str | Path | None,
    mode: str,
) -> str:
    if uploaded_image_path:
        path = Path(uploaded_image_path).resolve()
        if mode == "http":
            return _file_to_data_url(path)
        return path.as_uri()
    if mode == "http":
        scheme = urlparse(image_uri).scheme.lower()
        if scheme not in {"http", "https", "data"}:
            raise ValueError("HTTP mode requires image_uri to use http, https, or data URL")
    return image_uri


def _file_to_data_url(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(path.name)
    mime = mime_type or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _build_http_endpoint(base_url: str, endpoint: str) -> str:
    return f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"


if __name__ == "__main__":
    main()
