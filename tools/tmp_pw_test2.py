import sys, types
from epstein_downloader_gui import ensure_playwright_browsers
# Setup dummy modules
class DummyChromium:
    def launch(self, headless=True):
        raise RuntimeError('no browsers')
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
# Also ensure top-level package
top = types.ModuleType('playwright')
top.sync_api = dummy_mod
sys.modules['playwright'] = top
# Simulate frozen app
sys.frozen = True
called = {}
# Monkeypatch module-level
import epstein_downloader_gui as eg

def fake_show_toast(msg):
    called['msg'] = msg

eg.show_toast = fake_show_toast

ensure_playwright_browsers()
print('called:', called)
print('msg repr:', repr(called.get('msg')))
