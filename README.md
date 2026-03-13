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
- configurable in-memory / file-backed event result storage
- event query route by `event_id`
- structured request/workflow/callback logging
- success and failure path unit tests
- YAML-defined VLM-1 / VLM-2 system and user prompt templates

Not implemented yet:

- real model clients
- persistent database/object storage
- manual review loop

## Documentation

- [项目结构设计文档](./docs/project-structure-design.md)
- [项目开发日志](./docs/project-development-log.md)
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
├── infra/         # Config, logging, and event store backends
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

Recommended split-config service startup:

```bash
./scripts/run_service.sh --config config/service_config.example.yaml --host 0.0.0.0 --port 8000
```

The service now supports two `event_store` backends:

- `memory`
  - default behavior
  - keeps latest event payloads only in the current process memory
  - data is lost after process restart
- `file`
  - persists latest payloads under a local directory on disk
  - keeps one JSON file per `event_id`
  - survives process restart on the same machine

Recommended local persistence config:

```yaml
event_store:
  backend: file
  base_dir: ./data/event_store
```

With `backend: file`, the service writes event payloads to:

```text
<base_dir>/<event_id>.json
```

The current implementation uses atomic replace on save, so each event file is written through a temporary file before becoming visible.

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

If you want to pass `s3://bucket/object` instead, enable MinIO settings in the service config.
The service will resolve the `s3://...` URI into a presigned `http(s)` URL before calling `VLM-1`
and, in `full` mode, before calling `SAM3`.

Split configuration files:

- [service_config.example.yaml](./config/service_config.example.yaml)
  - service/runtime settings
  - logging
  - event_store backend
  - callback
  - model endpoints
  - feature switches
  - MinIO client settings
- [service_config.sanitized.example.yaml](./config/service_config.sanitized.example.yaml)
  - redacted template safe for version control
- [prompt_config.example.yaml](./config/prompt_config.example.yaml)
  - scene policies
  - prompts
  - category registry
  - open risk registry

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

```bash
  先在图片目录启动：

  cd /absolute/path/to/image-dir
  python3 -m http.server 9000

  然后请求：

  curl -X POST http://127.0.0.1:8000/v1/inspection-items \
    -H "Content-Type: application/json" \
    -d '{
      "image_uri": "http://127.0.0.1:9000/test.jpg",
      "camera_id": "front",
      "location": "南山路",
      "device_id": "dog-17",
      "task_id": "patrol-http-001",
      "occur_time": "2026-03-09T10:00:00Z"
    }'

```

Expected behavior:

- the app loads mock fixture data from `config/agent_config.example.yaml`
- the workflow runs `VLM-1 -> SAM3 -> VLM-2 -> callback`
- the response returns the refined event payload for the shared `event_id`
- the latest event result can be queried by `event_id`

Query the stored event payload:

```bash
curl http://127.0.0.1:8000/v1/events/<event_id>
```

When `event_store.backend=file`, the same payload is also persisted to the local `base_dir`.

## Logging

The service emits structured JSON logs to stdout.

Current log coverage includes:

- request lifecycle logs for `/v1/inspection-items`
- workflow stage logs for `preliminary`, `segmentation`, and `evidence_judge`
- model HTTP client logs for `VLM-1`, `SAM3`, and `VLM-2`
- callback start / retry / success / failure logs
- event store save/load logs

Correlation strategy:

- `event_id` is the primary chain key
- `request_id` is the HTTP-layer key

You can send your own request id through:

```bash
curl -X POST http://127.0.0.1:8000/v1/inspection-items \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: req-demo-001" \
  -d '{...}'
```

## Test `vlm1_only` with `s3://...`

If your service config enables:

- `orchestrator.chain_mode: vlm1_only`
- `minio.enabled: true`

you can directly test one object URI with:

```bash
./scripts/test_vlm1_only_s3.sh s3://your-bucket/your-object.jpg http://127.0.0.1:8000
```

This script:

- posts to `/v1/inspection-items`
- keeps `camera_id=front`
- keeps `location=南山路`
- prints the HTTP status and formatted JSON response

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
