import time
import threading
import pytest
import tkinter as tk

from epstein_downloader_gui import DownloaderGUI

class DummyBrowser:
    def __init__(self, delay=0.6):
        self._delay = delay
        self.closed = False

    def close(self):
        # Simulate a blocking close call
        time.sleep(self._delay)
        self.closed = True


def test_stop_all_returns_quickly_and_clears_browser():
    root = tk.Tk()
    root.withdraw()
    gui = DownloaderGUI(root)

    # Inject a dummy blocking browser to simulate Playwright
    gui._download_browser = DummyBrowser(delay=0.6)
    start = time.time()
    gui.stop_all()
    duration = time.time() - start
    # stop_all should return quickly (well under the dummy close delay)
    assert duration < 0.2, f"stop_all took too long: {duration}s"

    # The browser closure should happen asynchronously; wait briefly for cleanup
    waited = 0.0
    while getattr(gui, '_download_browser', None) is not None and waited < 1.5:
        time.sleep(0.05)
        waited += 0.05

    assert getattr(gui, '_download_browser', None) is None, "Active browser reference was not cleared"
    root.destroy()