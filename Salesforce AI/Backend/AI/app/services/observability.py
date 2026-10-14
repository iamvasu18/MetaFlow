"""Structured application logs without request bodies or credentials."""

import json
import logging
import os
import re
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from uuid import uuid4


request_id_context = ContextVar("request_id", default=None)
job_id_context = ContextVar("job_id", default=None)

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]{1,100}$")

# Only these explicitly supplied attributes enter structured logs.
_FIELDS = {
    "operation",
    "phase",
    "ai_calls",
    "input_tokens",
    "output_tokens",
    "state",
    "status_code",
    "duration_ms",
    "queue_ms",
    "plan_id",
    "salesforce_job_id",
    "error_type",
}


def safe_identifier(value):
    if isinstance(value, str) and _IDENTIFIER.fullmatch(value):
        return value
    return None


class JsonFormatter(logging.Formatter):
    def format(self, record):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": safe_identifier(
                getattr(record, "event", None)
            ) or "application_log",
        }

        for name, value in (
            ("request_id", request_id_context.get()),
            ("job_id", job_id_context.get()),
        ):
            identifier = safe_identifier(value)
            if identifier:
                entry[name] = identifier

        for name in _FIELDS:
            value = getattr(record, name, None)
            if value is None:
                continue

            if name in {
                "duration_ms",
                "queue_ms",
                "status_code",
                "ai_calls",
                "input_tokens",
                "output_tokens",
            }:
                if isinstance(value, (int, float)):
                    entry[name] = value
            elif safe_identifier(value):
                entry[name] = value

        if record.exc_info and record.exc_info[0]:
            entry["error_type"] = record.exc_info[0].__name__

        # Intentionally exclude arbitrary messages, exception text,
        # HTTP headers, query strings, payloads and source code.
        return json.dumps(entry, ensure_ascii=True, allow_nan=False)


def configure_logging():
    root = logging.getLogger()
    level = os.getenv("APP_LOG_LEVEL", "INFO").upper()
    root.setLevel(
        level if level in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        else "INFO"
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.handlers[:] = [handler]

    # Uvicorn access logs include URLs and OAuth query parameters.
    # The request middleware will provide safe access events instead.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True

    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def log_event(logger, event, *, level=logging.INFO, **fields):
    identifier = safe_identifier(event)
    if not identifier:
        raise ValueError("Invalid logging event identifier")

    attributes = {
        name: value
        for name, value in fields.items()
        if name in _FIELDS
    }
    attributes["event"] = identifier
    logger.log(level, event, extra=attributes)


@contextmanager
def job_log_context(job_id):
    token = job_id_context.set(safe_identifier(job_id))
    try:
        yield
    finally:
        job_id_context.reset(token)


def new_request_id():
    return uuid4().hex

class RequestLoggingMiddleware:
    """Track HTTP requests without logging URLs, headers or payloads."""

    def __init__(self, app):
        self.app = app
        self.logger = logging.getLogger("metaflow.requests")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        import time

        request_id = new_request_id()
        token = request_id_context.set(request_id)
        started = time.perf_counter()
        status_code = 500
        failed = False

        async def send_with_request_id(message):
            nonlocal status_code

            if message["type"] == "http.response.start":
                status_code = message["status"]
                message = dict(message)
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() != b"x-request-id"
                ]
                headers.append(
                    (b"x-request-id", request_id.encode("ascii"))
                )
                message["headers"] = headers

            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception as error:
            failed = True
            log_event(
                self.logger,
                "request_failed",
                level=logging.ERROR,
                error_type=type(error).__name__,
                status_code=status_code,
                duration_ms=round(
                    (time.perf_counter() - started) * 1000, 3
                ),
            )
            raise
        finally:
            try:
                if not failed:
                    route = scope.get("route")
                    operation = safe_identifier(
                        getattr(route, "name", None)
                    ) or "unmatched_request"

                    log_event(
                        self.logger,
                        "request_completed",
                        level=(
                            logging.ERROR
                            if status_code >= 500
                            else logging.INFO
                        ),
                        operation=operation,
                        status_code=status_code,
                        duration_ms=round(
                            (time.perf_counter() - started) * 1000, 3
                        ),
                    )
            finally:
                request_id_context.reset(token)

def timed_ai_call(method):
    from functools import wraps
    from time import perf_counter
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        started = perf_counter()
        state = 'failed'
        log_event(logging.getLogger('metaflow.ai'), 'ai_call_started', operation='generate', phase='ai_request', state='running')
        try:
            result = method(self, *args, **kwargs)
            state = 'succeeded'
            return result
        finally:
            log_event(logging.getLogger('metaflow.ai'), 'ai_call_finished', operation='generate', phase='ai_request', state=state, duration_ms=round((perf_counter()-started)*1000,3))
    return wrapped
