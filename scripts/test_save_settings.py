import importlib, pathlib, json, sys
repo = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo))
import epstein_downloader_gui as edg
import tkinter as tk
r = tk.Tk(); r.withdraw()
app = edg.DownloaderGUI(r)
# Set test values
app.base_dir.set(r"C:\Temp\EpsteinTest")
app.log_dir = str(repo / 'logs_test')
app.credentials_path = str(repo / 'tmp_creds_test.json')
app.concurrent_downloads.set(5)
# Advanced flags
app.auto_start = True
app.start_minimized = True
# Save
app.save_config()
print('Saved config to', app.config_path)
print('Config file contents:')
print(open(app.config_path,'r',encoding='utf-8').read())
# Now simulate re-opening settings: create new GUI instance and see initial vars
new_app = edg.DownloaderGUI(r)
print('New app base_dir:', new_app.base_dir.get())
print('New app log_dir attr:', getattr(new_app,'log_dir',None))
print('New app credentials_path:', getattr(new_app,'credentials_path',None))
print('new_app.config[\'auto_start\']=', new_app.config.get('auto_start'))
