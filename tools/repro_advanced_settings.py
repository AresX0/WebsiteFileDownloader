import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ['EPISTEIN_SKIP_INSTALL'] = '1'
import epstein_downloader_gui as gui
# Bypass single-instance lock
gui.acquire_single_instance_lock = lambda *a, **k: ('noop', None)
gui.release_single_instance_lock = lambda *a, **k: None

root = gui.tk.Tk()
root.withdraw()  # Keep main window hidden to avoid focus issues
app = gui.DownloaderGUI(root)

# Open Advanced Settings after startup
root.after(1000, lambda: app.open_settings_dialog())
# Apply a theme (may trigger third-party imports inside set_theme)
root.after(2500, lambda: app.set_theme('azure'))
# Save config (calls save_config)
root.after(4000, lambda: app.save_config())
# Write an explicit thread dump for analysis after actions
root.after(5500, lambda: app._write_thread_dump('advanced-settings-repro'))
# Cleanup after 9s
root.after(9000, lambda: (app.shutdown(timeout=1), root.destroy()))

root.mainloop()
print('done')