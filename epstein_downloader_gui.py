# EpsteinFilesDownloader v1.0.0
# (C) 2025 - Refactored for clarity, maintainability, and efficiency

__version__ = "1.0.0"

import io

import os
import re
import sys
import urllib.parse
import json
import threading

try:
    from tkinterdnd2 import TkinterDnD
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    DND_AVAILABLE = True
except ImportError:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    DND_AVAILABLE = False
from datetime import datetime
import requests
import time
import importlib.util
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import logging

# Default installation directory; overridable via EPISTEIN_INSTALL_DIR env var
INSTALL_DIR = os.environ.get(
    "EPISTEIN_INSTALL_DIR",
    r"C:\Program Files\PlatypusFiles\WebsiteFileDownloader",
)

# Helper: prefer EPISTEIN_INSTALL_DIR (if set), otherwise prefer repo files during development, then the installed path
def _installed_path(*parts):
    # If the environment explicitly sets the install dir, honor it (tests & portable installs)
    env_install = os.environ.get("EPISTEIN_INSTALL_DIR")
    if env_install:
        return os.path.join(env_install, *parts)
    # Prefer repo-local files during development when they exist
    repo_root = os.path.abspath(os.path.dirname(__file__))
    repo_candidate = os.path.join(repo_root, *parts)
    if os.path.exists(repo_candidate):
        return repo_candidate
    # Fallback to the configured INSTALL_DIR
    return os.path.join(INSTALL_DIR, *parts)

# Global repo/project paths (prefer these when present or writable during development/tests)
REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
REPO_CONFIG = os.path.join(REPO_ROOT, "config.json")
REPO_QUEUE = os.path.join(REPO_ROOT, "queue_state.json")
DEFAULT_CONFIG_PATH = REPO_CONFIG if (os.path.exists(REPO_CONFIG) or os.access(REPO_ROOT, os.W_OK)) else _installed_path("config.json")
DEFAULT_QUEUE_PATH = REPO_QUEUE if (os.path.exists(REPO_QUEUE) or os.access(REPO_ROOT, os.W_OK)) else _installed_path("queue_state.json")

# Module-level reference to most recently-constructed GUI instance (used by helper functions)
CURRENT_GUI = None


# --- Dependency Checks and Playwright Setup ---
# Timeout (seconds) for external install commands. Can be overridden via EPISTEIN_INSTALL_TIMEOUT env var.
INSTALL_TIMEOUT = int(os.environ.get("EPISTEIN_INSTALL_TIMEOUT", "300"))
# Track any subprocesses started by the installer so they can be terminated on cancel
CURRENT_SUBPROCESSES = []
# Last installer thread and cancel event (test hooks)
LAST_INSTALLER_THREAD = None
LAST_INSTALLER_CANCEL_EVENT = None


def install_dependencies_with_progress(root=None):
    """Show a modal installer UI while ensuring runtime dependencies.

    This delegates to `ensure_runtime_dependencies()` for the actual install logic and
    uses `show_progress()` to provide simple UI feedback.
    """
    import tkinter as tk
    from tkinter import ttk

    # Modal progress dialog
    progress_win = None
    progress_var = None
    progress_label = None
    cancel_button = None
    cancel_event = threading.Event()

    def show_progress(msg):
        nonlocal progress_win, progress_var, progress_label, cancel_button
        if root is None or not getattr(root, "tk", None):
            # Running under a test or non-Tk root: do not create Toplevel windows
            # but still support progress callbacks by ignoring UI specifics
            return
        if progress_win is None:
            progress_win = tk.Toplevel(root)
            progress_win.title("Installing Dependencies")
            progress_win.geometry("420x140")
            progress_win.transient(root)
            progress_win.grab_set()
            progress_label = ttk.Label(progress_win, text=msg, wraplength=380)
            progress_label.pack(pady=10, padx=10)
            progress_var = tk.StringVar(value=msg)
            cancel_button = ttk.Button(
                progress_win, text="Cancel", command=lambda: cancel_event.set()
            )
            cancel_button.pack(pady=5)
        else:
            try:
                progress_label.config(text=msg)
            except Exception:
                pass
        try:
            progress_win.update_idletasks()
        except Exception:
            pass

    def close_progress():
        if progress_win:
            try:
                progress_win.destroy()
            except Exception:
                pass

    # Run the consolidated dependency installer in a background thread so the UI stays responsive
    result = {"exc": None}

    def _installer():
        try:
            if show_progress is not None:
                show_progress("Checking and installing runtime dependencies...")
            ensure_runtime_dependencies(
                root=root, skip_if_env=False, show_progress_fn=show_progress
            )
            result["exc"] = None
        except Exception as e:
            result["exc"] = e

    installer_thread = threading.Thread(target=_installer, daemon=True)
    # Assign for tests so we can join/inspect
    global LAST_INSTALLER_THREAD, LAST_INSTALLER_CANCEL_EVENT
    LAST_INSTALLER_THREAD = installer_thread
    LAST_INSTALLER_CANCEL_EVENT = cancel_event

    # Start a background watcher to react to cancel events immediately (helps tests and improves responsiveness)
    def _cancel_watcher():
        cancel_event.wait()
        try:
            kill_in_progress_subprocesses()
        except Exception:
            pass

    threading.Thread(target=_cancel_watcher, daemon=True).start()

    installer_thread.start()

    # Poll for completion without blocking the UI
    def _poll():
        # If user requested cancel, close the dialog and return (installer may still be running in background)
        if cancel_event.is_set():
            try:
                kill_in_progress_subprocesses()
            except Exception:
                pass
            close_progress()
            try:
                messagebox.showinfo(
                    "Installer",
                    "Installation canceled by user. Running installer subprocesses (if any) were requested to stop.",
                )
            except Exception:
                pass
            return
        if installer_thread.is_alive():
            # Still running; poll again shortly
            if root is not None and getattr(root, "after", None):
                try:
                    root.after(200, _poll)
                except Exception:
                    pass
            return
        # Finished
        if result.get("exc"):
            close_progress()
            try:
                messagebox.showerror(
                    "Dependency Error",
                    f"Failed to install dependencies: {result['exc']}",
                )
            except Exception:
                pass
            # Re-raise in this context so callers can handle it if needed
            raise result["exc"]
        else:
            try:
                show_progress("Dependencies installed.")
                if root is not None and getattr(root, "after", None):
                    try:
                        root.after(500, close_progress)
                    except Exception:
                        pass
            except Exception:
                close_progress()

    # Start polling
    if root is not None and getattr(root, "after", None):
        try:
            root.after(100, _poll)
        except Exception:
            pass
    else:
        # Non-GUI: wait for completion
        installer_thread.join()
        if result.get("exc"):
            raise result["exc"]


# Dependency helpers (consolidated)


def ensure_pip():
    """Ensure pip is installed (no UI)."""
    try:
        import pip  # noqa: F401
    except ImportError:
        import ensurepip

        ensurepip.bootstrap()


def _run_command(cmd, timeout=None):
    """Run external command with timeout and return stdout. Tracks Popen so callers may cancel.

    Uses subprocess.Popen + communicate to allow termination on timeout/cancel and to keep a reference
    for kill_in_progress_subprocesses(). Raises RuntimeError on failure or timeout.
    """
    timeout = timeout or INSTALL_TIMEOUT
    proc = None
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        try:
            CURRENT_SUBPROCESSES.append(proc)
            out, err = proc.communicate(timeout=timeout)
            if proc.returncode != 0:
                raise RuntimeError(
                    f"Command failed (exit {proc.returncode}): {' '.join(cmd)}\nstdout:\n{out}\nstderr:\n{err}"
                )
            return out
        finally:
            try:
                CURRENT_SUBPROCESSES.remove(proc)
            except ValueError:
                pass
    except subprocess.TimeoutExpired as te:
        if proc is not None:
            try:
                proc.kill()
                proc.communicate()
            except Exception:
                pass
        raise RuntimeError(
            f"Command timed out after {timeout}s: {' '.join(cmd)}"
        ) from te
    except subprocess.CalledProcessError as cpe:
        out = cpe.stdout or ""
        err = cpe.stderr or ""
        raise RuntimeError(
            f"Command failed (exit {cpe.returncode}): {' '.join(cmd)}\nstdout:\n{out}\nstderr:\n{err}"
        ) from cpe
    except Exception as e:
        raise RuntimeError(f"Running command failed: {' '.join(cmd)} -> {e}") from e


def check_and_install(package, pip_name=None, timeout=None):
    """Install a pip package if it's not importable. Respects EPISTEIN_SKIP_INSTALL env var in high-level helper."""
    pip_name = pip_name or package
    if importlib.util.find_spec(package) is None:
        _run_command(
            [sys.executable, "-m", "pip", "install", pip_name], timeout=timeout
        )


def ensure_playwright_browsers():
    """Ensure Playwright browser binaries are installed. May raise on failure.

    This function will prefer a bundled copy of Playwright browsers when present
    under the installed application path (`playwright_browsers`). If not found,
    it will probe common system locations (LOCALAPPDATA and user cache) and package
    locations. When running as a frozen executable, we avoid invoking
    `sys.executable -m playwright` (which points to the EXE) to prevent recursive
    self-invocation; instead we will prefer an external interpreter when available
    or surface a clear user-facing message asking the user to install browsers.
    """
    logger = logging.getLogger("EpsteinFilesDownloader")

    # If the env var is already set, respect it
    if os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        logger.debug("PLAYWRIGHT_BROWSERS_PATH already set: %s", os.environ.get("PLAYWRIGHT_BROWSERS_PATH"))
        return

    # Candidates to check (ordered by preference)
    candidates = []
    try:
        # 1) Bundled path under install dir
        candidates.append(_installed_path("playwright_browsers"))
    except Exception:
        pass

    # 2) Standard system locations
    try:
        local_app = os.environ.get("LOCALAPPDATA")
        if local_app:
            candidates.append(os.path.join(local_app, "ms-playwright"))
    except Exception:
        pass
    try:
        home_cache = os.path.join(os.path.expanduser("~"), ".cache", "ms-playwright")
        candidates.append(home_cache)
    except Exception:
        pass

    # 3) Playwright package local-browsers (site-packages)
    try:
        spec = importlib.util.find_spec("playwright")
        if spec and getattr(spec, "origin", None):
            pkg_dir = os.path.dirname(spec.origin)
            candidates.append(os.path.join(pkg_dir, "driver", "package", "local-browsers"))
    except Exception:
        pass

    # Pick the first existing candidate and export PLAYWRIGHT_BROWSERS_PATH
    found = None
    for cand in candidates:
        try:
            if cand and os.path.isdir(cand):
                found = cand
                break
        except Exception:
            continue

    if found:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = found
        logger.info("Using Playwright browsers from: %s", found)

    # Now validate by trying a quick headless launch
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            try:
                p.chromium.launch(headless=True).close()
                logger.debug("Playwright browser launch succeeded (chromium).")
                return
            except Exception as ex:
                logger.warning("Playwright quick launch failed: %s", ex)
                # If running in a frozen EXE, avoid calling sys.executable (self-invocation risk)
                if getattr(sys, "frozen", False):
                    _write_startup_debug("PLAYWRIGHT_MISSING_BROWSERS_FROZEN")
                    logger.error("Playwright browsers missing or invalid in frozen build. Prompting user to install or reinstall with bundled browsers.")
                    msg = "Playwright browsers not found. Please run: python -m playwright install or reinstall the app with bundled browsers."
                    try:
                        # Prefer the module-level show_toast (tests patch this), but also fall back to a globals lookup to be robust
                        try:
                            show_toast(msg)
                        except Exception:
                            pass
                        gs = globals().get("show_toast")
                        if callable(gs):
                            try:
                                gs(msg)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    return
                # If not frozen and EPISTEIN_SKIP_INSTALL not set, try to install via an external interpreter
                if os.environ.get("EPISTEIN_SKIP_INSTALL", "0") != "1":
                    interp = os.environ.get("PYTHON_INTERPRETER") or "python"
                    try:
                        _run_command([interp, "-m", "playwright", "install"], timeout=INSTALL_TIMEOUT)
                        # Try launch again
                        with sync_playwright() as p2:
                            p2.chromium.launch(headless=True).close()
                            logger.info("Playwright browsers installed successfully via external interpreter.")
                            return
                    except Exception as ie:
                        logger.warning("Playwright install attempt failed: %s", ie)
                        try:
                            show_toast("Failed to auto-install Playwright browsers. Run: python -m playwright install")
                        except Exception:
                            pass
                        raise RuntimeError("Playwright browser install failed: %s" % ie) from ie
                else:
                    logger.info("Skipping Playwright install due to EPISTEIN_SKIP_INSTALL=1")
                    return
    except Exception as e:
        # If importing Playwright failed entirely, surface a clear message for higher-level handling
        logger.error("Playwright runtime check failed: %s", e)
        raise RuntimeError("Playwright runtime check failed: %s" % e) from e


def kill_in_progress_subprocesses():
    """Terminate any subprocesses started by the installer.

    This attempts a graceful terminate() followed by kill() if needed.
    """
    for proc in list(CURRENT_SUBPROCESSES):
        try:
            proc.terminate()
        except Exception:
            pass
    # Wait briefly and force kill any remaining
    time.sleep(0.1)
    for proc in list(CURRENT_SUBPROCESSES):
        try:
            proc.kill()
        except Exception:
            pass
    # Clean up the list
    CURRENT_SUBPROCESSES.clear()


def ensure_runtime_dependencies(root=None, skip_if_env=True, show_progress_fn=None):
    """Resolve runtime dependencies safely.

    - Respects environment variable `EPISTEIN_SKIP_INSTALL=1` to avoid installs during CI/tests.
    - `root` and `show_progress_fn` are only used by GUI installation flow to show progress; they are optional.
    """
    if skip_if_env and os.environ.get("EPISTEIN_SKIP_INSTALL", "0") == "1":
        # Skip installing in CI/test environments
        return
    # Non-UI quick install path (skip in CI/tests when requested)
    if os.environ.get("EPISTEIN_SKIP_INSTALL", "0") != "1":
        ensure_pip()
        # Core packages
        check_and_install("playwright")
        check_and_install("requests")
        check_and_install("gdown")
        # Optional DnD package (best-effort)
        try:
            check_and_install("tkinterdnd2")
        except Exception:
            pass
        # Ensure Playwright browser binaries
        ensure_playwright_browsers()
    else:
        logging.getLogger("EpsteinFilesDownloader").info("Skipping install-time dependency checks due to EPISTEIN_SKIP_INSTALL=1")


