import time, threading
import importlib.util, os
# Load GUI module by path
module_path = os.path.join(os.getcwd(), 'epstein_downloader_gui.py')
spec = importlib.util.spec_from_file_location('epstein_downloader_gui', module_path)
edg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(edg)
import tkinter as tk

root = tk.Tk()
root.withdraw()
app = edg.DownloaderGUI(root)
print('GUI created')

# Create a fake browser object whose close() method sleeps for 2s
class FakeBrowser:
    def __init__(self):
        self.closed = False
    def close(self):
        print('FakeBrowser.close() called; sleeping 2s to simulate blocking close')
        time.sleep(2)
        self.closed = True
        print('FakeBrowser.close() finished')

fake = FakeBrowser()
app._download_browser = fake

# Call stop_all and measure time
start = time.time()
app.stop_all()
elapsed = time.time() - start
print(f'stop_all() returned in {elapsed:.3f}s')
# Wait up to 3s for background thread to clear browser
for i in range(6):
    if getattr(app, '_download_browser', None) is None or getattr(app, '_download_browser', None).__class__.__name__ == 'NoneType':
        print('Download browser cleared')
        break
    print('Waiting for background close...')
    time.sleep(0.5)
# If still present, print status
print('Final _download_browser:', getattr(app, '_download_browser', None))
print('Test complete')
