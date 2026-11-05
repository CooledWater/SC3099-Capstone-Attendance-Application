"""Portable entry point that selects only this suite, from any working directory."""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", "-c", "hidden-tests/pytest.ini",
                                  "hidden-tests", *sys.argv[1:]], cwd=root))

