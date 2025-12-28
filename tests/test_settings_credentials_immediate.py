import unittest
import tempfile
import os
import tkinter as tk
from epstein_downloader_gui import DownloaderGUI


from tkinter import ttk

def find_widget_by_label(root, label_text, widget_type=tk.Entry):
    # Recursively search for a Label (tk.Label or ttk.Label) with given text, then return widget in same row, column=1
    def rec(parent):
        for child in parent.winfo_children():
            try:
                if isinstance(child, (tk.Label, ttk.Label)) and child.cget("text").startswith(label_text):
                    info = child.grid_info()
                    r = info.get("row")
                    # find sibling in same parent at column 1
                    for w in child.master.winfo_children():
                        try:
                            wi = w.grid_info()
                        except Exception:
                            continue
                        if wi.get("row") == r and wi.get("column") == 1:
                            return w
            except Exception:
                pass
            # Recurse
            res = rec(child)
            if res:
                return res
        return None
    return rec(root)


class TestSettingsCredentialsImmediate(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("Tk not available; skipping GUI tests")
        self.app = DownloaderGUI(self.root)

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_credentials_setting_applies_immediately_and_persists(self):
        tmp = os.path.join(os.getcwd(), "tmp_creds2.json")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("{}")
        try:
            reloaded = {"called": False}

            def fake_reload(p):
                reloaded["called"] = True

            self.app.reload_credentials = fake_reload

            # Open settings
            self.app.open_settings_dialog()
            # get Advanced Settings Toplevel
            tops = [w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)]
            self.assertTrue(tops, "Settings dialog not opened")
            win = None
            for t in tops:
                if t.title() == "Advanced Settings":
                    win = t
                    break
            self.assertIsNotNone(win, "Advanced Settings window not found")
            # find credentials entry
            entry = find_widget_by_label(win, "Credentials File:", widget_type=tk.Entry)
            self.assertIsNotNone(entry, "Credentials entry not found")
            # set to tmp
            entry.delete(0, tk.END)
            entry.insert(0, tmp)
            self.root.update_idletasks()
            # find Save button and invoke
            save_btn = None
            for w in win.winfo_children():
                for sub in w.winfo_children():
                    try:
                        if hasattr(sub, "cget") and sub.cget("text") == "Save":
                            save_btn = sub
                            break
                    except Exception:
                        pass
                if save_btn:
                    break
            # If not found, search recursively
            if save_btn is None:
                def recurse(children):
                    for w in children:
                        try:
                            if hasattr(w, "cget") and w.cget("text") == "Save":
                                return w
                        except Exception:
                            pass
                        res = recurse(w.winfo_children())
                        if res:
                            return res
                    return None
                save_btn = recurse(win.winfo_children())
            self.assertIsNotNone(save_btn, "Save button not found in settings dialog")
            save_btn.invoke()
            # after save, credentials_path should be updated immediately and reload called
            self.assertEqual(self.app.credentials_path, tmp)
            self.assertTrue(reloaded["called"])
            # config file should contain credentials_path
            with open(self.app.config_path, "r", encoding="utf-8") as f:
                cfg = f.read()
            self.assertIn("tmp_creds2.json", cfg)
            # Re-open settings and verify entry shows new path
            self.app.open_settings_dialog()
            tops2 = [w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)]
            self.assertTrue(tops2, "Settings dialog not opened second time")
            # pick the newest Toplevel (last)
            win2 = tops2[-1]
            entry2 = find_widget_by_label(win2, "Credentials File:", widget_type=tk.Entry)
            self.assertIsNotNone(entry2, "Credentials entry not found in reopened dialog")
            self.assertEqual(entry2.get(), tmp)
            # close dialog
            win2.destroy()
        finally:
            try:
                os.unlink(tmp)
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
