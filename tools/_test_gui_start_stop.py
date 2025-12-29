import os, time, threading, traceback
# Environment safety flags for tests
os.environ['EPISTEIN_SKIP_INSTALL'] = '1'
os.environ['EPISTEIN_SKIP_GDRIVE_VALIDATION'] = '1'
os.environ['EPISTEIN_TEST_SCRIPTS_DIR'] = os.path.join(os.getcwd(), 'tools')
print('Env set:', os.environ.get('EPISTEIN_TEST_SCRIPTS_DIR'))

try:
    import importlib.util, importlib.machinery, sys
    module_path = os.path.join(os.getcwd(), 'epstein_downloader_gui.py')
    spec = importlib.util.spec_from_file_location('epstein_downloader_gui', module_path)
    edg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(edg)
    print('Loaded epstein_downloader_gui from', module_path)
except Exception as e:
    print('Error importing epstein_downloader_gui by path:', e)
    traceback.print_exc()
    raise

try:
    import tkinter as tk
    root = tk.Tk()
    # Intentionally do not withdraw; test will create a visible window if supported
    gui = edg.DownloaderGUI(root)
    print('DownloaderGUI created; root=', root)
except Exception as e:
    print('Error creating DownloaderGUI:', e)
    traceback.print_exc()
    raise

# Provide a safe fake download_all that doesn't use Playwright or tkinter.after

def fake_download_all():
    print('fake_download_all: started')
    try:
        gui._stop_event = getattr(gui, '_stop_event', threading.Event())
        gui._is_stopped = False
        for i in range(10):
            if getattr(gui, '_stop_event', None) and gui._stop_event.is_set():
                print('fake_download_all: stop detected, exiting early')
                break
            print('fake_download_all: working', i)
            time.sleep(0.25)
    except Exception as e:
        print('Exception in fake_download_all:', e)
        traceback.print_exc()
    print('fake_download_all: finished')

# Patch the instance method
gui.download_all = fake_download_all

# Start the download thread
try:
    gui.start_download_all_thread()
    print('Started download thread')
except Exception as e:
    print('Error starting download thread:', e)
    traceback.print_exc()

# Let it run briefly, then stop
time.sleep(1.0)
print('Calling stop_all()')
try:
    gui.stop_all()
    print('stop_all() called')
except Exception as e:
    print('Exception in stop_all():', e)
    traceback.print_exc()

# Wait for thread to notice stop
time.sleep(0.5)

# Call on_close to shutdown GUI
print('Calling on_close()')
try:
    gui.on_close()
    print('on_close() returned')
except Exception as e:
    print('Exception in on_close():', e)
    traceback.print_exc()

print('Test script finished')
