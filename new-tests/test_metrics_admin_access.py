"""Metrics role enforcement over HTTP using isolated SQLite."""
import pytest
from fastapi.testclient import TestClient

from test_ta_scope import world
from app.main import app
from app import stats
import httpx


@pytest.mark.parametrize("uid", ["ia", "ib", "t1", "sa"])
@pytest.mark.parametrize("path", ["/metrics/", "/metrics/latency", "/metrics/request-rate", "/metrics/error-rate"])
def test_metrics_reject_non_admins(world, uid, path):
    call, _ = world
    response = call(uid, path)
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_metrics_remain_available_to_admin(world):
    call, _ = world
    response = call("admin", "/metrics/", limit=1)
    assert response.status_code == 200, response.text
    assert {"items", "total", "limit", "window_hours"} <= response.json().keys()
    assert response.json()["limit"] == 1


def test_metrics_require_authentication(world):
    response = TestClient(app).get("/api/v1/metrics/")
    assert response.status_code in (401, 403)


def test_instructor_keeps_course_analytics(world):
    call, _ = world
    response = call("ia", "/stats/courses/A")
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("value, expected", [("250.7", 250.7), ("0", 0), ("NaN", None), ("+Inf", None), ("-1", None), (None, None)])
def test_prometheus_latency_uses_combined_one_hour_histogram(world, monkeypatch, value, expected):
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(200, request=httpx.Request("GET", url), json={
            "status": "success", "data": {"resultType": "vector", "result":
                [] if value is None else [{"value": [123, value]}]},
        })
    monkeypatch.setattr(stats.httpx, "get", get)
    monkeypatch.setenv("PROMETHEUS_URL", "http://prometheus:9090/")
    call, _ = world
    response = call("admin", "/metrics/latency")
    assert response.status_code == 200, response.text
    assert response.json() == {"p95_ms": expected, "window_hours": 1, "source": "prometheus"}
    url, options = calls[0]
    assert url == "http://prometheus:9090/api/v1/query"
    assert options["params"]["query"] == ('histogram_quantile(0.95, sum by (le) '
        '(rate(http_request_duration_seconds_bucket{service="backend"}[1h]))) * 1000')
    assert options["timeout"] == 5.0


@pytest.mark.parametrize("failure, expected", [("timeout", 503), ("http", 502), ("invalid", 502)])
def test_prometheus_failures_do_not_return_zero_latency(world, monkeypatch, failure, expected):
    def get(url, **kwargs):
        if failure == "timeout":
            raise httpx.ConnectTimeout("unavailable")
        return httpx.Response(500 if failure == "http" else 200,
            request=httpx.Request("GET", url), json={"status": "error"})
    monkeypatch.setattr(stats.httpx, "get", get)
    call, _ = world
    response = call("admin", "/metrics/latency")
    assert response.status_code == expected
    assert "p95_ms" not in response.json()


@pytest.mark.parametrize("value, expected", [("360", 360.0), ("0", 0), ("NaN", None), (None, None)])
def test_one_hour_request_rate_aggregates_all_endpoints(world, monkeypatch, value, expected):
    def get(url, **kwargs):
        assert kwargs["params"]["query"] == 'sum(rate(http_requests_total{service="backend"}[1h])) * 3600'
        assert kwargs["timeout"] == 5.0
        return httpx.Response(200, request=httpx.Request("GET", url), json={
            "status": "success", "data": {"resultType": "vector", "result":
                [] if value is None else [{"value": [123, value]}]},
        })
    monkeypatch.setattr(stats.httpx, "get", get)
    call, _ = world
    response = call("admin", "/metrics/request-rate")
    assert response.status_code == 200, response.text
    assert response.json() == {"requests_per_hour": expected, "window_hours": 1, "source": "prometheus"}


@pytest.mark.parametrize("value, expected", [("2.5", 2.5), ("0", 0), ("NaN", None), (None, None)])
def test_one_hour_error_rate_uses_prometheus_5xx_percentage(world, monkeypatch, value, expected):
    def get(url, **kwargs):
        assert kwargs["params"]["query"] == (
            '100 * (sum(rate(http_requests_total{service="backend",status_class="5xx"}[1h])) '
            'or vector(0)) / sum(rate(http_requests_total{service="backend"}[1h]))')
        return httpx.Response(200, request=httpx.Request("GET", url), json={
            "status": "success", "data": {"resultType": "vector", "result":
                [] if value is None else [{"value": [123, value]}]},
        })
    monkeypatch.setattr(stats.httpx, "get", get)
    call, _ = world
    response = call("admin", "/metrics/error-rate")
    assert response.status_code == 200, response.text
    assert response.json() == {"error_rate_percent": expected, "window_hours": 1, "source": "prometheus"}
