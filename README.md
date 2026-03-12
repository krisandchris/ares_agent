# Ares Agent

Agno-based urban street visual inspection backend agent.

## Current Scope

This repository is currently a mocked closed-loop demo, not a production-ready backend.

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
- [生产化下一步规划](./docs/plans/2026-03-11-productionization-next-steps-plan.md)
- [`inspection-items` camera/location feature 方案](./docs/plans/2026-03-12-inspection-items-camera-location-feature-plan.md)

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

## Example Request

```bash
curl -X POST http://127.0.0.1:8000/v1/inspection-items \
  -H "Content-Type: application/json" \
  -d '{
    "image_uri": "s3://street/frame-001.jpg",
    "frame_id": "frame-001",
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

- `prompts.preliminary.system`
- `prompts.preliminary.user`
- `prompts.judge.system`
- `prompts.judge.user`

The code path in `src/ares_agent/prompts/builders.py` only injects configured variables:

- `VLM-1 user`
  - currently treated as static template text
  - the inspection image is attached separately as multimodal `image_url`
- `VLM-2 user`
  - supports:
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
