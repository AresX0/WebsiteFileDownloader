import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ['EPISTEIN_SKIP_INSTALL'] = '1'
import epstein_downloader_gui as gui
# Bypass single-instance lock
gui.acquire_single_instance_lock = lambda *a, **k: ('noop', None)
gui.release_single_instance_lock = lambda *a, **k: None

root = gui.tk.Tk()
root.withdraw()
app = gui.DownloaderGUI(root)

# Optionally open settings dialog to mirror user's action
try:
    root.after(1000, lambda: app.open_settings_dialog())
except Exception:
    pass

# Schedule a blocking sleep on the main thread to simulate a freeze
def _block_main():
    app.logger.info('Test: blocking main thread now (sleep 6s)')
    import time
    time.sleep(6)
    app.logger.info('Test: main thread sleep complete')

root.after(2000, _block_main)
# Exit after 12s
root.after(12000, lambda: (app.shutdown(timeout=1), root.destroy()))
root.mainloop()
print('done')