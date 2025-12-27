import os
import json
import shutil
import tkinter as tk
import pytest

from epstein_downloader_gui import DownloaderGUI

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config.json')
CONFIG_PATH = os.path.abspath(CONFIG_PATH)


def read_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def write_config(cfg):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2)


@pytest.fixture(scope='module')
def backup_and_restore_config():
    # Backup original config
    if os.path.exists(CONFIG_PATH):
        bak = CONFIG_PATH + '.bak'
        shutil.copy2(CONFIG_PATH, bak)
    else:
        bak = None

    yield

    # Restore
    if bak and os.path.exists(bak):
        shutil.move(bak, CONFIG_PATH)
    elif bak is None and os.path.exists(CONFIG_PATH):
        os.remove(CONFIG_PATH)


def test_settings_persist_across_save_and_reload(backup_and_restore_config, tmp_path):
    # Start from a known config
    base_cfg = {
        "download_dir": str(tmp_path / "downloads"),
        "log_dir": str(tmp_path / "logs"),
        "credentials_path": "",
        "concurrent_downloads": 3,
        "proxy": "",
        "speed_limit_kbps": 0,
        "theme": "light",
        "use_gdown_fallback": False,
        "url_list": [],
        "auto_start": False,
        "start_minimized": False,
    }
    write_config(base_cfg)

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk not available in this environment; skipping GUI tests.")
    root.withdraw()
    app = DownloaderGUI(root)

    # Modify settings programmatically as if user changed them in the Advanced Settings dialog
    new_download = str(tmp_path / "new_downloads")
    new_log = str(tmp_path / "new_logs")
    new_cred = str(tmp_path / "credentials.json")

    app.base_dir.set(new_download)
    app.log_dir = new_log
    app.credentials_path = new_cred
    if hasattr(app, 'use_gdown_fallback'):
        app.use_gdown_fallback.set(True)

    # Ensure UI vars exist and set them
    app.auto_start_var = getattr(app, 'auto_start_var', tk.BooleanVar(value=False))
    app.start_minimized_var = getattr(app, 'start_minimized_var', tk.BooleanVar(value=False))
    app.auto_start_var.set(True)
    app.start_minimized_var.set(True)

    # Save config
    app.save_config()
    root.destroy()

    cfg = read_config()

    assert cfg['download_dir'] == new_download
    assert cfg['log_dir'] == new_log
    assert cfg['credentials_path'] == new_cred
    assert cfg['use_gdown_fallback'] is True
    assert cfg['auto_start'] is True
    assert cfg['start_minimized'] is True

    # Now simulate restart and ensure values are loaded
    root2 = tk.Tk()
    root2.withdraw()
    app2 = DownloaderGUI(root2)

    assert app2.base_dir.get() == new_download
    assert getattr(app2, 'log_dir', None) == new_log
    assert getattr(app2, 'credentials_path', None) == new_cred
    assert bool(app2.config.get('use_gdown_fallback', False)) is True
    assert bool(app2.config.get('auto_start', False)) is True
    assert bool(app2.config.get('start_minimized', False)) is True

    root2.destroy()