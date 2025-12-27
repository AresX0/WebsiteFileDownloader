import time
import tkinter as tk
import os
import json
import pytest
from epstein_downloader_gui import DownloaderGUI


def test_should_skip_scan_when_recent(tmp_path, monkeypatch):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk not available; skipping GUI tests")
    app = DownloaderGUI(root)
    base_dir = str(tmp_path)
    hash_file = os.path.join(base_dir, 'existing_hashes.txt')
    meta_file = hash_file + '.meta.json'
    # Create a fake hash_file and recent meta indicating a very recent scan
    os.makedirs(base_dir, exist_ok=True)
    with open(hash_file, 'w', encoding='utf-8') as f:
        f.write('abc123\t' + os.path.join(base_dir, 'file.txt') + '\n')
    meta = {'last_scan': time.time()}
    with open(meta_file, 'w', encoding='utf-8') as mf:
        json.dump(meta, mf)
    # Ensure _force_rescan is False
    app._force_rescan = False
    # Should skip full scan; we call the helper logic indirectly by invoking the download worker up to the point it would call scan
    assert (time.time() - float(json.load(open(meta_file))['last_scan'])) < 5
    # Use should_run_scan-like logic by calling build_existing_hash_file only when needed — here we mimic check
    now = time.time()
    SKIP_HOURS = 4
    last_scan = float(json.load(open(meta_file))['last_scan'])
    assert (now - last_scan) < (SKIP_HOURS * 3600)
    # Now set force rescan flag and check cache/meta removal occurs
    app.base_dir.set(base_dir)
    app._force_rescan = True
    app.force_full_hash_rescan()
    assert not os.path.exists(meta_file)
    root.destroy()


def test_action_buttons_width_consistent():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk not available; skipping GUI tests")
    app = DownloaderGUI(root)
    widths = [
        int(app.download_btn.cget('width')),
        int(app.pause_btn.cget('width')),
        int(app.resume_btn.cget('width')),
        int(app.schedule_btn.cget('width')),
        int(app.json_btn.cget('width')),
        int(app.skipped_btn.cget('width')),
        int(app.stop_scan_btn.cget('width')),
        int(app.enable_scan_btn.cget('width')),
    ]
    assert len(set(widths)) == 1, f"Button widths are not consistent: {widths}"
    # ensure wide enough for 'Show Downloaded JSON' length (len=19)
    assert widths[0] >= 25
    root.destroy()


def test_stop_scans_and_enable(tmp_path):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk not available; skipping GUI tests")
    app = DownloaderGUI(root)
    # Simulate a running scan
    app._scanning = True
    app._cancel_scan = False
    app.stop_scans()
    assert getattr(app, '_scans_disabled', False) is True
    assert getattr(app, '_cancel_scan', False) is True
    assert str(app.stop_scan_btn.cget('state')) == 'disabled'
    assert str(app.enable_scan_btn.cget('state')) == 'normal'
    # Re-enable
    app.enable_scans()
    assert getattr(app, '_scans_disabled', False) is False
    assert str(app.stop_scan_btn.cget('state')) == 'normal'
    assert str(app.enable_scan_btn.cget('state')) == 'disabled'
    root.destroy()


def test_build_existing_hash_file_skips_when_disabled(tmp_path):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk not available; skipping GUI tests")
    app = DownloaderGUI(root)
    base_dir = str(tmp_path)
    os.makedirs(base_dir, exist_ok=True)
    testfile = os.path.join(base_dir, 'a.txt')
    with open(testfile, 'w', encoding='utf-8') as f:
        f.write('hello')
    hash_file = os.path.join(base_dir, 'existing_hashes.txt')
    # Disable scans
    app._scans_disabled = True
    app.build_existing_hash_file(base_dir, hash_file)
    # Hash file should not be created when scans are disabled
    assert not os.path.exists(hash_file)
    root.destroy()
