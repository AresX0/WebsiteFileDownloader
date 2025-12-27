import tkinter as tk
import pytest
from epstein_downloader_gui import DownloaderGUI


def test_show_json_handles_invalid(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    json_path = base / 'epstein_file_tree.json'
    # write invalid json (large)
    with open(json_path, 'w', encoding='utf-8') as f:
        f.write('{invalid:')

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('Tk not available')
    root.withdraw()
    app = DownloaderGUI(root)
    app.base_dir.set(str(base))
    # Should not raise
    app.show_json()
    root.destroy()