import unittest
import tkinter as tk
import os
import json

from epstein_downloader_gui import DownloaderGUI

class TestCredentialDrop(unittest.TestCase):
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

    def test_on_credential_drop_persists_and_loads(self):
        item = os.path.join(os.getcwd(), 'credentials.json')
        # create a dummy file so file existence isn't an issue
        with open(item, 'w', encoding='utf-8') as f:
            f.write('{}')
        try:
            called = {'reloaded': False}
            def fake_reload(p):
                called['reloaded'] = True
            # patch instance method
            self.app.reload_credentials = fake_reload

            class E:
                def __init__(self, data):
                    self.data = data
            ev = E(item)
            self.app.on_credential_drop(ev)
            self.assertEqual(self.app.credentials_path, item)
            self.assertEqual(self.app.config.get('credentials_path'), item)
            self.assertTrue(called['reloaded'])
            # Check file persisted
            with open(self.app.config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            self.assertEqual(cfg.get('credentials_path'), item)
        finally:
            try:
                os.unlink(item)
            except Exception:
                pass

if __name__ == '__main__':
    unittest.main()
