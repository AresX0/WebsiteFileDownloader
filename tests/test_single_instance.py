import os
import tempfile
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "epstein_downloader_gui",
    str(Path(__file__).resolve().parents[1] / "epstein_downloader_gui.py"),
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

acquire_single_instance_lock = mod.acquire_single_instance_lock
release_single_instance_lock = mod.release_single_instance_lock


def test_acquire_and_release_lock():
    token = acquire_single_instance_lock()
    # second acquisition should fail
    try:
        try:
            acquire_single_instance_lock()
            assert False, "Expected RuntimeError on second acquisition"
        except RuntimeError:
            pass
    finally:
        release_single_instance_lock(token)
    # after release, we can acquire again
    token2 = acquire_single_instance_lock()
    release_single_instance_lock(token2)
