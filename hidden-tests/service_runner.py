"""Launch unchanged application modules in separate processes, never the live DB."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main():
    if os.environ.get("SAIV_HIDDEN_OWNED_PROCESS") != "1":
        raise SystemExit("Use pytest with hidden-tests/pytest.ini to launch this helper")
    role, port = sys.argv[1:3]
    root = Path(__file__).resolve().parents[1]
    if role not in {"backend", "face"}:
        raise SystemExit("Unknown service")
    sys.path.insert(0, str(root / ("module2-backend" if role == "backend" else "module3-face-recognition")))
    from app.main import app
    if role == "backend":
        from app.auth import hash_password
        from app.database import SessionLocal
        from app.models import User
        # The only DB bootstrap: strict mode has no public admin registration.
        # Every course, session, enrollment and remaining user is created via HTTP.
        with SessionLocal() as db:
            if not db.query(User).filter_by(email="hidden-admin@example.org").first():
                db.add(User(email="hidden-admin@example.org", full_name="Disposable test administrator",
                            role="admin", hashed_password=hash_password(os.environ["SAIV_HIDDEN_PASSWORD"])))
                db.commit()
    if role == 'backend':
        # Exercise the deployment entry point, including its proxy trust policy.
        from app.server import run
    else:
        from uvicorn import run
    run(app, host="127.0.0.1", port=int(port), access_log=False, log_level="warning")


if __name__ == "__main__":
    main()

