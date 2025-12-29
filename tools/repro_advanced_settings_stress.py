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

themes = ["clam", "default", "azure", "sun-valley", "forest", "cosmo"]
count = 0

# Open Advanced Settings
root.after(500, lambda: app.open_settings_dialog())

def cycle(i=0):
    global count
    t = themes[i % len(themes)]
    try:
        app.logger.info(f"Stress: set_theme {t} (iter {count})")
        app.set_theme(t)
    except Exception as e:
        app.logger.exception("Stress: set_theme failed: %s", e)
    try:
        app.save_config()
    except Exception as e:
        app.logger.exception("Stress: save_config failed: %s", e)
    count += 1
    if count < 30:
        root.after(300, lambda: cycle(i+1))
    else:
        root.after(500, lambda: app._write_thread_dump('advanced-settings-stress-final'))
        root.after(1000, lambda: (app.shutdown(timeout=1), root.destroy()))

root.after(1000, cycle)
root.mainloop()
print('done')