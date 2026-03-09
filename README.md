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
- event query API
- manual review loop

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

## Query Latest Event

```bash
curl http://127.0.0.1:8000/v1/events/<event_id>
```

## Test

```bash
uv run pytest tests/unit
```
