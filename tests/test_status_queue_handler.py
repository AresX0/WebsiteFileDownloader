import logging
import threading
import time
import tempfile

from epstein_downloader_gui import attach_status_queue


class DummyGUI:
    def __init__(self):
        # minimal attributes
        self.log_dir = tempfile.mkdtemp()
        self.error_log_path = ""
        self.log_file = ""


def test_attach_status_queue_creates_queue_and_put_get():
    d = DummyGUI()
    q = attach_status_queue(d)
    assert q is not None

    q.put_nowait("test-message")
    assert q.get_nowait() == "test-message"
