import subprocess
import sys
import os

SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'check_deferred_exceptions.py')


def test_no_deferred_exception_usage():
    # Run the script; it exits with non-zero if issues are detected
    res = subprocess.run([sys.executable, SCRIPT], capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr)
    assert res.returncode == 0, 'Deferred-exception usage found by scripts/check_deferred_exceptions.py'
