"""Run backend tests in a subprocess to isolate Module 2/3 app packages."""
import subprocess
import sys
from pathlib import Path

def test_backend_motion_contracts():
    result = subprocess.run([sys.executable, '-m', 'pytest', str(Path(__file__).with_name('backend_motion_cases.py')), '-q', '--disable-warnings'], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
