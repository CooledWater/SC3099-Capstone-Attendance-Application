"""Run existing authentication contracts against disposable backend data.

Run in the Module 2 container with the repository mounted read-only at /workspace.
"""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="saiv-auth-regression-") as temporary:
    env = {
        **os.environ,
        "DATABASE_URL": "sqlite:///" + str(Path(temporary) / "test.db"),
        "JWT_SECRET": "isolated-auth-regression-secret",
        "PYTHONPATH": os.pathsep.join([str(root / "module2-backend"), str(root / "tests")]),
        "API_BASE_URL": "http://127.0.0.1:18000",
        "TEST_BACKEND_URL": "http://127.0.0.1:18000",
    }
    with open(Path(temporary) / "server.log", "w+") as log:
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "18000"],
            env=env, cwd=root, stdout=log, stderr=log,
        )
        try:
            for _ in range(100):
                try:
                    if httpx.get(env["TEST_BACKEND_URL"] + "/health").status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                if server.poll() is not None:
                    log.seek(0)
                    raise RuntimeError(log.read())
                time.sleep(0.1)
            else:
                raise RuntimeError("Temporary backend did not become healthy")
            result = subprocess.run([
                sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                "new-tests/test_auth_cookie.py",
                "tests/public/test_api_functional.py::TestAuthentication",
                "tests/public/test_frontend_dashboard.py::TestFrontendAuthContract",
                "tests/public/test_security_basic.py::TestAuthenticationSecurity",
                "tests/public/test_security_basic.py::TestAuthorizationControls",
            ], env=env, cwd=root)
        finally:
            server.terminate()
            server.wait(timeout=10)
    sys.exit(result.returncode)