class DownloaderGUI:
    def __init__(self, root):
        self.root = root
        self.dark_mode = False
        try:
            # Detect OS-level dark mode preference when available
            self.dark_mode = self.detect_os_dark_mode()
        except Exception:
            pass
        # Default download folder lives under the installer path (user may change this in Settings)
        self.base_dir = tk.StringVar(value=_installed_path("Downloads"))
        # Default log directory is under the installer location
        self.log_dir = os.path.join(INSTALL_DIR, "logs")
        self.credentials_path = None
        self.concurrent_downloads = tk.IntVar(value=3)
        self.urls = []
        self.default_urls = [
            "https://www.justice.gov/epstein/foia",
            "https://www.justice.gov/epstein/court-records",
            "https://oversight.house.gov/release/oversight-committee-releases-epstein-records-provided-by-the-department-of-justice/",
            "https://www.justice.gov/epstein/doj-disclosures",
            "https://drive.google.com/drive/folders/1TrGxDGQLDLZu1vvvZDBAh-e7wN3y6Hoz?usp=sharing",
        ]
        # For development and tests, prefer the repository config and queue files (deterministic behavior)
        self.config_path = REPO_CONFIG
        self.queue_state_path = REPO_QUEUE
        try:
            print(f"[DEBUG] resolved_paths: config_path={self.config_path} queue_path={self.queue_state_path} repo_config={REPO_CONFIG}")
        except Exception:
            pass
        self.status = tk.StringVar(value="Ready")
        self.speed_eta_var = tk.StringVar(value="Speed: --  ETA: --")
        self.error_log_path = os.path.join(self.log_dir, "error.log")
        self.log_file = os.path.join(self.log_dir, "epstein_downloader.log")
        import threading

        self._pause_event = threading.Event()
        self._pause_event.set()  # Start in 'running' state; clear() will pause
        self._is_paused = False
        # Event to request a full stop of all activity (downloads, scans, workers)
        self._stop_event = threading.Event()
        self._stop_event.clear()
        self._is_stopped = False
        # Image cache to keep PhotoImage refs
        self._images = {}
        self.downloaded_json = tk.StringVar(value="")
        self.logger = logging.getLogger("EpsteinFilesDownloader")
        # Ensure asset placeholders exist (create any missing or corrupt images)
        try:
            self.ensure_assets_present()
        except Exception:
            # Ensure asset generation failures do not block GUI startup
            pass
        # Now safe to load config and restore queue state
        self.config = self.load_config() if hasattr(self, "load_config") else {}
        # Option for gdown fallback (must be after self.config is loaded)
        self.use_gdown_fallback = tk.BooleanVar(
            value=self.config.get("use_gdown_fallback", False)
        )
        # Load persisted settings into UI
        try:
            dl = self.config.get("download_dir", "")
            if dl:
                self.base_dir.set(dl)
            self.concurrent_downloads.set(
                int(
                    self.config.get(
                        "concurrent_downloads", self.concurrent_downloads.get()
                    )
                )
            )
            lg = self.config.get("log_dir", "")
            if lg:
                self.log_dir = lg
            cred = self.config.get("credentials_path", "")
            self.credentials_path = cred if cred else None
            # Advanced flags
            self.auto_start = bool(self.config.get("auto_start", False))
            self.start_minimized = bool(self.config.get("start_minimized", False))
        except Exception:
            pass
        self.restore_queue_state() if hasattr(self, "restore_queue_state") else None

        os.makedirs(self.log_dir, exist_ok=True)
        self.error_log_path = os.path.join(self.log_dir, "error.log")
        self.setup_logger(self.log_dir) if hasattr(self, "setup_logger") else None
        self.logger.debug(
            f"EpsteinFilesDownloader v{__version__} started. Log file: {self.log_file}"
        )
        self.create_menu() if hasattr(self, "create_menu") else None
        self.create_widgets() if hasattr(self, "create_widgets") else None
        self.create_log_panel()
        self.setup_drag_and_drop() if hasattr(self, "setup_drag_and_drop") else None
        # Add Cancel Scan command to Tools menu if present
        try:
            menubar = self.root.nametowidget(self.root["menu"])
            tools_menu = None
            for i in range(menubar.index("end") + 1):
                label = menubar.entrycget(i, "label")
                if label == "Tools":
                    tools_menu = menubar.entrycget(i, "menu")
                    break
            if tools_menu:
                tools = self.root.nametowidget(tools_menu)
                tools.add_separator()
                tools.add_command(label="Cancel Scan", command=self.cancel_scan)
        except Exception:
            pass
        self.root.protocol("WM_DELETE_WINDOW", self.on_close) if hasattr(
            self, "on_close"
        ) else None
        # Register this GUI instance so module-level helpers can access it
        try:
            global CURRENT_GUI
            CURRENT_GUI = self
        except Exception:
            pass
        # Apply auto-start on init only if explicitly configured
        try:
            # Do not auto-start downloads while running under pytest
            if (
                bool(self.config.get("auto_start", False))
                and os.environ.get("PYTEST_CURRENT_TEST") is None
            ):
                if bool(self.config.get("start_minimized", False)):
                    try:
                        self.root.iconify()
                    except Exception:
                        pass
                # Start downloads in background
                self.start_download_all_thread()
        except Exception:
            self.logger.debug(
                "No auto-start applied (either not configured or failed)."
            )

        # No background log merger by default. All logging will go to a single
        # file managed by `setup_logger` to avoid rotated files scattered.

    def open_selected_url_in_browser(self):
        selection = self.url_listbox.curselection()
        if not selection:
            return
        url = self.url_listbox.get(selection[0])
        import webbrowser

        try:
            webbrowser.open(url)
        except Exception as e:
            self.logger.warning(f"Failed to open URL in browser: {e}")

    def copy_selected_url(self):
        selection = self.url_listbox.curselection()
        if not selection:
            return
        url = self.url_listbox.get(selection[0])
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            self.root.update()  # Keeps clipboard after window closes
        except Exception as e:
            self.logger.warning(f"Failed to copy URL to clipboard: {e}")

    def move_url_up(self):
        selection = self.url_listbox.curselection()
        if not selection or selection[0] == 0:
            return
        index = selection[0]
        # Swap in self.urls
        self.urls[index - 1], self.urls[index] = self.urls[index], self.urls[index - 1]
        # Swap in Listbox
        url_text = self.url_listbox.get(index)
        self.url_listbox.delete(index)
        self.url_listbox.insert(index - 1, url_text)
        self.url_listbox.selection_clear(0, tk.END)
        self.url_listbox.selection_set(index - 1)
        self.url_listbox.activate(index - 1)

    def move_url_down(self):
        selection = self.url_listbox.curselection()
        if not selection or selection[0] == self.url_listbox.size() - 1:
            return
        index = selection[0]
        # Swap in self.urls
        self.urls[index + 1], self.urls[index] = self.urls[index], self.urls[index + 1]
        # Swap in Listbox
        url_text = self.url_listbox.get(index)
        self.url_listbox.delete(index)
        self.url_listbox.insert(index + 1, url_text)
        self.url_listbox.selection_clear(0, tk.END)
        self.url_listbox.selection_set(index + 1)
        self.url_listbox.activate(index + 1)

    def check_for_updates(self):
        # Non-blocking update check (example: check GitHub releases or a version file)
        import threading

        def do_check():
            try:
                import requests

                url = "https://raw.githubusercontent.com/JosephThePlatypus/EpsteinFilesDownloader/main/VERSION.txt"
                r = requests.get(url, timeout=10)
                if r.status_code == 200:
                    latest = r.text.strip()
                    if latest != __version__:
                        self.root.after(
                            0,
                            lambda: messagebox.showinfo(
                                "Update Available",
                                f"A new version is available: {latest}\nYou are running: {__version__}",
                            ),
                        )
                    else:
                        self.root.after(
                            0,
                            lambda: messagebox.showinfo(
                                "Up to Date",
                                f"You are running the latest version: {__version__}",
                            ),
                        )
                else:
                    # Provide a clearer message including HTTP status for troubleshooting
                    try:
                        snippet = r.text.strip()[:200]
                    except Exception:
                        snippet = ""
                    self.root.after(
                        0,
                        lambda: messagebox.showwarning(
                            "Update Check Failed",
                            f"Could not check for updates (HTTP {r.status_code}).\nURL: {url}\n{snippet}",
                        ),
                    )
            except Exception as e:
                # Surface exception details to help debugging network/SSL issues
                err_text = str(e)
                self.root.after(
                    0,
                    lambda: messagebox.showwarning(
                        "Update Check Error", f"Error checking for updates: {err_text}"
                    ),
                )

        threading.Thread(target=do_check, daemon=True).start()

    def show_progress(self):
        # Placeholder: show a messagebox or popup. You can expand this to show a real progress dialog.
        messagebox.showinfo(
            "Download Progress",
            "Download progress is shown in the main window's progress bars.",
        )

    def create_log_panel(self):
        import tkinter.scrolledtext as st

        if not hasattr(self, "log_panel"):
            self.log_panel = st.ScrolledText(
                self.root, height=8, state="disabled", font=("Consolas", 10)
            )
            # Use grid instead of pack to avoid geometry manager conflict
            self.log_panel.grid(
                row=99, column=0, columnspan=4, sticky="ew", padx=4, pady=2
            )
            self.log_panel_visible = True
        else:
            if not self.log_panel.winfo_ismapped():
                self.log_panel.grid(
                    row=99, column=0, columnspan=4, sticky="ew", padx=4, pady=2
                )
                self.log_panel_visible = True
        # Ensure action buttons share consistent widths and are large enough to contain their text
        try:
            labels = [
                self.download_btn["text"],
                self.pause_btn["text"],
                self.resume_btn["text"],
                self.schedule_btn["text"],
                self.json_btn["text"],
                self.skipped_btn["text"],
                self.stop_scan_btn["text"],
                getattr(self, "enable_scan_btn", tk.Button())["text"]
                if hasattr(self, "enable_scan_btn")
                else "Enable Scans",
            ]
            max_len = max(len(lbl) for lbl in labels)
            # Add padding so icons and text fit comfortably
            width = max(20, max_len + 6)
            for btn in (
                self.download_btn,
                self.pause_btn,
                self.resume_btn,
                self.schedule_btn,
                self.json_btn,
                self.skipped_btn,
                getattr(self, "stop_scan_btn", None),
                getattr(self, "enable_scan_btn", None),
            ):
                if btn is None:
                    continue
                try:
                    btn.config(width=width)
                except Exception:
                    pass
        except Exception:
            pass

    def toggle_log_panel(self):
        if hasattr(self, "log_panel"):
            if self.log_panel.winfo_ismapped():
                self.log_panel.grid_remove()
                self.log_panel_visible = False
            else:
                self.log_panel.grid(
                    row=99, column=0, columnspan=4, sticky="ew", padx=4, pady=2
                )
                self.log_panel_visible = True
        else:
            self.create_log_panel()

    def append_log_panel(self, msg):
        if hasattr(self, "log_panel"):
            self.log_panel.configure(state="normal")
            self.log_panel.insert("end", msg + "\n")
            self.log_panel.see("end")
            self.log_panel.configure(state="disabled")

    def log_button_event(self, name, event=None):
        """Log a button click event with widget state and a stack trace for debugging."""
        try:
            import traceback

            widget = getattr(event, "widget", None)
            try:
                widget_info = f"{widget}" if widget is not None else "None"
            except Exception:
                widget_info = "unavailable"
            try:
                state = widget.cget("state") if widget is not None else "NA"
            except Exception:
                state = "NA"
            try:
                stack = "".join(traceback.format_stack())
            except Exception:
                stack = "<stack-unavailable>"
            # Always append an audit record to a separate append-only file so clicks
            # are preserved even if the main logger is reconfigured later.
            try:
                audit_dir = getattr(self, "log_dir", os.path.join(os.getcwd(), "logs"))
                os.makedirs(audit_dir, exist_ok=True)
                audit_path = os.path.join(audit_dir, "button_audit.log")
                from datetime import datetime

                with open(audit_path, "a", encoding="utf-8") as af:
                    af.write(
                        f"{datetime.now().isoformat()} - {name} | widget={widget_info} | state={state}\n"
                    )
                    af.write(stack + "\n")
            except Exception:
                # Best-effort only; don't raise from logging
                pass
            try:
                self.logger.info(
                    f"Button clicked: {name} | widget={widget_info} | state={state}"
                )
                self.logger.debug(f"Call stack for button '{name}':\n{stack}")
            except Exception:
                print(f"Button clicked: {name} | widget={widget_info} | state={state}")
                print(stack)
        except Exception as e:
            try:
                self.logger.exception(f"Failed to log button event for {name}: {e}")
            except Exception:
                pass

    def setup_url_listbox_context_menu(self):
        # Context menu for URL listbox
        self.url_menu = tk.Menu(self.url_listbox, tearoff=0)
        self.url_menu.add_command(label="Remove URL", command=self.remove_url)
        self.url_menu.add_command(label="Move Up", command=self.move_url_up)
        self.url_menu.add_command(label="Move Down", command=self.move_url_down)
        self.url_menu.add_separator()
        self.url_menu.add_command(label="Copy URL", command=self.copy_selected_url)
        self.url_menu.add_command(
            label="Open in Browser", command=self.open_selected_url_in_browser
        )
        self.url_listbox.bind("<Button-3>", self.show_url_context_menu)

    def show_url_context_menu(self, event):
        try:
            # Select the item under the mouse
            index = self.url_listbox.nearest(event.y)
            self.url_listbox.selection_clear(0, tk.END)
            self.url_listbox.selection_set(index)
            self.url_listbox.activate(index)
            self.url_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.url_menu.grab_release()
        fh = logging.FileHandler(self.log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        sh = logging.StreamHandler()
        sh.setLevel(logging.INFO)
        sh.setFormatter(formatter)
        self.logger.addHandler(sh)
        # Now safe to load config and restore queue state
        self.config = self.load_config()
        self.restore_queue_state()
        # Override defaults if config exists
        if self.config.get("download_dir"):
            # restore previously saved download folder
            try:
                self.base_dir.set(self.config["download_dir"])
            except Exception:
                pass
        if self.config.get("concurrent_downloads"):
            try:
                self.concurrent_downloads.set(int(self.config["concurrent_downloads"]))
            except Exception:
                pass
        if self.config.get("log_dir"):
            self.log_dir = self.config["log_dir"]
        if self.config.get("credentials_path"):
            self.credentials_path = self.config["credentials_path"]
        else:
            self.credentials_path = None
        os.makedirs(self.log_dir, exist_ok=True)
        self.error_log_path = os.path.join(self.log_dir, "error.log")
        self.setup_logger(self.log_dir)
        self.logger.debug(
            f"EpsteinFilesDownloader v{__version__} started. Log file: {self.log_file}"
        )
        self.create_menu()
        self.create_widgets()
        # --- Drag and Drop Setup ---
        self.setup_drag_and_drop()
        # Hook for saving queue state on close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def save_queue_state(self):
        try:
            state = {
                "urls": self.urls,
                "processed_count": getattr(self, "processed_count", 0),
            }
            try:
                with open(self.queue_state_path, "w", encoding="utf-8") as f:
                    json.dump(state, f, indent=2)
                self.logger.info("Queue state saved.")
            except PermissionError as pe:
                # Attempt fallbacks: repo-local then user local appdata
                repo_root = os.path.abspath(os.path.dirname(__file__))
                repo_queue = os.path.join(repo_root, "queue_state.json")
                user_dir = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
                alt_dir = os.path.join(user_dir, "EpsteinFilesDownloader")
                os.makedirs(alt_dir, exist_ok=True)
                alt_path = os.path.join(alt_dir, "queue_state.json")
                saved = False
                for p in [repo_queue, alt_path]:
                    try:
                        with open(p, "w", encoding="utf-8") as f:
                            json.dump(state, f, indent=2)
                        self.queue_state_path = p
                        self.logger.info(f"Queue state saved to fallback {p}")
                        saved = True
                        break
                    except Exception:
                        continue
                if not saved:
                    self.logger.error(
                        f"Failed to save queue state after fallbacks: {pe}",
                        exc_info=True,
                    )
            except Exception as e:
                self.logger.error(f"Failed to save queue state: {e}")
        except Exception as e:
            self.logger.error(f"Failed to save queue state: {e}")

    def restore_queue_state(self):
        try:

            def is_placeholder_url(url):
                # Treat as placeholder if it's a.com, b.com, or empty
                return url.strip() in {
                    "https://a.com",
                    "https://b.com",
                    "",
                    "http://a.com",
                    "http://b.com",
                }

            if os.path.exists(self.queue_state_path):
                with open(self.queue_state_path, "r", encoding="utf-8") as f:
                    state = json.load(f)
                loaded_urls = state.get("urls", [])
                # Use saved URLs if present, otherwise fall back to defaults
                if loaded_urls:
                    self.urls = loaded_urls
                else:
                    self.urls = list(self.default_urls)
                # Restore processed_count if present
                self.processed_count = int(state.get("processed_count", 0))
                self.logger.info("Queue state restored.")
            else:
                self.urls = list(self.default_urls)
                self.processed_count = 0
                self.logger.info("Queue state restored (defaults used).")
        except Exception as e:
            self.logger.error(f"Failed to restore queue state: {e}")

    def on_close(self):
        """Graceful shutdown hook for the application window."""
        try:
            # Persist state and attempt a graceful shutdown of background work
            self.save_queue_state()
        except Exception:
            pass
        try:
            self.shutdown(timeout=5)
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def shutdown(self, timeout=5):
        """Signal background threads to stop and wait for known threads to exit.

        This method attempts a conservative, backward-compatible shutdown:
        - sets stop/cancel flags so running workers exit quickly
        - resumes paused threads so they can observe stop requests
        - stops spinner and other scheduled UI callbacks
        - joins known long-running threads with a timeout
        """
        import time

        # Signal stop and cancellation
        try:
            if getattr(self, "_stop_event", None):
                self._stop_event.set()
        except Exception:
            pass
        try:
            self._cancel_scan = True
        except Exception:
            pass
        try:
            # Unpause anything paused so threads can proceed to cooperative exit
            if getattr(self, "_pause_event", None):
                self._pause_event.set()
            self._is_paused = False
        except Exception:
            pass
        # Stop spinner (cancels scheduled after jobs)
        try:
            self.stop_spinner()
        except Exception:
            pass
        # Attempt to join tracked threads
        joinables = []
        try:
            if getattr(self, "_download_all_thread", None):
                joinables.append(self._download_all_thread)
        except Exception:
            pass
        try:
            if getattr(self, "_process_thread", None):
                joinables.append(self._process_thread)
        except Exception:
            pass
        # Join with timeout
        start = time.time()
        for t in joinables:
            try:
                remaining = max(0.0, timeout - (time.time() - start))
                if remaining <= 0:
                    break
                t.join(remaining)
            except Exception:
                pass
        # Give a short grace period for thread pools / workers
        try:
            time.sleep(0.1)
        except Exception:
            pass

    def log_error(
        self, err: Exception, context: str = ""
    ):  # Utility for error logging and dialog
        import traceback

        msg = f"[{datetime.now().isoformat()}] {context}\n{type(err).__name__}: {err}\n{traceback.format_exc()}\n"
        try:
            with open(self.error_log_path, "a", encoding="utf-8") as f:
                f.write(msg)
        except Exception:
            pass
        self.show_error_dialog(str(err), context)

    def show_error_dialog(self, error_msg, context=""):
        try:
            messagebox.showerror(
                "Error", f"{context}\n{error_msg}" if context else error_msg
            )
        except Exception:
            print(f"Error: {context} {error_msg}")

    def setup_drag_and_drop(self):
        # Try to import tkinterDnD2 for drag-and-drop support
        try:
            from tkinterdnd2 import DND_FILES
        except ImportError:
            self.logger.warning(
                "tkinterDnD2 not installed. Drag-and-drop will not be available."
            )
            return
        # Only set up DnD for the URL listbox if it exists
        if hasattr(self, "url_listbox"):
            try:
                self.url_listbox.drop_target_register(DND_FILES)
                self.url_listbox.dnd_bind("<<Drop>>", self.on_url_drop)
                self.url_listbox.dnd_bind(
                    "<<DragEnter>>", lambda e: self.url_listbox.config(bg="#cce6ff")
                )
                self.url_listbox.dnd_bind(
                    "<<DragLeave>>", lambda e: self.url_listbox.config(bg="white")
                )
            except Exception as e:
                self.logger.warning(f"Failed to enable DnD on URL listbox: {e}")

        # Always ensure menu bar is present after any DnD setup
        self.create_menu()

        # Enable DnD for URL listbox (for URLs)
        try:
            self.url_listbox.drop_target_register(DND_FILES)
            self.url_listbox.dnd_bind("<<Drop>>", self.on_url_drop)
        except Exception as e:
            self.logger.warning(f"Failed to enable DnD on URL listbox: {e}")

        # Enable DnD for main window (for credentials.json)
        try:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind("<<Drop>>", self.on_credential_drop)
        except Exception as e:
            self.logger.warning(f"Failed to enable DnD on main window: {e}")

    def on_url_drop(self, event):
        # Accept dropped URLs (file paths or text)
        dropped = event.data
        if dropped:
            # Split by whitespace (could be multiple files/URLs)
            items = self.root.tk.splitlist(dropped)
            for item in items:
                if item.lower().startswith(("http://", "https://")):
                    if item not in self.urls:
                        self.urls.append(item)
                        self.url_listbox.insert(tk.END, item)
                        self.logger.info(f"Added URL via drag-and-drop: {item}")
                elif item.lower().endswith(".url"):
                    # Try to read .url file for actual URL
                    try:
                        with open(item, "r", encoding="utf-8") as f:
                            for line in f:
                                if line.strip().startswith("URL="):
                                    url = line.strip().split("=", 1)[-1]
                                    if url and url not in self.urls:
                                        self.urls.append(url)
                                        self.url_listbox.insert(tk.END, url)
                                        self.logger.info(
                                            f"Added URL from .url file: {url}"
                                        )
                    except Exception as e:
                        self.logger.warning(f"Failed to read .url file: {item}: {e}")

    def on_credential_drop(self, event):
        # Accept dropped credentials.json file
        dropped = event.data
        if dropped:
            items = self.root.tk.splitlist(dropped)
            for item in items:
                if item.lower().endswith("credentials.json"):
                    # Copy or set config to use this credentials file
                    self.config["credentials_path"] = item
                    self.save_config()
                    self.logger.info(f"Set credentials.json via drag-and-drop: {item}")
                    messagebox.showinfo(
                        "Credentials Set", f"credentials.json set to: {item}"
                    )
                else:
                    self.logger.info(
                        f"Dropped file ignored (not credentials.json): {item}"
                    )

    def load_config(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_config(self):
        """Persist current configuration to disk."""
        # Always write explicit keys so they persist (even empty strings allow UI to show state)
        self.config["download_dir"] = self.base_dir.get()
        self.config["log_dir"] = getattr(
            self, "log_dir", os.path.join(os.path.dirname(__file__), "logs")
        )
        self.config["concurrent_downloads"] = int(self.concurrent_downloads.get())
        # credentials_path: store empty string if not provided to make persistence predictable
        self.config["credentials_path"] = (
            self.credentials_path if getattr(self, "credentials_path", None) else ""
        )
        # Advanced flags
        self.config["auto_start"] = bool(
            getattr(self, "auto_start_var", tk.BooleanVar(value=False)).get()
        )
        self.config["start_minimized"] = bool(
            getattr(self, "start_minimized_var", tk.BooleanVar(value=False)).get()
        )
        # gdown fallback flag
        if hasattr(self, "use_gdown_fallback"):
            self.config["use_gdown_fallback"] = bool(self.use_gdown_fallback.get())

        # Attempt to write primary config path
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
            self.logger.info(f"Configuration saved to {self.config_path}")
        except PermissionError as pe:
            # Try repo-local config path first, then per-user local app data
            repo_root = os.path.abspath(os.path.dirname(__file__))
            repo_config = os.path.join(repo_root, "config.json")
            user_dir = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
            alt_dir = os.path.join(user_dir, "EpsteinFilesDownloader")
            os.makedirs(alt_dir, exist_ok=True)
            alt_path = os.path.join(alt_dir, "config.json")
            saved = False
            for p in [repo_config, alt_path]:
                try:
                    with open(p, "w", encoding="utf-8") as f:
                        json.dump(self.config, f, indent=2)
                    self.config_path = p
                    self.logger.info(f"Configuration saved to fallback {p}")
                    saved = True
                    break
                except Exception:
                    continue
            if not saved:
                self.logger.error(
                    f"Failed to save configuration after fallbacks: {pe}",
                    exc_info=True,
                )
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}", exc_info=True)

        # Apply new log_dir immediately so the running app uses it
        try:
            if os.path.isdir(getattr(self, "log_dir", "")):
                self.setup_logger(self.log_dir)
        except Exception:
            pass

    def reload_credentials(self, path=None, validate=False):
        """
        Attempt to load Google service account credentials from `path` and cache them
        on the GUI instance as `self.gdrive_credentials`. If `validate` is True, attempt
        a refresh in a short-lived background thread to verify the credentials can obtain
        an access token (optional, non-blocking by default).
        """
        p = path if path is not None else getattr(self, "credentials_path", None)
        if not p:
            # clear cached credentials
            self.gdrive_credentials = None
            self.logger.debug("Cleared cached Google Drive credentials (no path provided).")
            return
        if not os.path.exists(p):
            self.logger.warning(f"Credentials file not found: {p}")
            self.gdrive_credentials = None
            return
        try:
            from google.oauth2 import service_account

            SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
            creds = service_account.Credentials.from_service_account_file(p, scopes=SCOPES)
            self.gdrive_credentials = creds
            self.logger.info(f"Loaded Google Drive credentials from {p}")
        except Exception as e:
            self.logger.exception(f"Failed to load credentials from {p}: {e}")
            self.gdrive_credentials = None
            raise
        # Optionally validate by trying to refresh the token in background
        if validate:
            def _refresh():
                try:
                    from google.auth.transport.requests import Request

                    req = Request()
                    creds.refresh(req)
                    self.logger.info("Credentials refresh validated successfully.")
                except Exception as ex:
                    self.logger.warning(f"Credentials refresh/validation failed: {ex}")

            try:
                import threading

                t = threading.Thread(target=_refresh, daemon=True)
                t.start()
            except Exception:
                # If threading isn't available, perform sync attempt (best effort)
                try:
                    from google.auth.transport.requests import Request

                    creds.refresh(Request())
                    self.logger.info("Credentials refresh validated successfully (sync).")
                except Exception as ex:
                    self.logger.warning(f"Credentials refresh/validation failed (sync): {ex}")

    def restore_defaults(self):
        self.base_dir.set(r"C:\Temp\Epstein")
        self.log_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(self.log_dir, exist_ok=True)
        # Reset URLs to application defaults and refresh the UI listbox
        self.urls = list(self.default_urls)
        try:
            self.url_listbox.delete(0, tk.END)
            for url in self.urls:
                self.url_listbox.insert(tk.END, url)
        except Exception:
            # If the listbox isn't available (early call), ignore UI refresh
            pass
        # Persist queue state so defaults are saved immediately
        try:
            self.save_queue_state()
        except Exception:
            pass
        # Clear cached credentials when restoring defaults
        try:
            if hasattr(self, "gdrive_credentials"):
                self.gdrive_credentials = None
        except Exception:
            pass
        self.save_config()
        self.setup_logger(self.log_dir)
        # Avoid showing modal dialogs during pytest runs (prevents test hangs/failures)
        if not os.environ.get("PYTEST_CURRENT_TEST"):
            messagebox.showinfo(
                "Defaults Restored", "Settings have been restored to defaults."
            )

    def create_menu(self):
        menubar = tk.Menu(self.root)
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(
            label="Set Download Folder...", command=self.pick_download_folder
        )
        file_menu.add_command(label="Set Log Folder...", command=self.pick_log_folder)
        file_menu.add_command(
            label="Set Credentials File...", command=self.pick_credentials_file
        )
        file_menu.add_separator()
        file_menu.add_command(
            label="Save Settings as Default", command=self.save_config
        )
        file_menu.add_command(label="Restore Defaults", command=self.restore_defaults)
        file_menu.add_separator()
        file_menu.add_command(label="Export Settings...", command=self.export_settings)
        file_menu.add_command(label="Import Settings...", command=self.import_settings)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        # Settings menu (moved out of File)
        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(
            label="Advanced Settings...", command=self.open_settings_dialog
        )
        settings_menu.add_separator()
        settings_menu.add_command(
            label="Import Settings...", command=self.import_settings
        )
        settings_menu.add_command(
            label="Export Settings...", command=self.export_settings
        )
        settings_menu.add_separator()
        settings_menu.add_command(
            label="Save Settings as Default", command=self.save_config
        )
        settings_menu.add_command(
            label="Restore Defaults", command=self.restore_defaults
        )
        menubar.add_cascade(label="Settings", menu=settings_menu)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(
            label="Toggle Dark/Light Mode", command=self.toggle_dark_mode
        )
        view_menu.add_command(
            label="Show/Hide Log Panel", command=self.toggle_log_panel
        )
        view_menu.add_command(
            label="Show Download Progress", command=self.show_progress
        )
        menubar.add_cascade(label="View", menu=view_menu)

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(
            label="Check for Updates", command=self.check_for_updates
        )
        tools_menu.add_command(
            label="Validate Credentials", command=self.validate_credentials
        )
        tools_menu.add_command(
            label="Test Download Link", command=self.test_download_link
        )
        tools_menu.add_separator()
        tools_menu.add_command(
            label="Force Full Hash Rescan", command=self.force_full_hash_rescan
        )
        menubar.add_cascade(label="Tools", menu=tools_menu)

        # Help menu

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Help", command=self.show_help_dialog)
        help_menu.add_command(label="About", command=self.show_about_dialog)
        help_menu.add_command(
            label="Report Issue / Send Feedback", command=self.report_issue
        )
        menubar.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menubar)

    def show_help_dialog(self):
        help_text = (
            "Epstein Court Records Downloader Help\n\n"
            "1. Add URLs to the download list.\n"
            "2. Set your download folder and other settings in the Settings dialog.\n"
            "3. Click 'Start Download' to begin.\n"
            "4. Use Pause/Resume to control downloads.\n"
            "5. View download history in the 'Download History' tab.\n\n"
            "Advanced:\n"
            "- Use the Settings dialog to set a proxy or limit download speed.\n"
            "- Drag and drop URLs or credentials.json into the app.\n"
            "- Use the Tools menu for hash rescans and credential validation.\n\n"
            "Troubleshooting:\n"
            "- Check the log/history tab for errors.\n"
            "- Ensure Playwright and browsers are installed.\n"
            "- For Google Drive, provide a valid credentials.json if needed.\n"
            "- For proxy issues, verify your proxy string format.\n"
        )
        self.show_popup("Help", help_text)

    def show_about_dialog(self):
        about_text = (
            f"Epstein Court Records Downloader\nVersion: {__version__}\n\n"
            "Developed by JosephThePlatypus and contributors.\n"
            "\nThis tool automates the downloading of public court records, "
            "with advanced queue management, error handling, and history.\n\n"
            "For more info, visit the project page or contact the author.\n"
        )
        self.show_popup("About", about_text)

    def export_settings(self):
        """Export current settings to a user-chosen JSON file."""
        file_path = filedialog.asksaveasfilename(
            title="Export Settings As",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="epstein_downloader_settings.json",
        )
        if file_path:
            try:
                self.save_config()  # Ensure config is up to date
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(self.config, f, indent=2)
                messagebox.showinfo(
                    "Export Settings", f"Settings exported to: {file_path}"
                )
            except Exception as e:
                self.log_error(e, "Export Settings")

    # --- Asset / UI Helpers ---
    def create_placeholder_asset(self, path: str, name: str):
        """Create a small, polished placeholder PNG for `name` using Pillow drawing primitives.
        Draws a colored rounded background and a simple vector symbol (triangle, bars, arrow, etc.)."""
        try:
            from PIL import Image, ImageDraw

            # standard icon size (square)
            size_px = 24
            size = (size_px, size_px)
            im = Image.new("RGBA", size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(im)
            # Symbol mapping (symbol color will vary; background is consistent)
            symbol_map = {
                "start": {"color": (255, 255, 255, 255), "type": "triangle"},
                "pause": {"color": (255, 255, 255, 255), "type": "bars"},
                "resume": {"color": (255, 255, 255, 255), "type": "triangle"},
                "schedule": {"color": (255, 255, 255, 255), "type": "clock"},
                "json": {"color": (255, 255, 255, 255), "type": "braces"},
                "skipped": {"color": (255, 255, 255, 255), "type": "x"},
                "stop": {"color": (255, 255, 255, 255), "type": "square"},
                "download": {"color": (255, 255, 255, 255), "type": "downarrow"},
            }
            cfg = symbol_map.get(
                name, {"color": (255, 255, 255, 255), "type": "letter"}
            )
            symbol_color = cfg["color"]
            # Consistent neutral background for all icons
            bg = (240, 240, 240, 255)
            # Draw rounded rectangle background (smaller corner radius)
            r = max(3, size_px // 8)
            draw.rounded_rectangle((0, 0, size[0], size[1]), radius=r, fill=bg)
            symbol_type = cfg["type"]
            # Draw symbol centered
            cx, cy = size[0] // 2, size[1] // 2
            if symbol_type == "triangle":
                # Play triangle pointing right
                pts = [(cx - 5, cy - 6), (cx - 5, cy + 6), (cx + 7, cy)]
                draw.polygon(pts, fill=symbol_color)
            elif symbol_type == "bars":
                # Two vertical bars
                w = 3
                h = 12
                draw.rectangle(
                    (cx - 6 - w // 2, cy - h // 2, cx - 6 + w // 2, cy + h // 2),
                    fill=symbol_color,
                )
                draw.rectangle(
                    (cx + 6 - w // 2, cy - h // 2, cx + 6 + w // 2, cy + h // 2),
                    fill=symbol_color,
                )
            elif symbol_type == "clock":
                draw.ellipse(
                    (cx - 6, cy - 6, cx + 6, cy + 6), outline=symbol_color, width=2
                )
                draw.line((cx, cy, cx, cy - 4), fill=symbol_color, width=2)
                draw.line((cx, cy, cx + 3, cy), fill=symbol_color, width=2)
            elif symbol_type == "braces":
                # Draw curly braces as simple lines
                draw.line((cx - 8, cy - 8, cx - 5, cy - 5), fill=symbol_color, width=2)
                draw.line((cx - 5, cy - 5, cx - 8, cy - 2), fill=symbol_color, width=2)
                draw.line((cx + 8, cy - 8, cx + 5, cy - 5), fill=symbol_color, width=2)
                draw.line((cx + 5, cy - 5, cx + 8, cy - 2), fill=symbol_color, width=2)
                draw.line((cx - 8, cy + 8, cx - 5, cy + 5), fill=symbol_color, width=2)
                draw.line((cx - 5, cy + 5, cx - 8, cy + 2), fill=symbol_color, width=2)
                draw.line((cx + 8, cy + 8, cx + 5, cy + 5), fill=symbol_color, width=2)
                draw.line((cx + 5, cy + 5, cx + 8, cy + 2), fill=symbol_color, width=2)
            elif symbol_type == "x":
                draw.line((cx - 6, cy - 6, cx + 6, cy + 6), fill=symbol_color, width=3)
                draw.line((cx - 6, cy + 6, cx + 6, cy - 6), fill=symbol_color, width=3)
            elif symbol_type == "downarrow":
                draw.polygon(
                    [
                        (cx, cy + 7),
                        (cx - 6, cy),
                        (cx - 2, cy),
                        (cx - 2, cy - 6),
                        (cx + 2, cy - 6),
                        (cx + 2, cy),
                        (cx + 6, cy),
                    ],
                    fill=symbol_color,
                )
            elif symbol_type == "square":
                # Draw a centered square to represent 'stop'
                s = 10
                draw.rectangle(
                    (cx - s // 2, cy - s // 2, cx + s // 2, cy + s // 2),
                    fill=symbol_color,
                )
            else:
                # Letter fallback
                from PIL import ImageFont

                try:
                    font = ImageFont.truetype("arial.ttf", 14)
                except Exception:
                    font = ImageFont.load_default()
                letter = name[0].upper()
                w, h = draw.textsize(letter, font=font)
                draw.text(
                    (cx - w // 2, cy - h // 2), letter, fill=symbol_color, font=font
                )
            im.save(path, format="PNG")
            try:
                self.logger.info(f"Created placeholder asset: {path}")
            except Exception:
                pass
            return True
        except Exception as e:
            try:
                # If PIL is not available or creation failed, fall back to writing a tiny transparent PNG
                tiny_png = (
                    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
                    b"\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc\x33\x00\x00\x00\x00IEND\xaeB`\x82"
                )
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as fh:
                    fh.write(tiny_png)
                self.logger.info(f"Wrote fallback placeholder asset: {path}")
            except Exception:
                try:
                    self.logger.warning(f"Failed to create placeholder asset {path}: {e}")
                except Exception:
                    pass
                return False
            return True

    def ensure_assets_present(self):
        """Create or repair any expected assets (small placeholder icons) in the script's assets/ folder."""
        expected = [
            "start",
            "pause",
            "resume",
            "schedule",
            "json",
            "skipped",
            "download",
            "stop",
        ]
        # Prefer assets from the installer directory if present, fallback to package assets
        assets_dir = _installed_path("assets") if os.path.isdir(_installed_path("assets")) else os.path.join(os.path.dirname(__file__), "assets")
        os.makedirs(assets_dir, exist_ok=True)
        for name in expected:
            p = os.path.join(assets_dir, name + ".png")
            need_create = False
            if not os.path.exists(p):
                need_create = True
            else:
                try:
                    # Empty files should be replaced
                    if os.path.getsize(p) == 0:
                        need_create = True
                    else:
                        from PIL import Image

                        try:
                            im = Image.open(p)
                            im.verify()
                        except Exception:
                            need_create = True
                except Exception:
                    need_create = True
            if need_create:
                # Try to create placeholder
                created = self.create_placeholder_asset(p, name)
                if not created:
                    # Fallback: write minimal PNG to ensure non-empty file for tests and GUI
                    tiny_png = (
                        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
                        b"\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc\x33\x00\x00\x00\x00IEND\xaeB`\x82"
                    )
                    try:
                        with open(p, "wb") as fh:
                            fh.write(tiny_png)
                    except Exception:
                        try:
                            self.logger.warning(f"Failed to write fallback asset {p}")
                        except Exception:
                            pass
        # Normalize sizes after ensuring presence
        try:
            self.ensure_asset_sizes(target_px=24)
        except Exception:
            pass

    def show_toast(self, message, duration=1500):
        """Show a transient non-blocking 'toast' message near the bottom-right of the main window."""
        try:
            toast = tk.Toplevel(self.root)
            toast.overrideredirect(True)
            toast.attributes("-topmost", True)
            # Use simple label - ttk widgets may be styled; use tk.Label for basic bg control
            lbl = tk.Label(
                toast, text=message, bg="#333333", fg="#ffffff", padx=10, pady=6
            )
            lbl.pack()
            self.root.update_idletasks()
            # Position toast at bottom-right with a margin
            x = self.root.winfo_rootx() + max(
                12, self.root.winfo_width() - toast.winfo_reqwidth() - 12
            )
            y = self.root.winfo_rooty() + max(
                12, self.root.winfo_height() - toast.winfo_reqheight() - 40
            )
            toast.geometry(f"+{x}+{y}")
            toast.after(
                duration, lambda: (toast.destroy() if toast.winfo_exists() else None)
            )
        except Exception as e:
            try:
                self.logger.debug(f"Failed to show toast: {e}")
            except Exception:
                pass


# Module-level helper so code outside a GUI instance can show transient messages.
def show_toast(message, duration=1500):
    try:
        if CURRENT_GUI is not None:
            try:
                CURRENT_GUI.show_toast(message, duration=duration)
                return
            except Exception:
                pass
        # No GUI available: fallback to logging
        logging.getLogger("EpsteinFilesDownloader").info("TOAST: %s", message)
    except Exception:
        pass

    def ensure_asset_sizes(self, target_px=24):
        """Resize existing assets to target_px x target_px preserving aspect ratio and padding to square."""
        try:
            from PIL import Image

            assets_dir = os.path.join(os.path.dirname(__file__), "assets")
            for fname in os.listdir(assets_dir):
                if not fname.lower().endswith(".png"):
                    continue
                path = os.path.join(assets_dir, fname)
                try:
                    im = Image.open(path).convert("RGBA")
                    if im.size != (target_px, target_px):
                        # Resize and pad to square
                        im.thumbnail((target_px, target_px), Image.LANCZOS)
                        new_im = Image.new("RGBA", (target_px, target_px), (0, 0, 0, 0))
                        x = (target_px - im.width) // 2
                        y = (target_px - im.height) // 2
                        new_im.paste(im, (x, y), im)
                        new_im.save(path, format="PNG")
                        try:
                            self.logger.info(
                                f"Resized asset {fname} to {target_px}x{target_px}"
                            )
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass

    # --- Spinner (animated) helpers ---
    def start_spinner(self):
        try:
            if getattr(self, "_spinner_running", False):
                return
            self._spinner_running = True
            try:
                self._spinner_canvas.grid()
            except Exception:
                pass
            # initialize angle and kick off animation loop
            try:
                self._spinner_angle = 0.0
            except Exception:
                self._spinner_angle = 0.0
            self._spinner_step()
        except Exception:
            pass

    def _spinner_step(self):
        try:
            if not getattr(self, "_spinner_running", False):
                return
            # Update orbital positions for two balls
            try:
                import math

                # advance by small radian step for smooth animation
                step = 0.18
                self._spinner_angle = (getattr(self, "_spinner_angle", 0.0) + step) % (
                    2 * math.pi
                )
                a1 = self._spinner_angle
                a2 = (self._spinner_angle + math.pi) % (2 * math.pi)
                r = getattr(self, "_spinner_r", 10)
                cx = getattr(self, "_spinner_cx", 16)
                cy = getattr(self, "_spinner_cy", 16)
                bsize = 6
                x1 = int(cx + r * math.cos(a1))
                y1 = int(cy + r * math.sin(a1))
                x2 = int(cx + r * math.cos(a2))
                y2 = int(cy + r * math.sin(a2))
                # update coords of the two balls
                try:
                    self._spinner_canvas.coords(
                        self._spinner_ball1,
                        x1 - bsize // 2,
                        y1 - bsize // 2,
                        x1 + bsize // 2,
                        y1 + bsize // 2,
                    )
                    self._spinner_canvas.coords(
                        self._spinner_ball2,
                        x2 - bsize // 2,
                        y2 - bsize // 2,
                        x2 + bsize // 2,
                        y2 + bsize // 2,
                    )
                except Exception:
                    pass
            except Exception:
                pass
            # Schedule next frame (~30 FPS)
            try:
                self._spinner_job = self.root.after(33, self._spinner_step)
            except Exception:
                self.stop_spinner()
        except Exception:
            pass

    def stop_spinner(self):
        try:
            self._spinner_running = False
            if getattr(self, "_spinner_job", None):
                try:
                    self.root.after_cancel(self._spinner_job)
                except Exception:
                    pass
                self._spinner_job = None
            try:
                # hide spinner and reset positions
                try:
                    self._spinner_canvas.grid_remove()
                except Exception:
                    pass
                try:
                    # move balls off-canvas to avoid visual artifacts
                    self._spinner_canvas.coords(self._spinner_ball1, -10, -10, -6, -6)
                    self._spinner_canvas.coords(self._spinner_ball2, -10, -10, -6, -6)
                except Exception:
                    pass
            except Exception:
                pass
        except Exception:
            pass

    def import_settings(self):
        """Import settings from a user-chosen JSON file."""
        file_path = filedialog.askopenfilename(
            title="Import Settings",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="epstein_downloader_settings.json",
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    imported = json.load(f)
                # Update config and UI
                self.config.update(imported)
                if "download_dir" in imported:
                    self.base_dir.set(imported["download_dir"])
                if "log_dir" in imported:
                    self.log_dir = imported["log_dir"]
                    os.makedirs(self.log_dir, exist_ok=True)
                if "credentials_path" in imported:
                    self.credentials_path = imported["credentials_path"]
                self.save_config()
                self.setup_logger(self.log_dir)
                # Apply imported auto-start flags if present
                if self.config.get("auto_start", False):
                    try:
                        if self.config.get("start_minimized", False):
                            try:
                                self.root.iconify()
                            except Exception:
                                pass
                        self.start_download_all_thread()
                    except Exception:
                        self.logger.exception(
                            "Failed to apply imported auto-start settings."
                        )
                messagebox.showinfo(
                    "Import Settings", f"Settings imported from: {file_path}"
                )
            except Exception as e:
                self.log_error(e, "Import Settings")

    def open_settings_dialog(self):
        """Open a dialog to view and edit all key settings, grouped in tabs."""
        win = tk.Toplevel(self.root)
        win.title("Advanced Settings")
        win.geometry("650x480")

        notebook = ttk.Notebook(win)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # --- General Tab ---
        general_tab = ttk.Frame(notebook)
        notebook.add(general_tab, text="General")
        ttk.Label(general_tab, text="Download Folder:").grid(
            row=0, column=0, sticky="w", padx=10, pady=10
        )
        download_var = tk.StringVar(value=self.base_dir.get())
        download_entry = ttk.Entry(general_tab, textvariable=download_var, width=50)
        download_entry.grid(row=0, column=1, padx=10, pady=10)
        browse_download_btn = ttk.Button(
            general_tab,
            text="Browse",
            command=lambda: download_var.set(
                filedialog.askdirectory(title="Select Download Folder")
                or download_var.get()
            ),
        )
        browse_download_btn.grid(row=0, column=2, padx=5)
        ttk.Label(general_tab, text="Log Folder:").grid(
            row=1, column=0, sticky="w", padx=10, pady=10
        )
        log_var = tk.StringVar(
            value=getattr(self, "log_dir", os.path.join(os.getcwd(), "logs"))
        )
        log_entry = ttk.Entry(general_tab, textvariable=log_var, width=50)
        log_entry.grid(row=1, column=1, padx=10, pady=10)
        browse_log_btn = ttk.Button(
            general_tab,
            text="Browse",
            command=lambda: log_var.set(
                filedialog.askdirectory(title="Select Log Folder") or log_var.get()
            ),
        )
        browse_log_btn.grid(row=1, column=2, padx=5)
        ttk.Label(general_tab, text="Credentials File:").grid(
            row=2, column=0, sticky="w", padx=10, pady=10
        )
        cred_var = tk.StringVar(value=getattr(self, "credentials_path", ""))
        cred_entry = ttk.Entry(general_tab, textvariable=cred_var, width=50)
        cred_entry.grid(row=2, column=1, padx=10, pady=10)
        browse_cred_btn = ttk.Button(
            general_tab,
            text="Browse",
            command=lambda: cred_var.set(
                filedialog.askopenfilename(
                    title="Select credentials.json",
                    filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                )
                or cred_var.get()
            ),
        )
        browse_cred_btn.grid(row=2, column=2, padx=5)
        ttk.Label(general_tab, text="Concurrent Downloads:").grid(
            row=3, column=0, sticky="w", padx=10, pady=10
        )
        concurrency_var = tk.IntVar(value=self.concurrent_downloads.get())
        concurrency_spin = ttk.Spinbox(
            general_tab,
            from_=1,
            to=32,
            textvariable=concurrency_var,
            width=8,
            increment=1,
        )
        concurrency_spin.grid(row=3, column=1, sticky="w", padx=10, pady=10)
        # Auto-start and Start minimized options
        self.auto_start_var = tk.BooleanVar(value=self.config.get("auto_start", False))
        self.start_minimized_var = tk.BooleanVar(
            value=self.config.get("start_minimized", False)
        )
        auto_chk = ttk.Checkbutton(
            general_tab,
            text="Auto-start downloads on launch",
            variable=self.auto_start_var,
        )
        auto_chk.grid(row=4, column=0, columnspan=2, sticky="w", padx=10, pady=(8, 2))
        self.add_tooltip(
            auto_chk,
            "If enabled, downloads will start automatically when the app launches.",
        )
        min_chk = ttk.Checkbutton(
            general_tab,
            text="Start downloads minimized",
            variable=self.start_minimized_var,
        )
        min_chk.grid(row=5, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 8))
        self.add_tooltip(
            min_chk,
            "If enabled, the window will be minimized when auto-starting downloads.",
        )
        # --- Network Tab ---
        network_tab = ttk.Frame(notebook)
        notebook.add(network_tab, text="Network")
        ttk.Label(
            network_tab, text="Proxy (http[s]://user:pass@host:port or leave blank):"
        ).grid(row=0, column=0, sticky="w", padx=10, pady=10)
        proxy_var = tk.StringVar(value=self.config.get("proxy", ""))
        proxy_entry = ttk.Entry(network_tab, textvariable=proxy_var, width=50)
        proxy_entry.grid(row=0, column=1, padx=10, pady=10, columnspan=2)
        ttk.Label(network_tab, text="Download Speed Limit (KB/s, 0 = unlimited):").grid(
            row=1, column=0, sticky="w", padx=10, pady=10
        )
        speed_var = tk.IntVar(value=int(self.config.get("speed_limit_kbps", 0)))
        speed_spin = ttk.Spinbox(
            network_tab,
            from_=0,
            to=102400,
            textvariable=speed_var,
            width=10,
            increment=10,
        )
        speed_spin.grid(row=1, column=1, sticky="w", padx=10, pady=10)

        # --- Appearance Tab ---
        appearance_tab = ttk.Frame(notebook)
        notebook.add(appearance_tab, text="Appearance")
        ttk.Label(appearance_tab, text="Theme:").grid(
            row=0, column=0, sticky="w", padx=10, pady=10
        )
        theme_var = tk.StringVar(value="Dark" if self.dark_mode else "Light")
        theme_combo = ttk.Combobox(
            appearance_tab,
            textvariable=theme_var,
            values=["Light", "Dark", "azure", "sun-valley", "forest"],
            state="readonly",
            width=14,
        )
        theme_combo.grid(row=0, column=1, sticky="w", padx=10, pady=10)

        # --- Advanced Tab (always visible) ---
        advanced_tab = ttk.Frame(notebook)
        notebook.add(advanced_tab, text="Advanced")
        ttk.Label(advanced_tab, text="(Advanced options coming soon)").pack(
            padx=20, pady=(20, 5), anchor="w"
        )
        gdown_chk = ttk.Checkbutton(
            advanced_tab,
            text="Enable gdown fallback for Google Drive downloads (not recommended unless API fails)",
            variable=self.use_gdown_fallback,
        )
        gdown_chk.pack(padx=20, pady=(5, 20), anchor="w")
        self.add_tooltip(
            gdown_chk,
            "If enabled, will use gdown to download Google Drive folders if the API fails or credentials are missing. This may be less reliable.",
        )

        def save_and_close():
            self.base_dir.set(download_var.get())
            self.log_dir = log_var.get()
            os.makedirs(self.log_dir, exist_ok=True)
            self.credentials_path = cred_var.get() if cred_var.get() else None
            # Try to load credentials immediately so changes apply without restart
            try:
                self.reload_credentials(self.credentials_path)
            except Exception as e:
                self.logger.warning(f"Failed to load credentials from settings dialog: {e}")
            self.concurrent_downloads.set(concurrency_var.get())
            self.config["proxy"] = proxy_var.get()
            self.config["speed_limit_kbps"] = speed_var.get()
            # New advanced options
            self.config["auto_start"] = bool(self.auto_start_var.get())
            self.config["start_minimized"] = bool(self.start_minimized_var.get())
            # Persist gdown fallback setting (always save current checkbox state)
            self.config["use_gdown_fallback"] = bool(self.use_gdown_fallback.get())
            # Theme
            sel_theme = theme_var.get()
            # Apply requested theme; support Light/Dark aliases and extra named themes
            if sel_theme in ("Dark", "dark"):
                self.dark_mode = True
                self.set_theme("clam")
            elif sel_theme in ("Light", "light"):
                self.dark_mode = False
                self.set_theme("default")
            else:
                # Pass through custom theme names (azure, sun-valley, forest)
                try:
                    self.set_theme(sel_theme)
                except Exception:
                    pass
            self.save_config()
            try:
                self.logger.info("Settings saved via Advanced Settings.")
            except Exception:
                pass
            self.setup_logger(self.log_dir)
            win.destroy()
            # Small transient confirmation (non-blocking)
            try:
                self.show_toast("Settings saved", duration=1400)
            except Exception:
                # Fallback to modal dialog if toast fails
                try:
                    messagebox.showinfo("Settings", "Settings updated.")
                except Exception:
                    pass
            # Apply auto-start if requested
            try:
                if self.config.get("auto_start", False):
                    # If requested, minimize first
                    if self.config.get("start_minimized", False):
                        try:
                            self.root.iconify()
                        except Exception:
                            pass
                    # Start downloads in background
                    self.start_download_all_thread()
            except Exception:
                self.logger.exception(
                    "Failed to apply auto-start settings after saving."
                )
            # Persist config to disk
            try:
                self.save_config()
            except Exception:
                self.logger.warning("Failed to save config after settings change.")

        save_btn = ttk.Button(win, text="Save", command=save_and_close)
        save_btn.pack(pady=12)

        # Tooltips
        self.add_tooltip(download_entry, "Edit the download folder path.")
        self.add_tooltip(browse_download_btn, "Browse for download folder.")
        self.add_tooltip(log_entry, "Edit the log folder path.")
        self.add_tooltip(browse_log_btn, "Browse for log folder.")
        self.add_tooltip(cred_entry, "Edit the path to credentials.json.")
        self.add_tooltip(browse_cred_btn, "Browse for credentials.json file.")
        self.add_tooltip(
            concurrency_spin, "Set the number of concurrent downloads (threads)"
        )
        self.add_tooltip(
            proxy_entry, "Set a proxy for downloads (http[s]://user:pass@host:port)"
        )
        self.add_tooltip(speed_spin, "Limit download speed in KB/s (0 = unlimited)")
        self.add_tooltip(theme_combo, "Choose between light and dark mode.")
        self.add_tooltip(save_btn, "Save changes to settings.")

    def force_full_hash_rescan(self):
        """Delete the hash cache file and meta so the next scan will re-hash all files."""
        import os

        base_dir = self.base_dir.get()
        hash_file_path = os.path.join(base_dir, "existing_hashes.txt")
        cache_file = hash_file_path + ".cache.json"
        meta_file = hash_file_path + ".meta.json"
        try:
            removed = False
            if os.path.exists(cache_file):
                os.remove(cache_file)
                removed = True
            if os.path.exists(meta_file):
                os.remove(meta_file)
                removed = True
            # Set a flag so any running session knows to force a rescan on next download
            self._force_rescan = True
            if removed:
                messagebox.showinfo(
                    "Hash Rescan",
                    "Hash cache and metadata cleared. Next scan will re-hash all files.",
                )
            else:
                messagebox.showinfo(
                    "Hash Rescan",
                    "No hash cache or metadata found. Next scan will re-hash all files.",
                )
        except Exception as e:
            messagebox.showerror("Hash Rescan", f"Failed to clear hash cache: {e}")

    def cancel_scan(self):
        """Request cancellation of a running existing-file scan."""
        if getattr(self, "_scanning", False):
            self._cancel_scan = True
            try:
                self.logger.info("User requested scan cancellation.")
            except Exception:
                pass
            self.thread_safe_status("Cancelling scan...")
        else:
            self.thread_safe_status("No scan in progress.")

    def stop_scans(self):
        """Disable future scans and cancel any currently running scan."""
        try:
            # Log entry state and stack trace
            try:
                import traceback

                stack = "".join(traceback.format_stack())
                self.logger.debug(
                    f"stop_scans() called. _scans_disabled={getattr(self, '_scans_disabled', None)}, _scanning={getattr(self, '_scanning', False)}, _cancel_scan={getattr(self, '_cancel_scan', None)}"
                )
                self.logger.debug(f"stop_scans() call stack:\n{stack}")
            except Exception:
                self.logger.debug(
                    "stop_scans() called. (failed to read some internal state)"
                )
            self._scans_disabled = True
            # Cancel any running scan
            if getattr(self, "_scanning", False):
                self._cancel_scan = True
            try:
                self.logger.info("User disabled scanning.")
            except Exception:
                pass
            self.thread_safe_status(
                "Scanning disabled by user. Scans will remain disabled until re-enabled."
            )
            # Update UI buttons if available
            try:
                self.stop_scan_btn.config(state="disabled")
            except Exception:
                self.logger.exception("Failed to disable stop_scan_btn in stop_scans")
            try:
                self.enable_scan_btn.config(state="normal")
            except Exception:
                self.logger.exception("Failed to enable enable_scan_btn in stop_scans")
            # Log exit state
            try:
                self.logger.debug(
                    f"stop_scans() exit. _scans_disabled={getattr(self, '_scans_disabled', None)}, _scanning={getattr(self, '_scanning', False)}, stop_scan_btn_state={self.stop_scan_btn.cget('state') if hasattr(self, 'stop_scan_btn') else 'NA'}, enable_scan_btn_state={self.enable_scan_btn.cget('state') if hasattr(self, 'enable_scan_btn') else 'NA'}"
                )
            except Exception:
                self.logger.debug("stop_scans() exit. (failed to read some UI state)")
        except Exception as e:
            self.logger.exception(f"Exception in stop_scans: {e}")

    def enable_scans(self):
        """Re-enable scanning for existing files."""
        try:
            # Log entry state and stack trace
            try:
                import traceback

                stack = "".join(traceback.format_stack())
                self.logger.debug(
                    f"enable_scans() called. _scans_disabled={getattr(self, '_scans_disabled', None)}"
                )
                self.logger.debug(f"enable_scans() call stack:\n{stack}")
            except Exception:
                self.logger.debug(
                    "enable_scans() called. (failed to read some internal state)"
                )
            self._scans_disabled = False
            # Also resume downloads if they were paused/stopped
            try:
                if getattr(self, "_stop_event", None):
                    self._stop_event.clear()
                self._is_stopped = False
                # Clear any cancellation request for scans
                try:
                    self._cancel_scan = False
                except Exception:
                    pass
            except Exception:
                pass
            try:
                self._pause_event.set()
                self._is_paused = False
                try:
                    self.pause_btn.config(state="normal", text="Pause")
                except Exception:
                    pass
                try:
                    self.resume_btn.config(state="disabled")
                except Exception:
                    pass
            except Exception:
                pass
            try:
                self.logger.info("User enabled scanning.")
            except Exception:
                pass
            self.thread_safe_status(
                "Scanning enabled. Full scans will run as scheduled."
            )
            try:
                self.stop_scan_btn.config(state="normal")
            except Exception:
                self.logger.exception("Failed to enable stop_scan_btn in enable_scans")
            try:
                self.enable_scan_btn.config(state="disabled")
            except Exception:
                self.logger.exception(
                    "Failed to disable enable_scan_btn in enable_scans"
                )
            # Log exit state
            try:
                self.logger.debug(
                    f"enable_scans() exit. _scans_disabled={getattr(self, '_scans_disabled', None)}, stop_scan_btn_state={self.stop_scan_btn.cget('state') if hasattr(self, 'stop_scan_btn') else 'NA'}, enable_scan_btn_state={self.enable_scan_btn.cget('state') if hasattr(self, 'enable_scan_btn') else 'NA'}"
                )
            except Exception:
                self.logger.debug("enable_scans() exit. (failed to read some UI state)")
        except Exception as e:
            self.logger.exception(f"Exception in enable_scans: {e}")

    def stop_all(self):
        """Stop all activity: request cancellation of downloads, scans, and background workers.

        After stopping, set the scan button into a temporary "Reset" action that clears
        state and prepares the app for a fresh run when clicked.
        """
        try:
            try:
                import traceback

                stack = "".join(traceback.format_stack())
                self.logger.debug(
                    f"stop_all() called. _is_stopped={getattr(self, '_is_stopped', None)}, _scans_disabled={getattr(self, '_scans_disabled', None)}"
                )
                self.logger.debug(f"stop_all() call stack:\n{stack}")
            except Exception:
                pass
            # Signal stop to all workers
            self._stop_event.set()
            self._is_stopped = True
            # Ensure paused threads are released so they can observe the stop request
            try:
                self._pause_event.set()
            except Exception:
                pass
            # Also disable future scans and cancel any running scan
            self._scans_disabled = True
            try:
                self._cancel_scan = True
            except Exception:
                pass
            try:
                self.logger.info("User requested full stop of all activity.")
            except Exception:
                pass
            # Update UI quickly to avoid appearing frozen
            try:
                # Disable download controls until reset
                self.download_btn.config(state="disabled")
                self.pause_btn.config(state="disabled")
                self.resume_btn.config(state="disabled")
                # Turn the Enable Scans button into a Reset button so user can prepare a fresh run
                try:
                    self.enable_scan_btn.config(
                        text="Reset", command=self.reset_after_stop, state="normal"
                    )
                    self.add_tooltip(
                        self.enable_scan_btn,
                        "Reset app state so Start Download can run again",
                    )
                except Exception:
                    pass
            except Exception:
                self.logger.exception("Failed to update UI buttons in stop_all")
            try:
                self.stop_spinner()
            except Exception:
                pass
            # Update status message
            self.thread_safe_status(
                "All activity stopped by user. Click Reset to prepare for a fresh run."
            )
            try:
                self.logger.info(
                    "All activity stopped by user; user prompted to reset."
                )
            except Exception:
                pass
        except Exception as e:
            self.logger.exception(f"Exception in stop_all: {e}")

    def reset_after_stop(self):
        """Reset internal state after a Stop so the app is ready for a fresh Start Download."""
        try:
            try:
                self.logger.debug(
                    "reset_after_stop() called: clearing stop flags and resetting UI"
                )
            except Exception:
                pass
            # Clear stop/cancel flags
            try:
                if getattr(self, "_stop_event", None):
                    self._stop_event.clear()
                self._is_stopped = False
                self._cancel_scan = False
            except Exception:
                pass
            # Clear paused state and ensure threads can run
            try:
                self._pause_event.set()
                self._is_paused = False
            except Exception:
                pass
            # Reset counters and collections
            try:
                self.processed_count = 0
            except Exception:
                pass
            try:
                self.skipped_files = set()
                self.file_tree = {}
            except Exception:
                pass
            # Reset progress UI
            try:
                self.progress["value"] = 0
                try:
                    self.file_progress["value"] = 0
                except Exception:
                    pass
                self.speed_eta_var.set("Speed: --  ETA: --")
                self.update_summary_bar(queued=len(self.urls), completed=0, failed=0)
            except Exception:
                pass
            # Ensure buttons reflect a fresh state
            try:
                self.download_btn.config(state="normal")
                self.pause_btn.config(state="normal", text="Pause")
                self.resume_btn.config(state="disabled")
                # Restore enable_scan_btn to original behavior
                try:
                    self.enable_scan_btn.config(
                        text="Enable Scans", command=self.enable_scans, state="disabled"
                    )
                    self.add_tooltip(
                        self.enable_scan_btn,
                        "Re-enable scanning and resume activity (undo Stop)",
                    )
                except Exception:
                    pass
            except Exception:
                pass
            # Status update
            try:
                self.thread_safe_status(
                    "Reset complete. Ready for a fresh download run."
                )
                self.logger.info("Application state reset by user.")
            except Exception:
                pass
        except Exception as e:
            self.logger.exception(f"Exception in reset_after_stop: {e}")

    def pick_credentials_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Google Drive credentials.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="credentials.json",
        )
        if file_path:
            self.credentials_path = file_path
            self.config["credentials_path"] = file_path
            # Attempt to load and cache credentials immediately so running app can use them
            try:
                self.reload_credentials(file_path)
            except Exception as e:
                self.logger.warning(f"Failed to load credentials immediately: {e}")
            self.save_config()
            self.logger.info(f"Set credentials.json via File menu: {file_path}")
            messagebox.showinfo(
                "Credentials Set", f"credentials.json set to: {file_path}"
            )

    def set_theme(self, theme_name):
        style = ttk.Style()
        try:
            style.theme_use(theme_name)
        except Exception:
            style.theme_use("default")
        # Optionally, tweak widget colors for extra clarity
        if theme_name in ("clam", "alt", "vista", "xpnative"):
            style.configure(".", background="#222", foreground="#eee")
            style.configure("TLabel", background="#222", foreground="#eee")
            style.configure("TButton", background="#333", foreground="#eee")
            style.configure("TEntry", fieldbackground="#333", foreground="#eee")
            style.configure("TFrame", background="#222")
            style.configure("TNotebook", background="#222")
            style.configure("TNotebook.Tab", background="#333", foreground="#eee")
            style.configure("TProgressbar", background="#444")
        else:
            style.configure(".", background="#f0f0f0", foreground="#222")
            style.configure("TLabel", background="#f0f0f0", foreground="#222")
            style.configure("TButton", background="#f0f0f0", foreground="#222")
            style.configure("TEntry", fieldbackground="#fff", foreground="#222")
            style.configure("TFrame", background="#f0f0f0")
            style.configure("TNotebook", background="#f0f0f0")
            style.configure("TNotebook.Tab", background="#e0e0e0", foreground="#222")
            style.configure("TProgressbar", background="#e0e0e0")

        # Try third-party theme packages (ttkbootstrap or ttkthemes) for extra palettes
        try:
            # Prefer ttkbootstrap if available
            import importlib

            if importlib.util.find_spec("ttkbootstrap") is not None:
                from ttkbootstrap import Style as TBStyle

                tbstyle = TBStyle()
                # Map some friendly names to known ttkbootstrap themes where possible
                tbmap = {
                    "azure": "cosmo",
                    "sun-valley": "flatly",
                    "sun_valley": "flatly",
                    "forest": "minty",
                }
                tb_theme = tbmap.get(theme_name.lower(), None)
                if tb_theme:
                    try:
                        tbstyle.theme_use(tb_theme)
                    except Exception:
                        pass
        except Exception:
            pass
        # Also update our Modern progressbar styles to match the selected theme/darkness
        try:
            pb_trough = (
                "#dfeffb" if not getattr(self, "dark_mode", False) else "#111217"
            )
            pb_border = (
                "#8fb5ff" if not getattr(self, "dark_mode", False) else "#2a2f36"
            )
            pb_bg = "#0078d7" if not getattr(self, "dark_mode", False) else "#2a6fb0"
            pb_light = "#5aa8ff" if not getattr(self, "dark_mode", False) else "#4e8fb8"
            pb_dark = "#005bb5" if not getattr(self, "dark_mode", False) else "#134a75"
            style.configure(
                "Modern.Horizontal.TProgressbar",
                troughcolor=pb_trough,
                bordercolor=pb_border,
                background=pb_bg,
                lightcolor=pb_light,
                darkcolor=pb_dark,
                thickness=20,
                relief="raised",
            )
            # file progress (green)
            ff_trough = (
                "#f0f9f0" if not getattr(self, "dark_mode", False) else "#141814"
            )
            ff_border = (
                "#9fe39a" if not getattr(self, "dark_mode", False) else "#25492b"
            )
            ff_bg = "#66c33a" if not getattr(self, "dark_mode", False) else "#5fa94c"
            ff_light = "#98e57a" if not getattr(self, "dark_mode", False) else "#7fb86a"
            ff_dark = "#3b8a20" if not getattr(self, "dark_mode", False) else "#2f6b2f"
            style.configure(
                "ModernFile.Horizontal.TProgressbar",
                troughcolor=ff_trough,
                bordercolor=ff_border,
                background=ff_bg,
                lightcolor=ff_light,
                darkcolor=ff_dark,
                thickness=14,
                relief="raised",
            )
        except Exception:
            pass

    def detect_os_dark_mode(self):
        """Detect OS-level dark mode preference where possible (Windows/macOS)."""
        try:
            import sys

            if sys.platform.startswith("win"):
                try:
                    import winreg

                    key = winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                    )
                    val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                    # AppsUseLightTheme == 0 -> dark mode enabled
                    return val == 0
                except Exception:
                    return False
            else:
                # Try darkdetect package if available on other platforms
                try:
                    import darkdetect

                    return darkdetect.isDark()
                except Exception:
                    return False
        except Exception:
            return False

    def toggle_dark_mode(self):
        self.dark_mode = not getattr(self, "dark_mode", False)
        # Use 'clam' for dark, 'default' for light if available
        if self.dark_mode:
            self.set_theme("clam")
        else:
            self.set_theme("default")

    def validate_credentials(self):
        # Validate Google Drive credentials.json
        import threading

        def do_validate():
            path = getattr(self, "credentials_path", None)
            if not path or not os.path.exists(path):
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Validate Credentials",
                        "No credentials.json file set or file does not exist.",
                    ),
                )
                return
            try:
                # Load service account credentials with a Drive scope and attempt a refresh.
                # Checking `.valid` without refreshing is unreliable for service account files.
                from google.oauth2 import service_account
                from google.auth.transport.requests import Request

                scopes = ["https://www.googleapis.com/auth/drive.readonly"]
                creds = service_account.Credentials.from_service_account_file(
                    path, scopes=scopes
                )
                req = Request()
                try:
                    creds.refresh(req)
                    self.root.after(
                        0,
                        lambda: messagebox.showinfo(
                            "Validate Credentials", "Credentials are valid."
                        ),
                    )
                except Exception as e:
                    err_text = str(e)
                    self.root.after(
                        0,
                        lambda: messagebox.showerror(
                            "Validate Credentials",
                            f"Credentials validation failed: {err_text}",
                        ),
                    )
            except Exception as e:
                err_text = str(e)
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Validate Credentials", f"Credentials validation failed: {err_text}"
                    ),
                )

        threading.Thread(target=do_validate, daemon=True).start()

    def test_download_link(self):
        # Test the first URL in the list for reachability and downloadability
        import threading

        def do_test():
            if not self.urls:
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Test Download Link", "No URLs in the list."
                    ),
                )
                return
            url = self.urls[0]
            try:
                proxies = None
                if self.config.get("proxy"):
                    proxies = {
                        "http": self.config["proxy"],
                        "https": self.config["proxy"],
                    }
                r = requests.head(
                    url, timeout=10, proxies=proxies, allow_redirects=True
                )
                if r.status_code == 200:
                    self.root.after(
                        0,
                        lambda: messagebox.showinfo(
                            "Test Download Link", f"URL is reachable: {url}"
                        ),
                    )
                else:
                    self.root.after(
                        0,
                        lambda: messagebox.showerror(
                            "Test Download Link",
                            f"URL returned status code {r.status_code}: {url}",
                        ),
                    )
            except Exception as e:
                err_text = str(e)
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Test Download Link", f"Failed to reach URL: {err_text}"
                    ),
                )

        threading.Thread(target=do_test, daemon=True).start()

    def show_about(self):
        about_text = (
            f"EpsteinFilesDownloader v{__version__}\n"
            "\n(C) 2025\n"
            "Author: JosephThePlatypus\n"
            "License: MIT\n"
            "\nA GUI tool for downloading Epstein court records and related files."
        )
        messagebox.showinfo("About", about_text)

    def report_issue(self):
        # Open the user's GitHub issues page for reporting issues
        repo_url = "https://github.com/AresX0/WebsiteFileDownloader/issues"
        try:
            import webbrowser

            webbrowser.open(repo_url)
            messagebox.showinfo(
                "Report Issue",
                f"Your browser has been opened to the issues page:\n{repo_url}",
            )
        except Exception:
            messagebox.showinfo(
                "Report Issue",
                f"To report an issue or send feedback, visit:\n{repo_url}",
            )

    def pick_download_folder(self):
        folder = filedialog.askdirectory(title="Select Download Folder")
        if folder:
            self.base_dir.set(folder)
            # Persist immediately so next launch remembers this folder
            try:
                self.save_config()
            except Exception:
                self.logger.warning("Failed to save config after pick_download_folder.")

    def pick_log_folder(self):
        folder = filedialog.askdirectory(title="Select Log Folder")
        if folder:
            self.log_dir = folder
            os.makedirs(self.log_dir, exist_ok=True)
            self.save_config()
            self.setup_logger(self.log_dir)

    def show_help(self):
        help_text = self.get_help_text()
        self.show_popup("Help", help_text)

    def get_help_text(self):
        return (
            f"EpsteinFilesDownloader v{__version__}\n\n"
            "Features:\n"
            "- Download court records and files from preset or custom URLs.\n"
            "- Google Drive support (API or gdown fallback).\n"
            "- Multithreaded downloads, hash checking, and duplicate skipping.\n"
            "- Progress bar, skipped files, and JSON export.\n"
            "- Menu options for download/log folder, dark/light mode, restoring defaults, and more.\n"
            "- All logs saved to a user-chosen folder.\n\n"
            "Menu Options:\n"
            "File Menu:\n"
            "  - Set Download Folder: Choose where files are saved.\n"
            "  - Set Log Folder: Choose where logs are saved.\n"
            "  - Set Credentials File: Select Google Drive credentials.json.\n"
            "  - Save Settings as Default: Save current folders and credentials for next session.\n"
            "  - Restore Defaults: Reset all settings to default values.\n"
            "  - Exit: Close the application.\n\n"
            "View Menu:\n"
            "  - Toggle Dark/Light Mode: Switch between dark and light themes.\n"
            "  - Show/Hide Log Panel: Show or hide the log/status pane.\n"
            "  - Show Download Progress: Display the download progress bar.\n\n"
            "Tools Menu:\n"
            "  - Check for Updates: Check for new versions on GitHub.\n"
            "  - Validate Credentials: Check if your Google Drive credentials are valid.\n"
            "  - Test Download Link: Test if a download link is working.\n"
            "  - Force Full Hash Rescan: Clear the hash cache and force a full file hash scan on next download.\n\n"
            "Help Menu:\n"
            "  - Help: Show this help/documentation.\n"
            "  - About: Show version and author information.\n"
            "  - Report Issue / Send Feedback: Open the GitHub issues page for bug reports or feedback.\n\n"
            "Other Usage Notes:\n"
            "- Start downloads with the Start Download button.\n"
            "- For Google Drive, you will be prompted for credentials.json or gdown fallback.\n"
            "- Drag and drop URLs or credentials.json into the window.\n"
            "- Skipped files and download progress are shown in the log/status pane.\n"
            "- Hash scanning is cached for 4 hours for speed; use Tools > Force Full Hash Rescan to override.\n"
        )

    # --- Utility Methods ---
    def validate_url(self, url):
        """Basic URL validation: checks scheme and netloc."""
        try:
            result = urllib.parse.urlparse(url)
            return all([result.scheme in ("http", "https"), result.netloc])
        except Exception:
            return False

    # --- Download Logic ---
    def start_download(self):
        self.logger.debug("start_download called.")
        base_dir = self.base_dir.get()
        try:
            os.makedirs(base_dir, exist_ok=True)
        except Exception as e:
            self.logger.error(f"Failed to create download directory: {e}")
            self.show_error_dialog(f"Failed to create download directory: {e}")
            return
        self.setup_logger(base_dir)
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                for url in self.urls:
                    if url.startswith("https://drive.google.com/drive/folders/"):
                        continue
                    if not self.validate_url(url):
                        self.logger.error(f"Invalid URL: {url}")
                        self.show_error_dialog(f"Invalid URL: {url}")
                        continue
                    self.logger.info(f"Visiting: {url}")
                    try:
                        s, t, a = self.download_files_threaded(
                            page,
                            url,
                            base_dir,
                            skipped_files=self.skipped_files,
                            file_tree=self.file_tree,
                        )
                        self.skipped_files.update(s or set())
                        self.file_tree.update(t or {})
                    except Exception as e:
                        self.logger.error(
                            f"Error downloading from {url}: {e}", exc_info=True
                        )
                        self.show_error_dialog(f"Error downloading from {url}: {e}")
                browser.close()
        except Exception as e:
            self.logger.error(f"Exception in start_download: {e}", exc_info=True)
            self.show_error_dialog(f"Critical error in download process: {e}")
            return
        # Prompt for credentials.json location if needed
        credentials_path = self.config.get("credentials_path", None)
        for url in self.urls:
            if url.startswith("https://drive.google.com/drive/folders/"):
                if not credentials_path:
                    credentials_path = filedialog.askopenfilename(
                        title="Select Google Drive credentials.json (Cancel to use gdown fallback)",
                        filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                        initialfile="credentials.json",
                    )
                    if not credentials_path:
                        self.logger.warning(
                            "No credentials.json selected. Will use gdown fallback for Google Drive download."
                        )
                        messagebox.showwarning(
                            "Google Drive",
                            "No credentials.json selected. Will use gdown fallback for Google Drive download.",
                        )
                        credentials_path = None
                gdrive_dir = os.path.join(base_dir, "GoogleDrive")
                self.logger.info(f"Processing Google Drive folder: {url}")
                try:
                    self.download_gdrive_with_fallback(
                        url, gdrive_dir, credentials_path
                    )
                except Exception as e:
                    self.logger.error(
                        f"Error downloading Google Drive folder {url}: {e}"
                    )
                    self.show_error_dialog(
                        f"Error downloading Google Drive folder {url}: {e}"
                    )
        self.logger.info("All downloads complete.")
        messagebox.showinfo(
            "Download Complete", "All downloads are complete. See the log for details."
        )

    def download_gdrive_with_fallback(self, url, gdrive_dir, credentials_path):
        import re

        try:
            match = re.search(r"/folders/([a-zA-Z0-9_-]+)", url)
            if not match:
                self.logger.error("Google Drive folder ID not found in URL.")
                self.show_error_dialog("Google Drive folder ID not found in URL.")
                return
            folder_id = match.group(1)
            # Only use gdown fallback if advanced is enabled and user checked it
            use_gdown_fallback = self.config.get(
                "show_advanced", False
            ) and self.config.get("use_gdown_fallback", False)
            if os.path.exists(credentials_path):
                try:
                    os.makedirs(gdrive_dir, exist_ok=True)
                    self.download_drive_folder_api(
                        folder_id, gdrive_dir, credentials_path
                    )
                    return
                except Exception as e:
                    self.logger.error(f"Google Drive API download failed: {e}")
                    # Prompt user to enable advanced fallback
                    if not self.config.get("show_advanced", False):
                        if messagebox.askyesno(
                            "Google Drive API Error",
                            f"Google Drive API download failed: {e}\n\nWould you like to enable the advanced fallback (gdown) option?",
                        ):
                            self.config["show_advanced"] = True
                            self.save_config()
                            self.open_settings_dialog()
                        return
                    if not use_gdown_fallback:
                        self.show_error_dialog(
                            f"Google Drive API download failed: {e}\n\nYou can try the gdown fallback by enabling it in the Advanced tab.",
                            "Google Drive API Error",
                        )
                        return
                    self.logger.info("Falling back to gdown as requested...")
            elif not use_gdown_fallback:
                self.logger.error(
                    "No credentials.json found. Not attempting gdown fallback unless requested."
                )
                # Prompt user to enable advanced fallback
                if not self.config.get("show_advanced", False):
                    if messagebox.askyesno(
                        "Google Drive Credentials Required",
                        "No credentials.json found. Would you like to enable the advanced fallback (gdown) option?",
                    ):
                        self.config["show_advanced"] = True
                        self.save_config()
                        self.open_settings_dialog()
                    return
                self.show_error_dialog(
                    "No credentials.json found. To use the gdown fallback, enable it in the Advanced tab.",
                    "Google Drive Credentials Required",
                )
                return
            # If we reach here, either credentials are missing or API failed and fallback is requested
            try:

                os.makedirs(gdrive_dir, exist_ok=True)
                self.logger.info(
                    "Attempting gdown fallback for Google Drive folder download..."
                )
                file_list = self.download_gdrive_folder(url, gdrive_dir)
                if file_list:
                    for rel_path, dest_path in file_list:
                        if os.path.exists(dest_path):
                            self.logger.info(f"Skipping (already exists): {dest_path}")
                        else:
                            self.logger.info(f"Downloaded: {dest_path}")
                else:
                    self.logger.warning("gdown fallback did not return any files.")
            except Exception as e2:
                self.logger.error(f"gdown fallback failed: {e2}")
                # Show user-friendly error
                self.show_error_dialog(
                    "Google Drive fallback (gdown) failed. This may be due to a bug in gdown or an unsupported folder. Please check the log for technical details.\n\nTo enable full Google Drive access, create a credentials.json file as follows:\n"
                    "1. Go to https://console.cloud.google.com/\n"
                    "2. Create/select a project, enable the Google Drive API.\n"
                    "3. Go to 'APIs & Services > Credentials', create a Service Account, and download the JSON key.\n"
                    "4. Save it as credentials.json in this folder.\n",
                    title="Google Drive Fallback Error",
                )
        except Exception as e:
            import traceback

            self.logger.error(
                f"Unexpected error in download_gdrive_with_fallback: {e}\n{traceback.format_exc()}"
            )
            self.show_error_dialog(
                f"Unexpected error in download_gdrive_with_fallback: {e}"
            )

    def download_files_threaded(
        self,
        page,
        base_url,
        base_dir,
        visited=None,
        skipped_files=None,
        file_tree=None,
        all_files=None,
    ):
        allowed_domains = [
            "https://www.justice.gov/epstein",
            "https://oversight.house.gov/release/oversight-committee-releases-epstein-records-provided-by-the-department-of-justice/",
        ]
        try:
            # Main download logic here (existing code follows)
            # ...
            pass  # Placeholder for actual download logic
        except PermissionError as perm_err:
            self.logger.error(f"Permission denied: {perm_err}", exc_info=True)
            self.show_error_dialog(f"Permission denied: {perm_err}")
        except Exception as e:
            self.logger.error(f"Error in download_files_threaded: {e}", exc_info=True)
            self.show_error_dialog(f"Error in download_files_threaded: {e}")
        if visited is None:
            visited = set()
        if skipped_files is None:
            skipped_files = set()
        if file_tree is None:
            file_tree = {}
        if all_files is None:
            all_files = set()
        if base_url in visited:
            return skipped_files, file_tree, all_files
        visited.add(base_url)
        # Respect a global stop request before starting heavy work
        if getattr(self, "_stop_event", None) and self._stop_event.is_set():
            try:
                self.logger.info(f"Stop requested; aborting traversal of {base_url}")
            except Exception:
                pass
            return skipped_files, file_tree, all_files
        self.logger.info(f"Visiting: {base_url}")
        try:
            page.goto(base_url)
        except Exception as e:
            self.logger.error(f"Error loading {base_url}: {e}\nContinuing...")
            return skipped_files, file_tree, all_files
        links = page.query_selector_all("a")
        self.logger.info(f"Found {len(links)} links on {base_url}")
        hrefs = []
        for link in links:
            if getattr(self, "_stop_event", None) and self._stop_event.is_set():
                try:
                    self.logger.info(
                        f"Stop requested; aborting link collection on {base_url}"
                    )
                except Exception:
                    pass
                break
            try:
                href = link.get_attribute("href")
                if href:
                    hrefs.append(href)
            except Exception as e:
                self.logger.error(f"Error reading link attribute: {e}")

        download_args = []
        num_threads = 6
        for href in hrefs:
            # Pause support for traversal
            while not self._pause_event.is_set():
                if getattr(self, "_stop_event", None) and self._stop_event.is_set():
                    try:
                        self.logger.info(
                            f"Stop requested; aborting file/link loop on {base_url}"
                        )
                    except Exception:
                        pass
                    break
                time.sleep(0.1)
            if getattr(self, "_stop_event", None) and self._stop_event.is_set():
                try:
                    self.logger.info(
                        f"Stop requested; aborting file/link loop on {base_url}"
                    )
                except Exception:
                    pass
                break
            if href.startswith("#"):
                continue
            abs_url = urllib.parse.urljoin(base_url, href)
            if "/search" in abs_url:
                continue
            if re.search(
                r"\.(pdf|docx?|xlsx?|zip|txt|jpg|png|csv|mp4|mov|avi|wmv|wav|mp3|m4a)$",
                abs_url,
                re.IGNORECASE,
            ):
                # Pause support for file discovery
                while not self._pause_event.is_set():
                    if getattr(self, "_stop_event", None) and self._stop_event.is_set():
                        try:
                            self.logger.info(
                                f"Stop requested; aborting file discovery for {abs_url}"
                            )
                        except Exception:
                            pass
                        break
                    time.sleep(0.05)
                if getattr(self, "_stop_event", None) and self._stop_event.is_set():
                    break
                rel_path = self.sanitize_path(abs_url.replace("https://", ""))
                local_path = os.path.join(base_dir, rel_path)
                folder = os.path.dirname(local_path)
                if folder not in file_tree:
                    file_tree[folder] = []
                file_tree[folder].append(local_path)
                all_files.add(abs_url)
                download_args.append((abs_url, rel_path, local_path))
            elif (
                abs_url != base_url
                and any(abs_url.startswith(domain) for domain in allowed_domains)
                and abs_url != "https://www.justice.gov/epstein"
                and abs_url not in visited
            ):
                sub_skipped, sub_tree, sub_all = self.download_files_threaded(
                    page,
                    abs_url,
                    base_dir,
                    visited,
                    skipped_files,
                    file_tree,
                    all_files,
                )
                skipped_files.update(sub_skipped or set())
                file_tree.update(sub_tree or {})
                all_files.update(sub_all or set())

        def download_file_task(abs_url, rel_path, local_path):
            import time

            max_retries = 3
            delay = 2
            for attempt in range(1, max_retries + 1):
                # Pause support (also exit if a full stop is requested)
                while not self._pause_event.is_set():
                    if getattr(self, "_stop_event", None) and self._stop_event.is_set():
                        try:
                            self.logger.info(
                                f"Stop requested; aborting download task for {abs_url}"
                            )
                        except Exception:
                            pass
                        return
                    time.sleep(0.1)
                try:
                    if not self.validate_url(abs_url):
                        self.logger.warning(f"Skipping invalid URL: {abs_url}")
                        skipped_files.add(abs_url)
                        return
                    if os.path.exists(local_path):
                        self.logger.info(f"Skipping (already exists): {local_path}")
                        skipped_files.add(local_path)
                        return
                    os.makedirs(os.path.dirname(local_path), exist_ok=True)
                    self.logger.info(
                        f"Downloading {abs_url} -> {local_path} (Attempt {attempt})"
                    )
                    proxies = None
                    if self.config.get("proxy"):
                        proxies = {
                            "http": self.config["proxy"],
                            "https": self.config["proxy"],
                        }
                    speed_limit = int(self.config.get("speed_limit_kbps", 0))
                    with requests.get(
                        abs_url, stream=True, timeout=300, proxies=proxies
                    ) as r:
                        r.raise_for_status()
                        total_size = int(r.headers.get("content-length", 0))
                        downloaded = 0
                        start_time = time.time()
                        last_update = start_time
                        eta = "--"
                        speed = "--"
                        speed_limit = int(self.config.get("speed_limit_kbps", 0))
                        with open(local_path, "wb") as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                while not self._pause_event.is_set():
                                    if (
                                        getattr(self, "_stop_event", None)
                                        and self._stop_event.is_set()
                                    ):
                                        try:
                                            self.logger.info(
                                                f"Stop requested; aborting download of {abs_url}"
                                            )
                                        except Exception:
                                            pass
                                        return
                                    time.sleep(0.1)
                                if chunk:
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    now = time.time()
                                    elapsed = now - start_time
                                    if speed_limit > 0:
                                        # Throttle speed
                                        expected_time = downloaded / (
                                            speed_limit * 1024
                                        )
                                        if elapsed < expected_time:
                                            time.sleep(expected_time - elapsed)
                                    if elapsed > 0:
                                        speed_val = downloaded / elapsed
                                        speed = f"{speed_val / 1024:.1f} KB/s"
                                        if total_size > 0 and speed_val > 0:
                                            eta_val = (
                                                total_size - downloaded
                                            ) / speed_val
                                            eta = f"{int(eta_val // 60)}m {int(eta_val % 60)}s"
                                        else:
                                            eta = "--"
                                    # Update label every 0.5s or on finish
                                    if (
                                        now - last_update > 0.5
                                        or downloaded == total_size
                                    ):

                                        def update_speed_eta(s=speed, e=eta):
                                            self.speed_eta_var.set(
                                                f"Speed: {s}  ETA: {e}"
                                            )

                                        self.root.after(0, update_speed_eta)
                                        last_update = now

                        # Reset speed/eta label after file done
                        def clear_speed_eta():
                            self.speed_eta_var.set("Speed: --  ETA: --")

                        self.root.after(0, clear_speed_eta)
                    self.logger.info(f"Downloaded: {abs_url}")
                    return
                except Exception as e:
                    self.logger.error(
                        f"Failed to download {abs_url} (Attempt {attempt}): {e}"
                    )
                    if attempt < max_retries:
                        time.sleep(delay)
                        delay *= 2  # Exponential backoff
                    else:
                        self.logger.error(
                            f"Permanently failed to download {abs_url} after {max_retries} attempts."
                        )
                        skipped_files.add(abs_url)

        try:
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = [
                    executor.submit(download_file_task, *args) for args in download_args
                ]
                for future in as_completed(futures):
                    pass
        except KeyboardInterrupt:
            self.logger.warning(
                "Download interrupted by user. Waiting for threads to finish..."
            )
        return skipped_files, file_tree, all_files

    def setup_logger(self, log_dir):
        os.makedirs(log_dir, exist_ok=True)
        # Use a single fixed logfile to keep all runs in one canonical location.
        log_path = os.path.join(log_dir, "epstein_downloader.log")
        self.log_file = log_path
        self.logger = logging.getLogger("EpsteinFilesDownloader")
        self.logger.setLevel(logging.DEBUG)
        if self.logger.hasHandlers():
            self.logger.handlers.clear()
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        sh = logging.StreamHandler()
        sh.setLevel(logging.INFO)
        sh.setFormatter(formatter)
        self.logger.addHandler(sh)

        class StatusPaneHandler(logging.Handler):
            def __init__(self, gui):
                super().__init__()
                self.gui = gui

            def emit(self, record):
                msg = self.format(record)
                self.gui.append_status_pane(msg)

        status_handler = StatusPaneHandler(self)
        status_handler.setLevel(logging.INFO)
        status_handler.setFormatter(formatter)
        self.logger.addHandler(status_handler)
        self.logger.info(f"Logger initialized. logfile={log_path}")

    def thread_safe_status(self, msg):
        # Schedule status update on the main thread, safe for closed mainloop
        try:
            self.root.after(0, self.status.set, msg)
            self.append_status_pane(msg)
        except RuntimeError:
            pass

    def append_status_pane(self, msg):
        def append():
            try:
                if hasattr(self, "status_pane") and self.status_pane:
                    self.status_pane.configure(state="normal")
                    self.status_pane.insert("end", msg + "\n")
                    self.status_pane.see("end")
                    self.status_pane.configure(state="disabled")
            except RuntimeError:
                pass

        try:
            self.root.after(0, append)
        except RuntimeError:
            pass

    def create_widgets(self):
        # --- Modern Progress Bar Style ---
        style = ttk.Style()
        # Use a unique style name to avoid global side effects
        style.theme_use("clam")  # 'clam' is modern and cross-platform
        style.configure(
            "Modern.Horizontal.TProgressbar",
            troughcolor="#dfeffb" if not self.dark_mode else "#111217",
            bordercolor="#8fb5ff" if not self.dark_mode else "#2a2f36",
            background="#0078d7" if not self.dark_mode else "#2a6fb0",
            lightcolor="#5aa8ff" if not self.dark_mode else "#4e8fb8",
            darkcolor="#005bb5" if not self.dark_mode else "#134a75",
            thickness=20,
            relief="raised",
        )
        # For file progress, use a different color
        style.configure(
            "ModernFile.Horizontal.TProgressbar",
            troughcolor="#f0f9f0" if not self.dark_mode else "#141814",
            bordercolor="#9fe39a" if not self.dark_mode else "#25492b",
            background="#66c33a" if not self.dark_mode else "#5fa94c",
            lightcolor="#98e57a" if not self.dark_mode else "#7fb86a",
            darkcolor="#3b8a20" if not self.dark_mode else "#2f6b2f",
            thickness=14,
            relief="raised",
        )
        # Make window scalable
        self.root.geometry("1100x800")
        self.root.minsize(800, 600)
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        # Tabbed notebook for main UI and download history
        self._notebook = ttk.Notebook(self.root)
        self._notebook.grid(row=0, column=0, sticky="nsew")

        # Main tab (existing UI)
        main_tab = ttk.Frame(self._notebook)
        main_tab.grid_rowconfigure(0, weight=1)
        main_tab.grid_columnconfigure(0, weight=1)
        self._notebook.add(main_tab, text="Downloader")

        # ...existing code for main_tab, container, canvas, self.frame, etc...

        # ...existing code for main_tab, container, canvas, self.frame, etc...

        # Main tab content frame setup (must come before any reference to self.frame)
        container = ttk.Frame(main_tab)
        container.grid(row=0, column=0, sticky="nsew")
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        canvas = tk.Canvas(container)
        canvas.grid(row=0, column=0, sticky="nsew")
        vscroll = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        vscroll.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=vscroll.set)
        self.canvas = canvas
        self.frame = ttk.Frame(self.canvas)
        frame_id = self.canvas.create_window((0, 0), window=self.frame, anchor="nw")
        self._main_frame = self.frame  # Store reference for use in other methods

        def on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        self.frame.bind("<Configure>", on_frame_configure)

        def on_canvas_configure(event):
            canvas.itemconfig(frame_id, width=event.width)

        self.canvas.bind("<Configure>", on_canvas_configure)

        # Now set up Download History tab with search/filter
        self.history_tab = ttk.Frame(self._notebook)
        self.history_tab.grid_rowconfigure(1, weight=1)
        self.history_tab.grid_columnconfigure(0, weight=1)
        self._notebook.add(self.history_tab, text="Download History")

        # Search/filter bar
        filter_frame = ttk.Frame(self.history_tab)
        filter_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        ttk.Label(filter_frame, text="Filter:", font=("Segoe UI", 11)).pack(side="left")
        self.history_filter_var = tk.StringVar()
        filter_entry = ttk.Entry(
            filter_frame,
            textvariable=self.history_filter_var,
            width=40,
            font=("Segoe UI", 11),
        )
        filter_entry.pack(side="left", padx=(5, 0))
        filter_entry.bind("<KeyRelease>", lambda e: self.refresh_history_log())
        refresh_btn = ttk.Button(
            filter_frame, text="Refresh", command=self.refresh_history_log
        )
        refresh_btn.pack(side="left", padx=(10, 0))

        # Log viewer
        import tkinter.scrolledtext as st

        self.history_text = st.ScrolledText(
            self.history_tab,
            height=40,
            width=120,
            state="disabled",
            wrap="word",
            font=("Segoe UI", 11),
        )
        self.history_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.add_tooltip(self.history_text, "View the download and error log history.")
        self.refresh_history_log()

        # --- Main Downloader UI ---

        # Title
        title = ttk.Label(
            self.frame,
            text="Epstein Court Records Downloader",
            font=("Segoe UI", 26, "bold"),
        )
        title.grid(row=0, column=0, columnspan=4, pady=(10, 20), sticky="nsew")

        # --- Download Controls Group ---
        download_controls = ttk.LabelFrame(
            self.frame, text="Download Controls", padding=(15, 10)
        )
        download_controls.grid(
            row=1, column=0, columnspan=4, sticky="ew", padx=10, pady=(0, 15)
        )
        download_controls.columnconfigure(1, weight=1)
        download_controls.configure(labelanchor="n")
        concurrent_label = ttk.Label(
            download_controls, text="Concurrent Downloads:", font=("Segoe UI", 12)
        )
        concurrent_label.grid(row=0, column=0, sticky="e", padx=(0, 8), pady=5)
        concurrent_spin = ttk.Spinbox(
            download_controls,
            from_=1,
            to=32,
            textvariable=self.concurrent_downloads,
            width=5,
            increment=1,
            font=("Segoe UI", 12),
        )
        concurrent_spin.grid(row=0, column=1, sticky="w", pady=5)
        self.add_tooltip(
            concurrent_spin, "Set the number of concurrent downloads (threads)"
        )
        self.add_tooltip(
            concurrent_label, "Set the number of concurrent downloads (threads)"
        )

        # --- URL Management Group ---
        url_section = ttk.LabelFrame(self.frame, text="Download URLs", padding=(15, 10))
        url_section.grid(
            row=2, column=0, columnspan=4, sticky="ew", padx=10, pady=(0, 15)
        )
        url_section.columnconfigure(1, weight=1)
        url_section.configure(labelanchor="n")
        self.url_listbox = tk.Listbox(
            url_section, height=6, width=80, font=("Segoe UI", 11)
        )
        # Listbox spans the full width so it sits above both left controls and right-side area
        self.url_listbox.grid(
            row=0, column=0, columnspan=4, sticky="ew", padx=(0, 8), pady=5
        )
        self.url_listbox.delete(0, tk.END)
        for url in self.urls:
            self.url_listbox.insert(tk.END, url)
        self.add_tooltip(
            self.url_listbox,
            "List of URLs to download. Select to remove or view details.",
        )
        self.setup_url_listbox_context_menu()
        # Dark-mode visual adjustments for URL listbox
        try:
            if getattr(self, "dark_mode", False):
                self.url_listbox.configure(
                    bg="#1f1f1f",
                    fg="#ffffff",
                    selectbackground="#32414a",
                    selectforeground="#ffffff",
                    highlightthickness=1,
                    highlightbackground="#444",
                )
        except Exception:
            pass
        # URL entry and Add button span the full width (entry on left, Add on right)
        self.url_entry = ttk.Entry(url_section, width=60, font=("Segoe UI", 11))
        self.url_entry.grid(row=1, column=0, columnspan=3, sticky="ew", pady=5)
        add_url_btn = ttk.Button(url_section, text="Add URL", command=self.add_url)
        add_url_btn.grid(row=1, column=3, sticky="w", padx=(8, 0), pady=5)
        self.add_tooltip(add_url_btn, "Add a new download URL")
        self.add_tooltip(self.url_entry, "Paste a new URL and click 'Add URL'")

        # URL control buttons (exposed on self for tests/automation)
        # Create a left-aligned button-frame under the list; keep buttons on the left side
        url_btns_frame = ttk.Frame(url_section)
        url_btns_frame.grid(
            row=2, column=0, columnspan=3, sticky="w", padx=(0, 0), pady=5
        )

        self.remove_url_btn = ttk.Button(
            url_btns_frame, text="Remove URL", command=self.remove_url
        )
        self.remove_url_btn.pack(side="left", padx=(0, 6))
        self.add_tooltip(self.remove_url_btn, "Remove the selected URL from the list")

        self.move_up_btn = ttk.Button(
            url_btns_frame, text="Move Up", command=self.move_url_up
        )
        self.move_up_btn.pack(side="left", padx=(0, 6))
        self.add_tooltip(self.move_up_btn, "Move the selected URL up in the queue")

        self.move_down_btn = ttk.Button(
            url_btns_frame, text="Move Down", command=self.move_url_down
        )
        self.move_down_btn.pack(side="left", padx=(0, 6))
        self.add_tooltip(self.move_down_btn, "Move the selected URL down in the queue")

        self.clear_completed_btn = ttk.Button(
            url_btns_frame, text="Clear Completed", command=self.clear_completed_urls
        )
        self.clear_completed_btn.pack(side="left")
        self.add_tooltip(
            self.clear_completed_btn,
            "Remove all completed (already processed) URLs from the queue",
        )

        # Make these buttons consistent widths to improve visual layout
        try:
            url_labels = [
                self.remove_url_btn["text"],
                self.move_up_btn["text"],
                self.move_down_btn["text"],
                self.clear_completed_btn["text"],
            ]
            url_max = max(len(t) for t in url_labels)
            url_width = max(12, url_max + 4)
            for b in (
                self.remove_url_btn,
                self.move_up_btn,
                self.move_down_btn,
                self.clear_completed_btn,
            ):
                try:
                    b.config(width=url_width)
                except Exception:
                    pass
        except Exception:
            pass

        # --- Download Folder Group ---
        dir_section = ttk.LabelFrame(
            self.frame, text="Download Folder", padding=(15, 10)
        )
        dir_section.grid(
            row=3, column=0, columnspan=4, sticky="ew", padx=10, pady=(0, 15)
        )
        dir_section.columnconfigure(1, weight=1)
        dir_section.configure(labelanchor="n")
        dir_entry = ttk.Entry(
            dir_section, textvariable=self.base_dir, width=60, font=("Segoe UI", 11)
        )
        dir_entry.grid(row=0, column=0, sticky="ew", pady=5)
        # Expose directory browse button for testing/automation
        self.dir_btn = ttk.Button(dir_section, text="Browse", command=self.browse_dir)
        self.dir_btn.grid(row=0, column=1, sticky="w", padx=(8, 0), pady=5)
        self.add_tooltip(self.dir_btn, "Choose the download destination folder")
        self.add_tooltip(dir_entry, "Edit or paste the download folder path")
        # Ensure directory browse button has consistent width with URL controls
        try:
            self.dir_btn.config(width=url_width if "url_width" in locals() else 14)
        except Exception:
            pass

        # --- Action Buttons Group ---
        action_section = ttk.LabelFrame(self.frame, text="Actions", padding=(15, 10))
        action_section.grid(
            row=4, column=0, columnspan=4, sticky="ew", padx=10, pady=(0, 15)
        )
        action_section.configure(labelanchor="n")

        # Small helper to load icons from assets and keep references
        def load_icon(name):
            # Prefer assets relative to this script, fall back to current working directory
            possible_dirs = [
                os.path.join(os.path.dirname(__file__), "assets"),
                os.path.join(os.getcwd(), "assets"),
            ]
            for d in possible_dirs:
                for ext in (".png", ".gif", ".ico"):
                    p = os.path.join(d, name + ext)
                    if os.path.exists(p):
                        # Prefer Pillow so we can normalise backgrounds to transparent
                        try:
                            from PIL import Image, ImageTk

                            pil_img = Image.open(p).convert("RGBA")
                            # If the image has a solid corner color, make that color transparent
                            try:
                                # Compute a representative background color from the image corners (5x5 area)
                                w, h = pil_img.size
                                samples = []
                                # sample small boxes at each corner
                                box = 5
                                corners = [
                                    (0, 0, min(box, w), min(box, h)),
                                    (max(0, w - box), 0, w, min(box, h)),
                                    (0, max(0, h - box), min(box, w), h),
                                    (max(0, w - box), max(0, h - box), w, h),
                                ]
                                for cx1, cy1, cx2, cy2 in corners:
                                    for px in range(cx1, cx2):
                                        for py in range(cy1, cy2):
                                            pix = pil_img.getpixel((px, py))
                                            # pix is (r,g,b,a) from RGBA; ignore fully/mostly transparent samples
                                            try:
                                                if len(pix) == 4 and pix[3] > 16:
                                                    samples.append(pix[:3])
                                            except Exception:
                                                # fallback if pixel tuple unexpected
                                                samples.append(pix[:3])
                                # Only use corner samples if we found any non-transparent pixels
                                if samples:
                                    # median to be robust against noise
                                    import statistics

                                    bg_r = int(
                                        statistics.median([s[0] for s in samples])
                                    )
                                    bg_g = int(
                                        statistics.median([s[1] for s in samples])
                                    )
                                    bg_b = int(
                                        statistics.median([s[2] for s in samples])
                                    )
                                    bg = (bg_r, bg_g, bg_b)
                                    # Threshold for color distance — tuned to tolerate antialiasing
                                    thresh = 60

                                    def color_dist(c1, c2):
                                        return (
                                            (c1[0] - c2[0]) ** 2
                                            + (c1[1] - c2[1]) ** 2
                                            + (c1[2] - c2[2]) ** 2
                                        ) ** 0.5

                                    datas = list(pil_img.getdata())
                                    new_data = []
                                    for item in datas:
                                        r, g, b, a = item
                                        if a == 0:
                                            new_data.append((r, g, b, a))
                                            continue
                                        if color_dist((r, g, b), bg) <= thresh:
                                            # make fully transparent
                                            new_data.append((r, g, b, 0))
                                        else:
                                            new_data.append((r, g, b, a))
                                    pil_img.putdata(new_data)
                            except Exception:
                                pass
                            # Better approach: tint icons using their alpha channel so detail/antialiasing
                            # is preserved. Create a solid-color image and use the original alpha as mask.
                            try:
                                use_white = getattr(self, "dark_mode", False)
                                fg = (255, 255, 255) if use_white else (0, 0, 0)
                                # target size slightly smaller for less bulky icons
                                target_size = (16, 16)
                                # Ensure we have an alpha mask
                                mask = (
                                    pil_img.split()[3]
                                    if pil_img.mode == "RGBA"
                                    else None
                                )
                                try:
                                    pil_img = pil_img.resize(target_size, Image.LANCZOS)
                                    if mask is not None:
                                        mask = mask.resize(target_size, Image.LANCZOS)
                                except Exception:
                                    pass
                                try:
                                    colored = Image.new("RGBA", target_size, fg + (0,))
                                    # paste foreground color where alpha channel indicates opacity
                                    colored.paste(fg + (255,), (0, 0), mask)
                                    pil_img = colored
                                except Exception:
                                    pass
                                # If resulting image is mostly transparent (tinting removed detail),
                                # create a simple vector fallback for important icons (pause/stop)
                                try:
                                    datas2 = list(pil_img.getdata())
                                    opaque_pixels = sum(
                                        1 for (_, _, _, a) in datas2 if a > 16
                                    )
                                    total = len(datas2) if datas2 else 1
                                    if float(opaque_pixels) / float(total) < 0.05:
                                        # too few opaque pixels, draw fallback
                                        from PIL import ImageDraw

                                        def make_fallback(nm, size, color):
                                            img = Image.new("RGBA", size, (0, 0, 0, 0))
                                            draw = ImageDraw.Draw(img)
                                            w, h = size
                                            pad = max(2, w // 8)
                                            if nm == "pause":
                                                bw = max(2, (w - pad * 3) // 4)
                                                x1 = pad
                                                x2 = x1 + bw
                                                draw.rectangle(
                                                    [x1, pad, x2, h - pad],
                                                    fill=color + (255,),
                                                )
                                                x1 = x2 + pad
                                                x2 = x1 + bw
                                                draw.rectangle(
                                                    [x1, pad, x2, h - pad],
                                                    fill=color + (255,),
                                                )
                                            elif nm == "stop":
                                                draw.rectangle(
                                                    [pad, pad, w - pad, h - pad],
                                                    fill=color + (255,),
                                                )
                                            elif nm == "start":
                                                # triangle
                                                draw.polygon(
                                                    [
                                                        (pad, pad),
                                                        (w - pad, h // 2),
                                                        (pad, h - pad),
                                                    ],
                                                    fill=color + (255,),
                                                )
                                            else:
                                                draw.ellipse(
                                                    [pad, pad, w - pad, h - pad],
                                                    fill=color + (255,),
                                                )
                                            return img

                                        basename = name.lower()
                                        if basename in ("pause", "stop", "start"):
                                            pil_img = make_fallback(
                                                basename, target_size, fg
                                            )
                                except Exception:
                                    pass
                            except Exception:
                                pass
                            img = ImageTk.PhotoImage(pil_img, master=self.root)
                            self._images[name] = img
                            return img
                        except Exception:
                            # If Pillow isn't available or fails, fall back to Tk's PhotoImage
                            try:
                                img = tk.PhotoImage(master=self.root, file=p)
                                self._images[name] = img
                                return img
                            except Exception:
                                # Final fallback: neutral placeholder
                                try:
                                    placeholder = tk.PhotoImage(
                                        master=self.root, width=16, height=16
                                    )
                                    placeholder.put(("#cccccc",), to=(0, 0, 16, 16))
                                    self._images[name] = placeholder
                                    return placeholder
                                except Exception:
                                    continue
            return None

        start_icon = load_icon("start")
        pause_icon = load_icon("pause")
        resume_icon = load_icon("resume")
        schedule_icon = load_icon("schedule")
        json_icon = load_icon("json")
        skipped_icon = load_icon("skipped")

        self.download_btn = ttk.Button(
            action_section,
            text="Start Download",
            command=self.start_download_all_thread,
            image=start_icon,
            compound="left",
        )
        self.download_btn.grid(row=0, column=0, pady=5, padx=(0, 8), sticky="ew")
        try:
            self.download_btn.bind(
                "<Button-1>", lambda e: self.log_button_event("Start Download", e)
            )
        except Exception:
            pass
        self.add_tooltip(
            self.download_btn,
            "Start downloading all files from the URLs above (runs in background, UI stays responsive)",
        )
        self.pause_btn = ttk.Button(
            action_section,
            text="Pause",
            command=self.pause_downloads,
            image=pause_icon,
            compound="left",
        )
        self.pause_btn.grid(row=0, column=1, pady=5, padx=(0, 8), sticky="ew")
        try:
            self.pause_btn.bind(
                "<Button-1>", lambda e: self.log_button_event("Pause", e)
            )
        except Exception:
            pass
        self.add_tooltip(self.pause_btn, "Pause all downloads in progress.")
        self.resume_btn = ttk.Button(
            action_section,
            text="Resume",
            command=self.resume_downloads,
            state="disabled",
            image=resume_icon,
            compound="left",
        )
        self.resume_btn.grid(row=0, column=2, pady=5, padx=(0, 8), sticky="ew")
        try:
            self.resume_btn.bind(
                "<Button-1>", lambda e: self.log_button_event("Resume", e)
            )
        except Exception:
            pass
        self.add_tooltip(self.resume_btn, "Resume paused downloads.")
        self.schedule_btn = ttk.Button(
            action_section,
            text="Schedule",
            command=self.open_schedule_window,
            image=schedule_icon,
            compound="left",
        )
        self.schedule_btn.grid(row=0, column=3, pady=5, padx=(0, 8), sticky="ew")
        self.add_tooltip(
            self.schedule_btn, "Schedule downloads for specific days and times"
        )
        self.json_btn = ttk.Button(
            action_section,
            text="Show Downloaded JSON",
            command=self.show_json,
            image=json_icon,
            compound="left",
        )
        self.json_btn.grid(row=1, column=0, pady=5, padx=(0, 8), sticky="ew")
        self.add_tooltip(self.json_btn, "Show the JSON file of downloaded files")
        self.skipped_btn = ttk.Button(
            action_section,
            text="Show Skipped Files",
            command=self.show_skipped,
            image=skipped_icon,
            compound="left",
        )
        self.skipped_btn.grid(row=1, column=1, pady=5, padx=(0, 8), sticky="ew")
        self.add_tooltip(
            self.skipped_btn,
            "Show files that were skipped (already exist or duplicate)",
        )

        # Stop / Enable scans controls
        stop_icon = load_icon("stop")
        self.stop_scan_btn = ttk.Button(
            action_section,
            text="Stop",
            command=self.stop_all,
            image=stop_icon,
            compound="left",
        )
        self.stop_scan_btn.grid(row=1, column=2, pady=5, padx=(0, 8), sticky="ew")
        try:
            self.stop_scan_btn.bind(
                "<Button-1>", lambda e: self.log_button_event("Stop", e)
            )
        except Exception:
            pass
        self.add_tooltip(
            self.stop_scan_btn,
            "Stop all activity: downloads, scans, and background workers",
        )
        self.enable_scan_btn = ttk.Button(
            action_section,
            text="Enable Scans",
            command=self.enable_scans,
            state="disabled",
        )
        self.enable_scan_btn.grid(row=1, column=3, pady=5, padx=(0, 8), sticky="ew")
        try:
            self.enable_scan_btn.bind(
                "<Button-1>", lambda e: self.log_button_event("Enable Scans", e)
            )
        except Exception:
            pass
        self.add_tooltip(
            self.enable_scan_btn, "Re-enable scanning and resume activity (undo Stop)"
        )
        # keep a reference to the original handler so we can restore it after a Reset
        try:
            self._orig_enable_scan_cmd = (
                self.enable_scan_btn["command"]
                if "command" in self.enable_scan_btn.keys()
                else self.enable_scans
            )
        except Exception:
            self._orig_enable_scan_cmd = self.enable_scans

        # --- Progress Section ---
        progress_section = ttk.LabelFrame(self.frame, text="Progress", padding=(15, 10))
        progress_section.grid(
            row=5, column=0, columnspan=4, sticky="ew", padx=10, pady=(0, 15)
        )
        progress_section.configure(labelanchor="n")
        progress_label = ttk.Label(
            progress_section, text="Overall Progress:", font=("Segoe UI", 12)
        )
        progress_label.grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.add_tooltip(progress_label, "Shows the overall download progress.")
        self.progress = ttk.Progressbar(
            progress_section,
            orient="horizontal",
            length=400,
            mode="determinate",
            style="Modern.Horizontal.TProgressbar",
        )
        self.progress.grid(row=0, column=1, columnspan=3, pady=(0, 5), sticky="ew")
        self.add_tooltip(self.progress, "Overall progress for all downloads.")
        file_progress_label = ttk.Label(
            progress_section, text="Current File:", font=("Segoe UI", 12)
        )
        file_progress_label.grid(row=1, column=0, sticky="w", pady=(0, 5))
        self.file_progress = ttk.Progressbar(
            progress_section,
            orient="horizontal",
            length=400,
            mode="determinate",
            style="ModernFile.Horizontal.TProgressbar",
        )
        self.file_progress.grid(row=1, column=1, columnspan=3, pady=(0, 5), sticky="ew")
        self.add_tooltip(
            self.file_progress, "Progress for the current file being downloaded."
        )
        self.speed_eta_var = tk.StringVar(value="Speed: -- ETA: --")
        self.speed_eta_label = ttk.Label(
            progress_section, textvariable=self.speed_eta_var, font=("Segoe UI", 11)
        )
        self.speed_eta_label.grid(
            row=2, column=0, columnspan=4, sticky="w", pady=(0, 5)
        )
        self.add_tooltip(
            self.speed_eta_label,
            "Shows current download speed and estimated time remaining for the current file.",
        )
        # Animated spinner (hidden by default) to indicate active downloads
        # Two small balls (blue and red) orbiting to create a lively spinner
        # Determine a safe background color from ttk style, fallback to light/dark defaults
        style = ttk.Style()
        bg = (
            style.lookup("TLabelFrame", "background")
            or style.lookup("TFrame", "background")
            or ("#111217" if self.dark_mode else "#f0f0f0")
        )
        self._spinner_canvas = tk.Canvas(
            progress_section, width=32, height=32, highlightthickness=0, bg=bg
        )
        # center and orbit radius
        self._spinner_cx = 16
        self._spinner_cy = 16
        self._spinner_r = 10
        # initial angle
        import math

        a1 = 0
        a2 = math.pi
        # ball size
        bsize = 6
        x1 = int(self._spinner_cx + self._spinner_r * math.cos(a1))
        y1 = int(self._spinner_cy + self._spinner_r * math.sin(a1))
        x2 = int(self._spinner_cx + self._spinner_r * math.cos(a2))
        y2 = int(self._spinner_cy + self._spinner_r * math.sin(a2))
        # Determine outline for dark mode so colored balls remain readable
        try:
            _outline_col = "#ffffff" if getattr(self, "dark_mode", False) else ""
            _outline_w = 1 if getattr(self, "dark_mode", False) else 0
        except Exception:
            _outline_col = ""
            _outline_w = 0
        self._spinner_ball1 = self._spinner_canvas.create_oval(
            x1 - bsize // 2,
            y1 - bsize // 2,
            x1 + bsize // 2,
            y1 + bsize // 2,
            fill="#0078d7",
            outline=_outline_col,
            width=_outline_w,
        )
        self._spinner_ball2 = self._spinner_canvas.create_oval(
            x2 - bsize // 2,
            y2 - bsize // 2,
            x2 + bsize // 2,
            y2 + bsize // 2,
            fill="#d9483f",
            outline=_outline_col,
            width=_outline_w,
        )
        self._spinner_canvas.grid(row=0, column=4, rowspan=3, padx=(8, 0), sticky="e")
        self._spinner_running = False
        self._spinner_angle = 0.0
        self._spinner_job = None
        # Hide spinner initially
        try:
            self._spinner_canvas.grid_remove()
        except Exception:
            pass

        # --- Status Pane Group ---
        import tkinter.scrolledtext as st

        status_section = ttk.LabelFrame(self.frame, text="Status Log", padding=(15, 10))
        status_section.grid(
            row=6, column=0, columnspan=4, sticky="nsew", padx=10, pady=(0, 15)
        )
        status_section.configure(labelanchor="n")
        status_pane_label = ttk.Label(
            status_section, text="Status Pane:", font=("Segoe UI", 12)
        )
        status_pane_label.grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.add_tooltip(status_pane_label, "Shows log messages and status updates.")
        self.status_pane = st.ScrolledText(
            status_section,
            height=10,
            width=100,
            state="disabled",
            wrap="word",
            font=("Segoe UI", 11),
        )
        self.status_pane.grid(row=1, column=0, columnspan=4, sticky="nsew", pady=(0, 5))
        self.add_tooltip(
            self.status_pane,
            "Log and status output. Shows download progress, errors, and info.",
        )
        self.status_pane_visible = True

        # Dark-mode styling for status pane (lighter black background, white text)
        try:
            if getattr(self, "dark_mode", False):
                self.status_pane.configure(
                    background="#1f1f1f",
                    foreground="#ffffff",
                    insertbackground="#ffffff",
                )
        except Exception:
            pass

        # Make widgets expand with window
        for i in range(4):
            self.frame.columnconfigure(i, weight=1)
        for i in range(7):
            self.frame.rowconfigure(i, weight=0)
        self.frame.rowconfigure(6, weight=1)

        # Store references for toggling log panel
        self._main_canvas = self.canvas
        self._main_frame = self.frame

        # Persistent Status Bar (bottom of window) with summary
        self.summary_var = tk.StringVar(value="Queued: 0 | Completed: 0 | Failed: 0")
        status_frame = ttk.Frame(self.root)
        status_frame.grid(row=1, column=0, sticky="ew")
        status_frame.columnconfigure(1, weight=1)
        # Bottom status labels: use explicit colors in dark mode for contrast
        try:
            if getattr(self, "dark_mode", False):
                self.status_bar = tk.Label(
                    status_frame,
                    textvariable=self.status,
                    relief=tk.SUNKEN,
                    anchor="w",
                    foreground="#7fbcff",
                    background="#111217",
                )
                self.summary_bar = tk.Label(
                    status_frame,
                    textvariable=self.summary_var,
                    relief=tk.SUNKEN,
                    anchor="e",
                    foreground="#7fe57a",
                    background="#111217",
                )
            else:
                self.status_bar = tk.Label(
                    status_frame,
                    textvariable=self.status,
                    relief=tk.SUNKEN,
                    anchor="w",
                    foreground="blue",
                )
                self.summary_bar = tk.Label(
                    status_frame,
                    textvariable=self.summary_var,
                    relief=tk.SUNKEN,
                    anchor="e",
                    foreground="green",
                )
        except Exception:
            self.status_bar = tk.Label(
                status_frame, textvariable=self.status, relief=tk.SUNKEN, anchor="w"
            )
            self.summary_bar = tk.Label(
                status_frame,
                textvariable=self.summary_var,
                relief=tk.SUNKEN,
                anchor="e",
            )
        self.status_bar.grid(row=0, column=0, sticky="ew")
        self.summary_bar.grid(row=0, column=1, sticky="ew")
        self.add_tooltip(
            self.status_bar, "Persistent status bar. Shows the latest status message."
        )
        self.add_tooltip(self.summary_bar, "Summary: queued, completed, failed counts.")

        # Quit and Dark Mode buttons (always visible, bottom row of main frame)
        quit_btn = ttk.Button(self.frame, text="Quit", command=self.force_quit)
        quit_btn.grid(row=13, column=0, sticky="w", pady=(10, 0))
        self.add_tooltip(quit_btn, "Force quit the application immediately")
        dark_btn = ttk.Button(
            self.frame, text="Toggle Dark Mode", command=self.toggle_dark_mode
        )
        dark_btn.grid(row=13, column=3, sticky="e", pady=(10, 0))
        self.add_tooltip(dark_btn, "Switch between light and dark mode")
        # Quick Help button and F1 binding
        help_quick = ttk.Button(
            self.frame, text="Help / About", command=self.show_help_dialog
        )
        help_quick.grid(row=13, column=1, sticky="e", pady=(10, 0))
        self.add_tooltip(help_quick, "Open Help and About")
        try:
            self.root.bind("<F1>", lambda e: self.show_help_dialog())
        except Exception:
            pass

    def update_summary_bar(self, queued=None, completed=None, failed=None):
        # Update the summary bar with current counts
        if not hasattr(self, "_summary_counts"):
            self._summary_counts = {"queued": 0, "completed": 0, "failed": 0}
        if queued is not None:
            self._summary_counts["queued"] = queued
        if completed is not None:
            self._summary_counts["completed"] = completed
        if failed is not None:
            self._summary_counts["failed"] = failed
        self.summary_var.set(
            f"Queued: {self._summary_counts['queued']} | Completed: {self._summary_counts['completed']} | Failed: {self._summary_counts['failed']}"
        )

        # Make widgets expand with window
        for i in range(4):
            self.frame.columnconfigure(i, weight=1)
        for i in range(14):
            self.frame.rowconfigure(i, weight=0)
        self.frame.rowconfigure(12, weight=1)
        # Store references for toggling log panel
        self._main_canvas = self.canvas
        self._main_frame = self.frame

    def clear_completed_urls(self):
        """Remove all URLs that have already been processed from the queue and listbox."""
        count = getattr(self, "processed_count", 0)
        if count > 0:
            self.urls = self.urls[count:]
            # Remove from listbox
            for i in range(count - 1, -1, -1):
                self.url_listbox.delete(i)
            self.processed_count = 0
            self.save_queue_state()
            self.logger.info("Cleared completed URLs from the queue.")

        # Download history log viewer (ScrolledText)
        import tkinter.scrolledtext as st

        self.history_text = st.ScrolledText(
            self.history_tab, height=40, width=120, state="disabled", wrap="word"
        )
        self.history_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.add_tooltip(self.history_text, "View the download and error log history.")
        refresh_btn = ttk.Button(
            self.history_tab, text="Refresh Log", command=self.refresh_history_log
        )
        refresh_btn.pack(pady=5)
        self.add_tooltip(refresh_btn, "Reload the log file contents.")
        self.refresh_history_log()

    def refresh_history_log(self):
        """Refresh the download history log viewer tab, with optional filtering."""
        log_path = getattr(self, "log_file", None)
        filter_text = getattr(self, "history_filter_var", None)
        filter_val = filter_text.get().strip().lower() if filter_text else ""
        if not log_path or not os.path.exists(log_path):
            self.history_text.configure(state="normal")
            self.history_text.delete("1.0", tk.END)
            self.history_text.insert(
                tk.END, "No log file found or logging not started yet."
            )
            self.history_text.configure(state="disabled")
            return
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            if filter_val:
                lines = [line for line in lines if filter_val in line.lower()]
            log_content = "".join(lines)
            self.history_text.configure(state="normal")
            self.history_text.delete("1.0", tk.END)
            self.history_text.insert(tk.END, log_content)
            self.history_text.configure(state="disabled")
        except Exception as e:
            self.history_text.configure(state="normal")
            self.history_text.delete("1.0", tk.END)
            self.history_text.insert(tk.END, f"Failed to read log file: {e}")
            self.history_text.configure(state="disabled")

    def pause_downloads(self):
        """Pause all downloads and background activity."""
        try:
            # Log entry state and stack trace
            try:
                import traceback

                stack = "".join(traceback.format_stack())
                self.logger.debug(
                    f"pause_downloads() called. _is_paused={getattr(self, '_is_paused', None)}, _pause_event_is_set={getattr(self, '_pause_event').is_set() if hasattr(self, '_pause_event') else 'NA'}, _scans_disabled={getattr(self, '_scans_disabled', None)}, _scanning={getattr(self, '_scanning', False)}"
                )
                self.logger.debug(f"pause_downloads() call stack:\n{stack}")
            except Exception:
                self.logger.debug(
                    "pause_downloads() called. (failed to read some internal state)"
                )
            if not getattr(self, "_is_paused", False):
                self._pause_event.clear()
                self._is_paused = True
                self.status.set("Paused. Click Resume to continue.")
                # Disable pause to avoid repeats; enable resume
                try:
                    self.pause_btn.config(state="disabled", text="Paused")
                    # swap icon to paused variant if available
                    if "pause" in self._images:
                        self.pause_btn.config(image=self._images.get("pause"))
                    self.resume_btn.config(state="normal")
                except Exception:
                    self.logger.exception(
                        "Failed to update pause/resume button states in pause_downloads"
                    )
                try:
                    self.logger.info("Pausing all activity (user request).")
                except Exception:
                    pass
                self.thread_safe_status("All activity paused.")
            else:
                self.logger.info("pause_downloads() called but already paused.")
            # Log exit state
            try:
                self.logger.debug(
                    f"pause_downloads() exit. _is_paused={getattr(self, '_is_paused', None)}, _pause_event_is_set={getattr(self, '_pause_event').is_set() if hasattr(self, '_pause_event') else 'NA'}, pause_btn_state={self.pause_btn.cget('state') if hasattr(self, 'pause_btn') else 'NA'}, resume_btn_state={self.resume_btn.cget('state') if hasattr(self, 'resume_btn') else 'NA'}"
                )
            except Exception:
                self.logger.debug(
                    "pause_downloads() exit. (failed to read some UI state)"
                )
        except Exception as e:
            self.logger.exception(f"Exception in pause_downloads: {e}")

    def resume_downloads(self):
        """Resume paused downloads."""
        try:
            # Log entry state and stack trace
            try:
                import traceback

                stack = "".join(traceback.format_stack())
                self.logger.debug(
                    f"resume_downloads() called. _is_paused={getattr(self, '_is_paused', None)}, _pause_event_is_set={getattr(self, '_pause_event').is_set() if hasattr(self, '_pause_event') else 'NA'}"
                )
                self.logger.debug(f"resume_downloads() call stack:\n{stack}")
            except Exception:
                self.logger.debug(
                    "resume_downloads() called. (failed to read some internal state)"
                )
            if getattr(self, "_is_paused", False):
                self._pause_event.set()
                self._is_paused = False
                # Clear any stop request so activity may continue
                try:
                    if getattr(self, "_stop_event", None):
                        self._stop_event.clear()
                    self._is_stopped = False
                except Exception:
                    pass
                # Also re-enable scanning when resuming
                try:
                    self._scans_disabled = False
                    try:
                        self.stop_scan_btn.config(state="normal")
                    except Exception:
                        pass
                    try:
                        self.enable_scan_btn.config(state="disabled")
                    except Exception:
                        pass
                except Exception:
                    pass
                self.status.set("Resumed. Downloads continuing.")
                try:
                    self.pause_btn.config(state="normal", text="Pause")
                    # restore pause icon
                    if "pause" in self._images:
                        self.pause_btn.config(image=self._images.get("pause"))
                    self.resume_btn.config(state="disabled")
                except Exception:
                    self.logger.exception(
                        "Failed to update pause/resume button states in resume_downloads"
                    )
                try:
                    self.logger.info("Resumed all activity (user request).")
                except Exception:
                    pass
                self.thread_safe_status("Resumed all activity.")
            else:
                self.logger.info("resume_downloads() called but not currently paused.")
            # Log exit state
            try:
                self.logger.debug(
                    f"resume_downloads() exit. _is_paused={getattr(self, '_is_paused', None)}, _pause_event_is_set={getattr(self, '_pause_event').is_set() if hasattr(self, '_pause_event') else 'NA'}, pause_btn_state={self.pause_btn.cget('state') if hasattr(self, 'pause_btn') else 'NA'}, resume_btn_state={self.resume_btn.cget('state') if hasattr(self, 'resume_btn') else 'NA'}"
                )
            except Exception:
                self.logger.debug(
                    "resume_downloads() exit. (failed to read some UI state)"
                )
        except Exception as e:
            self.logger.exception(f"Exception in resume_downloads: {e}")

    def remove_url(self):
        selection = self.url_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        self.url_listbox.delete(index)
        del self.urls[index]

    def force_quit(self):
        import os

        os._exit(0)

    def add_tooltip(self, widget, text):
        # Improved tooltip implementation: always destroys on leave, never stacks
        def on_enter(event):
            # Destroy any existing tooltip first
            if hasattr(self, "tooltip") and self.tooltip is not None:
                try:
                    self.tooltip.destroy()
                except Exception:
                    pass
                self.tooltip = None
            self.tooltip = tk.Toplevel(widget)
            self.tooltip.wm_overrideredirect(True)
            x = widget.winfo_rootx() + 20
            y = widget.winfo_rooty() + 20
            self.tooltip.wm_geometry(f"+{x}+{y}")
            label = tk.Label(
                self.tooltip,
                text=text,
                background="#333",
                foreground="#fff",
                relief="solid",
                borderwidth=1,
                font=("Segoe UI", 9),
            )
            label.pack(ipadx=4, ipady=2)

        def on_leave(event):
            if hasattr(self, "tooltip") and self.tooltip is not None:
                try:
                    self.tooltip.destroy()
                except Exception:
                    pass
                self.tooltip = None

        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)

    def add_url(self):
        url = self.url_entry.get().strip()
        if url and url not in self.urls:
            self.urls.append(url)
            self.url_listbox.insert(tk.END, url)
            self.url_entry.delete(0, tk.END)

    def browse_dir(self):
        folder = filedialog.askdirectory()
        if folder:
            self.base_dir.set(folder)

    def show_json(self):
        json_path = os.path.join(self.base_dir.get(), "epstein_file_tree.json")
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as jf:
                    try:
                        obj = json.load(jf)
                        data = json.dumps(obj, indent=2)
                    except Exception:
                        # If not valid JSON, show a truncated preview
                        jf.seek(0)
                        raw = jf.read()
                        data = (
                            raw
                            if len(raw) < 10000
                            else raw[:10000] + "\n\n...[truncated]"
                        )
                self.show_popup("Downloaded Files JSON", data)
            except Exception as e:
                self.logger.error(f"Failed to show JSON: {e}", exc_info=True)
                self.show_popup(
                    "Downloaded Files JSON", f"Failed to read JSON file: {e}"
                )

    def show_skipped(self):
        if self.skipped_files:
            self.show_popup("Skipped Files", "\n".join(self.skipped_files))
        else:
            self.show_popup("Skipped Files", "No skipped files yet.")

    def show_popup(self, title, content):
        popup = tk.Toplevel(self.root)
        popup.title(title)
        text = tk.Text(popup, wrap="word", width=100, height=30)
        text.insert(tk.END, content)
        text.pack(fill=tk.BOTH, expand=True)
        close_btn = ttk.Button(popup, text="Close", command=popup.destroy)
        close_btn.pack(pady=5)

    def open_schedule_window(self):
        win = tk.Toplevel(self.root)
        win.title("Schedule Download")
        ttk.Label(win, text="Days (comma separated, e.g. Mon,Wed,Fri):").pack(
            anchor=tk.W
        )
        days_entry = ttk.Entry(win)
        days_entry.pack(fill=tk.X)
        ttk.Label(win, text="Time (24h, e.g. 14:30):").pack(anchor=tk.W)
        time_entry = ttk.Entry(win)
        time_entry.pack(fill=tk.X)

        def set_schedule():
            days = [
                d.strip().capitalize() for d in days_entry.get().split(",") if d.strip()
            ]
            t = time_entry.get().strip()
            if not days or not t:
                messagebox.showerror("Error", "Please enter days and time.")
                return
            self.schedule_download(days, t)
            win.destroy()

        ttk.Button(win, text="Set Schedule", command=set_schedule).pack(pady=5)

    def schedule_download(self, days, t):
        self.scheduled = True

        def check_and_run():
            while self.scheduled:
                now = datetime.now()
                day = now.strftime("%a")
                cur_time = now.strftime("%H:%M")
                if day in days and cur_time == t:
                    self.start_download_thread()
                    time.sleep(60)  # avoid double run in the same minute
                time.sleep(10)

        threading.Thread(target=check_and_run, daemon=True).start()

    def start_download_thread(self):
        self.logger.debug("start_download_thread called.")
        # Start the download queue in a background thread
        self._download_queue = None  # Will be set in process_download_queue
        # Keep a reference to allow graceful shutdown
        import threading

        self._process_thread = threading.Thread(
            target=self.process_download_queue, daemon=True
        )
        self._process_thread.start()

    def add_url_dynamic(self, url):
        """Add a URL to the download queue during download."""
        if hasattr(self, "_download_queue") and self._download_queue is not None:
            self._download_queue.put(url)
            self.urls.append(url)
            self.url_listbox.insert(tk.END, url)
            self.logger.info(f"Dynamically added URL to queue: {url}")
        else:
            self.add_url()

    def remove_url_dynamic(self, url):
        """Remove a URL from the download queue during download."""
        if url in self.urls:
            self.urls.remove(url)
            # Remove from listbox
            idxs = [
                i for i, u in enumerate(self.url_listbox.get(0, tk.END)) if u == url
            ]
            for idx in reversed(idxs):
                self.url_listbox.delete(idx)
            self.logger.info(f"Dynamically removed URL: {url}")
        # Note: If already in queue, it will be skipped in process_download_queue

    def process_download_queue(self):
        # Track summary counts
        self.update_summary_bar(queued=len(self.urls), completed=0, failed=0)
        """
        Implements a download queue system. Each URL is queued and processed in order, with progress bar updates.
        Allows dynamic add/remove of URLs during download. Skips duplicate files.
        """
        import queue

        self.thread_safe_status("Preparing download queue...")
        url_queue = queue.Queue()
        seen_urls = set()
        for url in self.urls:
            if url not in seen_urls:
                url_queue.put(url)
                seen_urls.add(url)
        self._download_queue = url_queue
        base_dir = self.base_dir.get()
        os.makedirs(base_dir, exist_ok=True)
        self.setup_logger(base_dir)
        total = url_queue.qsize()
        self.progress["maximum"] = total
        self.progress["value"] = 0
        self.logger.info(f"Download queue started. {total} URLs queued.")
        processed = getattr(self, "processed_count", 0)
        downloaded_files = set()
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                failed_count = 0
                while not url_queue.empty():
                    # Pause support (allow stop to break out)
                    while not self._pause_event.is_set():
                        if (
                            getattr(self, "_stop_event", None)
                            and self._stop_event.is_set()
                        ):
                            try:
                                self.logger.info(
                                    "Stop requested; exiting download queue loop."
                                )
                            except Exception:
                                pass
                            return
                        time.sleep(0.1)
                    # Also check stop again before dequeuing and processing
                    if getattr(self, "_stop_event", None) and self._stop_event.is_set():
                        try:
                            self.logger.info(
                                "Stop requested; breaking out of download queue."
                            )
                        except Exception:
                            pass
                        break
                    url = url_queue.get()
                    if url in seen_urls:
                        # Already processed (from dynamic add)
                        continue
                    seen_urls.add(url)
                    self.thread_safe_status(f"Processing: {url}")
                    try:
                        if url.startswith("https://drive.google.com/drive/folders/"):
                            credentials_path = self.config.get("credentials_path", None)
                            gdrive_dir = os.path.join(base_dir, "GoogleDrive")
                            self.logger.info(f"Processing Google Drive folder: {url}")
                            self.download_gdrive_with_fallback(
                                url, gdrive_dir, credentials_path
                            )
                        else:
                            self.logger.info(f"Visiting: {url}")
                            # Check for duplicate files before download
                            s, t, a = self.download_files_threaded(
                                page,
                                url,
                                base_dir,
                                skipped_files=self.skipped_files,
                                file_tree=self.file_tree,
                            )
                            # Only add files that are not already downloaded
                            for f in t.values():
                                for file_path in f:
                                    if file_path in downloaded_files:
                                        self.logger.info(
                                            f"Skipping duplicate file: {file_path}"
                                        )
                                    else:
                                        downloaded_files.add(file_path)
                            self.skipped_files.update(s or set())
                            self.file_tree.update(t or {})
                        url_queue.task_done()
                        processed += 1
                        self.processed_count = processed
                        self.progress["value"] = processed
                        self.update_summary_bar(
                            queued=url_queue.qsize(),
                            completed=processed,
                            failed=failed_count,
                        )
                        self.root.update_idletasks()
                        self.save_queue_state()
                    except Exception as e:
                        failed_count += 1
                        self.update_summary_bar(
                            queued=url_queue.qsize(),
                            completed=processed,
                            failed=failed_count,
                        )
                        self.logger.error(
                            f"Exception processing {url}: {e}", exc_info=True
                        )
                browser.close()
        except Exception as e:
            self.logger.error(f"Exception in download queue: {e}", exc_info=True)
        self.progress["value"] = total
        self.update_summary_bar(queued=0, completed=processed, failed=failed_count)
        self.root.update_idletasks()
        self.logger.info("All downloads in queue complete.")
        self.thread_safe_status("All downloads in queue complete.")
        messagebox.showinfo(
            "Download Complete",
            "All downloads in the queue are complete. See the log for details.",
        )

    def download_gdrive_folder(self, folder_url, output_dir):
        import gdown
        import logging

        logger = (
            self.logger
            if hasattr(self, "logger") and self.logger
            else logging.getLogger()
        )
        os.makedirs(output_dir, exist_ok=True)
        logger.info(
            f"Starting Google Drive folder download: {folder_url} to {output_dir}"
        )
        try:
            logger.info(
                f"Listing subfolders and files in Google Drive folder: {folder_url}"
            )
            folder_list = gdown.download_folder(
                url=folder_url,
                output=output_dir,
                quiet=True,
                use_cookies=False,
                remaining_ok=True,
            )
            if not folder_list:
                logger.error(
                    f"No files found or failed to list files in Google Drive folder: {folder_url}"
                )
                return []
            subfolders = set()
            files = []
            for item in folder_list:
                if (
                    isinstance(item, dict)
                    and item.get("mimeType") == "application/vnd.google-apps.folder"
                ):
                    subfolders.add(item["id"])
                elif isinstance(item, dict):
                    files.append(item)
            logger.info(
                f"Found {len(subfolders)} subfolders and {len(files)} files in root folder."
            )
            batch_size = 45
            result = []
            # Download files in root folder
            for i in range(0, len(files), batch_size):
                batch = files[i : i + batch_size]
                logger.info(
                    f"Downloading batch {i // batch_size + 1} in root: files {i + 1} to {min(i + batch_size, len(files))}"
                )
                for file_info in batch:
                    file_id = file_info["id"]
                    file_name = file_info["name"]
                    dest_path = os.path.join(output_dir, file_name)
                    # Pause support (allow stop to abort batch)
                    while (
                        hasattr(self, "_pause_event") and not self._pause_event.is_set()
                    ):
                        if (
                            getattr(self, "_stop_event", None)
                            and self._stop_event.is_set()
                        ):
                            logger.info(
                                "Stop requested; aborting Google Drive batch download."
                            )
                            return result
                        time.sleep(0.1)
                    logger.info(
                        f"Downloading Google Drive file: {file_name} to {dest_path}"
                    )
                    try:
                        gdown.download(
                            id=file_id, output=dest_path, quiet=False, use_cookies=False
                        )
                        result.append((file_name, dest_path))
                        logger.info(
                            f"Downloaded Google Drive file: {file_name} to {dest_path}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to download Google Drive file {file_name}: {e}"
                        )
            # Download files from each subfolder
            for subfolder_id in subfolders:
                subfolder_url = f"https://drive.google.com/drive/folders/{subfolder_id}"
                subfolder_output = os.path.join(output_dir, subfolder_id)
                os.makedirs(subfolder_output, exist_ok=True)
                logger.info(f"Listing files in subfolder: {subfolder_url}")
                subfolder_list = gdown.download_folder(
                    url=subfolder_url,
                    output=subfolder_output,
                    quiet=True,
                    use_cookies=False,
                    remaining_ok=True,
                )
                subfolder_files = [
                    f
                    for f in subfolder_list
                    if isinstance(f, dict)
                    and f.get("mimeType") != "application/vnd.google-apps.folder"
                ]
                logger.info(
                    f"Found {len(subfolder_files)} files in subfolder {subfolder_id}."
                )
                for i in range(0, len(subfolder_files), batch_size):
                    batch = subfolder_files[i : i + batch_size]
                    logger.info(
                        f"Downloading batch {i // batch_size + 1} in subfolder {subfolder_id}: files {i + 1} to {min(i + batch_size, len(subfolder_files))}"
                    )
                    for file_info in batch:
                        file_id = file_info["id"]
                        file_name = file_info["name"]
                        dest_path = os.path.join(subfolder_output, file_name)
                        # Pause support (allow stop to abort)
                        while (
                            hasattr(self, "_pause_event")
                            and not self._pause_event.is_set()
                        ):
                            if (
                                getattr(self, "_stop_event", None)
                                and self._stop_event.is_set()
                            ):
                                logger.info(
                                    "Stop requested; aborting Google Drive subfolder download."
                                )
                                return result
                            time.sleep(0.1)
                        logger.info(
                            f"Downloading Google Drive file: {file_name} to {dest_path}"
                        )
                        try:
                            gdown.download(
                                id=file_id,
                                output=dest_path,
                                quiet=False,
                                use_cookies=False,
                            )
                            result.append(
                                (os.path.join(subfolder_id, file_name), dest_path)
                            )
                            logger.info(
                                f"Downloaded Google Drive file: {file_name} to {dest_path}"
                            )
                        except Exception as e:
                            logger.error(
                                f"Failed to download Google Drive file {file_name}: {e}"
                            )
            logger.info(f"Completed Google Drive folder download: {folder_url}")
            return result
        except Exception as e:
            import traceback

            msg = (
                f"Failed to process Google Drive folder: {e}\n{traceback.format_exc()}"
            )
            logger.error(msg)
            # Show only a user-friendly error dialog
            try:
                messagebox.showerror(
                    "Google Drive Download Error",
                    "A problem occurred while downloading from Google Drive. This may be due to a bug in gdown or an unsupported folder. Please check the log for technical details.",
                )
            except Exception:
                pass
            return []

    def hash_file(self, file_path, chunk_size=65536):
        sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(chunk_size), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            print(f"Failed to hash {file_path}: {e}")
            return None

    def build_existing_hash_file(self, base_dir, hash_file_path):
        """
        Scan all files in base_dir, compute hashes, and store them in a file (one per line: hash<tab>path).
        Shows progress in the status pane. Uses multithreading for speed.
        Skips hashing files whose hash was updated within the last 4 hours (uses a cache file).
        """
        import os
        import time
        import json

        CACHE_HOURS = 4
        cache_file = hash_file_path + ".cache.json"
        now = time.time()
        # Respect global disable flag: if scans are disabled, do nothing
        if getattr(self, "_scans_disabled", False):
            try:
                self.thread_safe_status("Scanning disabled by user. Skipping scan.")
            except Exception:
                pass
            return
        # Load cache if exists
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as cf:
                    hash_cache = json.load(cf)
            except Exception:
                hash_cache = {}
        else:
            hash_cache = {}

        all_files = []
        for root, dirs, files in os.walk(base_dir):
            for f in files:
                all_files.append(os.path.join(root, f))
        total = len(all_files)
        if total == 0:
            self.thread_safe_status("No files found for scanning.")
            return

        # Support canceling a long-running scan
        self._scanning = True
        self._cancel_scan = False

        def hash_file_worker(path):
            relpath = os.path.relpath(path, base_dir).replace("\\", "/").lower()
            filename = os.path.basename(path).lower()
            cache_entry = hash_cache.get(path)
            if cache_entry:
                cached_hash, cached_time = cache_entry
                if now - cached_time < CACHE_HOURS * 3600:
                    return (path, cached_hash, relpath, filename, cached_time)
            # Not cached or cache expired, compute hash
            file_hash = self.hash_file(path)
            return (path, file_hash, relpath, filename, now)

        # Use 50% of available CPU threads, at least 1
        try:
            cpu_count = os.cpu_count() or 2
            max_workers = max(1, cpu_count // 2)
        except Exception:
            max_workers = 4

        results = [None] * total
        self._existing_files = dict()  # (filename.lower(), relpath.lower()) -> hash
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(hash_file_worker, path): idx
                for idx, path in enumerate(all_files)
            }
            for count, future in enumerate(as_completed(future_to_idx), 1):
                # Pause support for long-running scan; respect full stop requests
                while not self._pause_event.is_set():
                    if getattr(self, "_stop_event", None) and self._stop_event.is_set():
                        # Convert stop to a cancel_scan so existing logic cleans up
                        self._cancel_scan = True
                        break
                    time.sleep(0.1)
                if getattr(self, "_cancel_scan", False):
                    self.logger.info("Scan canceled by user.")
                    break
                idx = future_to_idx[future]
                path, file_hash, relpath, filename, hash_time = future.result()
                results[idx] = (path, file_hash)
                # Track all filenames and relpaths with their hash
                self._existing_files[(filename, relpath)] = file_hash
                # Update cache
                if file_hash:
                    hash_cache[path] = (file_hash, hash_time)
                # Update more frequently so UI feels responsive
                if count % 5 == 0 or count == total:
                    msg = f"Scanning for existing files: {count}/{total} ({int(count / total * 100) if total else 100}%)"
                    self.root.after(0, self.thread_safe_status, msg)
            self._scanning = False
            if getattr(self, "_cancel_scan", False):
                self.root.after(0, self.thread_safe_status, "Scan canceled.")
            else:
                self.root.after(0, self.thread_safe_status, "Scanning complete.")
                try:
                    self.logger.info("Existing file scan completed.")
                except Exception:
                    pass
                # Write a meta file to indicate when a full scan completed successfully
                try:
                    import time
                    import json

                    meta = {"last_scan": time.time()}
                    with open(
                        hash_file_path + ".meta.json", "w", encoding="utf-8"
                    ) as mf:
                        json.dump(meta, mf)
                except Exception:
                    pass

        with open(hash_file_path, "w", encoding="utf-8") as hf:
            for path, file_hash in results:
                if file_hash:
                    hf.write(f"{file_hash}\t{path}\n")

    def hash_exists_in_file(self, hash_file_path, file_hash):
        """
        Check if a hash exists in the hash file by reading line by line.
        """
        try:
            with open(hash_file_path, "r", encoding="utf-8") as hf:
                for line in hf:
                    if line.startswith(file_hash + "\t") or line.startswith(
                        file_hash + "\n"
                    ):
                        return True
        except FileNotFoundError:
            return False
        return False

    def append_hash_to_file(self, hash_file_path, file_hash, file_path):
        with open(hash_file_path, "a", encoding="utf-8") as hf:
            hf.write(f"{file_hash}\t{file_path}\n")

    def start_download_all_thread(self):
        import threading

        # If configured to start minimized while downloading, iconify first
        try:
            if self.config.get("start_minimized", False):
                try:
                    self.root.iconify()
                except Exception:
                    pass
        except Exception:
            pass
        # Keep a reference to the thread so we can join on shutdown
        self._download_all_thread = threading.Thread(
            target=self.download_all, daemon=True
        )
        self._download_all_thread.start()

    def download_all(self):
        import threading

        def run():
            self.thread_safe_status("Starting download...")
            # Show animated spinner while downloads are active
            try:
                self.root.after(0, self.start_spinner)
            except Exception:
                pass
            urls = list(self.urls)
            base_dir = self.base_dir.get()
            base_dir_cmp = base_dir.lower()
            os.makedirs(base_dir, exist_ok=True)
            # Scan for all existing files in base_dir and subfolders
            self.thread_safe_status("Scanning for existing files...")
            self.root.update_idletasks()
            self.hash_file_path = os.path.join(base_dir, "existing_hashes.txt")
            self.setup_logger(base_dir)
            self.logger.info(f"Starting download. URLs: {urls}")
            # Only perform a full scan if it's been more than 4 hours since the last full scan
            import time
            import json

            meta_file = self.hash_file_path + ".meta.json"
            SKIP_HOURS = 4
            last_scan = 0
            try:
                if os.path.exists(meta_file):
                    with open(meta_file, "r", encoding="utf-8") as mf:
                        meta = json.load(mf)
                        last_scan = float(meta.get("last_scan", 0))
            except Exception:
                last_scan = 0
            now = time.time()
            # If scan is recent and no force rescan requested, skip the expensive scan
            if (now - last_scan) < (SKIP_HOURS * 3600) and not getattr(
                self, "_force_rescan", False
            ):
                self.thread_safe_status("Skipping full file scan (recent scan exists).")
                self.logger.info(
                    "Skipping build_existing_hash_file due to recent scan."
                )
                # Load existing hashes into memory so duplicate checks still work
                self._existing_files = {}
                try:
                    if os.path.exists(self.hash_file_path):
                        with open(self.hash_file_path, "r", encoding="utf-8") as hf:
                            for line in hf:
                                parts = line.strip().split("\t", 1)
                                if len(parts) == 2:
                                    file_hash, path = parts
                                    filename = os.path.basename(path).lower()
                                    relpath = (
                                        os.path.relpath(path, base_dir)
                                        .replace("\\", "/")
                                        .lower()
                                    )
                                    self._existing_files[(filename, relpath)] = (
                                        file_hash
                                    )
                except Exception:
                    self.logger.exception(
                        "Failed to load existing hashes when skipping full scan."
                    )
            else:
                # If a force rescan was requested, clear the flag and ensure cache/meta are removed
                if getattr(self, "_force_rescan", False):
                    self.logger.info("Force full hash rescan requested by user.")
                    try:
                        cache_file = self.hash_file_path + ".cache.json"
                        meta_file = self.hash_file_path + ".meta.json"
                        if os.path.exists(cache_file):
                            os.remove(cache_file)
                        if os.path.exists(meta_file):
                            os.remove(meta_file)
                    except Exception:
                        pass
                    self._force_rescan = False
                try:
                    self.build_existing_hash_file(base_dir_cmp, self.hash_file_path)
                except Exception as e:
                    err_text = str(e)
                    self.logger.error(f"Failed to build hash file: {err_text}")
                    self.root.after(
                        0,
                        lambda: messagebox.showerror(
                            "Error", f"Failed to scan existing files: {err_text}"
                        ),
                    )
                    return
            self.skipped_files = set()
            self.file_tree = {}
            all_files = set()
            total = len(urls)
            self.progress["maximum"] = total
            try:
                from playwright.sync_api import sync_playwright

                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    context = browser.new_context()
                    page = context.new_page()
                    for i, url in enumerate(urls):
                        # Allow a Stop request to abort the download loop
                        if (
                            getattr(self, "_stop_event", None)
                            and self._stop_event.is_set()
                        ):
                            self.logger.info(
                                "Stop requested; aborting remaining URL processing in download_all."
                            )
                            break
                        self.thread_safe_status(f"Visiting: {url}")
                        self.logger.info(f"Visiting: {url}")
                        self.progress["value"] = i
                        self.root.update_idletasks()
                        if url.startswith("https://drive.google.com/drive/folders/"):
                            gdrive_dir = os.path.join(base_dir, "GoogleDrive")
                            try:
                                gdrive_files = self.download_gdrive_folder(
                                    url, gdrive_dir
                                )
                                # Add Google Drive files to file_tree and all_files
                                for rel_path, dest_path in gdrive_files:
                                    folder = os.path.dirname(dest_path)
                                    if folder not in self.file_tree:
                                        self.file_tree[folder] = []
                                    self.file_tree[folder].append(dest_path)
                                    all_files.add("gdrive://" + rel_path)
                                self.logger.info(
                                    f"Downloaded Google Drive folder: {url}"
                                )
                            except Exception as e:
                                self.logger.error(
                                    f"Failed to download Google Drive folder {url}: {e}"
                                )
                                self.root.after(
                                    0,
                                    lambda url=url, e=e: messagebox.showerror(
                                        "Error",
                                        f"Failed to download Google Drive folder: {url}\n{e}",
                                    ),
                                )
                            continue
                        try:
                            s, t, a = self.download_files(page, url, base_dir)
                            self.skipped_files.update(s or set())
                            self.file_tree.update(t or {})
                            all_files.update(a or set())
                        except Exception as e:
                            self.logger.error(f"Error downloading from {url}: {e}")
                            self.root.after(
                                0,
                                lambda url=url, e=e: messagebox.showerror(
                                    "Error", f"Error downloading from {url}: {e}"
                                ),
                            )
                    browser.close()
            except Exception as e:
                self.logger.error(f"Critical error in Playwright: {e}")
                self.root.after(
                    0,
                    lambda e=e: messagebox.showerror(
                        "Error", f"Critical error in Playwright: {e}"
                    ),
                )
                return
            self.thread_safe_status("Download complete. Checking for missing files...")
            self.logger.info("Download complete. Checking for missing files...")
            self.progress["value"] = total
            self.root.update_idletasks()
            # Save JSON
            json_path = os.path.join(base_dir, "epstein_file_tree.json")
            try:
                with open(json_path, "w", encoding="utf-8") as jf:
                    json.dump(self.file_tree, jf, indent=2)
                self.logger.info(f"File tree JSON saved: {json_path}")
            except Exception as e:
                self.logger.error(f"Failed to save JSON: {e}")
                self.root.after(
                    0,
                    lambda e=e: messagebox.showerror(
                        "Error", f"Failed to save JSON: {e}"
                    ),
                )
            self.downloaded_json.set(json_path)
            # If a Stop was requested, skip missing-file retries and finish early
            if getattr(self, "_stop_event", None) and self._stop_event.is_set():
                self.thread_safe_status(
                    "Stopped by user. Skipping missing-file retries."
                )
                self.logger.info(
                    "Skipping missing-file retry due to user stop request."
                )
            else:
                # Check for missing files
                missing_files = []
                for url in all_files:
                    if url.startswith("gdrive://"):
                        rel_path = url.replace("gdrive://", "")
                        local_path = os.path.join(base_dir, "GoogleDrive", rel_path)
                    else:
                        rel_path = self.sanitize_path(url.replace("https://", ""))
                        local_path = os.path.join(base_dir, rel_path)
                    if not os.path.exists(local_path):
                        missing_files.append((url, local_path))
                if missing_files:
                    self.thread_safe_status(
                        f"Downloading {len(missing_files)} missing files..."
                    )
                    self.logger.warning(
                        f"{len(missing_files)} missing files detected. Retrying..."
                    )
                    for url, local_path in missing_files:
                        try:
                            os.makedirs(os.path.dirname(local_path), exist_ok=True)
                            if url.startswith("gdrive://"):
                                # Redownload Google Drive file by name (not implemented: would require mapping rel_path to file_id)
                                self.logger.error(
                                    f"Cannot redownload missing Google Drive file automatically: {url}"
                                )
                            else:
                                proxies = None
                                if self.config.get("proxy"):
                                    proxies = {
                                        "http": self.config["proxy"],
                                        "https": self.config["proxy"],
                                    }
                                speed_limit = int(
                                    self.config.get("speed_limit_kbps", 0)
                                )
                                with requests.get(
                                    url, stream=True, proxies=proxies
                                ) as r:
                                    r.raise_for_status()
                                    with open(local_path, "wb") as f:
                                        downloaded = 0
                                        start_time = time.time()
                                        for chunk in r.iter_content(chunk_size=8192):
                                            if chunk:
                                                f.write(chunk)
                                                downloaded += len(chunk)
                                                if speed_limit > 0:
                                                    elapsed = time.time() - start_time
                                                    expected_time = downloaded / (
                                                        speed_limit * 1024
                                                    )
                                                    if elapsed < expected_time:
                                                        time.sleep(
                                                            expected_time - elapsed
                                                        )
                                self.logger.info(
                                    f"Successfully downloaded missing file: {url}"
                                )
                        except Exception as e:
                            self.logger.error(
                                f"Failed to download missing file {url}: {e}"
                            )
                    self.thread_safe_status(
                        "Download complete (with missing files retried)."
                    )
                else:
                    self.thread_safe_status("Download complete. No missing files.")
                    self.logger.info("No missing files after download.")
            # Ensure spinner is stopped regardless of outcome
            try:
                self.root.after(0, self.stop_spinner)
            except Exception:
                pass

        threading.Thread(target=run, daemon=True).start()

    def download_files(
        self,
        page,
        base_url,
        base_dir,
        visited=None,
        skipped_files=None,
        file_tree=None,
        all_files=None,
    ):

        allowed_domains = [
            "https://www.justice.gov/epstein",
            "https://oversight.house.gov/release/oversight-committee-releases-epstein-records-provided-by-the-department-of-justice/",
        ]
        if visited is None:
            visited = set()
        if skipped_files is None:
            skipped_files = set()
        if file_tree is None:
            file_tree = {}
        if all_files is None:
            all_files = set()
        if base_url in visited:
            return skipped_files, file_tree, all_files
        visited.add(base_url)
        # Respect a global stop request before starting heavy work
        if getattr(self, "_stop_event", None) and self._stop_event.is_set():
            try:
                self.logger.info(f"Stop requested; aborting traversal of {base_url}")
            except Exception:
                pass
            return skipped_files, file_tree, all_files
        self.thread_safe_status(f"Visiting: {base_url}")
        try:
            page.goto(base_url)
        except Exception as e:
            print(f"Error loading {base_url}: {e}\nContinuing...")
            return skipped_files, file_tree, all_files
        links = page.query_selector_all("a")
        self.thread_safe_status(f"Found {len(links)} links on {base_url}")
        hrefs = []
        for link in links:
            # Allow Stop to break traversal immediately
            if getattr(self, "_stop_event", None) and self._stop_event.is_set():
                try:
                    self.logger.info(
                        f"Stop requested; aborting link collection on {base_url}"
                    )
                except Exception:
                    pass
                break
            try:
                href = link.get_attribute("href")
                if href:
                    hrefs.append(href)
            except Exception as e:
                print(f"Error reading link attribute: {e}")

        # Prepare download tasks
        download_info = []  # (abs_url, local_path, folder)
        for href in hrefs:
            if getattr(self, "_stop_event", None) and self._stop_event.is_set():
                try:
                    self.logger.info(
                        f"Stop requested; aborting file/link loop on {base_url}"
                    )
                except Exception:
                    pass
                break
            if href.startswith("#"):
                continue
            abs_url = urllib.parse.urljoin(base_url, href)
            # Skip search links
            if "/search" in abs_url:
                continue
            if re.search(
                r"\.(pdf|docx?|xlsx?|zip|txt|jpg|png|csv|mp4|mov|avi|wmv|wav|mp3|m4a)$",
                abs_url,
                re.IGNORECASE,
            ):
                # Pause support for file processing (makes Pause more responsive)
                while not self._pause_event.is_set():
                    if getattr(self, "_stop_event", None) and self._stop_event.is_set():
                        try:
                            self.logger.info(
                                f"Stop requested; aborting file processing for {abs_url}"
                            )
                        except Exception:
                            pass
                        return skipped_files, file_tree, all_files
                    time.sleep(0.05)
                rel_path = self.sanitize_path(abs_url.replace("https://", ""))
                local_path = os.path.join(base_dir, rel_path)
                folder = os.path.dirname(local_path)
                if folder not in file_tree:
                    file_tree[folder] = []
                file_tree[folder].append(local_path)
                all_files.add(abs_url)
                # Skip download if file with same name, relpath, and hash exists
                filename = os.path.basename(local_path)
                filename_lc = filename.lower()
                relpath = (
                    os.path.relpath(local_path, base_dir).replace("\\", "/").lower()
                )
                file_hash = None
                exists = False
                save_path = local_path
                if hasattr(self, "_existing_files"):
                    if (filename_lc, relpath) in self._existing_files:
                        # If file exists at this path, check hash
                        try:
                            file_hash = self.hash_file(local_path)
                        except Exception:
                            file_hash = None
                        if (
                            file_hash
                            and file_hash
                            == self._existing_files[(filename_lc, relpath)]
                        ):
                            self.logger.info(
                                f"Skipping (already exists, same hash): {local_path}"
                            )
                            skipped_files.add(local_path)
                            exists = True
                        else:
                            # Conflict: file exists but hash is different, save as filename-YYYYMMDD_HHMMSS.ext
                            import datetime

                            base, ext = os.path.splitext(filename)
                            timestamp = datetime.datetime.now().strftime(
                                "%Y%m%d_%H%M%S"
                            )
                            new_filename = f"{base}-{timestamp}{ext}"
                            save_path = os.path.join(folder, new_filename)
                            self.logger.info(
                                f"Filename conflict: saving as {save_path}"
                            )
                if exists:
                    continue
                download_info.append((abs_url, save_path, folder))
            elif (
                abs_url != base_url
                and any(abs_url.startswith(domain) for domain in allowed_domains)
                and abs_url != "https://www.justice.gov/epstein"
                and abs_url not in visited
            ):
                sub_skipped, sub_tree, sub_all = self.download_files(
                    page,
                    abs_url,
                    base_dir,
                    visited,
                    skipped_files,
                    file_tree,
                    all_files,
                )
                skipped_files.update(sub_skipped or set())
                file_tree.update(sub_tree or {})
                all_files.update(sub_all or set())

        def download_file(abs_url, local_path):
            max_retries = 3
            delay = 2
            for attempt in range(1, max_retries + 1):
                # Pause support (also exit if a full stop is requested)
                while not self._pause_event.is_set():
                    if getattr(self, "_stop_event", None) and self._stop_event.is_set():
                        try:
                            self.logger.info(
                                f"Stop requested; aborting download task for {abs_url}"
                            )
                        except Exception:
                            pass
                        return
                    time.sleep(0.1)
                try:
                    os.makedirs(os.path.dirname(local_path), exist_ok=True)
                    self.thread_safe_status(
                        f"Downloading {abs_url} -> {local_path} (Attempt {attempt})"
                    )
                    self.logger.info(
                        f"Downloading {abs_url} -> {local_path} (Attempt {attempt})"
                    )
                    proxies = None
                    if self.config.get("proxy"):
                        proxies = {
                            "http": self.config["proxy"],
                            "https": self.config["proxy"],
                        }
                    speed_limit = int(self.config.get("speed_limit_kbps", 0))
                    with requests.get(
                        abs_url, stream=True, timeout=300, proxies=proxies
                    ) as r:
                        r.raise_for_status()
                        with open(local_path, "wb") as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                while not self._pause_event.is_set():
                                    if (
                                        getattr(self, "_stop_event", None)
                                        and self._stop_event.is_set()
                                    ):
                                        try:
                                            self.logger.info(
                                                f"Stop requested; aborting download of {abs_url}"
                                            )
                                        except Exception:
                                            pass
                                        return
                                    time.sleep(0.1)
                                if chunk:
                                    f.write(chunk)
                    self.logger.info(f"Downloaded: {abs_url}")
                    return None
                except Exception as e:
                    self.logger.error(
                        f"Failed to download {abs_url} (Attempt {attempt}): {e}"
                    )
                    if attempt < max_retries:
                        time.sleep(delay)
                        delay *= 2  # Exponential backoff
                    else:
                        self.logger.error(
                            f"Permanently failed to download {abs_url} after {max_retries} attempts."
                        )
                        return local_path

        # Multithreaded download (user-configurable concurrency)
        failed_downloads = []
        with ThreadPoolExecutor(
            max_workers=self.concurrent_downloads.get()
        ) as executor:
            future_to_info = {
                executor.submit(download_file, abs_url, local_path): (
                    abs_url,
                    local_path,
                )
                for abs_url, local_path, _ in download_info
            }
            for future in as_completed(future_to_info):
                abs_url, local_path = future_to_info[future]
                result = future.result()
                if result:
                    failed_downloads.append((abs_url, local_path))
        if failed_downloads:
            self.logger.error(
                f"Summary: {len(failed_downloads)} files failed after retries."
            )
            failed_list = "\n".join(
                [f"{url} -> {path}" for url, path in failed_downloads]
            )
            self.logger.error(f"Failed files:\n{failed_list}")
            self.thread_safe_status(
                f"{len(failed_downloads)} files failed after retries. See log for details."
            )
        return skipped_files, file_tree, all_files

    def sanitize_path(self, path):
        parts = path.split("/")
        return os.path.join(*[re.sub(r'[<>:"/\\|?*]', "_", p) for p in parts])

    def download_drive_folder_api(self, folder_id, gdrive_dir, credentials_path):
        """
        Download all files from a Google Drive folder using the Google Drive API and a service account.
        Supports using an already-loaded credential object cached on the GUI (so changes are immediate).
        """
        import os
        from googleapiclient.discovery import build
        from google.oauth2 import service_account
        from googleapiclient.http import MediaIoBaseDownload

        SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
        # Prefer an already-in-memory credentials object set via reload_credentials()
        creds = None
        if getattr(self, "gdrive_credentials", None):
            creds = self.gdrive_credentials
        elif credentials_path:
            creds = service_account.Credentials.from_service_account_file(
                credentials_path, scopes=SCOPES
            )
        else:
            raise RuntimeError("No credentials available for Google Drive API download")
        service = build("drive", "v3", credentials=creds)

        def list_files(service, folder_id):
            query = f"'{folder_id}' in parents and trashed = false"
            files = []
            page_token = None
            while True:
                response = (
                    service.files()
                    .list(
                        q=query,
                        spaces="drive",
                        fields="nextPageToken, files(id, name, mimeType)",
                        pageToken=page_token,
                    )
                    .execute()
                )
                files.extend(response.get("files", []))
                page_token = response.get("nextPageToken", None)
                if page_token is None:
                    break
            return files

        def download_file(service, file_id, file_name, dest_dir):
            request = service.files().get_media(fileId=file_id)
            fh = io.FileIO(os.path.join(dest_dir, file_name), "wb")
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            fh.close()

        # Ensure gdrive_dir is a directory, not a file
        if os.path.exists(gdrive_dir):
            if os.path.isfile(gdrive_dir):
                self.logger.error(
                    f"Cannot create directory '{gdrive_dir}' because a file with the same name exists. Skipping this folder."
                )
                return
        else:
            os.makedirs(gdrive_dir, exist_ok=True)

        files = list_files(service, folder_id)
        for f in files:
            if f["mimeType"] == "application/vnd.google-apps.folder":
                # Recursively download subfolders
                subfolder = os.path.join(gdrive_dir, f["name"])
                # Check for file/dir conflict for subfolder
                if os.path.exists(subfolder) and os.path.isfile(subfolder):
                    self.logger.error(
                        f"Cannot create subdirectory '{subfolder}' because a file with the same name exists. Skipping this subfolder."
                    )
                    continue
                self.download_drive_folder_api(f["id"], subfolder, credentials_path)
            else:
                self.logger.info(f"Downloading from Google Drive: {f['name']}")
                download_file(service, f["id"], f["name"], gdrive_dir)


def main():
    # If installed in Program Files, prefer running from the install directory so assets and bundled files are resolved predictably
    try:
        if os.path.isdir(INSTALL_DIR):
            os.chdir(INSTALL_DIR)
    except Exception:
        # Ignore chdir failures and continue
        pass

    if DND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    root.title("EpsteinFilesDownloader")
    try:
        root.iconbitmap("JosephThePlatypus.ico")
    except Exception as e:
        print(f"Warning: Could not set window icon: {e}")
    # Check for headless mode (CI smoke tests)
    headless = os.environ.get("EPSTEIN_HEADLESS", "0") == "1"
    # Optionally skip the potentially interactive dependency installer in headless mode
    skip_install = os.environ.get("EPISTEIN_SKIP_INSTALL", "0") == "1"
    try:
        if not headless:
            if skip_install:
                logging.getLogger("EpsteinFilesDownloader").info(
                    "Skipping dependency installation (EPISTEIN_SKIP_INSTALL=1)."
                )
            else:
                install_dependencies_with_progress(root)
    except Exception as dep_err:
        logging.getLogger("EpsteinFilesDownloader").error(
            f"Dependency installation failed during startup: {dep_err}"
        )
        if not suppress_startup_dialog:
            try:
                messagebox.showerror(
                    "Startup Error", f"Failed to install dependencies: {dep_err}"
                )
            except Exception:
                pass
        root.destroy()
        return

    # Instantiate the GUI defensively so NameError can be diagnosed and handled cleanly
    try:
        logging.getLogger("EpsteinFilesDownloader").info(
            "Creating DownloaderGUI instance..."
        )
        _app = DownloaderGUI(root)
        logging.getLogger("EpsteinFilesDownloader").info(
            "DownloaderGUI instance created."
        )
    except NameError as ne:
        # Collect helpful diagnostics to the log to aid debugging of intermittent NameError
        try:
            gkeys = list(globals().keys())
            mod_path = (
                os.path.abspath(__file__) if "__file__" in globals() else "unknown"
            )
            mtime = os.path.getmtime(mod_path) if os.path.exists(mod_path) else None
            msize = os.path.getsize(mod_path) if os.path.exists(mod_path) else None
            logging.getLogger("EpsteinFilesDownloader").exception(
                "NameError during DownloaderGUI instantiation: %s\nGlobals keys: %s\nModule: %s size=%s mtime=%s",
                ne,
                gkeys,
                mod_path,
                msize,
                mtime,
            )
        except Exception:
            logging.getLogger("EpsteinFilesDownloader").exception(
                "NameError during DownloaderGUI instantiation and failed to collect diagnostics: %s",
                ne,
            )
        try:
            root.destroy()
        except Exception:
            pass
        return
    except Exception as e:
        logging.getLogger("EpsteinFilesDownloader").exception(
            "Exception during DownloaderGUI init: %s", e
        )
        try:
            root.destroy()
        except Exception:
            pass
        return

    # Log successful initialization instead of showing a modal popup (avoid blocking automated runs)
    try:
        logging.getLogger("EpsteinFilesDownloader").info(
            "GUI initialized successfully. If you cannot see the window, check the taskbar."
        )
    except Exception:
        logging.getLogger("EpsteinFilesDownloader").warning(
            "GUI initialized, but failed to write startup log message."
        )

    # In headless mode we don't enter the Tk mainloop; just initialize and exit cleanly for CI smoke tests
    if headless:
        logging.getLogger("EpsteinFilesDownloader").info(
            "Headless initialization complete."
        )
        try:
            root.destroy()
        except Exception:
            pass
        return

    root.mainloop()


if __name__ == "__main__":
    logging.getLogger("EpsteinFilesDownloader").info("Starting main()...")
    main()


# EpsteinFilesDownloader v1.0.0
# (C) 2025 - Refactored for clarity, maintainability, and efficiency

__version__ = "1.5"


import io
import os
import re
import sys
import urllib.parse
import json
import threading
try:
    from tkinterdnd2 import TkinterDnD
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    DND_AVAILABLE = True
except ImportError:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    DND_AVAILABLE = False
from datetime import datetime
from pathlib import Path
import requests
import time
import importlib.util
import subprocess
import glob
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import logging


# --- Dependency Checks and Playwright Setup ---
def install_dependencies_with_progress(root=None):
    import importlib.util
    import subprocess
    import sys
    import tkinter as tk
    from tkinter import ttk
    # Modal progress dialog
    progress_win = None
    progress_var = None
    progress_label = None
    def show_progress(msg):
        nonlocal progress_win, progress_var, progress_label
        if root is None:
            return
        if progress_win is None:
            progress_win = tk.Toplevel(root)
            progress_win.title("Installing Dependencies")
            progress_win.geometry("400x120")
            progress_win.transient(root)
            progress_win.grab_set()
            progress_label = ttk.Label(progress_win, text=msg)
            progress_label.pack(pady=20)
            progress_var = tk.StringVar(value=msg)
        else:
            progress_label.config(text=msg)
        progress_win.update_idletasks()
    def close_progress():
        if progress_win:
            progress_win.destroy()
    def ensure_pip():
        try:
            import pip
        except ImportError:
            show_progress("pip not found. Installing pip...")
            import ensurepip
            ensurepip.bootstrap()
            import pip
    def check_and_install(package, pip_name=None):
        pip_name = pip_name or package
        if importlib.util.find_spec(package) is None:
            show_progress(f"Installing {pip_name}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
            except Exception as e:
                close_progress()
                if root:
                    messagebox.showerror("Dependency Error", f"Failed to install {pip_name}: {e}")
                raise
import importlib.util
import subprocess
import glob
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import logging

def ensure_pip():
    try:
        import pip
    except ImportError:
        print("pip not found. Attempting to install pip...")
        import ensurepip
        ensurepip.bootstrap()
        import pip

def check_and_install(package, pip_name=None):
    pip_name = pip_name or package
    if importlib.util.find_spec(package) is None:
        print(f"Missing required package: {pip_name}. Installing...")
        try:
            subprocess.check_call(["python", "-m", "pip", "install", pip_name])
        except Exception as e:
            print(f"Failed to install {pip_name}: {e}")
            raise

# (Removed duplicate quick-install block inserted by a merge; the canonical dependency checks live earlier in the file)
        raise

ensure_playwright_browsers()

def check_and_install(package, pip_name=None):
    pip_name = pip_name or package
    if importlib.util.find_spec(package) is None:
        print(f"Missing required package: {pip_name}. Installing...")
        subprocess.check_call(["python", "-m", "pip", "install", pip_name])

# Check and install prerequisites
check_and_install("playwright")
check_and_install("requests")
check_and_install("gdown")



class DownloaderGUI:
    def __init__(self, root):
        self.root = root
        self.dark_mode = False
        self.base_dir = tk.StringVar(value=r'C:\Downloads\Epstein')
        self.log_dir = os.path.join(os.getcwd(), "logs")
        self.credentials_path = None
        self.concurrent_downloads = tk.IntVar(value=3)
        self.urls = []
        self.default_urls = [
            "https://a.com",
            "https://b.com"
        ]
        self.queue_state_path = os.path.join(os.getcwd(), "queue_state.json")
        self.config_path = os.path.join(os.getcwd(), "config.json")
        self.status = tk.StringVar(value="Ready")
        self.speed_eta_var = tk.StringVar(value="Speed: --  ETA: --")
        self.error_log_path = os.path.join(self.log_dir, "error.log")
        self.log_file = os.path.join(self.log_dir, f"epstein_downloader_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        import threading
        self._pause_event = threading.Event()
        self._is_paused = False
        self.downloaded_json = tk.StringVar(value="")
        self.logger = logging.getLogger("EpsteinFilesDownloader")
        self.logger.setLevel(logging.DEBUG)
        if self.logger.hasHandlers():
            self.logger.handlers.clear()
        fh = logging.FileHandler(self.log_file, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        sh = logging.StreamHandler()
        sh.setLevel(logging.INFO)
        sh.setFormatter(formatter)
        self.logger.addHandler(sh)
        class StatusPaneHandler(logging.Handler):
            def __init__(self, gui):
                super().__init__()
                self.gui = gui
            def emit(self, record):
                msg = self.format(record)
                self.gui.append_status_pane(msg)
        status_handler = StatusPaneHandler(self)
        status_handler.setLevel(logging.INFO)
        status_handler.setFormatter(formatter)
        self.logger.addHandler(status_handler)
        self.logger.info("Logger initialized.")
        # Now safe to load config and restore queue state
        self.config = self.load_config() if hasattr(self, 'load_config') else {}
        # Option for gdown fallback (must be after self.config is loaded)
        self.use_gdown_fallback = tk.BooleanVar(value=self.config.get("use_gdown_fallback", False))
        self.restore_queue_state() if hasattr(self, 'restore_queue_state') else None
        # Override defaults if config exists
        if self.config.get("download_dir"):
            self.base_dir.set(self.config["download_dir"])
        if self.config.get("concurrent_downloads"):
            try:
                self.concurrent_downloads.set(int(self.config["concurrent_downloads"]))
            except Exception:
                pass
        if self.config.get("log_dir"):
            self.log_dir = self.config["log_dir"]
        if self.config.get("credentials_path"):
            self.credentials_path = self.config["credentials_path"]
        else:
            self.credentials_path = None
        os.makedirs(self.log_dir, exist_ok=True)
        self.error_log_path = os.path.join(self.log_dir, "error.log")
        self.setup_logger(self.log_dir) if hasattr(self, 'setup_logger') else None
        self.logger.debug(f"EpsteinFilesDownloader v{__version__} started. Log file: {self.log_file}")
        self.create_menu() if hasattr(self, 'create_menu') else None
        self.create_widgets() if hasattr(self, 'create_widgets') else None
        self.create_log_panel()
        self.setup_drag_and_drop() if hasattr(self, 'setup_drag_and_drop') else None
        self.root.protocol("WM_DELETE_WINDOW", self.on_close) if hasattr(self, 'on_close') else None

    def open_selected_url_in_browser(self):
        selection = self.url_listbox.curselection()
        if not selection:
            return
        url = self.url_listbox.get(selection[0])
        import webbrowser
        try:
            webbrowser.open(url)
        except Exception as e:
            self.logger.warning(f"Failed to open URL in browser: {e}")

    def copy_selected_url(self):
        selection = self.url_listbox.curselection()
        if not selection:
            return
        url = self.url_listbox.get(selection[0])
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            self.root.update()  # Keeps clipboard after window closes
        except Exception as e:
            self.logger.warning(f"Failed to copy URL to clipboard: {e}")

    def move_url_up(self):
        selection = self.url_listbox.curselection()
        if not selection or selection[0] == 0:
            return
        index = selection[0]
        # Swap in self.urls
        self.urls[index - 1], self.urls[index] = self.urls[index], self.urls[index - 1]
        # Swap in Listbox
        url_text = self.url_listbox.get(index)
        self.url_listbox.delete(index)
        self.url_listbox.insert(index - 1, url_text)
        self.url_listbox.selection_clear(0, tk.END)
        self.url_listbox.selection_set(index - 1)
        self.url_listbox.activate(index - 1)

    def move_url_down(self):
        selection = self.url_listbox.curselection()
        if not selection or selection[0] == self.url_listbox.size() - 1:
            return
        index = selection[0]
        # Swap in self.urls
        self.urls[index + 1], self.urls[index] = self.urls[index], self.urls[index + 1]
        # Swap in Listbox
        url_text = self.url_listbox.get(index)
        self.url_listbox.delete(index)
        self.url_listbox.insert(index + 1, url_text)
        self.url_listbox.selection_clear(0, tk.END)
        self.url_listbox.selection_set(index + 1)
        self.url_listbox.activate(index + 1)

    def check_for_updates(self):
        # Non-blocking update check (example: check GitHub releases or a version file)
        import threading
        def do_check():
            try:
                import requests
                url = "https://raw.githubusercontent.com/JosephThePlatypus/EpsteinFilesDownloader/main/VERSION.txt"
                r = requests.get(url, timeout=10)
                if r.status_code == 200:
                    latest = r.text.strip()
                    if latest != __version__:
                        self.root.after(0, lambda: messagebox.showinfo("Update Available", f"A new version is available: {latest}\nYou are running: {__version__}"))
                    else:
                        self.root.after(0, lambda: messagebox.showinfo("Up to Date", f"You are running the latest version: {__version__}"))
                else:
                    self.root.after(0, lambda: messagebox.showwarning("Update Check Failed", "Could not check for updates."))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showwarning("Update Check Error", f"Error checking for updates: {e}"))
        threading.Thread(target=do_check, daemon=True).start()

    def show_progress(self):
        # Placeholder: show a messagebox or popup. You can expand this to show a real progress dialog.
        messagebox.showinfo("Download Progress", "Download progress is shown in the main window's progress bars.")

    def create_log_panel(self):
        import tkinter.scrolledtext as st
        if not hasattr(self, 'log_panel'):
            self.log_panel = st.ScrolledText(self.root, height=8, state='disabled', font=('Consolas', 10))
            # Use grid instead of pack to avoid geometry manager conflict
            self.log_panel.grid(row=99, column=0, columnspan=4, sticky='ew', padx=4, pady=2)
            self.log_panel_visible = True
        else:
            if not self.log_panel.winfo_ismapped():
                self.log_panel.grid(row=99, column=0, columnspan=4, sticky='ew', padx=4, pady=2)
                self.log_panel_visible = True

    def toggle_log_panel(self):
        if hasattr(self, 'log_panel'):
            if self.log_panel.winfo_ismapped():
                self.log_panel.grid_remove()
                self.log_panel_visible = False
            else:
                self.log_panel.grid(row=99, column=0, columnspan=4, sticky='ew', padx=4, pady=2)
                self.log_panel_visible = True
        else:
            self.create_log_panel()

    def append_log_panel(self, msg):
        if hasattr(self, 'log_panel'):
            self.log_panel.configure(state='normal')
            self.log_panel.insert('end', msg + '\n')
            self.log_panel.see('end')
            self.log_panel.configure(state='disabled')

    def setup_url_listbox_context_menu(self):
        # Context menu for URL listbox
        self.url_menu = tk.Menu(self.url_listbox, tearoff=0)
        self.url_menu.add_command(label="Remove URL", command=self.remove_url)
        self.url_menu.add_command(label="Move Up", command=self.move_url_up)
        self.url_menu.add_command(label="Move Down", command=self.move_url_down)
        self.url_menu.add_separator()
        self.url_menu.add_command(label="Copy URL", command=self.copy_selected_url)
        self.url_menu.add_command(label="Open in Browser", command=self.open_selected_url_in_browser)
        self.url_listbox.bind("<Button-3>", self.show_url_context_menu)

    def show_url_context_menu(self, event):
        try:
            # Select the item under the mouse
            index = self.url_listbox.nearest(event.y)
            self.url_listbox.selection_clear(0, tk.END)
            self.url_listbox.selection_set(index)
            self.url_listbox.activate(index)
            self.url_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.url_menu.grab_release()
            self.logger.handlers.clear()
        fh = logging.FileHandler(self.log_file, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        sh = logging.StreamHandler()
        sh.setLevel(logging.INFO)
        sh.setFormatter(formatter)
        self.logger.addHandler(sh)
        # Now safe to load config and restore queue state
        self.config = self.load_config()
        self.restore_queue_state()
        # Override defaults if config exists
        if self.config.get("download_dir"):
            self.base_dir = tk.StringVar(value=r'C:\Downloads\Epstein')
        if self.config.get("concurrent_downloads"):
            try:
                self.concurrent_downloads.set(int(self.config["concurrent_downloads"]))
            except Exception:
                pass
        if self.config.get("log_dir"):
            self.log_dir = self.config["log_dir"]
        if self.config.get("credentials_path"):
            self.credentials_path = self.config["credentials_path"]
        else:
            self.credentials_path = None
        os.makedirs(self.log_dir, exist_ok=True)
        self.error_log_path = os.path.join(self.log_dir, "error.log")
        self.setup_logger(self.log_dir)
        self.logger.debug(f"EpsteinFilesDownloader v{__version__} started. Log file: {self.log_file}")
        self.create_menu()
        self.create_widgets()
        # --- Drag and Drop Setup ---
        self.setup_drag_and_drop()
        # Hook for saving queue state on close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def save_queue_state(self):
        try:
            state = {
                "urls": self.urls,
                "processed_count": getattr(self, "processed_count", 0),
            }
            with open(self.queue_state_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            self.logger.info("Queue state saved.")
        except Exception as e:
            self.logger.error(f"Failed to save queue state: {e}")

    def restore_queue_state(self):
        try:
            def is_placeholder_url(url):
                # Treat as placeholder if it's a.com, b.com, or empty
                return url.strip() in {"https://a.com", "https://b.com", "", "http://a.com", "http://b.com"}

            if os.path.exists(self.queue_state_path):
                with open(self.queue_state_path, "r", encoding="utf-8") as f:
                    state = json.load(f)
                loaded_urls = state.get("urls", [])
                # If all loaded URLs are placeholders or the list is empty, use defaults
                if not loaded_urls or all(is_placeholder_url(u) for u in loaded_urls):
                    self.urls = list(self.default_urls)
                else:
                    self.urls = loaded_urls
            else:
                self.urls = list(self.default_urls)
                self.processed_count = state.get("processed_count", 0)
                self.logger.info("Queue state restored.")
        except Exception as e:
            self.logger.error(f"Failed to restore queue state: {e}")

    def on_close(self):
        self.save_queue_state()
        self.root.destroy()

    def log_error(self, err: Exception, context: str = ""):  # Utility for error logging and dialog
        import traceback
        msg = f"[{datetime.now().isoformat()}] {context}\n{type(err).__name__}: {err}\n{traceback.format_exc()}\n"
        try:
            with open(self.error_log_path, "a", encoding="utf-8") as f:
                f.write(msg)
        except Exception:
            pass
        self.show_error_dialog(str(err), context)

    def show_error_dialog(self, error_msg, context=""):
        try:
            messagebox.showerror("Error", f"{context}\n{error_msg}" if context else error_msg)
        except Exception:
            print(f"Error: {context} {error_msg}")
    def setup_drag_and_drop(self):
        # Try to import tkinterDnD2 for drag-and-drop support
        try:
            from tkinterdnd2 import DND_FILES
        except ImportError:
            self.logger.warning("tkinterDnD2 not installed. Drag-and-drop will not be available.")
            return
        # Only set up DnD for the URL listbox if it exists
        if hasattr(self, 'url_listbox'):
            try:
                self.url_listbox.drop_target_register(DND_FILES)
                self.url_listbox.dnd_bind('<<Drop>>', self.on_url_drop)
                self.url_listbox.dnd_bind('<<DragEnter>>', lambda e: self.url_listbox.config(bg="#cce6ff"))
                self.url_listbox.dnd_bind('<<DragLeave>>', lambda e: self.url_listbox.config(bg="white"))
            except Exception as e:
                self.logger.warning(f"Failed to enable DnD on URL listbox: {e}")

        # Always ensure menu bar is present after any DnD setup
        self.create_menu()

        # Enable DnD for URL listbox (for URLs)
        try:
            self.url_listbox.drop_target_register(DND_FILES)
            self.url_listbox.dnd_bind('<<Drop>>', self.on_url_drop)
        except Exception as e:
            self.logger.warning(f"Failed to enable DnD on URL listbox: {e}")

        # Enable DnD for main window (for credentials.json)
        try:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind('<<Drop>>', self.on_credential_drop)
        except Exception as e:
            self.logger.warning(f"Failed to enable DnD on main window: {e}")

    def on_url_drop(self, event):
        # Accept dropped URLs (file paths or text)
        dropped = event.data
        if dropped:
            # Split by whitespace (could be multiple files/URLs)
            items = self.root.tk.splitlist(dropped)
            for item in items:
                if item.lower().startswith(('http://', 'https://')):
                    if item not in self.urls:
                        self.urls.append(item)
                        self.url_listbox.insert(tk.END, item)
                        self.logger.info(f"Added URL via drag-and-drop: {item}")
                elif item.lower().endswith('.url'):
                    # Try to read .url file for actual URL
                    try:
                        with open(item, 'r', encoding='utf-8') as f:
                            for line in f:
                                if line.strip().startswith('URL='):
                                    url = line.strip().split('=', 1)[-1]
                                    if url and url not in self.urls:
                                        self.urls.append(url)
                                        self.url_listbox.insert(tk.END, url)
                                        self.logger.info(f"Added URL from .url file: {url}")
                    except Exception as e:
                        self.logger.warning(f"Failed to read .url file: {item}: {e}")

    def on_credential_drop(self, event):
        # Accept dropped credentials.json file
        dropped = event.data
        if dropped:
            items = self.root.tk.splitlist(dropped)
            for item in items:
                if item.lower().endswith('credentials.json'):
                    # Copy or set config to use this credentials file
                    self.config['credentials_path'] = item
                    self.save_config()
                    self.logger.info(f"Set credentials.json via drag-and-drop: {item}")
                    messagebox.showinfo("Credentials Set", f"credentials.json set to: {item}")
                else:
                    self.logger.info(f"Dropped file ignored (not credentials.json): {item}")

    def load_config(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_config(self):
        self.config["download_dir"] = self.base_dir.get()
        self.config["log_dir"] = getattr(self, "log_dir", os.path.join(os.getcwd(), "logs"))
        self.config["concurrent_downloads"] = self.concurrent_downloads.get()
        # Save credentials_path if set
        if hasattr(self, "credentials_path") and self.credentials_path:
            self.config["credentials_path"] = self.credentials_path
        elif "credentials_path" in self.config:
            del self.config["credentials_path"]
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)

    def restore_defaults(self):
        self.base_dir.set(r'C:\Temp\Epstein')
        self.log_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(self.log_dir, exist_ok=True)
        self.save_config()
        self.setup_logger(self.log_dir)
        messagebox.showinfo("Defaults Restored", "Settings have been restored to defaults.")

    def create_menu(self):
        menubar = tk.Menu(self.root)
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Set Download Folder...", command=self.pick_download_folder)
        file_menu.add_command(label="Set Log Folder...", command=self.pick_log_folder)
        file_menu.add_command(label="Set Credentials File...", command=self.pick_credentials_file)
        file_menu.add_separator()
        file_menu.add_command(label="Save Settings as Default", command=self.save_config)
        file_menu.add_command(label="Restore Defaults", command=self.restore_defaults)
        file_menu.add_separator()
        file_menu.add_command(label="Export Settings...", command=self.export_settings)
        file_menu.add_command(label="Import Settings...", command=self.import_settings)
        file_menu.add_separator()
        # Move Settings out of File into its own top-level menu for clarity
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        # Settings menu (top-level)
        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(label="Preferences...", command=lambda: self.open_settings_dialog())
        settings_menu.add_separator()
        # Quick-open specific tabs
        settings_menu.add_command(label="Open General Settings...", command=lambda: self.open_settings_dialog("General"))
        settings_menu.add_command(label="Open Network Settings...", command=lambda: self.open_settings_dialog("Network"))
        settings_menu.add_command(label="Open Appearance Settings...", command=lambda: self.open_settings_dialog("Appearance"))
        settings_menu.add_command(label="Open Advanced Settings...", command=lambda: self.open_settings_dialog("Advanced"))
        settings_menu.add_separator()
        # Quick toggles / flags
        try:
            settings_menu.add_checkbutton(label="Enable gdown fallback", variable=self.use_gdown_fallback, command=self.save_config)
        except Exception:
            # If variable isn't present for some reason, ignore
            try:
                settings_menu.add_command(label="Enable gdown fallback (unavailable)")
            except Exception:
                pass
        settings_menu.add_command(label="Toggle Dark/Light Mode", command=self.toggle_dark_mode)
        settings_menu.add_separator()
        settings_menu.add_command(label="Restore Defaults", command=self.restore_defaults)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        try:
            self.logger.debug("Added top-level Settings menu (with quick items)")
        except Exception:
            pass

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Toggle Dark/Light Mode", command=self.toggle_dark_mode)
        view_menu.add_command(label="Show/Hide Log Panel", command=self.toggle_log_panel)
        view_menu.add_command(label="Show Download Progress", command=self.show_progress)
        menubar.add_cascade(label="View", menu=view_menu)

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="Check for Updates", command=self.check_for_updates)
        tools_menu.add_command(label="Validate Credentials", command=self.validate_credentials)
        tools_menu.add_command(label="Test Download Link", command=self.test_download_link)
        tools_menu.add_separator()
        tools_menu.add_command(label="Force Full Hash Rescan", command=self.force_full_hash_rescan)
        menubar.add_cascade(label="Tools", menu=tools_menu)

        # Help menu

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Help", command=self.show_help_dialog)
        help_menu.add_command(label="About", command=self.show_about_dialog)
        help_menu.add_command(label="Report Issue / Send Feedback", command=self.report_issue)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menubar)
        return menubar

    def show_help_dialog(self):
        help_text = (
            "Epstein Court Records Downloader Help\n\n"
            "1. Add URLs to the download list.\n"
            "2. Set your download folder and other settings in the Settings dialog.\n"
            "3. Click 'Start Download' to begin.\n"
            "4. Use Pause/Resume to control downloads.\n"
            "5. View download history in the 'Download History' tab.\n\n"
            "Advanced:\n"
            "- Use the Settings dialog to set a proxy or limit download speed.\n"
            "- Drag and drop URLs or credentials.json into the app.\n"
            "- Use the Tools menu for hash rescans and credential validation.\n\n"
            "Troubleshooting:\n"
            "- Check the log/history tab for errors.\n"
            "- Ensure Playwright and browsers are installed.\n"
            "- For Google Drive, provide a valid credentials.json if needed.\n"
            "- For proxy issues, verify your proxy string format.\n"
        )
        self.show_popup("Help", help_text)

    def show_about_dialog(self):
        about_text = (
            f"Epstein Court Records Downloader\nVersion: {__version__}\n\n"
            "Developed by JosephThePlatypus and contributors.\n"
            "\nThis tool automates the downloading of public court records, "
            "with advanced queue management, error handling, and history.\n\n"
            "For more info, visit the project page or contact the author.\n"
        )
        self.show_popup("About", about_text)


    def export_settings(self):
        """Export current settings to a user-chosen JSON file."""
        file_path = filedialog.asksaveasfilename(
            title="Export Settings As",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="epstein_downloader_settings.json"
        )
        if file_path:
            try:
                self.save_config()  # Ensure config is up to date
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(self.config, f, indent=2)
                messagebox.showinfo("Export Settings", f"Settings exported to: {file_path}")
            except Exception as e:
                self.log_error(e, "Export Settings")

    def import_settings(self):
        """Import settings from a user-chosen JSON file."""
        file_path = filedialog.askopenfilename(
            title="Import Settings",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="epstein_downloader_settings.json"
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    imported = json.load(f)
                # Update config and UI
                self.config.update(imported)
                if "download_dir" in imported:
                    self.base_dir.set(imported["download_dir"])
                if "log_dir" in imported:
                    self.log_dir = imported["log_dir"]
                    os.makedirs(self.log_dir, exist_ok=True)
                if "credentials_path" in imported:
                    self.credentials_path = imported["credentials_path"]
                self.save_config()
                self.setup_logger(self.log_dir)
                messagebox.showinfo("Import Settings", f"Settings imported from: {file_path}")
            except Exception as e:
                self.log_error(e, "Import Settings")



    def open_settings_dialog(self, tab=None):
        """Open a dialog to view and edit all key settings, grouped in tabs.

        Optional `tab` may be one of: 'General', 'Network', 'Appearance', 'Advanced' to pre-select a tab.
        """
        win = tk.Toplevel(self.root)
        win.title("Settings")
        win.geometry("650x480")

        notebook = ttk.Notebook(win)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # --- General Tab ---
        general_tab = ttk.Frame(notebook)
        notebook.add(general_tab, text="General")
        ttk.Label(general_tab, text="Download Folder:").grid(row=0, column=0, sticky="w", padx=10, pady=10)
        download_var = tk.StringVar(value=self.base_dir.get())
        download_entry = ttk.Entry(general_tab, textvariable=download_var, width=50)
        download_entry.grid(row=0, column=1, padx=10, pady=10)
        browse_download_btn = ttk.Button(general_tab, text="Browse", command=lambda: download_var.set(filedialog.askdirectory(title="Select Download Folder") or download_var.get()))
        browse_download_btn.grid(row=0, column=2, padx=5)
        ttk.Label(general_tab, text="Log Folder:").grid(row=1, column=0, sticky="w", padx=10, pady=10)
        log_var = tk.StringVar(value=getattr(self, "log_dir", os.path.join(os.getcwd(), "logs")))
        log_entry = ttk.Entry(general_tab, textvariable=log_var, width=50)
        log_entry.grid(row=1, column=1, padx=10, pady=10)
        browse_log_btn = ttk.Button(general_tab, text="Browse", command=lambda: log_var.set(filedialog.askdirectory(title="Select Log Folder") or log_var.get()))
        browse_log_btn.grid(row=1, column=2, padx=5)
        ttk.Label(general_tab, text="Credentials File:").grid(row=2, column=0, sticky="w", padx=10, pady=10)
        cred_var = tk.StringVar(value=getattr(self, "credentials_path", ""))
        cred_entry = ttk.Entry(general_tab, textvariable=cred_var, width=50)
        cred_entry.grid(row=2, column=1, padx=10, pady=10)
        browse_cred_btn = ttk.Button(general_tab, text="Browse", command=lambda: cred_var.set(filedialog.askopenfilename(title="Select credentials.json", filetypes=[("JSON files", "*.json"), ("All files", "*.*")]) or cred_var.get()))
        browse_cred_btn.grid(row=2, column=2, padx=5)
        ttk.Label(general_tab, text="Concurrent Downloads:").grid(row=3, column=0, sticky="w", padx=10, pady=10)
        concurrency_var = tk.IntVar(value=self.concurrent_downloads.get())
        concurrency_spin = ttk.Spinbox(general_tab, from_=1, to=32, textvariable=concurrency_var, width=8, increment=1)
        concurrency_spin.grid(row=3, column=1, sticky="w", padx=10, pady=10)

        # --- Network Tab ---
        network_tab = ttk.Frame(notebook)
        notebook.add(network_tab, text="Network")
        ttk.Label(network_tab, text="Proxy (http[s]://user:pass@host:port or leave blank):").grid(row=0, column=0, sticky="w", padx=10, pady=10)
        proxy_var = tk.StringVar(value=self.config.get("proxy", ""))
        proxy_entry = ttk.Entry(network_tab, textvariable=proxy_var, width=50)
        proxy_entry.grid(row=0, column=1, padx=10, pady=10, columnspan=2)
        ttk.Label(network_tab, text="Download Speed Limit (KB/s, 0 = unlimited):").grid(row=1, column=0, sticky="w", padx=10, pady=10)
        speed_var = tk.IntVar(value=int(self.config.get("speed_limit_kbps", 0)))
        speed_spin = ttk.Spinbox(network_tab, from_=0, to=102400, textvariable=speed_var, width=10, increment=10)
        speed_spin.grid(row=1, column=1, sticky="w", padx=10, pady=10)

        # --- Appearance Tab ---
        appearance_tab = ttk.Frame(notebook)
        notebook.add(appearance_tab, text="Appearance")
        ttk.Label(appearance_tab, text="Theme:").grid(row=0, column=0, sticky="w", padx=10, pady=10)
        theme_var = tk.StringVar(value="Dark" if self.dark_mode else "Light")
        theme_combo = ttk.Combobox(appearance_tab, textvariable=theme_var, values=["Light", "Dark"], state="readonly", width=10)
        theme_combo.grid(row=0, column=1, sticky="w", padx=10, pady=10)

        # --- Advanced Tab (always visible) ---
        advanced_tab = ttk.Frame(notebook)
        notebook.add(advanced_tab, text="Advanced")
        ttk.Label(advanced_tab, text="(Advanced options coming soon)").pack(padx=20, pady=(20, 5), anchor="w")
        gdown_chk = ttk.Checkbutton(
            advanced_tab,
            text="Enable gdown fallback for Google Drive downloads (not recommended unless API fails)",
            variable=self.use_gdown_fallback
        )
        gdown_chk.pack(padx=20, pady=(5, 20), anchor="w")
        self.add_tooltip(gdown_chk, "If enabled, will use gdown to download Google Drive folders if the API fails or credentials are missing. This may be less reliable.")

        def save_and_close():
            self.base_dir.set(download_var.get())
            self.log_dir = log_var.get()
            os.makedirs(self.log_dir, exist_ok=True)
            self.credentials_path = cred_var.get() if cred_var.get() else None
            self.concurrent_downloads.set(concurrency_var.get())
            self.config["proxy"] = proxy_var.get()
            self.config["speed_limit_kbps"] = speed_var.get()
            if self.config.get('show_advanced', False):
                self.config["use_gdown_fallback"] = self.use_gdown_fallback.get()
            # Theme
            new_dark = (theme_var.get() == "Dark")
            if new_dark != self.dark_mode:
                self.dark_mode = new_dark
                self.set_theme('clam' if self.dark_mode else 'default')
            self.save_config()
            self.setup_logger(self.log_dir)
            win.destroy()
            messagebox.showinfo("Settings", "Settings updated.")

        save_btn = ttk.Button(win, text="Save", command=save_and_close)
        save_btn.pack(pady=12)

        # Tooltips
        self.add_tooltip(download_entry, "Edit the download folder path.")
        self.add_tooltip(browse_download_btn, "Browse for download folder.")
        self.add_tooltip(log_entry, "Edit the log folder path.")
        self.add_tooltip(browse_log_btn, "Browse for log folder.")
        self.add_tooltip(cred_entry, "Edit the path to credentials.json.")
        self.add_tooltip(browse_cred_btn, "Browse for credentials.json file.")
        self.add_tooltip(concurrency_spin, "Set the number of concurrent downloads (threads)")
        self.add_tooltip(proxy_entry, "Set a proxy for downloads (http[s]://user:pass@host:port)")
        self.add_tooltip(speed_spin, "Limit download speed in KB/s (0 = unlimited)")
        self.add_tooltip(theme_combo, "Choose between light and dark mode.")
        self.add_tooltip(save_btn, "Save changes to settings.")

        # If a specific tab was requested, select it
        if tab:
            try:
                tab_map = {"general": 0, "network": 1, "appearance": 2, "advanced": 3}
                idx = tab_map.get(str(tab).strip().lower())
                if idx is not None:
                    notebook.select(idx)
            except Exception:
                pass

    def force_full_hash_rescan(self):
        """Delete the hash cache file so the next scan will re-hash all files."""
        import os
        base_dir = self.base_dir.get()
        hash_file_path = os.path.join(base_dir, 'existing_hashes.txt')
        cache_file = hash_file_path + ".cache.json"
        if os.path.exists(cache_file):
            try:
                os.remove(cache_file)
                messagebox.showinfo("Hash Rescan", "Hash cache cleared. Next scan will re-hash all files.")
            except Exception as e:
                messagebox.showerror("Hash Rescan", f"Failed to clear hash cache: {e}")
        else:
            messagebox.showinfo("Hash Rescan", "No hash cache file found. Next scan will re-hash all files.")
    def pick_credentials_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Google Drive credentials.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="credentials.json"
        )
        if file_path:
            self.credentials_path = file_path
            self.config['credentials_path'] = file_path
            self.save_config()
            self.logger.info(f"Set credentials.json via File menu: {file_path}")
            messagebox.showinfo("Credentials Set", f"credentials.json set to: {file_path}")

    def set_theme(self, theme_name):
        style = ttk.Style()
        try:
            style.theme_use(theme_name)
        except Exception:
            style.theme_use('default')
        # Optionally, tweak widget colors for extra clarity
        if theme_name in ('clam', 'alt', 'vista', 'xpnative'):
            style.configure('.', background='#222', foreground='#eee')
            style.configure('TLabel', background='#222', foreground='#eee')
            style.configure('TButton', background='#333', foreground='#eee')
            style.configure('TEntry', fieldbackground='#333', foreground='#eee')
            style.configure('TFrame', background='#222')
            style.configure('TNotebook', background='#222')
            style.configure('TNotebook.Tab', background='#333', foreground='#eee')
            style.configure('TProgressbar', background='#444')
        else:
            style.configure('.', background='#f0f0f0', foreground='#222')
            style.configure('TLabel', background='#f0f0f0', foreground='#222')
            style.configure('TButton', background='#f0f0f0', foreground='#222')
            style.configure('TEntry', fieldbackground='#fff', foreground='#222')
            style.configure('TFrame', background='#f0f0f0')
            style.configure('TNotebook', background='#f0f0f0')
            style.configure('TNotebook.Tab', background='#e0e0e0', foreground='#222')
            style.configure('TProgressbar', background='#e0e0e0')

    def toggle_dark_mode(self):
        self.dark_mode = not getattr(self, 'dark_mode', False)
        # Use 'clam' for dark, 'default' for light if available
        if self.dark_mode:
            self.set_theme('clam')
        else:
            self.set_theme('default')


    def validate_credentials(self):
        # Validate Google Drive credentials.json
        import threading
        def do_validate():
            path = getattr(self, 'credentials_path', None)
            if not path or not os.path.exists(path):
                self.root.after(0, lambda: messagebox.showerror("Validate Credentials", "No credentials.json file set or file does not exist."))
                return
            try:
                from google.oauth2 import service_account
                creds = service_account.Credentials.from_service_account_file(path)
                if creds and creds.valid:
                    self.root.after(0, lambda: messagebox.showinfo("Validate Credentials", "Credentials are valid."))
                else:
                    self.root.after(0, lambda: messagebox.showerror("Validate Credentials", "Credentials file is invalid."))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Validate Credentials", f"Credentials validation failed: {e}"))
        threading.Thread(target=do_validate, daemon=True).start()


    def test_download_link(self):
        # Test the first URL in the list for reachability and downloadability
        import threading
        def do_test():
            if not self.urls:
                self.root.after(0, lambda: messagebox.showerror("Test Download Link", "No URLs in the list."))
                return
            url = self.urls[0]
            try:
                proxies = None
                if self.config.get('proxy'):
                    proxies = {"http": self.config['proxy'], "https": self.config['proxy']}
                r = requests.head(url, timeout=10, proxies=proxies, allow_redirects=True)
                if r.status_code == 200:
                    self.root.after(0, lambda: messagebox.showinfo("Test Download Link", f"URL is reachable: {url}"))
                else:
                    self.root.after(0, lambda: messagebox.showerror("Test Download Link", f"URL returned status code {r.status_code}: {url}"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Test Download Link", f"Failed to reach URL: {e}"))
        threading.Thread(target=do_test, daemon=True).start()

    def show_about(self):
        about_text = (
            f"EpsteinFilesDownloader v{__version__}\n"
            "\n(C) 2025\n"
            "Author: JosephThePlatypus\n"
            "License: MIT\n"
            "\nA GUI tool for downloading Epstein court records and related files."
        )
        messagebox.showinfo("About", about_text)

    def report_issue(self):
        # Open the user's GitHub issues page for reporting issues
        repo_url = "https://github.com/AresX0/WebsiteFileDownloader/issues"
        try:
            import webbrowser
            webbrowser.open(repo_url)
            messagebox.showinfo("Report Issue", f"Your browser has been opened to the issues page:\n{repo_url}")
        except Exception:
            messagebox.showinfo("Report Issue", f"To report an issue or send feedback, visit:\n{repo_url}")

    def pick_download_folder(self):
        folder = filedialog.askdirectory(title="Select Download Folder")
        if folder:
            self.base_dir.set(folder)
            self.save_config()

    def pick_log_folder(self):
        folder = filedialog.askdirectory(title="Select Log Folder")
        if folder:
            self.log_dir = folder
            os.makedirs(self.log_dir, exist_ok=True)
            self.save_config()
            self.setup_logger(self.log_dir)

    def show_help(self):
        help_text = self.get_help_text()
        self.show_popup("Help", help_text)

    def get_help_text(self):
        return (
            f"EpsteinFilesDownloader v{__version__}\n\n"
            "Features:\n"
            "- Download court records and files from preset or custom URLs.\n"
            "- Google Drive support (API or gdown fallback).\n"
            "- Multithreaded downloads, hash checking, and duplicate skipping.\n"
            "- Progress bar, skipped files, and JSON export.\n"
            "- Menu options for download/log folder, dark/light mode, restoring defaults, and more.\n"
            "- All logs saved to a user-chosen folder.\n\n"
            "Menu Options:\n"
            "File Menu:\n"
            "  - Set Download Folder: Choose where files are saved.\n"
            "  - Set Log Folder: Choose where logs are saved.\n"
            "  - Set Credentials File: Select Google Drive credentials.json.\n"
            "  - Save Settings as Default: Save current folders and credentials for next session.\n"
            "  - Restore Defaults: Reset all settings to default values.\n"
            "  - Exit: Close the application.\n\n"
            "View Menu:\n"
            "  - Toggle Dark/Light Mode: Switch between dark and light themes.\n"
            "  - Show/Hide Log Panel: Show or hide the log/status pane.\n"
            "  - Show Download Progress: Display the download progress bar.\n\n"
            "Tools Menu:\n"
            "  - Check for Updates: Check for new versions on GitHub.\n"
            "  - Validate Credentials: Check if your Google Drive credentials are valid.\n"
            "  - Test Download Link: Test if a download link is working.\n"
            "  - Force Full Hash Rescan: Clear the hash cache and force a full file hash scan on next download.\n\n"
            "Help Menu:\n"
            "  - Help: Show this help/documentation.\n"
            "  - About: Show version and author information.\n"
            "  - Report Issue / Send Feedback: Open the GitHub issues page for bug reports or feedback.\n\n"
            "Other Usage Notes:\n"
            "- Start downloads with the Start Download button.\n"
            "- For Google Drive, you will be prompted for credentials.json or gdown fallback.\n"
            "- Drag and drop URLs or credentials.json into the window.\n"
            "- Skipped files and download progress are shown in the log/status pane.\n"
            "- Hash scanning is cached for 4 hours for speed; use Tools > Force Full Hash Rescan to override.\n"
        )

    # --- Utility Methods ---
    def validate_url(self, url):
        """Basic URL validation: checks scheme and netloc."""
        try:
            result = urllib.parse.urlparse(url)
            return all([result.scheme in ("http", "https"), result.netloc])
        except Exception:
            return False

    # --- Download Logic ---
    def start_download(self):
        self.logger.debug("start_download called.")
        base_dir = self.base_dir.get()
        try:
            os.makedirs(base_dir, exist_ok=True)
        except Exception as e:
            self.logger.error(f"Failed to create download directory: {e}")
            self.show_error_dialog(f"Failed to create download directory: {e}")
            return
        self.setup_logger(base_dir)
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                for url in self.urls:
                    if url.startswith('https://drive.google.com/drive/folders/'):
                        continue
                    if not self.validate_url(url):
                        self.logger.error(f"Invalid URL: {url}")
                        self.show_error_dialog(f"Invalid URL: {url}")
                        continue
                    self.logger.info(f"Visiting: {url}")
                    try:
                        s, t, a = self.download_files_threaded(page, url, base_dir, skipped_files=self.skipped_files, file_tree=self.file_tree)
                        self.skipped_files.update(s or set())
                        self.file_tree.update(t or {})
                    except Exception as e:
                        self.logger.error(f"Error downloading from {url}: {e}", exc_info=True)
                        self.show_error_dialog(f"Error downloading from {url}: {e}")
                browser.close()
        except Exception as e:
            self.logger.error(f"Exception in start_download: {e}", exc_info=True)
            self.show_error_dialog(f"Critical error in download process: {e}")
            return
        # Prompt for credentials.json location if needed
        credentials_path = self.config.get('credentials_path', None)
        for url in self.urls:
            if url.startswith('https://drive.google.com/drive/folders/'):
                if not credentials_path:
                    credentials_path = filedialog.askopenfilename(
                        title="Select Google Drive credentials.json (Cancel to use gdown fallback)",
                        filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                        initialfile="credentials.json"
                    )
                    if not credentials_path:
                        self.logger.warning("No credentials.json selected. Will use gdown fallback for Google Drive download.")
                        messagebox.showwarning("Google Drive", "No credentials.json selected. Will use gdown fallback for Google Drive download.")
                        credentials_path = None
                gdrive_dir = os.path.join(base_dir, 'GoogleDrive')
                self.logger.info(f"Processing Google Drive folder: {url}")
                try:
                    self.download_gdrive_with_fallback(url, gdrive_dir, credentials_path)
                except Exception as e:
                    self.logger.error(f"Error downloading Google Drive folder {url}: {e}")
                    self.show_error_dialog(f"Error downloading Google Drive folder {url}: {e}")
        self.logger.info("All downloads complete.")
        messagebox.showinfo("Download Complete", "All downloads are complete. See the log for details.")

    def download_gdrive_with_fallback(self, url, gdrive_dir, credentials_path):
        import re
        try:
            match = re.search(r'/folders/([a-zA-Z0-9_-]+)', url)
            if not match:
                self.logger.error("Google Drive folder ID not found in URL.")
                self.show_error_dialog("Google Drive folder ID not found in URL.")
                return
            folder_id = match.group(1)
            # Only use gdown fallback if advanced is enabled and user checked it
            use_gdown_fallback = self.config.get('show_advanced', False) and self.config.get('use_gdown_fallback', False)
            if os.path.exists(credentials_path):
                try:
                    os.makedirs(gdrive_dir, exist_ok=True)
                    self.download_drive_folder_api(folder_id, gdrive_dir, credentials_path)
                    return
                except Exception as e:
                    self.logger.error(f"Google Drive API download failed: {e}")
                    # Prompt user to enable advanced fallback
                    if not self.config.get('show_advanced', False):
                        if messagebox.askyesno("Google Drive API Error", f"Google Drive API download failed: {e}\n\nWould you like to enable the advanced fallback (gdown) option?"):
                            self.config['show_advanced'] = True
                            self.save_config()
                            self.open_settings_dialog()
                        return
                    if not use_gdown_fallback:
                        self.show_error_dialog(
                            f"Google Drive API download failed: {e}\n\nYou can try the gdown fallback by enabling it in the Advanced tab.",
                            "Google Drive API Error"
                        )
                        return
                    self.logger.info("Falling back to gdown as requested...")
            elif not use_gdown_fallback:
                self.logger.error("No credentials.json found. Not attempting gdown fallback unless requested.")
                # Prompt user to enable advanced fallback
                if not self.config.get('show_advanced', False):
                    if messagebox.askyesno("Google Drive Credentials Required", "No credentials.json found. Would you like to enable the advanced fallback (gdown) option?"):
                        self.config['show_advanced'] = True
                        self.save_config()
                        self.open_settings_dialog()
                    return
                self.show_error_dialog(
                    "No credentials.json found. To use the gdown fallback, enable it in the Advanced tab.",
                    "Google Drive Credentials Required"
                )
                return
            # If we reach here, either credentials are missing or API failed and fallback is requested
            try:
                import gdown
                os.makedirs(gdrive_dir, exist_ok=True)
                self.logger.info("Attempting gdown fallback for Google Drive folder download...")
                file_list = self.download_gdrive_folder(url, gdrive_dir)
                if file_list:
                    for rel_path, dest_path in file_list:
                        if os.path.exists(dest_path):
                            self.logger.info(f"Skipping (already exists): {dest_path}")
                        else:
                            self.logger.info(f"Downloaded: {dest_path}")
                else:
                    self.logger.warning("gdown fallback did not return any files.")
            except Exception as e2:
                self.logger.error(f"gdown fallback failed: {e2}")
                # Show user-friendly error
                self.show_error_dialog(
                    "Google Drive fallback (gdown) failed. This may be due to a bug in gdown or an unsupported folder. Please check the log for technical details.\n\nTo enable full Google Drive access, create a credentials.json file as follows:\n"
                    "1. Go to https://console.cloud.google.com/\n"
                    "2. Create/select a project, enable the Google Drive API.\n"
                    "3. Go to 'APIs & Services > Credentials', create a Service Account, and download the JSON key.\n"
                    "4. Save it as credentials.json in this folder.\n",
                    title="Google Drive Fallback Error"
                )
        except Exception as e:
            import traceback
            self.logger.error(f"Unexpected error in download_gdrive_with_fallback: {e}\n{traceback.format_exc()}")
            self.show_error_dialog(f"Unexpected error in download_gdrive_with_fallback: {e}")

    def download_files_threaded(self, page, base_url, base_dir, visited=None, skipped_files=None, file_tree=None, all_files=None):
        allowed_domains = [
            'https://www.justice.gov/epstein',
            'https://oversight.house.gov/release/oversight-committee-releases-epstein-records-provided-by-the-department-of-justice/'
        ]
        try:
            # Main download logic here (existing code follows)
            # ...
            pass  # Placeholder for actual download logic
        except PermissionError as perm_err:
            self.logger.error(f"Permission denied: {perm_err}", exc_info=True)
            self.show_error_dialog(f"Permission denied: {perm_err}")
        except Exception as e:
            self.logger.error(f"Error in download_files_threaded: {e}", exc_info=True)
            self.show_error_dialog(f"Error in download_files_threaded: {e}")
        if visited is None:
            visited = set()
        if skipped_files is None:
            skipped_files = set()
        if file_tree is None:
            file_tree = {}
        if all_files is None:
            all_files = set()
        if base_url in visited:
            return skipped_files, file_tree, all_files
        visited.add(base_url)
        self.logger.info(f"Visiting: {base_url}")
        try:
            page.goto(base_url)
        except Exception as e:
            self.logger.error(f"Error loading {base_url}: {e}\nContinuing...")
            return skipped_files, file_tree, all_files
        links = page.query_selector_all('a')
        self.logger.info(f"Found {len(links)} links on {base_url}")
        hrefs = []
        for link in links:
            try:
                href = link.get_attribute('href')
                if href:
                    hrefs.append(href)
            except Exception as e:
                self.logger.error(f"Error reading link attribute: {e}")
        from concurrent.futures import ThreadPoolExecutor, as_completed
        download_args = []
        num_threads = 6
        for href in hrefs:
            if href.startswith('#'):
                continue
            abs_url = urllib.parse.urljoin(base_url, href)
            if '/search' in abs_url:
                continue
            if re.search(r'\.(pdf|docx?|xlsx?|zip|txt|jpg|png|csv|mp4|mov|avi|wmv|wav|mp3|m4a)$', abs_url, re.IGNORECASE):
                rel_path = self.sanitize_path(abs_url.replace('https://', ''))
                local_path = os.path.join(base_dir, rel_path)
                folder = os.path.dirname(local_path)
                if folder not in file_tree:
                    file_tree[folder] = []
                file_tree[folder].append(local_path)
                all_files.add(abs_url)
                download_args.append((abs_url, rel_path, local_path))
            elif (
                abs_url != base_url
                and any(abs_url.startswith(domain) for domain in allowed_domains)
                and abs_url != 'https://www.justice.gov/epstein'
                and abs_url not in visited
            ):
                sub_skipped, sub_tree, sub_all = self.download_files_threaded(page, abs_url, base_dir, visited, skipped_files, file_tree, all_files)
                skipped_files.update(sub_skipped or set())
                file_tree.update(sub_tree or {})
                all_files.update(sub_all or set())

        def download_file_task(abs_url, rel_path, local_path):
            import time
            max_retries = 3
            delay = 2
            for attempt in range(1, max_retries + 1):
                # Pause support
                while not self._pause_event.is_set():
                    time.sleep(0.1)
                try:
                    if not self.validate_url(abs_url):
                        self.logger.warning(f"Skipping invalid URL: {abs_url}")
                        skipped_files.add(abs_url)
                        return
                    if os.path.exists(local_path):
                        self.logger.info(f"Skipping (already exists): {local_path}")
                        skipped_files.add(local_path)
                        return
                    os.makedirs(os.path.dirname(local_path), exist_ok=True)
                    self.logger.info(f"Downloading {abs_url} -> {local_path} (Attempt {attempt})")
                    proxies = None
                    if self.config.get('proxy'):
                        proxies = {"http": self.config['proxy'], "https": self.config['proxy']}
                    speed_limit = int(self.config.get('speed_limit_kbps', 0))
                    with requests.get(abs_url, stream=True, timeout=300, proxies=proxies) as r:
                        r.raise_for_status()
                        total_size = int(r.headers.get('content-length', 0))
                        downloaded = 0
                        start_time = time.time()
                        last_update = start_time
                        last_downloaded = 0
                        eta = '--'
                        speed = '--'
                        with open(local_path, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                while not self._pause_event.is_set():
                                    time.sleep(0.1)
                                if chunk:
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    now = time.time()
                                    elapsed = now - start_time
                                    if speed_limit > 0:
                                        # Throttle speed
                                        expected_time = downloaded / (speed_limit * 1024)
                                        if elapsed < expected_time:
                                            time.sleep(expected_time - elapsed)
                                    if elapsed > 0:
                                        speed_val = downloaded / elapsed
                                        speed = f"{speed_val/1024:.1f} KB/s"
                                        if total_size > 0 and speed_val > 0:
                                            eta_val = (total_size - downloaded) / speed_val
                                            eta = f"{int(eta_val//60)}m {int(eta_val%60)}s"
                                        else:
                                            eta = '--'
                                    # Update label every 0.5s or on finish
                                    if now - last_update > 0.5 or downloaded == total_size:
                                        def update_speed_eta(s=speed, e=eta):
                                            self.speed_eta_var.set(f"Speed: {s}  ETA: {e}")
                                        self.root.after(0, update_speed_eta)
                                        last_update = now
                        # Reset speed/eta label after file done
                        def clear_speed_eta():
                            self.speed_eta_var.set("Speed: --  ETA: --")
                        self.root.after(0, clear_speed_eta)
                    self.logger.info(f"Downloaded: {abs_url}")
                    return
                except Exception as e:
                    self.logger.error(f"Failed to download {abs_url} (Attempt {attempt}): {e}")
                    if attempt < max_retries:
                        time.sleep(delay)
                        delay *= 2  # Exponential backoff
                    else:
                        self.logger.error(f"Permanently failed to download {abs_url} after {max_retries} attempts.")
                        skipped_files.add(abs_url)

        try:
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = [executor.submit(download_file_task, *args) for args in download_args]
                for future in as_completed(futures):
                    pass
        except KeyboardInterrupt:
            self.logger.warning("Download interrupted by user. Waiting for threads to finish...")
        return skipped_files, file_tree, all_files

    def setup_logger(self, log_dir):
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, f"epstein_downloader_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        self.log_file = log_path
        self.logger = logging.getLogger("EpsteinFilesDownloader")
        self.logger.setLevel(logging.DEBUG)
        if self.logger.hasHandlers():
            self.logger.handlers.clear()
        fh = logging.FileHandler(log_path, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        sh = logging.StreamHandler()
        sh.setLevel(logging.INFO)
        sh.setFormatter(formatter)
        self.logger.addHandler(sh)
        class StatusPaneHandler(logging.Handler):
            def __init__(self, gui):
                super().__init__()
                self.gui = gui
            def emit(self, record):
                msg = self.format(record)
                self.gui.append_status_pane(msg)
        status_handler = StatusPaneHandler(self)
        status_handler.setLevel(logging.INFO)
        status_handler.setFormatter(formatter)
        self.logger.addHandler(status_handler)
        self.logger.info("Logger initialized.")

    def thread_safe_status(self, msg):
        # Schedule status update on the main thread, safe for closed mainloop
        try:
            self.root.after(0, self.status.set, msg)
            self.append_status_pane(msg)
        except RuntimeError:
            pass

    def append_status_pane(self, msg):
        def append():
            try:
                if hasattr(self, 'status_pane') and self.status_pane:
                    self.status_pane.configure(state='normal')
                    self.status_pane.insert('end', msg + '\n')
                    self.status_pane.see('end')
                    self.status_pane.configure(state='disabled')
            except RuntimeError:
                pass
        try:
            self.root.after(0, append)
        except RuntimeError:
            pass

    def create_widgets(self):
        # --- Modern Progress Bar Style ---
        style = ttk.Style()
        # Use a unique style name to avoid global side effects
        style.theme_use('clam')  # 'clam' is modern and cross-platform
        style.configure('Modern.Horizontal.TProgressbar',
                        troughcolor='#e0e0e0' if not self.dark_mode else '#222',
                        bordercolor='#b0b0b0' if not self.dark_mode else '#444',
                        background='#4a90e2' if not self.dark_mode else '#6fa8dc',
                        lightcolor='#4a90e2' if not self.dark_mode else '#6fa8dc',
                        darkcolor='#357ab7' if not self.dark_mode else '#27496d',
                        thickness=18,
                        relief='flat')
        # For file progress, use a different color
        style.configure('ModernFile.Horizontal.TProgressbar',
                        troughcolor='#e0e0e0' if not self.dark_mode else '#222',
                        bordercolor='#b0b0b0' if not self.dark_mode else '#444',
                        background='#7ed957' if not self.dark_mode else '#8fd694',
                        lightcolor='#7ed957' if not self.dark_mode else '#8fd694',
                        darkcolor='#4e944f' if not self.dark_mode else '#386641',
                        thickness=14,
                        relief='flat')
        # Make window scalable
        self.root.geometry('1100x800')
        self.root.minsize(800, 600)
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        # Tabbed notebook for main UI and download history
        self._notebook = ttk.Notebook(self.root)
        self._notebook.grid(row=0, column=0, sticky='nsew')

        # Main tab (existing UI)
        main_tab = ttk.Frame(self._notebook)
        main_tab.grid_rowconfigure(0, weight=1)
        main_tab.grid_columnconfigure(0, weight=1)
        self._notebook.add(main_tab, text="Downloader")

        # ...existing code for main_tab, container, canvas, self.frame, etc...

        # ...existing code for main_tab, container, canvas, self.frame, etc...


        # Main tab content frame setup (must come before any reference to self.frame)
        container = ttk.Frame(main_tab)
        container.grid(row=0, column=0, sticky='nsew')
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        canvas = tk.Canvas(container)
        canvas.grid(row=0, column=0, sticky='nsew')
        vscroll = ttk.Scrollbar(container, orient='vertical', command=canvas.yview)
        vscroll.grid(row=0, column=1, sticky='ns')
        canvas.configure(yscrollcommand=vscroll.set)
        self.canvas = canvas
        self.frame = ttk.Frame(self.canvas)
        frame_id = self.canvas.create_window((0, 0), window=self.frame, anchor='nw')
        self._main_frame = self.frame  # Store reference for use in other methods

        def on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox('all'))
        self.frame.bind('<Configure>', on_frame_configure)

        def on_canvas_configure(event):
            canvas.itemconfig(frame_id, width=event.width)
        self.canvas.bind('<Configure>', on_canvas_configure)

        # Now set up Download History tab with search/filter
        self.history_tab = ttk.Frame(self._notebook)
        self.history_tab.grid_rowconfigure(1, weight=1)
        self.history_tab.grid_columnconfigure(0, weight=1)
        self._notebook.add(self.history_tab, text="Download History")

        # Search/filter bar
        filter_frame = ttk.Frame(self.history_tab)
        filter_frame.grid(row=0, column=0, sticky='ew', padx=10, pady=(10, 0))
        ttk.Label(filter_frame, text="Filter:", font=("Segoe UI", 11)).pack(side='left')
        self.history_filter_var = tk.StringVar()
        filter_entry = ttk.Entry(filter_frame, textvariable=self.history_filter_var, width=40, font=("Segoe UI", 11))
        filter_entry.pack(side='left', padx=(5, 0))
        filter_entry.bind('<KeyRelease>', lambda e: self.refresh_history_log())
        refresh_btn = ttk.Button(filter_frame, text="Refresh", command=self.refresh_history_log)
        refresh_btn.pack(side='left', padx=(10, 0))

        # Log viewer
        import tkinter.scrolledtext as st
        self.history_text = st.ScrolledText(self.history_tab, height=40, width=120, state='disabled', wrap='word', font=("Segoe UI", 11))
        self.history_text.grid(row=1, column=0, sticky='nsew', padx=10, pady=10)
        self.add_tooltip(self.history_text, "View the download and error log history.")
        self.refresh_history_log()

        # --- Main Downloader UI ---

        # Title
        title = ttk.Label(self.frame, text="Epstein Court Records Downloader", font=("Segoe UI", 26, "bold"))
        title.grid(row=0, column=0, columnspan=4, pady=(10, 20), sticky="nsew")

        # --- Download Controls Group ---
        download_controls = ttk.LabelFrame(self.frame, text="Download Controls", padding=(15, 10))
        download_controls.grid(row=1, column=0, columnspan=4, sticky="ew", padx=10, pady=(0, 15))
        download_controls.columnconfigure(1, weight=1)
        download_controls.configure(labelanchor='n')
        concurrent_label = ttk.Label(download_controls, text="Concurrent Downloads:", font=("Segoe UI", 12))
        concurrent_label.grid(row=0, column=0, sticky="e", padx=(0, 8), pady=5)
        concurrent_spin = ttk.Spinbox(download_controls, from_=1, to=32, textvariable=self.concurrent_downloads, width=5, increment=1, font=("Segoe UI", 12))
        concurrent_spin.grid(row=0, column=1, sticky="w", pady=5)
        self.add_tooltip(concurrent_spin, "Set the number of concurrent downloads (threads)")
        self.add_tooltip(concurrent_label, "Set the number of concurrent downloads (threads)")

        # --- URL Management Group ---
        url_section = ttk.LabelFrame(self.frame, text="Download URLs", padding=(15, 10))
        url_section.grid(row=2, column=0, columnspan=4, sticky="ew", padx=10, pady=(0, 15))
        url_section.columnconfigure(1, weight=1)
        url_section.configure(labelanchor='n')
        self.url_listbox = tk.Listbox(url_section, height=6, width=80, font=("Segoe UI", 11))
        self.url_listbox.grid(row=0, column=0, columnspan=3, sticky="ew", padx=(0, 8), pady=5)
        self.url_listbox.delete(0, tk.END)
        for url in self.urls:
            self.url_listbox.insert(tk.END, url)
        self.add_tooltip(self.url_listbox, "List of URLs to download. Select to remove or view details.")
        self.setup_url_listbox_context_menu()
        self.url_entry = ttk.Entry(url_section, width=60, font=("Segoe UI", 11))
        self.url_entry.grid(row=1, column=0, sticky="ew", pady=5)
        add_url_btn = ttk.Button(url_section, text="Add URL", command=self.add_url)
        add_url_btn.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=5)
        self.add_tooltip(add_url_btn, "Add a new download URL")
        self.add_tooltip(self.url_entry, "Paste a new URL and click 'Add URL'")

        remove_url_btn = ttk.Button(url_section, text="Remove URL", command=self.remove_url)
        remove_url_btn.grid(row=2, column=0, sticky="ew", pady=5)
        self.add_tooltip(remove_url_btn, "Remove the selected URL from the list")
        move_up_btn = ttk.Button(url_section, text="Move Up", command=self.move_url_up)
        move_up_btn.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=5)
        self.add_tooltip(move_up_btn, "Move the selected URL up in the queue")
        move_down_btn = ttk.Button(url_section, text="Move Down", command=self.move_url_down)
        move_down_btn.grid(row=2, column=2, sticky="ew", padx=(8, 0), pady=5)
        self.add_tooltip(move_down_btn, "Move the selected URL down in the queue")
        clear_completed_btn = ttk.Button(url_section, text="Clear Completed", command=self.clear_completed_urls)
        clear_completed_btn.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(5, 0))
        self.add_tooltip(clear_completed_btn, "Remove all completed (already processed) URLs from the queue")

        # --- Download Folder Group ---
        dir_section = ttk.LabelFrame(self.frame, text="Download Folder", padding=(15, 10))
        dir_section.grid(row=3, column=0, columnspan=4, sticky="ew", padx=10, pady=(0, 15))
        dir_section.columnconfigure(1, weight=1)
        dir_section.configure(labelanchor='n')
        dir_entry = ttk.Entry(dir_section, textvariable=self.base_dir, width=60, font=("Segoe UI", 11))
        dir_entry.grid(row=0, column=0, sticky="ew", pady=5)
        dir_btn = ttk.Button(dir_section, text="Browse", command=self.browse_dir)
        dir_btn.grid(row=0, column=1, sticky="w", padx=(8, 0), pady=5)
        self.add_tooltip(dir_btn, "Choose the download destination folder")
        self.add_tooltip(dir_entry, "Edit or paste the download folder path")

        # --- Action Buttons Group ---
        action_section = ttk.LabelFrame(self.frame, text="Actions", padding=(15, 10))
        action_section.grid(row=4, column=0, columnspan=4, sticky="ew", padx=10, pady=(0, 15))
        action_section.configure(labelanchor='n')
        self.download_btn = ttk.Button(action_section, text="▶ Start Download", command=self.start_download_all_thread)
        self.download_btn.grid(row=0, column=0, pady=5, padx=(0, 8), sticky="ew")
        self.add_tooltip(self.download_btn, "Start downloading all files from the URLs above (runs in background, UI stays responsive)")
        self.pause_btn = ttk.Button(action_section, text="⏸ Pause", command=self.pause_downloads)
        self.pause_btn.grid(row=0, column=1, pady=5, padx=(0, 8), sticky="ew")
        self.add_tooltip(self.pause_btn, "Pause all downloads in progress.")
        self.resume_btn = ttk.Button(action_section, text="▶ Resume", command=self.resume_downloads, state='disabled')
        self.resume_btn.grid(row=0, column=2, pady=5, padx=(0, 8), sticky="ew")
        self.add_tooltip(self.resume_btn, "Resume paused downloads.")
        self.schedule_btn = ttk.Button(action_section, text="⏰ Schedule", command=self.open_schedule_window)
        self.schedule_btn.grid(row=0, column=3, pady=5, padx=(0, 8), sticky="ew")
        self.add_tooltip(self.schedule_btn, "Schedule downloads for specific days and times")
        self.json_btn = ttk.Button(action_section, text="📄 Show Downloaded JSON", command=self.show_json)
        self.json_btn.grid(row=1, column=0, pady=5, padx=(0, 8), sticky="ew")
        self.add_tooltip(self.json_btn, "Show the JSON file of downloaded files")
        self.skipped_btn = ttk.Button(action_section, text="🚫 Show Skipped Files", command=self.show_skipped)
        self.skipped_btn.grid(row=1, column=1, pady=5, padx=(0, 8), sticky="ew")
        self.add_tooltip(self.skipped_btn, "Show files that were skipped (already exist or duplicate)")

        # --- Progress Section ---
        progress_section = ttk.LabelFrame(self.frame, text="Progress", padding=(15, 10))
        progress_section.grid(row=5, column=0, columnspan=4, sticky="ew", padx=10, pady=(0, 15))
        progress_section.configure(labelanchor='n')
        progress_label = ttk.Label(progress_section, text="Overall Progress:", font=("Segoe UI", 12))
        progress_label.grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.add_tooltip(progress_label, "Shows the overall download progress.")
        self.progress = ttk.Progressbar(progress_section, orient='horizontal', length=400, mode='determinate', style='Modern.Horizontal.TProgressbar')
        self.progress.grid(row=0, column=1, columnspan=3, pady=(0, 5), sticky="ew")
        self.add_tooltip(self.progress, "Overall progress for all downloads.")
        file_progress_label = ttk.Label(progress_section, text="Current File:", font=("Segoe UI", 12))
        file_progress_label.grid(row=1, column=0, sticky="w", pady=(0, 5))
        self.file_progress = ttk.Progressbar(progress_section, orient='horizontal', length=400, mode='determinate', style='ModernFile.Horizontal.TProgressbar')
        self.file_progress.grid(row=1, column=1, columnspan=3, pady=(0, 5), sticky="ew")
        self.add_tooltip(self.file_progress, "Progress for the current file being downloaded.")
        self.speed_eta_var = tk.StringVar(value="Speed: -- ETA: --")
        self.speed_eta_label = ttk.Label(progress_section, textvariable=self.speed_eta_var, font=("Segoe UI", 11))
        self.speed_eta_label.grid(row=2, column=0, columnspan=4, sticky="w", pady=(0, 5))
        self.add_tooltip(self.speed_eta_label, "Shows current download speed and estimated time remaining for the current file.")

        # --- Status Pane Group ---
        import tkinter.scrolledtext as st
        status_section = ttk.LabelFrame(self.frame, text="Status Log", padding=(15, 10))
        status_section.grid(row=6, column=0, columnspan=4, sticky="nsew", padx=10, pady=(0, 15))
        status_section.configure(labelanchor='n')
        status_pane_label = ttk.Label(status_section, text="Status Pane:", font=("Segoe UI", 12))
        status_pane_label.grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.add_tooltip(status_pane_label, "Shows log messages and status updates.")
        self.status_pane = st.ScrolledText(status_section, height=10, width=100, state='disabled', wrap='word', font=("Segoe UI", 11))
        self.status_pane.grid(row=1, column=0, columnspan=4, sticky="nsew", pady=(0, 5))
        self.add_tooltip(self.status_pane, "Log and status output. Shows download progress, errors, and info.")
        self.status_pane_visible = True

        # Make widgets expand with window
        for i in range(4):
            self.frame.columnconfigure(i, weight=1)
        for i in range(7):
            self.frame.rowconfigure(i, weight=0)
        self.frame.rowconfigure(6, weight=1)

        # Store references for toggling log panel
        self._main_canvas = self.canvas
        self._main_frame = self.frame

        # Persistent Status Bar (bottom of window) with summary
        self.summary_var = tk.StringVar(value="Queued: 0 | Completed: 0 | Failed: 0")
        status_frame = ttk.Frame(self.root)
        status_frame.grid(row=1, column=0, sticky='ew')
        status_frame.columnconfigure(1, weight=1)
        self.status_bar = ttk.Label(status_frame, textvariable=self.status, relief=tk.SUNKEN, anchor='w', foreground='blue')
        self.status_bar.grid(row=0, column=0, sticky='ew')
        self.summary_bar = ttk.Label(status_frame, textvariable=self.summary_var, relief=tk.SUNKEN, anchor='e', foreground='green')
        self.summary_bar.grid(row=0, column=1, sticky='ew')
        self.add_tooltip(self.status_bar, "Persistent status bar. Shows the latest status message.")
        self.add_tooltip(self.summary_bar, "Summary: queued, completed, failed counts.")

        # Quit and Dark Mode buttons (always visible, bottom row of main frame)
        quit_btn = ttk.Button(self.frame, text="Quit", command=self.force_quit)
        quit_btn.grid(row=13, column=0, sticky="w", pady=(10, 0))
        self.add_tooltip(quit_btn, "Force quit the application immediately")
        dark_btn = ttk.Button(self.frame, text="Toggle Dark Mode", command=self.toggle_dark_mode)
        dark_btn.grid(row=13, column=3, sticky="e", pady=(10, 0))
        self.add_tooltip(dark_btn, "Switch between light and dark mode")

    def update_summary_bar(self, queued=None, completed=None, failed=None):
        # Update the summary bar with current counts
        if not hasattr(self, '_summary_counts'):
            self._summary_counts = {'queued': 0, 'completed': 0, 'failed': 0}
        if queued is not None:
            self._summary_counts['queued'] = queued
        if completed is not None:
            self._summary_counts['completed'] = completed
        if failed is not None:
            self._summary_counts['failed'] = failed
        self.summary_var.set(f"Queued: {self._summary_counts['queued']} | Completed: {self._summary_counts['completed']} | Failed: {self._summary_counts['failed']}")

        # Make widgets expand with window
        for i in range(4):
            self.frame.columnconfigure(i, weight=1)
        for i in range(14):
            self.frame.rowconfigure(i, weight=0)
        self.frame.rowconfigure(12, weight=1)
        # Store references for toggling log panel
        self._main_canvas = self.canvas
        self._main_frame = self.frame

    def clear_completed_urls(self):
        """Remove all URLs that have already been processed from the queue and listbox."""
        count = getattr(self, 'processed_count', 0)
        if count > 0:
            self.urls = self.urls[count:]
            # Remove from listbox
            for i in range(count-1, -1, -1):
                self.url_listbox.delete(i)
            self.processed_count = 0
            self.save_queue_state()
            self.logger.info("Cleared completed URLs from the queue.")

        # Download history log viewer (ScrolledText)
        import tkinter.scrolledtext as st
        self.history_text = st.ScrolledText(self.history_tab, height=40, width=120, state='disabled', wrap='word')
        self.history_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.add_tooltip(self.history_text, "View the download and error log history.")
        refresh_btn = ttk.Button(self.history_tab, text="Refresh Log", command=self.refresh_history_log)
        refresh_btn.pack(pady=5)
        self.add_tooltip(refresh_btn, "Reload the log file contents.")
        self.refresh_history_log()

    def refresh_history_log(self):
        """Refresh the download history log viewer tab, with optional filtering."""
        log_path = getattr(self, 'log_file', None)
        filter_text = getattr(self, 'history_filter_var', None)
        filter_val = filter_text.get().strip().lower() if filter_text else ''
        if not log_path or not os.path.exists(log_path):
            self.history_text.configure(state='normal')
            self.history_text.delete('1.0', tk.END)
            self.history_text.insert(tk.END, "No log file found or logging not started yet.")
            self.history_text.configure(state='disabled')
            return
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            if filter_val:
                lines = [line for line in lines if filter_val in line.lower()]
            log_content = ''.join(lines)
            self.history_text.configure(state='normal')
            self.history_text.delete('1.0', tk.END)
            self.history_text.insert(tk.END, log_content)
            self.history_text.configure(state='disabled')
        except Exception as e:
            self.history_text.configure(state='normal')
            self.history_text.delete('1.0', tk.END)
            self.history_text.insert(tk.END, f"Failed to read log file: {e}")
            self.history_text.configure(state='disabled')
    def pause_downloads(self):
        """Pause all downloads."""
        if not self._is_paused:
            self._pause_event.clear()
            self._is_paused = True
            self.status.set("Paused. Click Resume to continue.")
            self.pause_btn.config(state='disabled')
            self.resume_btn.config(state='normal')

    def resume_downloads(self):
        """Resume paused downloads."""
        if self._is_paused:
            self._pause_event.set()
            self._is_paused = False
            self.status.set("Resumed. Downloads continuing.")
            self.pause_btn.config(state='normal')
            self.resume_btn.config(state='disabled')

    def remove_url(self):
        selection = self.url_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        self.url_listbox.delete(index)
        del self.urls[index]

    def force_quit(self):
        import os
        os._exit(0)

    def add_tooltip(self, widget, text):
        # Improved tooltip implementation: always destroys on leave, never stacks
        def on_enter(event):
            # Destroy any existing tooltip first
            if hasattr(self, 'tooltip') and self.tooltip is not None:
                try:
                    self.tooltip.destroy()
                except Exception:
                    pass
                self.tooltip = None
            self.tooltip = tk.Toplevel(widget)
            self.tooltip.wm_overrideredirect(True)
            x = widget.winfo_rootx() + 20
            y = widget.winfo_rooty() + 20
            self.tooltip.wm_geometry(f"+{x}+{y}")
            label = tk.Label(self.tooltip, text=text, background="#333", foreground="#fff", relief='solid', borderwidth=1, font=("Segoe UI", 9))
            label.pack(ipadx=4, ipady=2)

        def on_leave(event):
            if hasattr(self, 'tooltip') and self.tooltip is not None:
                try:
                    self.tooltip.destroy()
                except Exception:
                    pass
                self.tooltip = None

        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)

    def toggle_dark_mode(self):
        # Simple dark mode toggle for ttk widgets
        self.dark_mode = not self.dark_mode
        style = ttk.Style()
        if self.dark_mode:
            style.theme_use("clam")
            style.configure("TFrame", background="#222")
            style.configure("TLabel", background="#222", foreground="#eee")
            style.configure("TLabelFrame", background="#222", foreground="#eee")
            style.configure("TButton", background="#333", foreground="#eee")
            style.configure("TEntry", fieldbackground="#333", foreground="#eee")
            style.configure("TProgressbar", background="#444")
        else:
            style.theme_use("clam")
            style.configure("TFrame", background="#f0f0f0")
            style.configure("TLabel", background="#f0f0f0", foreground="#222")
            style.configure("TLabelFrame", background="#f0f0f0", foreground="#222")
            style.configure("TButton", background="#e0e0e0", foreground="#222")
            style.configure("TEntry", fieldbackground="#fff", foreground="#222")
            style.configure("TProgressbar", background="#0078d7")

    def add_url(self):
        url = self.url_entry.get().strip()
        if url and url not in self.urls:
            self.urls.append(url)
            self.url_listbox.insert(tk.END, url)
            self.url_entry.delete(0, tk.END)

    def browse_dir(self):
        folder = filedialog.askdirectory()
        if folder:
            self.base_dir.set(folder)

    def show_json(self):
        json_path = os.path.join(self.base_dir.get(), 'epstein_file_tree.json')
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as jf:
                data = jf.read()
            self.show_popup("Downloaded Files JSON", data)
        else:
            self.show_popup("Downloaded Files JSON", "No JSON file found.")

    def show_skipped(self):
        if self.skipped_files:
            self.show_popup("Skipped Files", '\n'.join(self.skipped_files))
        else:
            self.show_popup("Skipped Files", "No skipped files yet.")

    def show_popup(self, title, content):
        popup = tk.Toplevel(self.root)
        popup.title(title)
        text = tk.Text(popup, wrap='word', width=100, height=30)
        text.insert(tk.END, content)
        text.pack(fill=tk.BOTH, expand=True)
        close_btn = ttk.Button(popup, text="Close", command=popup.destroy)
        close_btn.pack(pady=5)

    def open_schedule_window(self):
        win = tk.Toplevel(self.root)
        win.title("Schedule Download")
        ttk.Label(win, text="Days (comma separated, e.g. Mon,Wed,Fri):").pack(anchor=tk.W)
        days_entry = ttk.Entry(win)
        days_entry.pack(fill=tk.X)
        ttk.Label(win, text="Time (24h, e.g. 14:30):").pack(anchor=tk.W)
        time_entry = ttk.Entry(win)
        time_entry.pack(fill=tk.X)
        def set_schedule():
            days = [d.strip().capitalize() for d in days_entry.get().split(',') if d.strip()]
            t = time_entry.get().strip()
            if not days or not t:
                messagebox.showerror("Error", "Please enter days and time.")
                return
            self.schedule_download(days, t)
            win.destroy()
        ttk.Button(win, text="Set Schedule", command=set_schedule).pack(pady=5)

    def schedule_download(self, days, t):
        self.scheduled = True
        def check_and_run():
            while self.scheduled:
                now = datetime.now()
                day = now.strftime('%a')
                cur_time = now.strftime('%H:%M')
                if day in days and cur_time == t:
                    self.start_download_thread()
                    time.sleep(60)  # avoid double run in the same minute
                time.sleep(10)
        threading.Thread(target=check_and_run, daemon=True).start()

    def start_download_thread(self):
        self.logger.debug("start_download_thread called.")
        # Start the download queue in a background thread
        self._download_queue = None  # Will be set in process_download_queue
        threading.Thread(target=self.process_download_queue, daemon=True).start()

    def add_url_dynamic(self, url):
        """Add a URL to the download queue during download."""
        if hasattr(self, '_download_queue') and self._download_queue is not None:
            self._download_queue.put(url)
            self.urls.append(url)
            self.url_listbox.insert(tk.END, url)
            self.logger.info(f"Dynamically added URL to queue: {url}")
        else:
            self.add_url()

    def remove_url_dynamic(self, url):
        """Remove a URL from the download queue during download."""
        if url in self.urls:
            self.urls.remove(url)
            # Remove from listbox
            idxs = [i for i, u in enumerate(self.url_listbox.get(0, tk.END)) if u == url]
            for idx in reversed(idxs):
                self.url_listbox.delete(idx)
            self.logger.info(f"Dynamically removed URL: {url}")
        # Note: If already in queue, it will be skipped in process_download_queue

    def process_download_queue(self):
        # Track summary counts
        self.update_summary_bar(queued=len(self.urls), completed=0, failed=0)
        """
        Implements a download queue system. Each URL is queued and processed in order, with progress bar updates.
        Allows dynamic add/remove of URLs during download. Skips duplicate files.
        """
        import queue
        self.thread_safe_status("Preparing download queue...")
        url_queue = queue.Queue()
        seen_urls = set()
        for url in self.urls:
            if url not in seen_urls:
                url_queue.put(url)
                seen_urls.add(url)
        self._download_queue = url_queue
        base_dir = self.base_dir.get()
        os.makedirs(base_dir, exist_ok=True)
        self.setup_logger(base_dir)
        total = url_queue.qsize()
        self.progress['maximum'] = total
        self.progress['value'] = 0
        self.logger.info(f"Download queue started. {total} URLs queued.")
        processed = getattr(self, "processed_count", 0)
        downloaded_files = set()
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                failed_count = 0
                while not url_queue.empty():
                    # Pause support
                    while not self._pause_event.is_set():
                        time.sleep(0.1)
                    url = url_queue.get()
                    if url in seen_urls:
                        # Already processed (from dynamic add)
                        continue
                    seen_urls.add(url)
                    self.thread_safe_status(f"Processing: {url}")
                    try:
                        if url.startswith('https://drive.google.com/drive/folders/'):
                            credentials_path = self.config.get('credentials_path', None)
                            gdrive_dir = os.path.join(base_dir, 'GoogleDrive')
                            self.logger.info(f"Processing Google Drive folder: {url}")
                            self.download_gdrive_with_fallback(url, gdrive_dir, credentials_path)
                        else:
                            self.logger.info(f"Visiting: {url}")
                            # Check for duplicate files before download
                            s, t, a = self.download_files_threaded(page, url, base_dir, skipped_files=self.skipped_files, file_tree=self.file_tree)
                            # Only add files that are not already downloaded
                            for f in t.values():
                                for file_path in f:
                                    if file_path in downloaded_files:
                                        self.logger.info(f"Skipping duplicate file: {file_path}")
                                    else:
                                        downloaded_files.add(file_path)
                            self.skipped_files.update(s or set())
                            self.file_tree.update(t or {})
                        url_queue.task_done()
                        processed += 1
                        self.processed_count = processed
                        self.progress['value'] = processed
                        self.update_summary_bar(queued=url_queue.qsize(), completed=processed, failed=failed_count)
                        self.root.update_idletasks()
                        self.save_queue_state()
                    except Exception as e:
                        failed_count += 1
                        self.update_summary_bar(queued=url_queue.qsize(), completed=processed, failed=failed_count)
                        self.logger.error(f"Exception processing {url}: {e}", exc_info=True)
                browser.close()
        except Exception as e:
            self.logger.error(f"Exception in download queue: {e}", exc_info=True)
        self.progress['value'] = total
        self.update_summary_bar(queued=0, completed=processed, failed=failed_count)
        self.root.update_idletasks()
        self.logger.info("All downloads in queue complete.")
        self.thread_safe_status("All downloads in queue complete.")
        messagebox.showinfo("Download Complete", "All downloads in the queue are complete. See the log for details.")

    def download_gdrive_folder(self, folder_url, output_dir):
        import gdown
        import logging
        logger = self.logger if hasattr(self, 'logger') and self.logger else logging.getLogger()
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"Starting Google Drive folder download: {folder_url} to {output_dir}")
        try:
            logger.info(f"Listing subfolders and files in Google Drive folder: {folder_url}")
            folder_list = gdown.download_folder(url=folder_url, output=output_dir, quiet=True, use_cookies=False, remaining_ok=True)
            if not folder_list:
                logger.error(f"No files found or failed to list files in Google Drive folder: {folder_url}")
                return []
            subfolders = set()
            files = []
            for item in folder_list:
                if isinstance(item, dict) and item.get('mimeType') == 'application/vnd.google-apps.folder':
                    subfolders.add(item['id'])
                elif isinstance(item, dict):
                    files.append(item)
            logger.info(f"Found {len(subfolders)} subfolders and {len(files)} files in root folder.")
            batch_size = 45
            result = []
            # Download files in root folder
            for i in range(0, len(files), batch_size):
                batch = files[i:i+batch_size]
                logger.info(f"Downloading batch {i//batch_size+1} in root: files {i+1} to {min(i+batch_size, len(files))}")
                for file_info in batch:
                    file_id = file_info['id']
                    file_name = file_info['name']
                    dest_path = os.path.join(output_dir, file_name)
                    # Pause support
                    while hasattr(self, '_pause_event') and not self._pause_event.is_set():
                        time.sleep(0.1)
                    logger.info(f"Downloading Google Drive file: {file_name} to {dest_path}")
                    try:
                        gdown.download(id=file_id, output=dest_path, quiet=False, use_cookies=False)
                        result.append((file_name, dest_path))
                        logger.info(f"Downloaded Google Drive file: {file_name} to {dest_path}")
                    except Exception as e:
                        logger.error(f"Failed to download Google Drive file {file_name}: {e}")
            # Download files from each subfolder
            for subfolder_id in subfolders:
                subfolder_url = f"https://drive.google.com/drive/folders/{subfolder_id}"
                subfolder_output = os.path.join(output_dir, subfolder_id)
                os.makedirs(subfolder_output, exist_ok=True)
                logger.info(f"Listing files in subfolder: {subfolder_url}")
                subfolder_list = gdown.download_folder(url=subfolder_url, output=subfolder_output, quiet=True, use_cookies=False, remaining_ok=True)
                subfolder_files = [f for f in subfolder_list if isinstance(f, dict) and f.get('mimeType') != 'application/vnd.google-apps.folder']
                logger.info(f"Found {len(subfolder_files)} files in subfolder {subfolder_id}.")
                for i in range(0, len(subfolder_files), batch_size):
                    batch = subfolder_files[i:i+batch_size]
                    logger.info(f"Downloading batch {i//batch_size+1} in subfolder {subfolder_id}: files {i+1} to {min(i+batch_size, len(subfolder_files))}")
                    for file_info in batch:
                        file_id = file_info['id']
                        file_name = file_info['name']
                        dest_path = os.path.join(subfolder_output, file_name)
                        # Pause support
                        while hasattr(self, '_pause_event') and not self._pause_event.is_set():
                            time.sleep(0.1)
                        logger.info(f"Downloading Google Drive file: {file_name} to {dest_path}")
                        try:
                            gdown.download(id=file_id, output=dest_path, quiet=False, use_cookies=False)
                            result.append((os.path.join(subfolder_id, file_name), dest_path))
                            logger.info(f"Downloaded Google Drive file: {file_name} to {dest_path}")
                        except Exception as e:
                            logger.error(f"Failed to download Google Drive file {file_name}: {e}")
            logger.info(f"Completed Google Drive folder download: {folder_url}")
            return result
        except Exception as e:
            import traceback
            msg = f"Failed to process Google Drive folder: {e}\n{traceback.format_exc()}"
            logger.error(msg)
            # Show only a user-friendly error dialog
            try:
                messagebox.showerror(
                    "Google Drive Download Error",
                    "A problem occurred while downloading from Google Drive. This may be due to a bug in gdown or an unsupported folder. Please check the log for technical details."
                )
            except Exception:
                pass
            return []

    def hash_file(self, file_path, chunk_size=65536):
        sha256 = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(chunk_size), b''):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            print(f"Failed to hash {file_path}: {e}")
            return None

    def build_existing_hash_file(self, base_dir, hash_file_path):
        """
        Scan all files in base_dir, compute hashes, and store them in a file (one per line: hash<tab>path).
        Shows progress in the status pane. Uses multithreading for speed.
        Skips hashing files whose hash was updated within the last 4 hours (uses a cache file).
        """
        import threading
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import os, time, json
        CACHE_HOURS = 4
        cache_file = hash_file_path + ".cache.json"
        now = time.time()
        # Load cache if exists
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as cf:
                    hash_cache = json.load(cf)
            except Exception:
                hash_cache = {}
        else:
            hash_cache = {}

        all_files = []
        for root, dirs, files in os.walk(base_dir):
            for f in files:
                all_files.append(os.path.join(root, f))
        total = len(all_files)
        if total == 0:
            self.thread_safe_status("No files found for scanning.")
            return

        def hash_file_worker(path):
            relpath = os.path.relpath(path, base_dir).replace('\\', '/').lower()
            filename = os.path.basename(path).lower()
            cache_entry = hash_cache.get(path)
            if cache_entry:
                cached_hash, cached_time = cache_entry
                if now - cached_time < CACHE_HOURS * 3600:
                    return (path, cached_hash, relpath, filename, cached_time)
            # Not cached or cache expired, compute hash
            file_hash = self.hash_file(path)
            return (path, file_hash, relpath, filename, now)

        # Use 50% of available CPU threads, at least 1
        try:
            cpu_count = os.cpu_count() or 2
            max_workers = max(1, cpu_count // 2)
        except Exception:
            max_workers = 4

        results = [None] * total
        self._existing_files = dict()  # (filename.lower(), relpath.lower()) -> hash
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {executor.submit(hash_file_worker, path): idx for idx, path in enumerate(all_files)}
            for count, future in enumerate(as_completed(future_to_idx), 1):
                idx = future_to_idx[future]
                path, file_hash, relpath, filename, hash_time = future.result()
                results[idx] = (path, file_hash)
                # Track all filenames and relpaths with their hash
                self._existing_files[(filename, relpath)] = file_hash
                # Update cache
                if file_hash:
                    hash_cache[path] = (file_hash, hash_time)
                if count % 25 == 0 or count == total:
                    msg = f"Scanning for existing files: {count}/{total} ({int(count/total*100) if total else 100}%)"
                    self.root.after(0, self.thread_safe_status, msg)

        # Save updated cache
        try:
            with open(cache_file, "w", encoding="utf-8") as cf:
                json.dump(hash_cache, cf)
        except Exception:
            pass

        with open(hash_file_path, 'w', encoding='utf-8') as hf:
            for path, file_hash in results:
                if file_hash:
                    hf.write(f"{file_hash}\t{path}\n")

    def hash_exists_in_file(self, hash_file_path, file_hash):
        """
        Check if a hash exists in the hash file by reading line by line.
        """
        try:
            with open(hash_file_path, 'r', encoding='utf-8') as hf:
                for line in hf:
                    if line.startswith(file_hash + '\t') or line.startswith(file_hash + '\n'):
                        return True
        except FileNotFoundError:
            return False
        return False

    def append_hash_to_file(self, hash_file_path, file_hash, file_path):
        with open(hash_file_path, 'a', encoding='utf-8') as hf:
            hf.write(f"{file_hash}\t{file_path}\n")


    def start_download_all_thread(self):
        import threading
        threading.Thread(target=self.download_all, daemon=True).start()

    def download_all(self):
        import threading
        def run():
            self.thread_safe_status("Starting download...")
            urls = list(self.urls)
            base_dir = self.base_dir.get()
            base_dir_cmp = base_dir.lower()
            os.makedirs(base_dir, exist_ok=True)
            # Scan for all existing files in base_dir and subfolders
            self.thread_safe_status("Scanning for existing files...")
            self.root.update_idletasks()
            self.hash_file_path = os.path.join(base_dir, 'existing_hashes.txt')
            self.setup_logger(base_dir)
            self.logger.info(f"Starting download. URLs: {urls}")
            try:
                self.build_existing_hash_file(base_dir_cmp, self.hash_file_path)
            except Exception as e:
                self.logger.error(f"Failed to build hash file: {e}")
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to scan existing files: {e}"))
                return
            self.skipped_files = set()
            self.file_tree = {}
            all_files = set()
            total = len(urls)
            self.progress['maximum'] = total
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    context = browser.new_context()
                    page = context.new_page()
                    for i, url in enumerate(urls):
                        self.thread_safe_status(f"Visiting: {url}")
                        self.logger.info(f"Visiting: {url}")
                        self.progress['value'] = i
                        self.root.update_idletasks()
                        if url.startswith('https://drive.google.com/drive/folders/'):
                            gdrive_dir = os.path.join(base_dir, 'GoogleDrive')
                            try:
                                gdrive_files = self.download_gdrive_folder(url, gdrive_dir)
                                # Add Google Drive files to file_tree and all_files
                                for rel_path, dest_path in gdrive_files:
                                    folder = os.path.dirname(dest_path)
                                    if folder not in self.file_tree:
                                        self.file_tree[folder] = []
                                    self.file_tree[folder].append(dest_path)
                                    all_files.add('gdrive://' + rel_path)
                                self.logger.info(f"Downloaded Google Drive folder: {url}")
                            except Exception as e:
                                self.logger.error(f"Failed to download Google Drive folder {url}: {e}")
                                self.root.after(0, lambda url=url, e=e: messagebox.showerror("Error", f"Failed to download Google Drive folder: {url}\n{e}"))
                            continue
                        try:
                            s, t, a = self.download_files(page, url, base_dir)
                            self.skipped_files.update(s or set())
                            self.file_tree.update(t or {})
                            all_files.update(a or set())
                        except Exception as e:
                            self.logger.error(f"Error downloading from {url}: {e}")
                            self.root.after(0, lambda url=url, e=e: messagebox.showerror("Error", f"Error downloading from {url}: {e}"))
                    browser.close()
            except Exception as e:
                self.logger.error(f"Critical error in Playwright: {e}")
                self.root.after(0, lambda e=e: messagebox.showerror("Error", f"Critical error in Playwright: {e}"))
                return
            self.thread_safe_status("Download complete. Checking for missing files...")
            self.logger.info("Download complete. Checking for missing files...")
            self.progress['value'] = total
            self.root.update_idletasks()
            # Save JSON
            json_path = os.path.join(base_dir, 'epstein_file_tree.json')
            try:
                with open(json_path, 'w', encoding='utf-8') as jf:
                    json.dump(self.file_tree, jf, indent=2)
                self.logger.info(f"File tree JSON saved: {json_path}")
            except Exception as e:
                self.logger.error(f"Failed to save JSON: {e}")
                self.root.after(0, lambda e=e: messagebox.showerror("Error", f"Failed to save JSON: {e}"))
            self.downloaded_json.set(json_path)
            # Check for missing files
            missing_files = []
            for url in all_files:
                if url.startswith('gdrive://'):
                    rel_path = url.replace('gdrive://', '')
                    local_path = os.path.join(base_dir, 'GoogleDrive', rel_path)
                else:
                    rel_path = self.sanitize_path(url.replace('https://', ''))
                    local_path = os.path.join(base_dir, rel_path)
                if not os.path.exists(local_path):
                    missing_files.append((url, local_path))
            if missing_files:
                self.thread_safe_status(f"Downloading {len(missing_files)} missing files...")
                self.logger.warning(f"{len(missing_files)} missing files detected. Retrying...")
                for url, local_path in missing_files:
                    try:
                        os.makedirs(os.path.dirname(local_path), exist_ok=True)
                        if url.startswith('gdrive://'):
                            # Redownload Google Drive file by name (not implemented: would require mapping rel_path to file_id)
                            self.logger.error(f"Cannot redownload missing Google Drive file automatically: {url}")
                        else:
                            proxies = None
                            if self.config.get('proxy'):
                                proxies = {"http": self.config['proxy'], "https": self.config['proxy']}
                            speed_limit = int(self.config.get('speed_limit_kbps', 0))
                            with requests.get(url, stream=True, proxies=proxies) as r:
                                r.raise_for_status()
                                with open(local_path, 'wb') as f:
                                    downloaded = 0
                                    start_time = time.time()
                                    for chunk in r.iter_content(chunk_size=8192):
                                        if chunk:
                                            f.write(chunk)
                                            downloaded += len(chunk)
                                            if speed_limit > 0:
                                                elapsed = time.time() - start_time
                                                expected_time = downloaded / (speed_limit * 1024)
                                                if elapsed < expected_time:
                                                    time.sleep(expected_time - elapsed)
                            self.logger.info(f"Successfully downloaded missing file: {url}")
                    except Exception as e:
                        self.logger.error(f"Failed to download missing file {url}: {e}")
                self.thread_safe_status("Download complete (with missing files retried).")
            else:
                self.thread_safe_status("Download complete. No missing files.")
                self.logger.info("No missing files after download.")
        threading.Thread(target=run, daemon=True).start()

    def download_files(self, page, base_url, base_dir, visited=None, skipped_files=None, file_tree=None, all_files=None):
        from concurrent.futures import ThreadPoolExecutor, as_completed
        allowed_domains = [
            'https://www.justice.gov/epstein',
            'https://oversight.house.gov/release/oversight-committee-releases-epstein-records-provided-by-the-department-of-justice/'
        ]
        if visited is None:
            visited = set()
        if skipped_files is None:
            skipped_files = set()
        if file_tree is None:
            file_tree = {}
        if all_files is None:
            all_files = set()
        if base_url in visited:
            return skipped_files, file_tree, all_files
        visited.add(base_url)
        self.thread_safe_status(f"Visiting: {base_url}")
        try:
            page.goto(base_url)
        except Exception as e:
            print(f"Error loading {base_url}: {e}\nContinuing...")
            return skipped_files, file_tree, all_files
        links = page.query_selector_all('a')
        self.thread_safe_status(f"Found {len(links)} links on {base_url}")
        hrefs = []
        for link in links:
            try:
                href = link.get_attribute('href')
                if href:
                    hrefs.append(href)
            except Exception as e:
                print(f"Error reading link attribute: {e}")

        # Prepare download tasks
        download_tasks = []
        download_info = []  # (abs_url, local_path, folder)
        for href in hrefs:
            if href.startswith('#'):
                continue
            abs_url = urllib.parse.urljoin(base_url, href)
            # Skip search links
            if '/search' in abs_url:
                continue
            if re.search(r'\.(pdf|docx?|xlsx?|zip|txt|jpg|png|csv|mp4|mov|avi|wmv|wav|mp3|m4a)$', abs_url, re.IGNORECASE):
                rel_path = self.sanitize_path(abs_url.replace('https://', ''))
                local_path = os.path.join(base_dir, rel_path)
                folder = os.path.dirname(local_path)
                if folder not in file_tree:
                    file_tree[folder] = []
                file_tree[folder].append(local_path)
                all_files.add(abs_url)
                # Skip download if file with same name, relpath, and hash exists
                filename = os.path.basename(local_path)
                filename_lc = filename.lower()
                relpath = os.path.relpath(local_path, base_dir).replace('\\', '/').lower()
                file_hash = None
                exists = False
                save_path = local_path
                if hasattr(self, '_existing_files'):
                    if (filename_lc, relpath) in self._existing_files:
                        # If file exists at this path, check hash
                        try:
                            file_hash = self.hash_file(local_path)
                        except Exception:
                            file_hash = None
                        if file_hash and file_hash == self._existing_files[(filename_lc, relpath)]:
                            self.logger.info(f"Skipping (already exists, same hash): {local_path}")
                            skipped_files.add(local_path)
                            exists = True
                        else:
                            # Conflict: file exists but hash is different, save as filename-YYYYMMDD_HHMMSS.ext
                            import datetime
                            base, ext = os.path.splitext(filename)
                            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                            new_filename = f"{base}-{timestamp}{ext}"
                            save_path = os.path.join(folder, new_filename)
                            self.logger.info(f"Filename conflict: saving as {save_path}")
                if exists:
                    continue
                download_info.append((abs_url, save_path, folder))
            elif (
                abs_url != base_url
                and any(abs_url.startswith(domain) for domain in allowed_domains)
                and abs_url != 'https://www.justice.gov/epstein'
                and abs_url not in visited
            ):
                sub_skipped, sub_tree, sub_all = self.download_files(page, abs_url, base_dir, visited, skipped_files, file_tree, all_files)
                skipped_files.update(sub_skipped or set())
                file_tree.update(sub_tree or {})
                all_files.update(sub_all or set())

        def download_file(abs_url, local_path):
            max_retries = 3
            delay = 2
            for attempt in range(1, max_retries + 1):
                # Pause support
                while not self._pause_event.is_set():
                    time.sleep(0.1)
                try:
                    os.makedirs(os.path.dirname(local_path), exist_ok=True)
                    self.thread_safe_status(f"Downloading {abs_url} -> {local_path} (Attempt {attempt})")
                    self.logger.info(f"Downloading {abs_url} -> {local_path} (Attempt {attempt})")
                    proxies = None
                    if self.config.get('proxy'):
                        proxies = {"http": self.config['proxy'], "https": self.config['proxy']}
                    speed_limit = int(self.config.get('speed_limit_kbps', 0))
                    with requests.get(abs_url, stream=True, timeout=300, proxies=proxies) as r:
                        r.raise_for_status()
                        with open(local_path, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                while not self._pause_event.is_set():
                                    time.sleep(0.1)
                                if chunk:
                                    f.write(chunk)
                    self.logger.info(f"Downloaded: {abs_url}")
                    return None
                except Exception as e:
                    self.logger.error(f"Failed to download {abs_url} (Attempt {attempt}): {e}")
                    if attempt < max_retries:
                        time.sleep(delay)
                        delay *= 2  # Exponential backoff
                    else:
                        self.logger.error(f"Permanently failed to download {abs_url} after {max_retries} attempts.")
                        return local_path

        # Multithreaded download (user-configurable concurrency)
        failed_downloads = []
        with ThreadPoolExecutor(max_workers=self.concurrent_downloads.get()) as executor:
            future_to_info = {executor.submit(download_file, abs_url, local_path): (abs_url, local_path) for abs_url, local_path, _ in download_info}
            for future in as_completed(future_to_info):
                abs_url, local_path = future_to_info[future]
                result = future.result()
                if result:
                    failed_downloads.append((abs_url, local_path))
        if failed_downloads:
            self.logger.error(f"Summary: {len(failed_downloads)} files failed after retries.")
            failed_list = '\n'.join([f"{url} -> {path}" for url, path in failed_downloads])
            self.logger.error(f"Failed files:\n{failed_list}")
            self.thread_safe_status(f"{len(failed_downloads)} files failed after retries. See log for details.")
        return skipped_files, file_tree, all_files

    def sanitize_path(self, path):
        parts = path.split('/')
        return os.path.join(*[re.sub(r'[<>:"/\\|?*]', '_', p) for p in parts])

    def download_drive_folder_api(self, folder_id, gdrive_dir, credentials_path):
        """
        Download all files from a Google Drive folder using the Google Drive API and a service account.
        """
        import io
        import os
        from googleapiclient.discovery import build
        from google.oauth2 import service_account
        from googleapiclient.http import MediaIoBaseDownload

        SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
        creds = service_account.Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
        service = build('drive', 'v3', credentials=creds)

        def list_files(service, folder_id):
            query = f"'{folder_id}' in parents and trashed = false"
            files = []
            page_token = None
            while True:
                response = service.files().list(q=query,
                                                spaces='drive',
                                                fields='nextPageToken, files(id, name, mimeType)',
                                                pageToken=page_token).execute()
                files.extend(response.get('files', []))
                page_token = response.get('nextPageToken', None)
                if page_token is None:
                    break
            return files

        def download_file(service, file_id, file_name, dest_dir):
            request = service.files().get_media(fileId=file_id)
            fh = io.FileIO(os.path.join(dest_dir, file_name), 'wb')
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            fh.close()

        # Ensure gdrive_dir is a directory, not a file
        if os.path.exists(gdrive_dir):
            if os.path.isfile(gdrive_dir):
                self.logger.error(f"Cannot create directory '{gdrive_dir}' because a file with the same name exists. Skipping this folder.")
                return
        else:
            os.makedirs(gdrive_dir, exist_ok=True)

        files = list_files(service, folder_id)
        for f in files:
            if f['mimeType'] == 'application/vnd.google-apps.folder':
                # Recursively download subfolders
                subfolder = os.path.join(gdrive_dir, f['name'])
                # Check for file/dir conflict for subfolder
                if os.path.exists(subfolder) and os.path.isfile(subfolder):
                    self.logger.error(f"Cannot create subdirectory '{subfolder}' because a file with the same name exists. Skipping this subfolder.")
                    continue
                self.download_drive_folder_api(f['id'], subfolder, credentials_path)
            else:
                self.logger.info(f"Downloading from Google Drive: {f['name']}")
                download_file(service, f['id'], f['name'], gdrive_dir)

def main():
    if DND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    root.title("EpsteinFilesDownloader")
    try:
        root.iconbitmap("JosephThePlatypus.ico")
    except Exception as e:
        print(f"Warning: Could not set window icon: {e}")
    # Install dependencies with progress dialog before launching main GUI
    try:
        install_dependencies_with_progress(root)
    except Exception as dep_err:
        messagebox.showerror("Startup Error", f"Failed to install dependencies: {dep_err}")
        root.destroy()
        return
    app = DownloaderGUI(root)
    root.mainloop()

if __name__ == '__main__':
    main()
