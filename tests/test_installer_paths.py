import os
import tempfile
import importlib

import epstein_downloader_gui as gui


def test_install_dir_constant_exists():
    assert hasattr(gui, 'INSTALL_DIR')
    assert hasattr(gui, "INSTALL_DIR")
    assert isinstance(gui.INSTALL_DIR, str)


def test_installed_path_resolves(tmp_path, monkeypatch):
    # set env to a temp directory and ensure _installed_path builds paths under it
    tmp = str(tmp_path)
    monkeypatch.setenv('EPISTEIN_INSTALL_DIR', tmp)
    importlib.reload(gui)
    p = gui._installed_path('assets', 'start.png')
    assert p.startswith(tmp.replace('/', os.sep))
    assert p.endswith(os.path.join('assets', 'start.png'))
    monkeypatch.setenv("EPISTEIN_INSTALL_DIR", tmp)
    importlib.reload(gui)
    p = gui._installed_path("assets", "start.png")
    assert p.startswith(tmp.replace("/", os.sep))
    assert p.endswith(os.path.join("assets", "start.png"))
