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
- configurable VLM prompt templates via YAML

Not implemented yet:

- real model clients
- persistent database/object storage
- manual review loop

## Documentation

- [项目结构设计文档](./docs/project-structure-design.md)
- [街道巡检后端 Agent 设计](./docs/plans/2026-03-09-street-inspection-agent-design.md)
- [框架选型记录](./docs/plans/2026-03-09-agent-framework-selection-among-agentscope-dify-agno.md)

## Project Structure

```text
src/ares_agent/
├── api/           # FastAPI app and schemas
├── domain/        # Event / evidence / taxonomy definitions
├── infra/         # Config and in-memory event store
├── model_clients/ # Mock clients and HTTP-style model clients
├── plugins/       # Callback adapters
├── prompts/       # Prompt builders
├── services/      # Feedback payload builders
└── workflows/     # Main inspection workflow
```

Current runtime chain:

`FastAPI -> VLM-1 -> SAM3 -> VLM-2 -> callback -> event_store`

## Setup

```bash
uv sync
```

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

## Query Latest Event

```bash
curl http://127.0.0.1:8000/v1/events/<event_id>
```

## Test

```bash
uv run pytest tests/unit
```
