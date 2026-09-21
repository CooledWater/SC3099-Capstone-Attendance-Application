"""Prometheus scrape endpoint (``GET /metrics``) for Module 4's Prometheus.

module4-observability/prometheus.yml scrapes ``backend:8000`` at
``/metrics`` every 15s (job ``saiv-backend``). This is the *exposition*
endpoint and is unrelated to ``GET /api/v1/metrics/`` (app/stats.py), the
authenticated JSON feed behind the dashboard's MetricsPanel.

It is intentionally unauthenticated, like Module 3's ``/metrics``: the scrape
config carries no credentials and docs/INTEGRATION-GUIDE.md lists
"Prometheus -> M2, M3 /metrics" with auth "None". Nothing exported here is
user data - only route *templates* ("/api/v1/sessions/{session_id}", never a
concrete ID), fixed status classes and aggregate counters.

HTTP timing is not measured a second time: ``stats.MetricsMiddleware`` already
times every request and resolves its route template, and calls
``observe_http`` from the same measurement. Metric names and the
``service/method/route/status_class`` labels match Module 3's so the two
services can be queried together (``sum by (service) (...)``).

Exported (plus prometheus-client's default process/python collectors):

* ``http_requests_total`` / ``http_request_duration_seconds`` - technical
  health; failed logins are visible as
  ``http_requests_total{route="/api/v1/auth/login",status_class="4xx"}``.
* ``checkin_attempts_total`` - every check-in that reached a decision and was
  recorded (the same moment the ``checkin_attempted`` audit row is written).
  Requests refused earlier (window closed, not enrolled, duplicate, ...) are
  4xx on ``http_requests_total`` for the check-in route instead.
* ``checkin_success_total`` - attempts whose decision was ``approved``.
* ``checkin_outcomes_total{status}`` - approved / flagged / rejected, for the
  flagged-versus-approved ratio.
* ``checkin_risk_score`` - histogram of the final combined risk score.
"""

from fastapi import APIRouter, Response

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        Counter,
        Histogram,
        generate_latest,
    )
except ImportError:  # keep the API up if the optional dependency is missing
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    Counter = Histogram = generate_latest = None

METRICS_PATH = "/metrics"
SERVICE_LABEL = "backend"

_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"})
_CHECKIN_STATUSES = ("approved", "flagged", "rejected")


def _metric(factory, name, description, labels=(), **kwargs):
    if factory is None:
        return None
    try:
        return factory(name, description, list(labels), **kwargs)
    except ValueError:
        # Module re-imported in the same process (test runners): the collector
        # is already registered, so recording becomes a no-op instead of a crash.
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
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
CHECKIN_ATTEMPTS = _metric(
    Counter,
    "checkin_attempts_total",
    "Check-ins that reached a decision and were recorded.",
)
CHECKIN_SUCCESS = _metric(
    Counter,
    "checkin_success_total",
    "Recorded check-ins whose decision was approved.",
)
CHECKIN_OUTCOMES = _metric(
    Counter,
    "checkin_outcomes_total",
    "Recorded check-ins by decision.",
    ["status"],
)
CHECKIN_RISK = _metric(
    Histogram,
    "checkin_risk_score",
    "Combined risk score (0-1) of recorded check-ins.",
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)

if CHECKIN_OUTCOMES is not None:
    # Export every outcome at 0 so flagged/approved ratios have a series from
    # the first scrape instead of "no data" until the first flagged check-in.
    for _status in _CHECKIN_STATUSES:
        CHECKIN_OUTCOMES.labels(status=_status)


def observe_http(method: str, route: str | None, status_code: int, seconds: float) -> None:
    """Record one finished request (called by ``stats.MetricsMiddleware``).

    ``route`` is the matched route template; requests that match no route
    share the single ``unmatched`` label so arbitrary paths cannot create
    new series.
    """
    if HTTP_REQUESTS is None:
        return
    method = method.upper() if method.upper() in _METHODS else "other"
    route = route or "unmatched"
    status_class = f"{status_code // 100}xx" if 100 <= status_code <= 599 else "unknown"
    HTTP_REQUESTS.labels(SERVICE_LABEL, method, route, status_class).inc()
    HTTP_DURATION.labels(SERVICE_LABEL, method, route).observe(max(0.0, seconds))


def record_checkin(status: str, risk_score: float) -> None:
    """Record one persisted check-in decision (called from ``create_checkin``)."""
    if CHECKIN_ATTEMPTS is None:
        return
    CHECKIN_ATTEMPTS.inc()
    if status == "approved":
        CHECKIN_SUCCESS.inc()
    CHECKIN_OUTCOMES.labels(status=status if status in _CHECKIN_STATUSES else "other").inc()
    CHECKIN_RISK.observe(min(1.0, max(0.0, float(risk_score))))


router = APIRouter()


@router.get(METRICS_PATH, include_in_schema=False)
async def prometheus_scrape() -> Response:
    if generate_latest is None:
        return Response(
            content="prometheus_client is not installed\n",
            status_code=503,
            media_type="text/plain",
        )
    return Response(content=generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST})
