import subprocess
import sys
import os


def test_import_respects_skip_install():
    env = os.environ.copy()
    env['EPISTEIN_SKIP_INSTALL'] = '1'
    # Run a fresh Python interpreter to avoid import caching and to guarantee isolation
    cmd = [sys.executable, '-c', 'import epstein_downloader_gui; print("IMPORTED")']
    p = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert p.returncode == 0, f"Import failed: {p.stderr}"
    assert "IMPORTED" in p.stdout
