# Helper to start the GUI for manual testing without acquiring single-instance lock
import os
os.environ['EPISTEIN_SKIP_INSTALL'] = '1'
# Bypass single-instance lock (tests/dev convenience)
import epstein_downloader_gui as gui
try:
    gui.acquire_single_instance_lock = lambda *a, **k: ('noop', None)
    gui.release_single_instance_lock = lambda *a, **k: None
except Exception:
    pass

if __name__ == '__main__':
    gui.main()
