import threading
import time
import tkinter as tk
import pytest

from epstein_downloader_gui import DownloaderGUI


def test_pause_resume_behavior():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk not available in this environment; skipping GUI tests.")

    root.withdraw()
    app = DownloaderGUI(root)

    # Worker that app simulates during downloads: iterate 5 steps and respect pause event
    progress = []
    done = threading.Event()

    def worker():
        for i in range(5):
            # Wait until not paused
            while not app._pause_event.is_set():
                time.sleep(0.01)
            progress.append(i)
            time.sleep(0.05)
        done.set()

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    # Wait for at least one progress step
    timeout = time.time() + 2
    while len(progress) == 0 and time.time() < timeout:
        time.sleep(0.01)
    assert len(progress) >= 1

    # Pause the downloads
    app.pause_downloads()
    prev_len = len(progress)
    # Allow some time to verify no progress during pause
    time.sleep(0.3)
    assert len(progress) == prev_len, "Progress advanced while paused"

    # Resume and wait for completion
    app.resume_downloads()
    assert done.wait(timeout=2), "Worker did not finish after resume"
    root.destroy()