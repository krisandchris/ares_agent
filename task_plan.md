# Task Plan

## Goal
Design a backend visual inspection agent for an urban street inspection robot dog that processes uploaded street-view images, detects violations, and organizes evidence output around an existing fine-tuned VLM and a SAM3 segmentation model.

## Context
- User explicitly requested the `brainstorming` workflow.
- Project directory is currently almost empty and is not a Git repository.
- Available local context is limited to the user's description, so design work will proceed from first principles.

## Phases
| Phase | Status | Notes |
|---|---|---|
| Inspect current project context | complete | Directory only contains `.venv`; no code/docs to anchor design |
| Initialize planning files | complete | `task_plan.md`, `findings.md`, `progress.md` |
| Clarify scope and constraints | complete | Hybrid mode, dual outputs, standardized taxonomy, open-risk support, plugin action layer |
| Propose architecture options | complete | Recommended layered orchestration backend |
| Draft validated design sections | complete | Architecture, data flow, state machine, config, exception handling, testing |
| Persist final design doc | complete | Wrote formal design doc under `docs/plans/` |
| Break into implementable modules | complete | Wrote module inventory and implementation sequencing |
| Select framework stack | complete | Chose Temporal + FastAPI with rationale against LangGraph/Celery/Prefect |
| Re-scope framework selection to user-provided candidates | complete | Compared AgentScope, Dify, Agno and selected Agno |
| Build minimal project skeleton | complete | Added pyproject, uv.lock, tests, Agno-oriented package layout, config and workflow skeleton |
| Implement minimal Agno inspection chain | complete | Wired VLM-1 -> SAM3 -> VLM-2 -> callback as a tested workflow |
| Add mock interface layer and callback adapter | complete | Added JSON-backed mock model clients and HTTP callback plugin with tests |
| Wire FastAPI ingress to the mock workflow | complete | Added POST ingestion route that executes the Agno workflow and returns shared-event results |
| Make workflow bootstrap config-driven | complete | App now builds mock workflow from YAML config rather than hardcoded fixture paths |
| Expand mock coverage across categories | complete | Added fixtures and tests for goods-blocking-road, unauthorized-wiring, and motor-vehicle-illegal-parking |
| Freeze MVP scope and define backlog | complete | Prioritized P0/P1 backlog based on current mocked workflow skeleton |
| Add local HTTP stub model interfaces | complete | Added local VLM/SAM3 stub endpoints and HTTP-style clients to simulate deployed services |
| Align prompt templates to config-only definitions | complete | VLM-1 user prompt no longer injects metadata; VLM-2 system/user prompts are both YAML-defined with code-only variable substitution |
| Sync docs with prompt-template contract | complete | README and structure docs now describe YAML-owned VLM-1/VLM-2 prompts and code-side variable injection only |
| Fix HTTP client response typing | complete | VLM chat-completion parsing now uses a typed helper instead of indexing raw `object` values, removing editor type errors on `response[\"choices\"]...` |
| Enforce configurable prompt builder in HTTP mode | complete | HTTP bootstrap now requires configured prompt templates and no longer falls back to DefaultInspectionPromptBuilder |
| Stop after SAM3 segmentation failure | complete | Workflow now emits a failed-stage event and skips VLM-2 when `segmentation_status=failed` |
| Enforce callback stage semantics | complete | Invalid `refined-without-preliminary` configs now fail validation; workflow honors `send_preliminary/send_refined` switches |

## Open Questions
- Primary operating mode is confirmed as hybrid: synchronous preliminary judgment plus asynchronous evidence refinement and review task generation.
- Final outputs are confirmed as both:
  - structured event streams for city platform integration
  - evidence packages for review, enforcement, and archival
- What latency and throughput constraints apply per robot/per image burst?
- What latency target should the synchronous preliminary judgment path meet?
- Whether the deployment can host Temporal Server (self-hosted or cloud)
- Preferred management-service callback protocol: HTTP, MQ, or gRPC
- Whether first release requires review-signal roundtrip from management service back into workflow

## Current Version Backlog

### P0
- Complete:
  - ingestion now requires `image_uri` plus metadata
  - in-memory event store persists the latest workflow result by `event_id`
  - workflow/callback/fixture failure paths return structured failed payloads
  - README now includes setup, run command, and example request
  - current release boundary is explicitly set to `mocked closed-loop demo`

### P1
- Complete:
  - request/response schemas extracted into `api/schemas`
  - callback config now includes timeout/retry/auth-source fields
  - integration-style tests cover HTTP -> workflow -> callback and failure/query roundtrips
  - lightweight query surface added via `GET /v1/events/{event_id}`

## Post-P1 Additions
- Added local stub endpoints to simulate deployed services:
  - `/mock/vlm/preliminary`
  - `/mock/vlm/judge`
  - `/mock/sam3/segment`
- Added HTTP-style model clients to mimic:
  - SGLang/vLLM OpenAI-compatible VLM calls
  - FastAPI-based SAM3 calls
- Verified the workflow can run through these local HTTP stub clients end-to-end

## Initial Violation Taxonomy
- `road_occupying_vendor`
- `goods_blocking_road`
- `unauthorized_electrical_wiring`
- `motor_vehicle_illegal_parking`
- `nonmotor_vehicle_illegal_parking`
- `vagrants_blocking_roadway`
- `begging_blocking_roadway`
- `off_leash_dog_nuisance`
- `staff_not_wear_mask`
- Requirement: support additional open risk categories via VLM-generated risk descriptions or candidate labels

## Confirmed Design Constraints
- Business actions must be implemented as flexible plugins rather than hard-coded branches.
- Plugin enablement should be controlled by startup configuration.
- Different violation categories may require different action policies and review gates.
- Avoid reinventing workflow/state-machine/retry infrastructure if mature frameworks can cover it.

## Errors Encountered
| Error | Attempt | Resolution |
|---|---|---|
| `git log` failed because current directory is not a Git repository | 1 | Proceeded with filesystem-only context inspection |
| `uv run pytest` initially failed because `README.md` was missing from package metadata | 1 | Added minimal `README.md` |
| `uv run pytest` then failed because Hatch could not infer package files | 1 | Added `src/ares_agent` package and explicit Hatch wheel packages config |
| `uv lock` failed in sandbox due to uv cache permission restriction | 1 | Re-ran with escalated permissions and generated `uv.lock` |
