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

    # Find Settings cascade and inspect its items
    settings_labels = []
    try:
        if 'Settings' in labels:
            idx = labels.index('Settings')
            menu_name = menubar.entrycget(idx, 'menu')
            settings_menu = gui.root.nametowidget(menu_name)
            end2 = settings_menu.index('end')
            for j in range(0, end2 + 1):
                try:
                    s_lbl = settings_menu.entrycget(j, 'label')
                except Exception:
                    s_lbl = None
                settings_labels.append(s_lbl)
    except Exception:
        pass

    root.destroy()
    assert 'Settings' in labels, f"Top-level Settings menu not found. Found: {labels}"
    # Ensure at least one of the new quick items is present
    assert 'Open General Settings...' in settings_labels, f"Expected 'Open General Settings...' in Settings menu, found: {settings_labels}"
    assert any(l and 'gdown' in (l.lower() if isinstance(l, str) else '') for l in settings_labels), f"Expected gdown fallback item in Settings menu, found: {settings_labels}"
