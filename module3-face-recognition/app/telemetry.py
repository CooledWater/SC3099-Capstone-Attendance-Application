"""Privacy-preserving logging and optional OpenTelemetry wiring.

Telemetry is deliberately metadata-only.  Helpers in this module accept only a
small attribute allowlist and scrub images, biometric templates, signatures,
IP addresses, authorization values, and oversized/base64-shaped text before a
log record reaches a handler.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator, Mapping

from .config import MAX_LOG_FIELD_CHARS, SERVICE_NAME


MAX_LOG_VALUE_LENGTH = MAX_LOG_FIELD_CHARS
REDACTED = "[REDACTED]"

_SENSITIVE_KEY_PARTS = (
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
    "image",
    "photo",
    "base64",
    "embedding",
    "template",
    "hash",
    "signature",
    "public_key",
    "private_key",
    "challenge",
    "body",
    "payload",
    "request",
    "response",
    "raw",
    "ip_address",
    "client_ip",
    "remote_addr",
)
_SAFE_SPAN_ATTRIBUTES = frozenset(
    {
        "face.detected",
        "face.confidence",
        "face.count",
        "match.score",
        "match.passed",
        "liveness.score",
        "liveness.passed",
        "liveness.challenge_type",
        "risk.score",
        "risk.level",
        "operation.name",
        "operation.outcome",
        "operation.latency_ms",
    }
)
_SAFE_CHALLENGES = frozenset({"passive", "blink", "head_turn"})
_SAFE_RISK_LEVELS = frozenset({"LOW", "MEDIUM", "HIGH", "CRITICAL"})
_SAFE_OPERATIONS = frozenset(
    {"face_enroll", "face_verify", "face_match", "liveness_check", "risk_assess", "device_attest"}
)
_SAFE_OUTCOMES = frozenset({"success", "failure", "passed", "failed", "no_face", "invalid", "error"})

_BASE64_PATTERN = re.compile(r"(?<![A-Za-z0-9+/=_-])[A-Za-z0-9+/=_-]{80,}(?![A-Za-z0-9+/=_-])")
_HEX_TEMPLATE_PATTERN = re.compile(r"\b[0-9a-fA-F]{64}\b")
_IPV4_PATTERN = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
_IPV6_PATTERN = re.compile(
    r"(?<![0-9A-Fa-f:])(?:[0-9A-Fa-f]{1,4}:){2,7}[0-9A-Fa-f:]{0,4}(?![0-9A-Fa-f:])"
)
_KEY_VALUE_PATTERN = re.compile(
    r"(?i)(authorization|cookie|password|secret|token|image|photo|base64|embedding|"
    r"template(?:_hash)?|signature|public_key|private_key|challenge|body|payload|request|"
    r"response|raw|ip_address|client_ip)"
    r"(\s*[=:]\s*)(?:\"[^\"]*\"|'[^']*'|[^,}\s]+)"
)

_STANDARD_LOG_RECORD_FIELDS = frozenset(logging.makeLogRecord({}).__dict__)
_configure_lock = threading.Lock()
_telemetry_configured = False


def _is_sensitive_key(key: Any) -> bool:
    normalised = str(key).strip().lower().replace("-", "_")
    return any(part in normalised for part in _SENSITIVE_KEY_PARTS)


def scrub_text(value: Any) -> str:
    """Return bounded text with common biometric/credential shapes removed."""

    text = str(value)
    text = _KEY_VALUE_PATTERN.sub(lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}", text)
    text = _HEX_TEMPLATE_PATTERN.sub(REDACTED, text)
    text = _BASE64_PATTERN.sub(REDACTED, text)
    text = _IPV4_PATTERN.sub(REDACTED, text)
    text = _IPV6_PATTERN.sub(REDACTED, text)
    if len(text) > MAX_LOG_VALUE_LENGTH:
        return f"{text[:MAX_LOG_VALUE_LENGTH]}...[TRUNCATED]"
    return text


def scrub_value(key: Any, value: Any, *, depth: int = 0) -> Any:
    if _is_sensitive_key(key):
        return REDACTED
    if depth >= 3:
        return "[MAX_DEPTH]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return scrub_text(value)
    if isinstance(value, Mapping):
        return {
            scrub_text(nested_key): scrub_value(nested_key, nested_value, depth=depth + 1)
            for nested_key, nested_value in list(value.items())[:32]
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [scrub_value("item", item, depth=depth + 1) for item in list(value)[:32]]
    return scrub_text(type(value).__name__)


def scrub_fields(fields: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): scrub_value(key, value) for key, value in list(fields.items())[:64]}


class PrivacyFilter(logging.Filter):
    """Scrub the rendered message before every attached logging handler."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered = record.getMessage()
        except Exception:
            rendered = "Unrenderable log message"
        record.msg = scrub_text(rendered)
        record.args = ()
        return True


