import os
import sys
import importlib
import pytest

# Ensure repo root is on sys.path so tests can import application module directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from epstein_downloader_gui import ensure_playwright_browsers, _installed_path


def test_detects_bundled_dir(monkeypatch, tmp_path):
    # Simulate a bundled directory under the installed path
    bundled = str(tmp_path / "playwright_browsers")
    monkeypatch.setenv("EPISTEIN_SKIP_INSTALL", "1")
    # Ensure _installed_path will return our tmp path for playwright_browsers
    monkeypatch.setattr('epstein_downloader_gui._installed_path', lambda *parts: bundled)
    monkeypatch.setattr('os.path.isdir', lambda p: True if p == bundled else False)
    # Clear any pre-existing env var
    if 'PLAYWRIGHT_BROWSERS_PATH' in os.environ:
        del os.environ['PLAYWRIGHT_BROWSERS_PATH']

    ensure_playwright_browsers()
    assert os.environ.get('PLAYWRIGHT_BROWSERS_PATH') == bundled


def test_detects_localappdata(monkeypatch, tmp_path):
    # Simulate a system LocalAppData ms-playwright install
    ms_dir = str(tmp_path / "ms-playwright")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("EPISTEIN_SKIP_INSTALL", "1")
    monkeypatch.setattr('os.path.isdir', lambda p: True if p == ms_dir else False)
    # Monkeypatch installed_path to something else
    monkeypatch.setattr('epstein_downloader_gui._installed_path', lambda *parts: str(tmp_path / "not_this"))
    if 'PLAYWRIGHT_BROWSERS_PATH' in os.environ:
        del os.environ['PLAYWRIGHT_BROWSERS_PATH']

    ensure_playwright_browsers()
    assert os.environ.get('PLAYWRIGHT_BROWSERS_PATH') == ms_dir


def test_frozen_does_not_invoke_self_install_and_shows_toast(monkeypatch):
    # Simulate frozen build and playwright present but launch failing
    monkeypatch.setenv("EPISTEIN_SKIP_INSTALL", "0")
    # Simulate frozen build (sys.frozen may not exist on test host)
    monkeypatch.setattr(sys, 'frozen', True, raising=False)

    # Monkeypatch import of playwright.sync_api so that `from playwright.sync_api import sync_playwright`
    # will resolve to our dummy object that raises on launch.
    import types

    class DummyChromium:
        def launch(self, headless=True):
            raise RuntimeError("no browsers")

    class DummyPW:
        def __enter__(self):
            class P:
                chromium = DummyChromium()
            return P()

        def __exit__(self, exc_type, exc, tb):
            return False

    dummy_mod = types.ModuleType('playwright.sync_api')
    dummy_mod.sync_playwright = lambda: DummyPW()
    sys.modules['playwright.sync_api'] = dummy_mod
    # Also ensure top-level 'playwright' package exists for the import machinery
    top = types.ModuleType('playwright')
    top.sync_api = dummy_mod
    sys.modules['playwright'] = top

    called = {}

    def fake_show_toast(msg):
        called['msg'] = msg

    monkeypatch.setattr('epstein_downloader_gui.show_toast', fake_show_toast)

    # Ensure no exception thrown and user gets guidance
    ensure_playwright_browsers()
    assert 'Playwright browsers not found' in called.get('msg') or 'please run' in called.get('msg').lower()