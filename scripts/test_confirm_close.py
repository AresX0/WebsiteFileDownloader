import importlib, pathlib, json, sys, time
repo = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo))
import epstein_downloader_gui as edg
import tkinter as tk
import tkinter.messagebox as mb
import pytest
try:
    r = tk.Tk(); r.withdraw()
except tk.TclError:
    pytest.skip("Skipping UI tests - Tcl/Tk not available", allow_module_level=True)
app = edg.DownloaderGUI(r)
# Save baseline
app.save_config()
orig = json.loads(open(app.config_path,'r',encoding='utf-8').read())
# Open settings dialog
app.open_settings_dialog()
win = [w for w in r.winfo_children() if isinstance(w, tk.Toplevel)][-1]
# Make a change
app.base_dir.set(r"C:\Temp\EpsteinConfirm")
# Case 1: Discard (askyesnocancel returns False)
saved = []
orig_ask = mb.askyesnocancel
try:
    mb.askyesnocancel = lambda *a, **k: False
    # trigger Escape (bound to close handler)
    win.event_generate('<Escape>')
    time.sleep(0.2)
    # reopen settings to check persisted value
    app.open_settings_dialog()
    win2 = [w for w in r.winfo_children() if isinstance(w, tk.Toplevel)][-1]
    # Find Download Folder entry value
    def find_entry_with_label(parent, label_text):
        for c in parent.winfo_children():
            try:
                if getattr(c,'cget',None) and c.cget('text')==label_text:
                    # next sibling entry
                    siblings=parent.winfo_children()
                    idx=siblings.index(c)
                    for s in siblings[idx+1:idx+5]:
                        try:
                            if s.winfo_class().lower() in ('entry','tentry'):
                                return s.get()
                        except Exception:
                            pass
            except Exception:
                pass
            r=find_entry_with_label(c,label_text)
            if r: return r
        return None
    val = find_entry_with_label(win2,'Download Folder:')
    print('After discard, Download Folder entry:', val)
    try:
        win2.destroy()
    except Exception:
        pass
    # Case 2: Save (askyesnocancel returns True)
    app.open_settings_dialog()
    win3 = [w for w in r.winfo_children() if isinstance(w, tk.Toplevel)][-1]
    app.base_dir.set(r"C:\Temp\EpsteinConfirmSave")
    mb.askyesnocancel = lambda *a, **k: True
    win3.event_generate('<Escape>')
    time.sleep(0.2)
    # Read config file
    cfg = json.loads(open(app.config_path,'r',encoding='utf-8').read())
    print('After save, config download_dir:', cfg.get('download_dir'))
finally:
    mb.askyesnocancel = orig_ask
    try:
        for w in r.winfo_children():
            w.destroy()
    except Exception:
        pass
    r.destroy()
