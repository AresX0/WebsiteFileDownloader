import sys, types
if 'epstein_downloader_gui' in sys.modules:
    del sys.modules['epstein_downloader_gui']
import epstein_downloader_gui as m

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

import types
dummy_mod = types.ModuleType('playwright.sync_api')
dummy_mod.sync_playwright = lambda: DummyPW()
sys.modules['playwright.sync_api'] = dummy_mod
# Also ensure top-level
top = types.ModuleType('playwright')
top.sync_api = dummy_mod
sys.modules['playwright'] = top

setattr(sys, 'frozen', True)

called = {}
def fake_show_toast(msg):
    called['msg'] = msg

m.show_toast = fake_show_toast

try:
    m.ensure_playwright_browsers()
except Exception as e:
    print('ensure_playwright_browsers raised', e)

print('called =', called)
