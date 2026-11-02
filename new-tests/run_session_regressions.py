"""Run scheduling/API regressions against a disposable local SQLite backend."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import threading

import uvicorn

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="saiv-schedule-") as temporary:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    env = dict(os.environ, DATABASE_URL=f"sqlite:///{Path(temporary).as_posix()}/test.db",
               JWT_SECRET="isolated-scheduling-test-secret",
               TEST_BACKEND_URL=f"http://127.0.0.1:{port}",
               API_BASE_URL=f"http://127.0.0.1:{port}",
               STRICT_SECURITY_MODE="false",
               PYTHONPATH=str(root / "tests"))
    os.environ.update(env)
    sys.path.insert(0, str(root / "module2-backend"))
    from app.main import app
    from app.database import engine

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    worker = threading.Thread(target=server.run)
    worker.start()
    try:
        for _ in range(100):
            if server.started:
                break
            if not worker.is_alive():
                raise RuntimeError("Scratch backend exited during startup")
            time.sleep(0.1)
        else:
            raise RuntimeError("Scratch backend did not become healthy")
        targets = sys.argv[1:] or [
            "new-tests/test_session_lifecycle.py", "new-tests/test_missing_endpoints.py",
            "new-tests/test_session_deletion.py", "tests/public/test_api_functional.py",
            "tests/public/test_observability.py",
        ]
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *targets], cwd=root, env=env,
        )
    finally:
        server.should_exit = True
        worker.join(timeout=15)
        engine.dispose()
sys.exit(result.returncode)
