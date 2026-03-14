"""Structured logging configuration for the Ares agent."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, Any, TextIO, cast

import structlog
from structlog.typing import EventDict, Processor

if TYPE_CHECKING:
    from ares_agent.infra.config import LoggingSettings


_DEFAULT_SERVICE_NAME = "ares-agent"


class _StdoutProxy:
    def write(self, message: str) -> int:
        return sys.stdout.write(message)

    def flush(self) -> None:
        sys.stdout.flush()


def _drop_none_values(_: Any, __: str, event_dict: EventDict) -> EventDict:
    return {key: value for key, value in event_dict.items() if value is not None}


def _add_service_name(service_name: str) -> Processor:
    def processor(_: Any, __: str, event_dict: EventDict) -> EventDict:
        event_dict.setdefault("service", service_name)
        return event_dict

    return processor


def configure_logging(
    settings: LoggingSettings | None = None,
    *,
    force: bool = False,
    stream: TextIO | None = None,
) -> None:
    if getattr(configure_logging, "_configured", False) and not force:
        return

    level_name = getattr(settings, "level", "INFO")
    service_name = getattr(settings, "service_name", _DEFAULT_SERVICE_NAME)
    enabled = getattr(settings, "enabled", True)
    level = logging.CRITICAL + 1 if not enabled else getattr(logging, str(level_name).upper(), logging.INFO)

    structlog.reset_defaults()
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_service_name(service_name),
        structlog.processors.format_exc_info,
        _drop_none_values,
        structlog.processors.JSONRenderer(),
    ]
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=cast(TextIO, stream or _StdoutProxy())),
        cache_logger_on_first_use=False,
    )
    configure_logging._configured = True  # type: ignore[attr-defined]


def get_logger(name: str) -> Any:
    return structlog.get_logger(name)
