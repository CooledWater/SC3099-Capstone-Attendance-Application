"""Prometheus metrics with fixed-cardinality, privacy-safe labels."""

from __future__ import annotations

import time
from typing import Any, Mapping


try:
    from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
except ImportError:  # The face service remains usable if metrics are not installed.
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    Counter = Histogram = None  # type: ignore[assignment,misc]
    generate_latest = None  # type: ignore[assignment]


SERVICE_LABEL = "face-recognition"
_ROUTES = frozenset(
    {
        "/",
        "/health",
        "/metrics",
        "/face/enroll",
        "/face/verify",
        "/face/match",
        "/liveness/check",
        "/risk/assess",
        "/device/attest",
    }
)
_METHODS = frozenset({"GET", "POST", "OPTIONS", "HEAD"})
_FACE_OPERATIONS = frozenset({"enroll", "verify", "match"})
_FACE_OUTCOMES = frozenset({"success", "failure", "no_face", "invalid_input", "error"})
_CHALLENGES = frozenset({"passive", "blink", "head_turn"})
_LIVENESS_OUTCOMES = frozenset({"passed", "failed", "no_face", "error"})
_RISK_LEVELS = frozenset({"LOW", "MEDIUM", "HIGH", "CRITICAL"})


def _metric(factory: Any, name: str, description: str, labels: list[str], **kwargs: Any) -> Any:
    if factory is None:
        return None
    try:
        return factory(name, description, labels, **kwargs)
    except ValueError:
        # Supports module reload in test/dev servers without duplicate collector
        # crashes.  Recording becomes a safe no-op for the reloaded module.
        return None


HTTP_REQUESTS = _metric(
    Counter,
    "http_requests_total",
    "HTTP requests handled by the service.",
    ["service", "method", "route", "status_class"],
)
HTTP_DURATION = _metric(
    Histogram,
    "http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["service", "method", "route"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0),
)
FACE_OUTCOMES = _metric(
    Counter,
    "face_operation_outcomes_total",
    "Face operation outcomes.",
    ["operation", "outcome"],
)
FACE_DURATION = _metric(
    Histogram,
    "face_operation_duration_seconds",
    "Face operation latency in seconds.",
    ["operation"],
    buckets=(0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0),
)
LIVENESS_OUTCOMES = _metric(
    Counter,
    "liveness_outcomes_total",
    "Liveness decisions by supported challenge type.",
    ["challenge_type", "outcome"],
)
RISK_OUTCOMES = _metric(
    Counter,
    "risk_assessments_total",
    "Risk decisions by bounded risk level and pass decision.",
    ["risk_level", "decision"],
)


def _bounded(value: Any, allowed: frozenset[str], fallback: str = "other") -> str:
    candidate = str(value)
    return candidate if candidate in allowed else fallback


def _route(scope: Mapping[str, Any]) -> str:
    route_object = scope.get("route")
    route_path = getattr(route_object, "path", None)
    if route_path in _ROUTES:
        return route_path
    raw_path = scope.get("path")
    return raw_path if raw_path in _ROUTES else "other"


def _status_class(status: int) -> str:
    if 100 <= status <= 599:
        return f"{status // 100}xx"
    return "unknown"


def _increment(metric: Any, **labels: str) -> None:
    if metric is not None:
        metric.labels(**labels).inc()


def _observe(metric: Any, value: float, **labels: str) -> None:
    if metric is not None:
        metric.labels(**labels).observe(max(0.0, float(value)))


class PrometheusMiddleware:
    """Minimal ASGI middleware; it never reads or buffers request/response bodies."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http" or scope.get("path") == "/metrics":
            await self.app(scope, receive, send)
            return

        started = time.perf_counter()
        status_code = 500

        async def capture_status(message: dict[str, Any]) -> None:
            nonlocal status_code
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status", 500))
            await send(message)

        try:
            await self.app(scope, receive, capture_status)
        finally:
            method = _bounded(str(scope.get("method", "")).upper(), _METHODS)
            route = _route(scope)
            _increment(
                HTTP_REQUESTS,
                service=SERVICE_LABEL,
                method=method,
                route=route,
                status_class=_status_class(status_code),
            )
            _observe(
                HTTP_DURATION,
                time.perf_counter() - started,
                service=SERVICE_LABEL,
                method=method,
                route=route,
            )


def render_metrics() -> bytes:
    if generate_latest is None:
        return b"# prometheus_client is unavailable\n"
    return generate_latest()


def metrics_response() -> Any:
    from fastapi import Response

    return Response(
        content=render_metrics(),
        headers={"Content-Type": CONTENT_TYPE_LATEST},
    )


def setup_metrics(app: Any, *, enabled: bool = True) -> bool:
    """Add middleware and an exact ``GET /metrics`` route idempotently."""

    if not enabled or generate_latest is None:
        return False
    if getattr(getattr(app, "state", None), "prometheus_metrics_configured", False):
        return True

    existing_paths = {getattr(route, "path", None) for route in getattr(app, "routes", [])}
    if "/metrics" not in existing_paths:
        app.add_api_route(
            "/metrics",
            metrics_response,
            methods=["GET"],
            include_in_schema=False,
            name="prometheus_metrics",
        )
    app.add_middleware(PrometheusMiddleware)
    if getattr(app, "state", None) is not None:
        app.state.prometheus_metrics_configured = True
    return True


def record_face_outcome(operation: str, outcome: str, latency_seconds: float | None = None) -> None:
    safe_operation = _bounded(operation, _FACE_OPERATIONS)
    safe_outcome = _bounded(outcome, _FACE_OUTCOMES)
    _increment(FACE_OUTCOMES, operation=safe_operation, outcome=safe_outcome)
    if latency_seconds is not None:
        _observe(FACE_DURATION, latency_seconds, operation=safe_operation)


def record_liveness_outcome(challenge_type: str, outcome: str) -> None:
    _increment(
        LIVENESS_OUTCOMES,
        challenge_type=_bounded(challenge_type, _CHALLENGES, "unknown"),
        outcome=_bounded(outcome, _LIVENESS_OUTCOMES),
    )


def record_risk_outcome(risk_level: str, passed: bool) -> None:
    _increment(
        RISK_OUTCOMES,
        risk_level=_bounded(risk_level, _RISK_LEVELS, "UNKNOWN"),
        decision="pass" if bool(passed) else "fail",
    )


# Compatibility alias for application wiring.
instrument_app = setup_metrics


__all__ = [
    "PrometheusMiddleware",
    "instrument_app",
    "metrics_response",
    "record_face_outcome",
    "record_liveness_outcome",
    "record_risk_outcome",
    "render_metrics",
    "setup_metrics",
]
