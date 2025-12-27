import tkinter as tk
from epstein_downloader_gui import DownloaderGUI
root = tk.Tk()
root.withdraw()
app = DownloaderGUI(root)
buttons = ['remove_url_btn','move_up_btn','move_down_btn','clear_completed_btn','dir_btn','stop_scan_btn','enable_scan_btn']
print('Button widths:')
for b in buttons:
    if hasattr(app, b):
        w = app.__getattribute__(b).cget('width')
    else:
        w = 'MISSING'
    print(f"{b}: {w}")
root.destroy()
