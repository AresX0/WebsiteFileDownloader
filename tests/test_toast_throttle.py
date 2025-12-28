import tkinter as tk
import time
import importlib.util
from pathlib import Path

# Import module by path to avoid module lookup issues in test environment
spec = importlib.util.spec_from_file_location(
    "epstein_downloader_gui",
    str(Path(__file__).resolve().parents[1] / "epstein_downloader_gui.py"),
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
DownloaderGUI = mod.DownloaderGUI


def test_toast_throttle():
    root = tk.Tk()
    root.withdraw()
    app = DownloaderGUI(root)

    # Call show_toast several times quickly; should not create many Toplevels
    for _ in range(10):
        app.show_toast("Spam test", duration=1000)
        time.sleep(0.02)

    # give Tk a moment to process
    root.update_idletasks()
    toplevels = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
    # At most 1 toast should be visible (throttled)
    assert len(toplevels) <= 1

    # Clean up
    try:
        if app._toast_window and app._toast_window.winfo_exists():
            app._toast_window.destroy()
    except Exception:
        pass
    root.destroy()
