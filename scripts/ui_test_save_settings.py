import importlib, pathlib, json, sys, time
repo = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo))
import epstein_downloader_gui as edg
import tkinter as tk
import pytest
try:
    r = tk.Tk(); r.withdraw()
except tk.TclError:
    pytest.skip("Skipping UI tests - Tcl/Tk not available", allow_module_level=True)
app = edg.DownloaderGUI(r)
# Open settings dialog
app.open_settings_dialog()
# Find the Toplevel window
tops = [w for w in r.winfo_children() if isinstance(w, tk.Toplevel)]
if not tops:
    print('No settings dialog found')
    raise SystemExit(1)
win = tops[-1]
# Set fields: find entries by widget type and positions
# download_entry is first entry; log_entry second; cred_entry third
entries = [w for w in win.winfo_children() if isinstance(w, tk.Entry) or isinstance(w, tk.ttk.Entry)]
# The above may not find nested widgets; search recursively
def find_widgets(parent, cls):
    res=[]
    for c in parent.winfo_children():
        if c.winfo_class().lower() in ('entry','tentry','ttk::entry'):
            res.append(c)
        res.extend(find_widgets(c, cls))
    return res
entries=find_widgets(win, tk.Entry)
print('entries count', len(entries))
# Instead of relying on traversal, set the StringVars directly if accessible
# We expect app.open_settings_dialog created local 'download_var','log_var','cred_var' as local vars but also set self.auto_start_var etc.
# Simulate user actions by setting attributes directly as the Save closure reads them via these self vars. We'll set their values.
# Set download
try:
    for child in win.winfo_children():
        for sub in child.winfo_children():
            if getattr(sub, 'get', None) and callable(sub.get):
                pass
except Exception:
    pass
# Set attributes on app as if user changed them
app.base_dir.set(r"C:\Temp\EpsteinUI")
app.log_dir = str(repo / 'logs_ui_test')
app.credentials_path = str(repo / 'tmp_ui_creds.json')
# Find and click Save
save_btn=None
for w in win.winfo_children():
    for sub in w.winfo_children():
        try:
            if getattr(sub, 'cget', None) and sub.cget('text')=='Save':
                save_btn=sub
        except Exception:
            pass
if save_btn is None:
    # search whole tree
    def find_save(w):
        for c in w.winfo_children():
            try:
                if getattr(c, 'cget', None) and c.cget('text')=='Save':
                    return c
            except Exception:
                pass
            r=find_save(c)
            if r: return r
    save_btn=find_save(win)
if not save_btn:
    print('Save button not found')
else:
    print('Invoking Save')
    save_btn.invoke()
    time.sleep(0.5)
    # Re-open settings to check values
    app.open_settings_dialog()
    tops2 = [w for w in r.winfo_children() if isinstance(w, tk.Toplevel)]
    win2 = tops2[-1]
    # Find credential entry value
    cred='unknown'
    def find_entry_with_label(parent, label_text):
        for c in parent.winfo_children():
            try:
                if getattr(c,'cget',None) and c.cget('text')==label_text:
                    # next sibling entry
                    siblings=parent.winfo_children()
                    idx=siblings.index(c)
                    # look ahead for Entry
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
    cred=find_entry_with_label(win2,'Credentials File:')
    dl=find_entry_with_label(win2,'Download Folder:')
    lg=find_entry_with_label(win2,'Log Folder:')
    print('Reopened settings values:', dl, lg, cred)
    # Clean up
    for t in [win, win2]:
        try: t.destroy()
        except: pass
    r.destroy()
