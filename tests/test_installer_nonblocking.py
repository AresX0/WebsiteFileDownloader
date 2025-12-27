import time
import threading

import epstein_downloader_gui as gui


class FakeRoot:
    def __init__(self):
        self._timers = []

    def after(self, ms, func):
        # schedule func to run in background shortly so polling can proceed
        t = threading.Timer(ms / 1000.0, func)
        t.daemon = True
        t.start()
        self._timers.append(t)


def test_installer_runs_in_background_with_root(monkeypatch):
    called = []

    def slow_ensure(*args, **kwargs):
        called.append("started")
        time.sleep(0.5)
        called.append("finished")

    monkeypatch.setattr(gui, "ensure_runtime_dependencies", slow_ensure)

    root = FakeRoot()
    start = time.perf_counter()
    gui.install_dependencies_with_progress(root)
    duration = time.perf_counter() - start
    # Should return promptly (non-blocking), well under the slow task duration
    assert duration < 0.2

    # Wait for background thread to complete
    if gui.LAST_INSTALLER_THREAD is not None:
        gui.LAST_INSTALLER_THREAD.join(timeout=2.0)

    assert "started" in called
    assert "finished" in called


def test_installer_blocks_without_root(monkeypatch):
    # Non-GUI path should wait until installation completes
    def slow_ensure(*args, **kwargs):
        time.sleep(0.4)

    monkeypatch.setattr(gui, "ensure_runtime_dependencies", slow_ensure)
    start = time.perf_counter()
    gui.install_dependencies_with_progress(None)
    duration = time.perf_counter() - start
    assert duration >= 0.4


def test_cancel_requests_kill(monkeypatch):
    killed = {"called": False}

    def slow_ensure(*args, **kwargs):
        # Wait longer than we will allow; just sleep so a cancel can be issued
        time.sleep(2.0)

    def fake_kill():
        killed["called"] = True

    monkeypatch.setattr(gui, "ensure_runtime_dependencies", slow_ensure)
    monkeypatch.setattr(gui, "kill_in_progress_subprocesses", fake_kill)

    root = FakeRoot()
    gui.install_dependencies_with_progress(root)

    # Give it a moment to start
    time.sleep(0.1)
    # Simulate user pressing cancel
    if gui.LAST_INSTALLER_CANCEL_EVENT is not None:
        gui.LAST_INSTALLER_CANCEL_EVENT.set()

    # Poll to allow the handler to run
    time.sleep(0.2)
    assert killed["called"] is True
