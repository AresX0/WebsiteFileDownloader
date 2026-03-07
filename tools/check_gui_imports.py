import importlib, traceback, sys, os, inspect

print('Checking epstein_downloader_gui import and DownloaderGUI presence...')
try:
    import epstein_downloader_gui as gui
    print('Imported module:', gui.__file__)
    print('Module size:', os.path.getsize(gui.__file__))
    has = hasattr(gui, 'DownloaderGUI')
    print('Has DownloaderGUI:', has)
    if has:
        cls = getattr(gui, 'DownloaderGUI')
        print('DownloaderGUI type:', type(cls))
        # Try to instantiate with a hidden Tk root
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            try:
                app = cls(root)
                print('Instantiation succeeded. app keys:', list(k for k in dir(app) if not k.startswith('_'))[:20])
                try:
                    root.destroy()
                except Exception:
                    pass
            except Exception as e:
                print('Instantiation failed:', e)
                traceback.print_exc()
        except Exception as e:
            print('Tk init failed (likely headless):', e)
            traceback.print_exc()
except Exception as e:
    print('Import failed:', e)
    traceback.print_exc()
    # If module file exists, print last lines
    module_path = os.path.join(os.getcwd(), 'epstein_downloader_gui.py')
    try:
        if os.path.exists(module_path):
            print('\n=== module file snippet ===')
            with open(module_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            print('File length:', len(lines))
            print('Last 200 lines:')
            print(''.join(lines[-200:]))
    except Exception as e:
        print('Failed to show module snippet:', e)

print('Done.')
