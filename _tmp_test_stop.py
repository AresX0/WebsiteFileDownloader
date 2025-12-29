"""Ad-hoc stop freeze verifier. Creates a DownloaderGUI, injects a blocking DummyBrowser, calls stop_all(), and reports timing/results."""
import importlib.util, os, sys, time
repo_root = os.path.abspath(os.path.dirname(__file__))
mod_path = os.path.join(repo_root, 'epstein_downloader_gui.py')
if not os.path.exists(mod_path):
    print('ERROR: module file missing:', mod_path); sys.exit(2)
spec = importlib.util.spec_from_file_location('epstein_downloader_gui', mod_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
DownloaderGUI = mod.DownloaderGUI
from tkinter import Tk
root = Tk(); root.withdraw()

def test():
    gui = DownloaderGUI(root)
    class DummyBrowser:
        def __init__(self): self.closed = False
        def close(self): time.sleep(0.6); self.closed = True
    gui._download_browser = DummyBrowser(); gui._download_context = object(); gui._download_page = object()
    start = time.time()
    try:
        gui.stop_all()
    except Exception as e:
        print('ERROR: stop_all raised', e); return 2
    elapsed = time.time() - start
    print(f'stop_all returned in {elapsed:.3f}s')
    deadline = time.time() + 3.0
    while time.time() < deadline and getattr(gui, '_download_browser', None) is not None:
        time.sleep(0.05)
    br = getattr(gui, '_download_browser', None)
    if elapsed < 1.0 and br is None:
        print('OK: stop returned quickly and browser cleared asynchronously')
        return 0
    else:
        print('FAIL: elapsed=', elapsed, 'browser_ref=', br)
        return 1

code = test()
try: root.destroy()
except Exception: pass
sys.exit(code)
