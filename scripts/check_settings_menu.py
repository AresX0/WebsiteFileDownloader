import os
import sys
import tkinter as tk
# Ensure repository root is on sys.path so we import the application module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from epstein_downloader_gui import DownloaderGUI

# Ensure we don't trigger installs or auto-start
os.environ['EPISTEIN_SKIP_INSTALL'] = '1'

root = tk.Tk()
root.withdraw()  # Don't show the window
try:
    app = DownloaderGUI(root)
    menubar_name = root['menu']
    menubar = root.nametowidget(menubar_name)
    items = []
    try:
        end = menubar.index('end')
    except Exception:
        end = -1
    for i in range(0, (end + 1) if end is not None and end >= 0 else 0):
        try:
            label = menubar.entrycget(i, 'label')
        except Exception:
            try:
                t = menubar.type(i)
                label = f'<{t}>'
            except Exception:
                label = '<unknown>'
        items.append(label)
    print('Menubar items:', items)
    # Find Settings cascade and list its items
    found = False
    for i, label in enumerate(items):
        if label == 'Settings':
            found = True
            menu_name = menubar.entrycget(i, 'menu')
            settings_menu = root.nametowidget(menu_name)
            subitems = []
            try:
                end = settings_menu.index('end')
            except Exception:
                end = -1
            for j in range(0, (end + 1) if end is not None and end >= 0 else 0):
                try:
                    sublabel = settings_menu.entrycget(j, 'label')
                except Exception:
                    try:
                        t = settings_menu.type(j)
                        sublabel = f'<{t}>'
                    except Exception:
                        sublabel = '<unknown>'
                subitems.append(sublabel)
            print('Settings menu items:', subitems)
            break
    if not found:
        print('Settings menu not found')
except Exception as e:
    print('Error while checking settings menu:', e)
finally:
    try:
        root.destroy()
    except Exception:
        pass