class JsonPrivacyFormatter(logging.Formatter):
    """Small structured formatter that excludes traceback-local request data."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": scrub_text(record.name),
            "message": scrub_text(record.getMessage()),
        }
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_LOG_RECORD_FIELDS and key not in {"message", "asctime"}
        }
        if extras:
            payload["fields"] = scrub_fields(extras)
        if record.exc_info:
            payload["exception"] = scrub_text(self.formatException(record.exc_info))
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=True, default=str)


def configure_privacy_logging(level: str | int | None = None) -> logging.Logger:
    """Configure root JSON logging idempotently and return the service logger."""

    root = logging.getLogger()
    configured_level: str | int = level or os.getenv("LOG_LEVEL", "INFO")
    root.setLevel(configured_level)

    if not root.handlers:
        root.addHandler(logging.StreamHandler())
    for handler in root.handlers:
        if not any(isinstance(item, PrivacyFilter) for item in handler.filters):
            handler.addFilter(PrivacyFilter())
        handler.setFormatter(JsonPrivacyFormatter())
    return logging.getLogger(SERVICE_NAME)


def safe_log(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    """Log a short event with scrubbed structured metadata."""

    safe_fields = {
        key: value
        for key, value in scrub_fields(fields).items()
        if key not in _STANDARD_LOG_RECORD_FIELDS and key not in {"message", "asctime"}
    }
    logger.log(level, scrub_text(event), extra=safe_fields)


def _bounded_span_value(key: str, value: Any) -> Any | None:
    if key not in _SAFE_SPAN_ATTRIBUTES:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if not isinstance(value, str):
        return None
    if key == "liveness.challenge_type":
        return value if value in _SAFE_CHALLENGES else "unknown"
    if key == "risk.level":
        return value if value in _SAFE_RISK_LEVELS else "UNKNOWN"
    if key == "operation.name":
        return value if value in _SAFE_OPERATIONS else "other"
    if key == "operation.outcome":
        return value if value in _SAFE_OUTCOMES else "other"
    return scrub_text(value)


def set_span_attributes(span: Any = None, **attributes: Any) -> None:
    """Set only explicitly allowed, low-cardinality scalar span attributes."""

    if span is None:
        try:
            from opentelemetry import trace

            span = trace.get_current_span()
        except ImportError:
            return
    for key, value in attributes.items():
        safe_value = _bounded_span_value(key, value)
        if safe_value is not None:
            try:
                span.set_attribute(key, safe_value)
            except Exception:
                continue


def get_tracer(name: str = SERVICE_NAME) -> Any:
    try:
        from opentelemetry import trace

        return trace.get_tracer(name)
    except ImportError:
        return _NoOpTracer()


class _NoOpSpan:
    def __enter__(self) -> "_NoOpSpan":
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def set_attribute(self, *_args: Any, **_kwargs: Any) -> None:
        return None


class _NoOpTracer:
    def start_as_current_span(self, *_args: Any, **_kwargs: Any) -> _NoOpSpan:
        return _NoOpSpan()


@contextmanager
def operation_span(operation: str) -> Iterator[Any]:
    safe_operation = operation if operation in _SAFE_OPERATIONS else "other"
    with get_tracer().start_as_current_span(safe_operation) as span:
        set_span_attributes(span, **{"operation.name": safe_operation})
        yield span


def configure_telemetry(
    app: Any,
    *,
    service_name: str = SERVICE_NAME,
    endpoint: str | None = None,
    enabled: bool | None = None,
) -> bool:
    """Instrument a FastAPI app; return ``False`` when OTel is unavailable.

    OTLP exporting is asynchronous, so an unavailable collector never prevents
    request handling.  Calling this function more than once is safe.
    """

    global _telemetry_configured

    if enabled is None:
        enabled = os.getenv("TELEMETRY_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}
    if not enabled:
        return False
    if getattr(getattr(app, "state", None), "otel_configured", False):
        return True

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        return False

    with _configure_lock:
        if not _telemetry_configured:
            provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
            otlp_endpoint = endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
            if otlp_endpoint:
                exporter = OTLPSpanExporter(
                    endpoint=otlp_endpoint,
                    insecure=otlp_endpoint.lower().startswith("http://"),
                )
                provider.add_span_processor(BatchSpanProcessor(exporter))
            # OpenTelemetry permits only one global provider.  If a host process
            # installed one first, keep it and still instrument the app.
            current_provider = trace.get_tracer_provider()
            if current_provider.__class__.__name__ == "ProxyTracerProvider":
                trace.set_tracer_provider(provider)
            _telemetry_configured = True

        try:
            FastAPIInstrumentor.instrument_app(
                app,
                excluded_urls="health,metrics",
                server_request_hook=_server_request_hook,
            )
        except Exception:
            return False
        if getattr(app, "state", None) is not None:
            app.state.otel_configured = True
    return True


def _server_request_hook(span: Any, scope: Mapping[str, Any]) -> None:
    """Remove network identifiers attached by default ASGI instrumentation."""

    if span is None:
        return
    # The SDK Span exposes its mutable attributes during on-start hooks.  This
    # is deliberately defensive across OTel semantic-convention versions.
    attributes = getattr(span, "_attributes", None)
    if not hasattr(attributes, "pop"):
        return
    sensitive_keys = (
        "client.address",
        "client.port",
        "http.client_ip",
        "http.target",
        "http.url",
        "net.peer.ip",
        "net.peer.name",
        "net.peer.port",
        "network.peer.address",
        "network.peer.port",
        "server.address",
        "server.port",
        "url.full",
        "url.query",
        "user_agent.original",
    )
    for key in sensitive_keys:
        attributes.pop(key, None)


def shutdown_telemetry() -> None:
    try:
        from opentelemetry import trace

        provider = trace.get_tracer_provider()
        shutdown = getattr(provider, "shutdown", None)
        if callable(shutdown):
            shutdown()
    except Exception:
        return


# Compatibility alias used by simple application wiring.
instrument_fastapi = configure_telemetry


__all__ = [
    "JsonPrivacyFormatter",
    "PrivacyFilter",
    "configure_privacy_logging",
    "configure_telemetry",
    "get_tracer",
    "instrument_fastapi",
    "operation_span",
    "safe_log",
    "scrub_fields",
    "scrub_text",
    "set_span_attributes",
    "shutdown_telemetry",
]
