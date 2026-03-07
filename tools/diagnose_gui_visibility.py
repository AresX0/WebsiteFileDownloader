import os
import sys
# Ensure repository root is on sys.path so local module imports succeed when running from tools/
try:
    _repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
except Exception:
    _repo_root = os.path.abspath(os.getcwd())
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

os.environ.setdefault('EPISTEIN_SKIP_INSTALL','1')
# Avoid starting the heartbeat in this diagnostic run
os.environ.setdefault('EPISTEIN_DISABLE_HEARTBEAT','1')

try:
    import tkinter as tk
    from epstein_downloader_gui import DownloaderGUI
except Exception as e:
    print(f"Failed to import application module: {e}")
    print("Make sure you run this script from the repository or set PYTHONPATH to include the repo root")
    raise

root = tk.Tk()
root.withdraw()  # keep from showing during diagnostics
app = DownloaderGUI(root)

print('root.state():', root.state())
try:
    print('root.wm_state():', root.wm_state())
except Exception as e:
    print('root.wm_state() failed:', e)
print('root.winfo_ismapped():', root.winfo_ismapped())
print('root.winfo_viewable():', getattr(root, 'winfo_viewable', lambda: 'n/a')())
print('root.geometry():', root.geometry())

# Check key widget presence and mapping
widgets = ['url_listbox', 'status_pane', 'log_panel', 'download_btn', 'pause_btn', 'resume_btn']
for w in widgets:
    present = hasattr(app, w)
    print(f"{w}: present={present}")
    if present:
        wid = getattr(app, w)
        try:
            print(f"  ismapped={wid.winfo_ismapped()}, viewable={getattr(wid,'winfo_viewable',lambda: 'n/a')()}, size=({wid.winfo_width()},{wid.winfo_height()}), grid_info={wid.grid_info() if hasattr(wid,'grid_info') else None}")
        except Exception as e:
            print('  info failed:', e)

# Print config flags
print('app.start_minimized:', getattr(app, 'start_minimized', None))
print('app.auto_start:', getattr(app, 'auto_start', None))
print('config_path:', getattr(app, 'config_path', None))

# Clean up
root.destroy()
print('diagnostic finished')
