import os
import shutil
import tkinter as tk
import pytest

from epstein_downloader_gui import DownloaderGUI

ASSET_NAMES = ['start', 'pause', 'resume']


def _backup_and_zero(path):
    bak = path + '.bak'
    if os.path.exists(path):
        shutil.copy2(path, bak)
        # zero file
        with open(path, 'wb') as f:
            f.truncate(0)
    else:
        # mark no backup
        bak = None
        with open(path, 'wb') as f:
            f.truncate(0)
    return bak


def _restore_backup(path, bak):
    if bak and os.path.exists(bak):
        shutil.move(bak, path)
    else:
        try:
            os.remove(path)
        except Exception:
            pass


@pytest.mark.skipif(os.environ.get('CI_HEADLESS') == '1', reason="Tk not available in headless CI")
def test_placeholder_assets_created_and_loaded():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk not available in this environment; skipping GUI tests.")
    root.withdraw()
    assets_dir = os.path.join(os.path.dirname(__file__), '..', 'assets')
    assets_dir = os.path.abspath(assets_dir)
    os.makedirs(assets_dir, exist_ok=True)

    backups = {}
    try:
        # Backup existing and zero files to simulate corruption
        for name in ASSET_NAMES:
            p = os.path.join(assets_dir, name + '.png')
            backups[name] = _backup_and_zero(p)

        app = DownloaderGUI(root)

        for name in ASSET_NAMES:
            p = os.path.join(assets_dir, name + '.png')
            assert os.path.exists(p) and os.path.getsize(p) > 0, f"Placeholder not created for {name}"
            assert name in app._images and app._images[name] is not None
            assert hasattr(app._images[name], 'width')

        # Show toast and assert no exception
        app.show_toast('Test toast', duration=200)

    finally:
        for name in ASSET_NAMES:
            p = os.path.join(assets_dir, name + '.png')
            _restore_backup(p, backups.get(name))
        try:
            root.destroy()
        except Exception:
            pass