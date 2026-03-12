# Ares Agent

Agno-based urban street visual inspection backend agent.

## Current Scope

This repository is currently a mocked closed-loop demo, not a production-ready backend.

Current minimum convergence boundary:

- stable `v1/inspection-items` contract
- stable `camera_id + location` scene-aware `VLM-1` prompting
- stable `VLM-1 -> SAM3 -> VLM-2 -> callback -> event_store` minimum chain

Implemented today:

- FastAPI ingress
- Agno workflow orchestration
- JSON fixture-backed mock VLM-1 / SAM3 / VLM-2 clients
- HTTP callback plugin
- in-memory event result storage
- event query route by `event_id`
- success and failure path unit tests
- YAML-defined VLM-1 / VLM-2 system and user prompt templates

Not implemented yet:

- real model clients
- persistent database/object storage
- manual review loop

## Documentation

- [项目结构设计文档](./docs/project-structure-design.md)
- [剩余待办与优化点](./docs/remaining-todo-and-optimizations.md)
- [街道巡检后端 Agent 设计](./docs/plans/2026-03-09-street-inspection-agent-design.md)
- [框架选型记录](./docs/plans/2026-03-09-agent-framework-selection-among-agentscope-dify-agno.md)
- [MVP 收口报告](./docs/plans/2026-03-11-mvp-closure-report.md)
- [MVP 最小收敛边界](./docs/plans/2026-03-12-mvp-minimum-convergence-boundary.md)
- [生产化下一步规划](./docs/plans/2026-03-11-productionization-next-steps-plan.md)
- [`inspection-items` camera/location feature 方案](./docs/plans/2026-03-12-inspection-items-camera-location-feature-plan.md)
- [Gradio VLM-1 测试应用设计](./docs/plans/2026-03-12-gradio-vlm1-tester-design.md)

## Project Structure

```text
src/ares_agent/
├── api/           # FastAPI app and schemas
├── domain/        # Event / evidence / taxonomy definitions
├── infra/         # Config and in-memory event store
├── model_clients/ # Mock clients and HTTP-style model clients
├── plugins/       # Callback adapters
├── prompts/       # Prompt builders with config-template variable injection
├── services/      # Feedback payload builders
└── workflows/     # Main inspection workflow
```

```text
tests/unit/
├── api/           # FastAPI app, bootstrap, schemas, stub endpoints
├── domain/        # Domain event/id helpers
├── infra/         # Config and event store
├── integration/   # HTTP roundtrip tests across modules
├── model_clients/ # VLM/SAM3/mock client behavior, including VLM-1 focused tests
├── plugins/       # Callback plugin behavior
├── prompts/       # Prompt builder and template rendering
├── services/      # Feedback payload builders
└── workflows/     # Workflow orchestration behavior
```

Current runtime chain:

`FastAPI -> VLM-1 -> SAM3 -> VLM-2 -> callback -> event_store`

## Setup

```bash
uv sync
```

This repository uses a `src/` layout. `pyrightconfig.json` is included so editors can resolve `ares_agent.*` imports against `src` and the local `.venv`.

## Run

```bash
uv run uvicorn ares_agent.api.app:app --host 0.0.0.0 --port 8000
```

## Run Formal Service

```bash
./scripts/run_service.sh --config config/agent_config.example.yaml --host 0.0.0.0 --port 8000
```

`orchestrator.chain_mode` in config controls the runtime chain:

- `full`
  - synchronously runs `VLM-1 -> SAM3 -> VLM-2`
  - HTTP returns `stage=refined`
- `vlm1_only`
  - only runs `VLM-1`
  - HTTP returns `stage=preliminary`
  - requires `callback.send_refined=false`

`callback.send_preliminary` and `callback.send_refined` only control whether stage results are sent to the backend management service.
They do not change the HTTP response stage of `/v1/inspection-items`.

Current callback/return behavior matrix:

| `chain_mode` | `send_preliminary` | `send_refined` | backend callback | HTTP response |
|---|---:|---:|---|---|
| `vlm1_only` | `true` | `false` | sends `preliminary` | `stage=preliminary` |
| `vlm1_only` | `false` | `false` | sends nothing | `stage=preliminary` |
| `full` | `true` | `true` | sends `preliminary` + `refined` | `stage=refined` |
| `full` | `true` | `false` | sends `preliminary` only | `stage=refined` |
| `full` | `false` | `false` | sends nothing | `stage=refined` |

Illegal configuration:

- `send_refined=true` and `send_preliminary=false`
- `chain_mode=vlm1_only` and `send_refined=true`

For MinIO object storage, provide `image_uri` as an `http(s)` object URL.
That URL is passed through to `VLM-1` unchanged in service mode.

## Run VLM-1 Tester

```bash
uv run python -m ares_agent.tools.vlm1_tester --config config/agent_config.example.yaml --host 127.0.0.1 --port 7860
```

This launches a standalone Gradio app that only tests the `camera_id + location -> scene policy -> VLM-1` path.
It does not enter the main `SAM3 -> VLM-2 -> callback` workflow.

Tester extras:

- upload a local image and automatically convert it to a transport-safe URI
- switch between `mock` and `http` mode per run
- inspect the final `messages` JSON sent to `VLM-1`

HTTP-mode note:

- uploaded local images are converted to `data:` URLs before sending to the VLM service
- raw `s3://` or `file://` image URIs are rejected in HTTP mode unless you provide an `http(s)` or `data:` URL

## Example Request

```bash
curl -X POST http://127.0.0.1:8000/v1/inspection-items \
  -H "Content-Type: application/json" \
  -d '{
    "image_uri": "s3://street/frame-001.jpg",
    "camera_id": "front",
    "location": "南山路",
    "device_id": "dog-17",
    "task_id": "patrol-sh-001",
    "occur_time": "2026-03-09T10:00:00Z"
  }'
```

Expected behavior:

- the app loads mock fixture data from `config/agent_config.example.yaml`
- the workflow runs `VLM-1 -> SAM3 -> VLM-2 -> callback`
- the response returns the refined event payload for the shared `event_id`
- the latest event result can be queried by `event_id`

## Prompt Configuration

Prompt templates are defined in `config/agent_config.example.yaml`.

- `prompts.preliminary.role_block`
- `prompts.preliminary.scene_activation_block_template`
- `prompts.preliminary.category_focus_block_template`
- `prompts.preliminary.reasoning_block`
- `prompts.preliminary.output_contract_block`
- `prompts.preliminary.user`
- `prompts.judge.system`
- `prompts.judge.user`
- `category_registry`
- `open_risk_registry`

The code path in `src/ares_agent/prompts/builders.py` currently works as follows:

- `VLM-1`
  - `camera_id + location` are used only by the backend scene-policy resolver
  - the model does not receive those raw control fields directly
  - the final preliminary `system prompt` injects:
    - `scene_hint`
    - `priority_categories`
    - `open_risk_guidance`
    - focused category definitions rendered from `category_registry`
  - `user prompt` is kept lightweight
  - the image is attached separately as multimodal `image_url`

- `VLM-2`
  - `user` supports:
    - `{category_code}`
    - `{mask_labels}`
    - `{relation_hint}`
    - `{evidence_basis_summary}`
  - `overlay_image` is attached separately as multimodal `image_url`

## Query Latest Event

```bash
curl http://127.0.0.1:8000/v1/events/<event_id>
```

## Test

```bash
uv run pytest tests/unit
```
