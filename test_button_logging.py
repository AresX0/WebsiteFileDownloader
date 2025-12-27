import time
import tkinter as tk
from epstein_downloader_gui import DownloaderGUI

# Create a hidden Tk root so widgets are initialized but no window shows
root = tk.Tk()
root.withdraw()
app = DownloaderGUI(root)
# Allow logger and widgets to initialize
time.sleep(0.2)
print("Invoking pause_downloads()")
app.pause_downloads()
time.sleep(0.1)
print("Invoking resume_downloads()")
app.resume_downloads()
time.sleep(0.1)
print("Invoking stop_scans()")
app.stop_scans()
time.sleep(0.1)
print("Invoking enable_scans()")
app.enable_scans()
time.sleep(0.2)
# Dump last part of log file for quick inspection
try:
    with open(app.log_file, 'r', encoding='utf-8') as f:
        data = f.read()
    tail = data[-4000:]
    print('\n=== LOG TAIL START ===')
    print(tail)
    print('=== LOG TAIL END ===\n')
except Exception as e:
    print(f"Failed to read log file: {e}")

# Clean up
try:
    root.destroy()
except Exception:
    pass
print('Test complete')
