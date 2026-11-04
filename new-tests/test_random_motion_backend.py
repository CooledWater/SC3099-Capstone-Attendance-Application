"""Collect v2 HTTP regressions without mixing M2 and M3's app packages."""
import subprocess
import sys
from pathlib import Path


def test_random_motion_backend_contracts():
    result = subprocess.run([
        sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
        str(Path(__file__).with_name('random_motion_backend_cases.py')),
    ], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
