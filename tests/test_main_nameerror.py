import os
import tkinter as tk
import pytest
import epstein_downloader_gui


def test_main_handles_missing_downloader_class(caplog):
    # Skip if Tk not available
    try:
        _ = tk.Tk()
        _.destroy()
    except tk.TclError:
        pytest.skip("Tk not available; skipping GUI tests")

    # Ensure headless so main exits after initialization
    os.environ['EPSTEIN_HEADLESS'] = '1'
    # Temporarily remove the class from the module globals
    saved = getattr(epstein_downloader_gui, 'DownloaderGUI', None)
    if 'DownloaderGUI' in epstein_downloader_gui.__dict__:
        del epstein_downloader_gui.__dict__['DownloaderGUI']
    try:
        caplog.clear()
        caplog.set_level('ERROR')
        # Calling main should not raise, it should log a NameError diagnostic and return
        epstein_downloader_gui.main()
        found = any('NameError during DownloaderGUI instantiation' in rec.message for rec in caplog.records)
        assert found, 'Expected NameError diagnostic in logs when DownloaderGUI missing'
    finally:
        # Restore class
        if saved is not None:
            epstein_downloader_gui.DownloaderGUI = saved
        os.environ.pop('EPSTEIN_HEADLESS', None)
