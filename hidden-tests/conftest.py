"""Owned subprocesses and explicit coverage gates for the hidden-style suite."""
from __future__ import annotations

import sys
import pytest
from harness import Runtime, World


def pytest_addoption(parser):
    group = parser.getgroup("hidden-style")
    group.addoption("--redis-server", help="redis-server executable; harness launches its own instance")
    group.addoption("--backend-only", action="store_true", help="Explicitly skip native face tests")
    group.addoption("--run-stress", action="store_true", help="Run the 100-user workloads")
    group.addoption("--include-interpretations", action="store_true", help="Include inferred requirements, e.g. impossible travel")
    group.addoption("--attack-manifest", help="Path to the labelled physical-capture JSON manifest")
    group.addoption("--require-physical", action="store_true", help="Fail if the real-attack corpus is missing")
    group.addoption("--postgres", action="store_true", help="Use disposable PostgreSQL inside hidden-tests/compose.yml")
    group.addoption("--stress-p95", type=float, default=2.0, help="Local p95 target in seconds (hidden rubric unspecified)")


def pytest_configure(config):
    if sys.version_info < (3, 11):
        raise pytest.UsageError("hidden-tests requires Python 3.11+ (the project Docker images use 3.11)")
    if config.getoption("--stress-p95") <= 0:
        raise pytest.UsageError("--stress-p95 must be positive")
    if hasattr(config, "workerinput"):
        raise pytest.UsageError("Run without pytest-xdist: rate-limit tests own and reset disposable Redis")


def pytest_collection_modifyitems(config, items):
    for item in items:
        if "stress" in item.keywords and not config.getoption("--run-stress"):
            item.add_marker(pytest.mark.skip(reason="Enable 100-user workloads with --run-stress"))
        if "interpretation" in item.keywords and not config.getoption("--include-interpretations"):
            item.add_marker(pytest.mark.skip(reason="Inferred requirement; enable --include-interpretations"))
        if "postgres" in item.keywords and not config.getoption("--postgres"):
            item.add_marker(pytest.mark.skip(reason="Requires the disposable PostgreSQL Compose profile"))


@pytest.fixture(scope="session")
def runtime(tmp_path_factory, pytestconfig):
    instance = Runtime(tmp_path_factory.mktemp("saiv-hidden"), pytestconfig)
    try:
        yield instance
    finally:
        instance.close()


@pytest.fixture
def world(runtime):
    return World(runtime.backend())


@pytest.fixture
def strict_world(runtime):
    service = runtime.backend(strict=True)
    runtime.clear_limits(service)
    return World(service)


@pytest.fixture(params=["compat", "strict"])
def security_world(runtime, request):
    service = runtime.backend(strict=request.param == "strict")
    runtime.clear_limits(service)
    return World(service)


@pytest.fixture(scope="session")
def face(runtime):
    return runtime.face()

