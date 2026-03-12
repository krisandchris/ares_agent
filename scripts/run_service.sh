#!/usr/bin/env bash
set -euo pipefail

uv run python -m ares_agent.tools.run_service "$@"
