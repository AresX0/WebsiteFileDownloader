import os
import json
import sys
import pathlib
import tkinter as tk
# Ensure repo root is on sys.path so imports work when running from scripts/
repo_root = str(pathlib.Path(__file__).resolve().parents[1])
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
from epstein_downloader_gui import DownloaderGUI

root = None
root2 = None
try:
    try:
        root = tk.Tk()
    except tk.TclError:
        print('Tk not available; cannot perform interactive-like persistence test.')
        raise SystemExit(1)
    app = DownloaderGUI(root)
    tmp = os.path.join(os.getcwd(), 'tmp_credentials.json')
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write('{}')
    # Simulate user setting credentials in settings dialog
    app.credentials_path = tmp
    app.config['credentials_path'] = tmp
    app.save_config()
    print('Saved credentials_path to config:', app.config.get('credentials_path'))
    root.destroy()

    # Re-instantiate to simulate restart
    root2 = tk.Tk()
    app2 = DownloaderGUI(root2)
    loaded = app2.config.get('credentials_path')
    print('Loaded credentials_path from new instance:', loaded)
    if loaded == tmp:
        print('PASS: credentials_path persisted across restart')
        result = 0
    else:
        print('FAIL: credentials_path did not persist')
        result = 2
    root2.destroy()
finally:
    try:
        os.unlink(tmp)
    except Exception:
        pass
    raise SystemExit(result)
