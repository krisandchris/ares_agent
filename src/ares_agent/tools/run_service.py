"""Formal service startup entrypoint."""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from ares_agent.api.app import create_app


def build_service_app(config_path: str | Path) -> FastAPI:
    return create_app(config_path=config_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch the Ares inspection service.")
    parser.add_argument(
        "--config",
        default=str(Path.cwd() / "config/agent_config.example.yaml"),
        help="Path to the YAML config file.",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host address for the FastAPI service.")
    parser.add_argument("--port", type=int, default=8000, help="Port for the FastAPI service.")
    args = parser.parse_args()

    app = build_service_app(args.config)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
