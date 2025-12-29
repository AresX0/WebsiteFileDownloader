import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ['EPISTEIN_SKIP_INSTALL'] = '1'
import epstein_downloader_gui as gui
# Bypass single-instance lock
gui.acquire_single_instance_lock = lambda *a, **k: ('noop', None)
gui.release_single_instance_lock = lambda *a, **k: None


def test_write_thread_dump_direct():
    """Direct test that invokes the thread dump writer.

    This test requires a working Tk installation to create a temporary root window.
    If Tk is not available in the environment (common in headless CI), the test
    will be skipped during collection instead of causing an import-time failure.
    """
    try:
        root = gui.tk.Tk()
    except Exception as e:
        # If Tcl/Tk isn't installed properly, skip the test cleanly
        try:
            import tkinter as _tk
            if isinstance(e, _tk.TclError):
                pytest.skip("Tk not available; skipping thread-dump direct test")
        except Exception:
            pytest.skip("Tk not available; skipping thread-dump direct test")
    try:
        root.withdraw()
        app = gui.DownloaderGUI(root)
        app._write_thread_dump('direct-test')
    finally:
        try:
            root.destroy()
        except Exception:
            pass