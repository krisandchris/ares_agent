"""Thin decorators for structured chain logging."""

from __future__ import annotations

import inspect
import time
from collections.abc import Callable, Mapping
from functools import wraps
from typing import Any, TypeVar, cast

from ares_agent.infra.log_context import bind_context_from_fields
from ares_agent.infra.logging import get_logger

F = TypeVar("F", bound=Callable[..., Any])
FieldExtractor = Callable[..., Mapping[str, Any] | None]


def _safe_extract_fields(
    field_extractor: FieldExtractor | None,
    *args: Any,
    **kwargs: Any,
) -> dict[str, Any]:
    if field_extractor is None:
        return {}
    try:
        extracted = field_extractor(*args, **kwargs) or {}
    except Exception as exc:  # pragma: no cover - defensive logging path
        return {
            "field_extractor_error": exc.__class__.__name__,
            "field_extractor_message": str(exc),
        }
    return {key: value for key, value in extracted.items() if value is not None}


def _log_call(
    *,
    base_event: str,
    fixed_fields: Mapping[str, Any] | None = None,
    field_extractor: FieldExtractor | None = None,
) -> Callable[[F], F]:
    fixed_fields = dict(fixed_fields or {})

    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = get_logger(func.__module__)
            extracted = _safe_extract_fields(field_extractor, *args, **kwargs)
            bind_context_from_fields(extracted)
            start = time.perf_counter()
            logger.info(f"{base_event}.started", **fixed_fields, **extracted)
            try:
                result = await func(*args, **kwargs)
            except Exception as exc:
                logger.exception(
                    f"{base_event}.failed",
                    **fixed_fields,
                    **extracted,
                    duration_ms=round((time.perf_counter() - start) * 1000, 3),
                    error_type=exc.__class__.__name__,
                    error_message=str(exc),
                )
                raise
            logger.info(
                f"{base_event}.succeeded",
                **fixed_fields,
                **extracted,
                duration_ms=round((time.perf_counter() - start) * 1000, 3),
            )
            return result

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = get_logger(func.__module__)
            extracted = _safe_extract_fields(field_extractor, *args, **kwargs)
            bind_context_from_fields(extracted)
            start = time.perf_counter()
            logger.info(f"{base_event}.started", **fixed_fields, **extracted)
            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                logger.exception(
                    f"{base_event}.failed",
                    **fixed_fields,
                    **extracted,
                    duration_ms=round((time.perf_counter() - start) * 1000, 3),
                    error_type=exc.__class__.__name__,
                    error_message=str(exc),
                )
                raise
            logger.info(
                f"{base_event}.succeeded",
                **fixed_fields,
                **extracted,
                duration_ms=round((time.perf_counter() - start) * 1000, 3),
            )
            return result

        if inspect.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        return cast(F, sync_wrapper)

    return decorator


def log_stage(stage_name: str, *, field_extractor: FieldExtractor | None = None) -> Callable[[F], F]:
    return _log_call(
        base_event="workflow.stage",
        fixed_fields={"stage": stage_name},
        field_extractor=field_extractor,
    )


def log_external_call(
    target_name: str,
    *,
    event_name: str = "model.request",
    field_extractor: FieldExtractor | None = None,
) -> Callable[[F], F]:
    return _log_call(
        base_event=event_name,
        fixed_fields={"target": target_name},
        field_extractor=field_extractor,
    )
