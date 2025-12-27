import threading
import time
import tkinter as tk
import pytest

from epstein_downloader_gui import DownloaderGUI


def test_shutdown_joins_background_thread():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk not available in this environment; skipping GUI tests.")
    root.withdraw()
    app = DownloaderGUI(root)

    # Start a test background thread that waits on the app stop event
    def long_running():
        # Wait until stop requested (simulate long-running worker)
        if getattr(app, '_stop_event', None):
            app._stop_event.wait()

    t = threading.Thread(target=long_running, daemon=True)
    t.start()
    # Attach to app so shutdown will attempt join
    app._download_all_thread = t

    # Call shutdown and ensure thread is no longer alive after
    app.shutdown(timeout=2)
    t.join(timeout=1)
    assert not t.is_alive()
    try:
        root.destroy()
    except Exception:
        pass


def test_shutdown_stops_spinner():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk not available in this environment; skipping GUI tests.")
    root.withdraw()
    app = DownloaderGUI(root)

    # Schedule a dummy after job and simulate spinner running
    def noop():
        return None
    app._spinner_job = root.after(5000, noop)
    app._spinner_running = True
    # Ensure shutdown cancels the spinner job
    app.shutdown(timeout=1)
    assert not getattr(app, '_spinner_running', False)
    # _spinner_job should be cleared or the scheduled job should not exist anymore
    try:
        if getattr(app, '_spinner_job', None):
            # try to cancel if still present
            root.after_cancel(app._spinner_job)
    except Exception:
        pass
    try:
        root.destroy()
    except Exception:
        pass
