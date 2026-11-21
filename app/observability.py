"""Stdlib structured JSON logging and X-Request-ID ASGI correlation."""

import contextvars
import datetime
import json
import logging
import os
import re
import time
import uuid

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)

_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_VALID_HEADER_NAME = re.compile(r"^[A-Za-z0-9-]+$")
_ALLOWED_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def get_request_id_header() -> str:
    raw = (os.environ.get("REQUEST_ID_HEADER") or "X-Request-ID").strip()
    if _VALID_HEADER_NAME.fullmatch(raw):
        return raw
    return "X-Request-ID"


def sanitize_request_id(raw: str | None) -> str:
    if raw and _VALID_REQUEST_ID.fullmatch(raw.strip()):
        return raw.strip()
    return uuid.uuid4().hex


class RequestIdFilter(logging.Filter):
    """Ensure every log record exposes ``request_id`` for text formatters."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = request_id_var.get()
        return True


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.datetime.now(datetime.timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        for key in (
            "method",
            "path",
            "status_code",
            "duration_ms",
            "client_ip",
            "error_type",
        ):
            val = getattr(record, key, None)
            if val is not None:
                payload[key] = val
        return json.dumps(payload, separators=(",", ":"), default=str)


def configure_logging() -> logging.Logger:
    level_name = (os.environ.get("LOG_LEVEL") or "INFO").strip().upper()
    if level_name not in _ALLOWED_LEVELS:
        level_name = "INFO"
    fmt_mode = (os.environ.get("LOG_FORMAT") or "text").strip().lower()

    logger = logging.getLogger("app.http")
    logger.setLevel(getattr(logging, level_name))
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.addFilter(RequestIdFilter())
        if fmt_mode == "json":
            handler.setFormatter(JsonLogFormatter())
        else:
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s %(levelname)s [%(name)s] req=%(request_id)s %(message)s"
                )
            )
        logger.addHandler(handler)
        logger.propagate = False
    return logger


def configure_handler_formatters(logger: logging.Logger) -> None:
    fmt_mode = (os.environ.get("LOG_FORMAT") or "text").strip().lower()
    for handler in logger.handlers:
        if not any(isinstance(f, RequestIdFilter) for f in handler.filters):
            handler.addFilter(RequestIdFilter())
        if fmt_mode == "json":
            handler.setFormatter(JsonLogFormatter())
        else:
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s %(levelname)s [%(name)s] req=%(request_id)s %(message)s"
                )
            )


def wrap_request_id_middleware(app_asgi, *, logger: logging.Logger | None = None):
    """Wrap ASGI app (outside ServerErrorMiddleware) for X-Request-ID and structured access logs."""
    http_logger = logger or configure_logging()

    async def middleware(scope, receive, send):
        if scope["type"] != "http":
            await app_asgi(scope, receive, send)
            return

        header_name = get_request_id_header()
        header_bytes = header_name.lower().encode("ascii")
        incoming_id = None
        for k, v in scope.get("headers") or ():
            if k.lower() == header_bytes:
                incoming_id = v.decode("latin-1", errors="ignore")
                break

        req_id = sanitize_request_id(incoming_id)
        token = request_id_var.set(req_id)
        start = time.perf_counter()
        status_code = 500
        client = scope.get("client")
        client_ip = client[0] if client else None

        async def send_wrapped(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers") or [])
                lower_key = header_name.lower().encode("ascii")
                headers = [(k, v) for k, v in headers if k.lower() != lower_key]
                headers.append((lower_key, req_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await app_asgi(scope, receive, send_wrapped)
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000.0, 2)
            http_logger.info(
                "http_request",
                extra={
                    "request_id": req_id,
                    "method": scope.get("method", "-"),
                    "path": scope.get("path", "/"),
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "client_ip": client_ip,
                },
            )
            request_id_var.reset(token)

    return middleware
