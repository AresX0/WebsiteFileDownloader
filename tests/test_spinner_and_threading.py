import pytest
import threading
import time
import tkinter as tk

from epstein_downloader_gui import DownloaderGUI


def test_spinner_shows_and_hides():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk not available")
    gui = DownloaderGUI(root)
    menubar = gui.create_menu()
    # Start spinner via main thread scheduling
    root.after(0, gui.start_spinner)
    root.update()
    time.sleep(0.05)
    root.update()
    assert getattr(gui, "_spinner_running", False)
    assert gui._spinner_canvas.winfo_ismapped()
    # Stop spinner
    root.after(0, gui.stop_spinner)
    root.update()
    time.sleep(0.01)
    root.update()
    assert not getattr(gui, "_spinner_running", False)
    root.destroy()


def test_stop_button_and_resume_pause():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk not available")
    gui = DownloaderGUI(root)
    # Buttons should exist
    assert hasattr(gui, 'pause_btn')
    assert hasattr(gui, 'resume_btn')
    assert hasattr(gui, 'stop_btn')
    # Pause disables pause button, enables resume
    gui.pause_downloads()
    assert gui.pause_btn['state'] == 'disabled'
    assert gui.resume_btn['state'] == 'normal'
    # Resume restores
    gui.resume_downloads()
    assert gui.pause_btn['state'] == 'normal'
    assert gui.resume_btn['state'] == 'disabled'
    root.destroy()


def test_show_error_called_from_thread_does_not_raise_tcl_asyncdelete():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk not available")
    gui = DownloaderGUI(root)
    exception = None
    def worker():
        try:
            gui.show_error_dialog("Simulated error from background thread")
        except Exception as e:
            nonlocal exception
            exception = e
    t = threading.Thread(target=worker)
    t.start()
    t.join(timeout=2)
    root.update()
    root.destroy()
    assert exception is None, f"Background show_error_dialog raised: {exception}"
