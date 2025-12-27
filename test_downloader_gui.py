import unittest
from epstein_downloader_gui import DownloaderGUI
import tkinter as tk
import json

class TestDownloaderGUI(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("Tk not available in this environment; skipping GUI tests.")
        self.app = DownloaderGUI(self.root)

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_url_validation(self):
        valid = [
            'https://example.com',
            'http://justice.gov/epstein',
        ]
        invalid = [
            'ftp://example.com',
            'not_a_url',
            'http:/broken.com',
            '',
        ]
        for url in valid:
            self.assertTrue(self.app.validate_url(url), f"Should be valid: {url}")
        for url in invalid:
            self.assertFalse(self.app.validate_url(url), f"Should be invalid: {url}")

    def test_config_save_and_load(self):
        self.app.base_dir.set('C:/TestDir')
        self.app.log_dir = 'C:/TestLogs'
        self.app.concurrent_downloads.set(3)
        self.app.credentials_path = 'C:/Test/credentials.json'
        self.app.save_config()
        # Now reload config
        config_path = self.app.config_path
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        self.assertEqual(config['download_dir'], 'C:/TestDir')
        self.assertEqual(config['log_dir'], 'C:/TestLogs')
        self.assertEqual(config['concurrent_downloads'], 3)
        self.assertEqual(config['credentials_path'], 'C:/Test/credentials.json')

    def test_queue_persistence(self):
        self.app.urls = ['https://a.com', 'https://b.com']
        self.app.processed_count = 1
        self.app.save_queue_state()
        # Simulate new app instance
        self.app.urls = []
        self.app.processed_count = 0
        self.app.restore_queue_state()
        self.assertEqual(self.app.urls, ['https://a.com', 'https://b.com'])
        self.assertEqual(self.app.processed_count, 1)

if __name__ == '__main__':
    unittest.main()
