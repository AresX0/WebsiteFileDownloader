import pytest
import tkinter as tk
from epstein_downloader_gui import DownloaderGUI


def test_default_urls_and_restore_defaults():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk not available in this environment; skipping GUI tests.")
    app = DownloaderGUI(root)
    expected = [
        'https://www.justice.gov/epstein/foia',
        'https://www.justice.gov/epstein/court-records',
        'https://oversight.house.gov/release/oversight-committee-releases-epstein-records-provided-by-the-department-of-justice/',
        'https://www.justice.gov/epstein/doj-disclosures',
        'https://drive.google.com/drive/folders/1TrGxDGQLDLZu1vvvZDBAh-e7wN3y6Hoz?usp=sharing',
    ]
    assert app.default_urls == expected

    # Clear current URLs and call restore_defaults()
    app.urls = []
    app.url_listbox.delete(0, tk.END)
    app.restore_defaults()
    assert app.urls == expected

    # Check listbox content matches expected
    listbox_items = [app.url_listbox.get(i) for i in range(app.url_listbox.size())]
    assert listbox_items == expected

    root.destroy()
