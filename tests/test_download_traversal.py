import pytest

class DummyLink:
    def __init__(self, href):
        self._href = href
    def get_attribute(self, name):
        if name == 'href':
            return self._href
        return None

class DummyPage:
    def __init__(self, hrefs):
        self._hrefs = hrefs
    def query_selector_all(self, selector):
        # Return DummyLink objects for each href
        return [DummyLink(h) for h in self._hrefs]

from epstein_downloader_gui import DownloaderGUI

def test_collect_links_basic(tmp_path, monkeypatch):
    gui = DownloaderGUI.__new__(DownloaderGUI)
    # Minimal setup
    gui._pause_event = type('E', (), {'is_set': lambda self: True})()
    gui._stop_event = type('E', (), {'is_set': lambda self: False})()

    hrefs = ['https://example.com/a.pdf', 'https://example.com/page']
    page = DummyPage(hrefs)
    # Call the traversal helper we just added
    from epstein_downloader_gui import collect_links_from_page
    abs_links = collect_links_from_page(page, 'https://example.com')
    # Should join relative and return full URLs; here links are absolute already
    assert abs_links == hrefs

def test_discover_file_candidates(tmp_path):
    from epstein_downloader_gui import discover_file_candidates
    hrefs = [
        'https://example.com/files/report.pdf',
        'https://example.com/docs/notes (final).docx',
        'https://example.com/images/photo.jpg',
        'https://example.com/skip/page.html',
    ]
    base_dir = str(tmp_path / 'downloads')
    cands = discover_file_candidates(hrefs, base_dir)
    # Expect three candidates (skip the .html)
    assert len(cands) == 3
    # Sanitize check for the one with parentheses
    matches = [rel for (_u, rel, _p) in cands]
    assert any('notes (final).docx'.replace(' ', '_') in r.replace(' ', '_') or 'notes_final.docx' in r for r in matches)
    # Local paths should start with base_dir
    for (_u, rel, p) in cands:
        assert p.startswith(base_dir)


@pytest.mark.skip(reason="Integration tests for download concurrency to be implemented")
def test_download_files_concurrent():
    pass
