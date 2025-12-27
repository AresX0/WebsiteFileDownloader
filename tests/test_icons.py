import os
import tkinter as tk
import pytest

from epstein_downloader_gui import DownloaderGUI


def test_icons_load_if_present():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk not available in this environment; skipping GUI tests.")
    root.withdraw()
    app = DownloaderGUI(root)

    assets_dir = os.path.join(os.path.dirname(__file__), '..', 'assets')
    assets_dir = os.path.abspath(assets_dir)
    # If there are no assets, skip the test
    expected_files = ['start.png', 'pause.png', 'resume.png']
    found = [f for f in expected_files if os.path.exists(os.path.join(assets_dir, f))]
    if not found:
        pytest.skip("No icon assets present to test.")

    # If assets present, ensure load_icon cached them
    for name in ['start', 'pause', 'resume']:
        if os.path.exists(os.path.join(assets_dir, name + '.png')):
            assert name in app._images and app._images[name] is not None, f"Icon '{name}' not loaded"
            # Ensure image-like object provides a width() method
            assert hasattr(app._images[name], 'width'), f"Icon '{name}' not a valid image object"
    root.destroy()