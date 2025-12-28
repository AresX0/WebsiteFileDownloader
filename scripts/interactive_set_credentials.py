import os
import sys
import tempfile
import time
import pathlib
import tkinter as tk
from tkinter import messagebox

# Ensure repo root on path
repo_root = str(pathlib.Path(__file__).resolve().parents[1])
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from epstein_downloader_gui import DownloaderGUI


def find_widget_by_label(root, label_text):
    # Recursive search for a label then sibling entry in same row
    for child in root.winfo_children():
        try:
            if isinstance(child, tk.Label) and child.cget("text").startswith(label_text):
                info = child.grid_info()
                r = info.get("row")
                for w in child.master.winfo_children():
                    try:
                        wi = w.grid_info()
                    except Exception:
                        continue
                    if wi.get("row") == r and wi.get("column") == 1:
                        return w
        except Exception:
            pass
        res = find_widget_by_label(child, label_text)
        if res:
            return res
    return None


def run():
    tmp = os.path.join(os.getcwd(), "interactive_tmp_creds.json")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("{}")

    # Prevent messagebox popups from blocking automation
    orig_info = messagebox.showinfo
    orig_error = messagebox.showerror
    messagebox.showinfo = lambda *a, **k: None
    messagebox.showerror = lambda *a, **k: None

    try:
        root = tk.Tk()
        app = DownloaderGUI(root)
        # Open settings
        app.open_settings_dialog()
        # find Advanced Settings toplevel
        tops = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
        if not tops:
            print("FAIL: Settings not opened")
            return 2
        win = None
        for t in tops:
            if t.title() == "Advanced Settings":
                win = t
                break
        if not win:
            print("FAIL: Advanced Settings window not found")
            return 2
        root.update_idletasks()
        # Wait (poll) for the entry to appear - UI may not be fully rendered instantly
        entry = None
        # Use the label widget to find the sibling Entry more reliably
        def find_label_widget(parent, label_text):
            for c in parent.winfo_children():
                try:
                    if isinstance(c, (tk.Label, tk.ttk.Label)) and c.cget('text').startswith(label_text):
                        return c
                except Exception:
                    pass
                res = find_label_widget(c, label_text)
                if res:
                    return res
            return None

        lab = None
        for _ in range(20):
            lab = find_label_widget(win, 'Credentials File:')
            if lab:
                break
            root.update_idletasks()
            time.sleep(0.1)
        if not lab:
            # Fallback debug info
            from tkinter import ttk
            labels = []
            def collect_labels(parent):
                for c in parent.winfo_children():
                    try:
                        if isinstance(c, (tk.Label, ttk.Label)):
                            labels.append(c.cget('text'))
                    except Exception:
                        pass
                    collect_labels(c)
            collect_labels(win)
            print('Dialog labels present:', labels)
            print('FAIL: Credentials label not found in dialog')
            return 2
        # Now find the entry sibling in the same parent with same row, column==1
        lab_info = lab.grid_info()
        parent = lab.master
        target_row = lab_info.get('row')
        for w in parent.winfo_children():
            try:
                gi = w.grid_info()
            except Exception:
                continue
            if gi.get('row') == target_row and gi.get('column') == 1:
                entry = w
                break
        if entry is None:
            print('FAIL: Could not locate the credentials Entry sibling')
            return 2
        # Set path
        entry.delete(0, tk.END)
        entry.insert(0, tmp)
        root.update_idletasks()
        # find Save button
        save_btn = None
        def recurse(children):
            for w in children:
                try:
                    if hasattr(w, 'cget') and w.cget('text') == 'Save':
                        return w
                except Exception:
                    pass
                res = recurse(w.winfo_children())
                if res:
                    return res
            return None
        save_btn = recurse(win.winfo_children())
        if not save_btn:
            print('FAIL: Save button not found')
            return 2
        # Click save
        save_btn.invoke()
        root.update_idletasks()
        time.sleep(0.2)
        # Check immediate application
        if app.credentials_path != tmp:
            print('FAIL: credentials_path not applied immediately in app', app.credentials_path)
            return 2
        # Check config persisted
        with open(app.config_path, 'r', encoding='utf-8') as f:
            cfg = f.read()
        if 'interactive_tmp_creds.json' not in cfg:
            print('FAIL: config file did not persist credentials_path')
            return 2
        # Close the first settings window then re-open settings dialog and verify the entry shows the value
        try:
            win.destroy()
        except Exception:
            pass
        app.open_settings_dialog()
        root.update_idletasks()
        # choose newest Toplevel
        tops2 = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
        if not tops2:
            print('FAIL: Settings dialog not reopened')
            return 2
        win2 = tops2[-1]
        # wait briefly for widgets
        entry2 = None
        # Use the label-based sibling lookup (handles ttk.Label)
        for _ in range(50):
            lab2 = find_label_widget(win2, 'Credentials File:')
            if lab2 is not None:
                lab_info2 = lab2.grid_info()
                parent2 = lab2.master
                for w in parent2.winfo_children():
                    try:
                        gi = w.grid_info()
                    except Exception:
                        continue
                    if gi.get('row') == lab_info2.get('row') and gi.get('column') == 1:
                        entry2 = w
                        break
            if entry2 is not None:
                break
            root.update()
            win2.update_idletasks()
            time.sleep(0.1)
        if not entry2:
            # Debug: find label widget and print sibling info in reopened dialog
            from tkinter import ttk
            labels2 = []
            def collect_labels2(parent):
                for c in parent.winfo_children():
                    try:
                        if isinstance(c, (tk.Label, ttk.Label)):
                            labels2.append(c.cget('text'))
                    except Exception:
                        pass
                    collect_labels2(c)
            collect_labels2(win2)
            print('Reopened dialog labels present:', labels2)
            lab2 = find_label_widget(win2, 'Credentials File:')
            if lab2 is not None:
                info2 = lab2.grid_info()
                print('Found label grid info (reopen):', info2)
                parent2 = lab2.master
                print('Parent2 type:', type(parent2).__name__)
                for w in parent2.winfo_children():
                    try:
                        txt = w.cget('text') if hasattr(w,'cget') else ''
                    except Exception:
                        txt = ''
                    try:
                        gi = w.grid_info()
                    except Exception:
                        gi = {}
                    print('   sibling:', type(w).__name__, repr(txt), gi)
            else:
                print('Label widget not found on reopen')
            print('FAIL: Credentials entry not found on reopen')
            return 2
        if entry2.get() != tmp:
            print('FAIL: reopened settings do not show saved path', entry2.get())
            return 2
        print('PASS: Settings applied immediately and persisted; UI shows updated path on reopen')
        # Now simulate restart: destroy and re-instantiate
        root.destroy()
        time.sleep(0.2)
        root2 = tk.Tk()
        app2 = DownloaderGUI(root2)
        if app2.config.get('credentials_path') != tmp:
            print('FAIL: After restart config did not contain credentials_path', app2.config.get('credentials_path'))
            return 2
        print('PASS: credentials_path persisted across restart')
        root2.destroy()
        return 0
    finally:
        messagebox.showinfo = orig_info
        messagebox.showerror = orig_error
        try:
            os.unlink(tmp)
        except Exception:
            pass


if __name__ == '__main__':
    sys.exit(run())
