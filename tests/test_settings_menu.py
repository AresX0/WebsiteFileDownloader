import pytest
import tkinter as tk

from epstein_downloader_gui import DownloaderGUI


def test_top_level_settings_menu_present():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk not available in this environment")

    # Minimal instantiate without starting mainloop
    gui = DownloaderGUI(root)
    # Ensure menu is created and get the menubar
    menubar = gui.create_menu()
    labels = []
    try:
        end = menubar.index('end')
        for i in range(0, end + 1):
            try:
                lbl = menubar.entrycget(i, 'label')
            except Exception:
                lbl = None
            labels.append(lbl)
    except Exception:
        # No entries
        pass

    root.destroy()
    assert 'Settings' in labels, f"Top-level Settings menu not found. Found: {labels}"
