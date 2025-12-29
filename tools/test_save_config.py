import os
import json
import shutil
import pytest

pytest.importorskip("tkinter")

def test_save_config(tmp_path):
    import tkinter as tk

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tcl/Tk not available in environment")

    root.withdraw()

    from epstein_downloader_gui import DownloaderGUI

    cfg_path = os.path.join(os.path.dirname(__file__), 'config.json')
    # Backup original config and ensure we restore it after the test
    backup = cfg_path + ".bak"
    shutil.copy(cfg_path, backup)

    try:
        # Ensure auto_start is False before instantiating, to avoid downloads starting
        try:
            cfg = json.load(open(cfg_path, 'r', encoding='utf-8'))
        except Exception:
            cfg = {}
        cfg['auto_start'] = False
        json.dump(cfg, open(cfg_path, 'w', encoding='utf-8'), indent=2)

        app = DownloaderGUI(root)
        # Modify some settings as if the user changed them in Advanced Settings
        app.base_dir.set(r'C:\Temp\Epstein_saved_test')
        app.log_dir = os.path.join(os.getcwd(), 'test_logs')
        app.credentials_path = r'C:\Temp\credentials_saved_test.json'
        # Ensure use_gdown_fallback exists
        if hasattr(app, 'use_gdown_fallback'):
            app.use_gdown_fallback.set(True)
        # Ensure the UI vars for auto/start_min exist and set them
        app.auto_start_var = getattr(app, 'auto_start_var', tk.BooleanVar(value=False))
        app.start_minimized_var = getattr(app, 'start_minimized_var', tk.BooleanVar(value=False))
        app.auto_start_var.set(True)
        app.start_minimized_var.set(True)
        # Call save_config and then verify the resulting config file
        app.save_config()

        saved = json.load(open(cfg_path, 'r', encoding='utf-8'))
        assert saved.get('auto_start') is True

    finally:
        root.destroy()
        shutil.move(backup, cfg_path)