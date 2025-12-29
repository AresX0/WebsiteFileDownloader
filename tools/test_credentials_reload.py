import unittest
import os
import tempfile
import tkinter as tk
from unittest.mock import patch

from epstein_downloader_gui import DownloaderGUI

class FakeFiles:
    def __init__(self):
        pass
    def list(self, *args, **kwargs):
        class Exec:
            def execute(self_inner):
                return {"files": []}
        return Exec()

class FakeService:
    def files(self):
        return FakeFiles()

class TestCredentialsReload(unittest.TestCase):
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

    def test_reload_credentials_caches_object(self):
        tf = tempfile.NamedTemporaryFile(delete=False)
        tf.write(b"{}")
        tf.close()
        try:
            with patch("google.oauth2.service_account.Credentials.from_service_account_file", return_value="CREDS") as mock_from:
                self.app.reload_credentials(tf.name)
                self.assertEqual(self.app.gdrive_credentials, "CREDS")
                mock_from.assert_called_once_with(tf.name, scopes=["https://www.googleapis.com/auth/drive.readonly"]) 
        finally:
            os.unlink(tf.name)

    def test_download_drive_api_uses_cached_credentials(self):
        # create a temporary directory to act as gdrive_dir
        td = tempfile.mkdtemp()
        # ensure gdrive_credentials is set
        self.app.gdrive_credentials = "CREDS"
        with patch("googleapiclient.discovery.build", return_value=FakeService()) as mock_build:
            # Should not raise
            self.app.download_drive_folder_api("folderid", td, credentials_path=None)
            mock_build.assert_called_once() 

if __name__ == '__main__':
    unittest.main()
