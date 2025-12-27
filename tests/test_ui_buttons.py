import tkinter as tk
import pytest
from epstein_downloader_gui import DownloaderGUI


def test_url_and_dir_buttons_width_consistent():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk not available; skipping GUI tests")
    app = DownloaderGUI(root)
    widths = [
        int(app.remove_url_btn.cget('width')),
        int(app.move_up_btn.cget('width')),
        int(app.move_down_btn.cget('width')),
        int(app.clear_completed_btn.cget('width')),
        int(app.dir_btn.cget('width')),
    ]
    # Convert to plain ints/str to avoid Tcl-specific return objects
    widths = [int(str(w)) for w in widths]
    assert len(set(widths)) == 1, f"URL and Browse button widths not consistent: {widths}"
    # ensure wide enough for 'Clear Completed' (len=15)
    assert widths[0] >= 18
    root.destroy()
