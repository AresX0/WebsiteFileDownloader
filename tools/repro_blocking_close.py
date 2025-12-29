import time
import threading
import os, sys
# Ensure the project root is on sys.path when running from tools/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ['EPISTEIN_SKIP_INSTALL'] = '1'
import epstein_downloader_gui as gui
# Bypass single-instance lock
gui.acquire_single_instance_lock = lambda *a, **k: ('noop', None)
gui.release_single_instance_lock = lambda *a, **k: None

root = gui.tk.Tk()
root.withdraw()  # Hide window for test
app = gui.DownloaderGUI(root)

class DummyBrowser:
    def close(self):
        # Simulate a blocking close
        time.sleep(6)

# Attach dummy browser to simulate blocking close on stop
app._download_browser = DummyBrowser()

# Start a thread that calls stop_all so we can observe watchdog
def call_stop():
    app.logger.info('Test: invoking stop_all()')
    app.stop_all()
    app.logger.info('Test: stop_all() returned')

th = threading.Thread(target=call_stop, daemon=True)
th.start()

# Wait longer than dummy close to let watchdog act
time.sleep(8)
app.logger.info('Test complete, cleaning up')
try:
    app.shutdown(timeout=1)
except Exception:
    pass
try:
    root.destroy()
except Exception:
    pass
print('done')