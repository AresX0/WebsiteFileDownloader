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
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
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
            subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
        except Exception as e:
            print(f"Failed to install {pip_name}: {e}")
            raise

ensure_pip()
for pkg in ("playwright", "requests", "gdown", "google-api-python-client", "google-auth", "google-auth-httplib2"):
    check_and_install(pkg)

def ensure_playwright_browsers():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            try:
                p.chromium.launch(headless=True).close()
            except Exception:
                print("Playwright browsers not found or not installed. Installing...")
                subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
    except Exception as e:
        print(f"Error ensuring Playwright browsers: {e}")
        raise

ensure_playwright_browsers()

# --- DownloaderGUI Class ---

import os
import re
import urllib.parse
import json
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright
import requests
import sched
import time
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

# Ensure pip is available
ensure_pip()

# Check and install prerequisites
check_and_install("playwright")
check_and_install("requests")
check_and_install("gdown")

# Ensure Playwright browsers are installed
def ensure_playwright_browsers():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            # Try launching a browser to see if binaries are present
            try:
                p.chromium.launch(headless=True).close()
            except Exception:
                print("Playwright browsers not found or not installed. Installing...")
                subprocess.check_call(["python", "-m", "playwright", "install", "chromium"])
    except Exception as e:
        print(f"Error ensuring Playwright browsers: {e}")
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
        # Logger setup is handled by setup_logger below
        self.urls = [
            'https://www.justice.gov/epstein/foia',
            'https://www.justice.gov/epstein/court-records',
            'https://oversight.house.gov/release/oversight-committee-releases-epstein-records-provided-by-the-department-of-justice/',
            'https://www.justice.gov/epstein/doj-disclosures',
            'https://drive.google.com/drive/folders/1TrGxDGQLDLZu1vvvZDBAh-e7wN3y6Hoz?usp=sharing',
        ]
        self.base_dir = tk.StringVar(value=r'C:\Temp\Epstein')
        self.status = tk.StringVar(value="Ready.")
        self.skipped_files = set()
        self.file_tree = {}
        self.downloaded_json = tk.StringVar(value="")
        self.dark_mode = False
        self.scheduled = False
        # Load config
        self.config_path = os.path.join(os.getcwd(), "config.json")
        self.config = self.load_config()
        # Override defaults if config exists
        if self.config.get("download_dir"):
            self.base_dir.set(self.config["download_dir"])
        if self.config.get("log_dir"):
            self.log_dir = self.config["log_dir"]
        else:
            self.log_dir = os.path.join(os.getcwd(), "logs")
        if self.config.get("credentials_path"):
            self.credentials_path = self.config["credentials_path"]
        else:
            self.credentials_path = None
        os.makedirs(self.log_dir, exist_ok=True)
        self.setup_logger(self.log_dir)
        self.logger.debug(f"EpsteinFilesDownloader v{__version__} started. Log file: {self.log_file}")
        self.create_menu()
        self.create_widgets()
        # --- Drag and Drop Setup ---
        self.setup_drag_and_drop()
    def setup_drag_and_drop(self):
        # Try to import tkinterDnD2 for drag-and-drop support
        try:
            from tkinterdnd2 import DND_FILES, TkinterDnD
        except ImportError:
            self.logger.warning("tkinterDnD2 not installed. Drag-and-drop will not be available.")
            return

        # Re-wrap root window for DnD
        if not hasattr(self.root, '_dnd_wrapped'):
            try:
                old_root = self.root
                self.root = TkinterDnD.Tk()  # Re-wrap as DnD window
                self.root._dnd_wrapped = True
                # Re-create menu bar after root replacement
                self.create_menu()
                # Re-create widgets if needed
                if hasattr(self, 'create_widgets'):
                    self.create_widgets()
                # Transfer geometry and title
                try:
                    self.root.geometry(old_root.geometry())
                    self.root.title(old_root.title())
                except Exception:
                    pass
            except Exception as e:
                self.logger.warning(f"Failed to enable drag-and-drop: {e}")
                return

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
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

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
        help_menu.add_command(label="Help", command=self.show_help)
        help_menu.add_command(label="About", command=self.show_about)
        help_menu.add_command(label="Report Issue / Send Feedback", command=self.report_issue)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

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

    def toggle_log_panel(self):
        # Show/hide the status pane and its label
        if not hasattr(self, 'status_pane_visible'):
            self.status_pane_visible = True
        if self.status_pane_visible:
            self.status_pane.grid_remove()
            if hasattr(self, '_status_pane_label'):
                self._status_pane_label.grid_remove()
            self.status_pane_visible = False
        else:
            self.status_pane.grid()
            if hasattr(self, '_status_pane_label'):
                self._status_pane_label.grid()
            self.status_pane_visible = True

    def show_progress(self):
        # Placeholder: implement showing download progress
        pass

    def check_for_updates(self):
        # Check for new commits or releases at the GitHub repository
        import requests
        repo_api_url = "https://api.github.com/repos/AresX0/WebsiteFileDownloader/commits"
        try:
            response = requests.get(repo_api_url, timeout=10)
            if response.status_code == 200:
                commits = response.json()
                if commits:
                    latest_commit = commits[0]
                    latest_sha = latest_commit.get('sha', '')
                    latest_msg = latest_commit.get('commit', {}).get('message', '')
                    # Optionally, compare with a local version/sha if tracked
                    message = f"Latest commit SHA: {latest_sha[:7]}\nMessage: {latest_msg}\n\nSee all changes at:\nhttps://github.com/AresX0/WebsiteFileDownloader/commits/main"
                    self.thread_safe_popup("Update Check", message)
                else:
                    self.thread_safe_popup("Update Check", "No commits found in the repository.")
            else:
                self.thread_safe_popup("Update Check", f"Failed to check updates. Status code: {response.status_code}")
        except Exception as e:
            self.thread_safe_popup("Update Check", f"Error checking for updates:\n{e}")

    def validate_credentials(self):
        # Placeholder: implement credentials validation
        messagebox.showinfo("Validate Credentials", "This feature is not yet implemented.")

    def test_download_link(self):
        # Placeholder: implement download link tester
        messagebox.showinfo("Test Download Link", "This feature is not yet implemented.")

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
        os.makedirs(base_dir, exist_ok=True)
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
                    self.logger.info(f"Visiting: {url}")
                    s, t, a = self.download_files_threaded(page, url, base_dir, skipped_files=self.skipped_files, file_tree=self.file_tree)
                    self.skipped_files.update(s or set())
                    self.file_tree.update(t or {})
                browser.close()
        except Exception as e:
            self.logger.error(f"Exception in start_download: {e}", exc_info=True)
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
                        credentials_path = None
                gdrive_dir = os.path.join(base_dir, 'GoogleDrive')
                self.logger.info(f"Processing Google Drive folder: {url}")
                self.download_gdrive_with_fallback(url, gdrive_dir, credentials_path)
        self.logger.info("All downloads complete.")
        messagebox.showinfo("Download Complete", "All downloads are complete. See the log for details.")

    def download_gdrive_with_fallback(self, url, gdrive_dir, credentials_path):
        import re
        match = re.search(r'/folders/([a-zA-Z0-9_-]+)', url)
        if match:
            folder_id = match.group(1)
            if os.path.exists(credentials_path):
                try:
                    os.makedirs(gdrive_dir, exist_ok=True)
                    self.download_drive_folder_api(folder_id, gdrive_dir, credentials_path)
                except Exception as e:
                    self.logger.error(f"Google Drive API download failed: {e}")
                    self.logger.info("Falling back to gdown...")
                    try:
                        import gdown
                        os.makedirs(gdrive_dir, exist_ok=True)
                        # Download all files, but skip those that already exist
                        file_list = gdown.download_folder(url=url, output=gdrive_dir, quiet=False, use_cookies=False, remaining_ok=True, return_filelist=True)
                        if file_list:
                            for f in file_list:
                                if os.path.exists(f):
                                    self.logger.info(f"Skipping (already exists): {f}")
                                else:
                                    gdown.cached_download(f, quiet=False)
                    except Exception as e2:
                        self.logger.error(f"gdown fallback failed: {e2}")
                        messagebox.showinfo(
                            "Google Drive Credentials Required",
                            "To enable full Google Drive access, create a credentials.json file as follows:\n"
                            "1. Go to https://console.cloud.google.com/\n"
                            "2. Create/select a project, enable the Google Drive API.\n"
                            "3. Go to 'APIs & Services > Credentials', create a Service Account, and download the JSON key.\n"
                            "4. Save it as credentials.json in this folder.\n"
                        )
        else:
            self.logger.error("Google Drive folder ID not found in URL.")

    def download_files_threaded(self, page, base_url, base_dir, visited=None, skipped_files=None, file_tree=None, all_files=None):
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
            max_retries = 3
            delay = 2
            for attempt in range(1, max_retries + 1):
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
                    with requests.get(abs_url, stream=True, timeout=300) as r:
                        r.raise_for_status()
                        with open(local_path, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
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
        # Schedule status update on the main thread
        self.root.after(0, self.status.set, msg)
        self.append_status_pane(msg)

    def append_status_pane(self, msg):
        def append():
            self.status_pane.configure(state='normal')
            self.status_pane.insert('end', msg + '\n')
            self.status_pane.see('end')
            self.status_pane.configure(state='disabled')
        self.root.after(0, append)

    def create_widgets(self):
        # Make window scalable
        self.root.geometry('1100x800')
        self.root.minsize(800, 600)
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        # Container frame for scrollable content (so menu bar is not covered)
        container = ttk.Frame(self.root)
        container.grid(row=0, column=0, sticky='nsew')
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        # Add a scrollable canvas for the main content
        canvas = tk.Canvas(container)
        canvas.grid(row=0, column=0, sticky='nsew')
        vscroll = ttk.Scrollbar(container, orient='vertical', command=canvas.yview)
        vscroll.grid(row=0, column=1, sticky='ns')
        canvas.configure(yscrollcommand=vscroll.set)
        frame = ttk.Frame(canvas)
        frame_id = canvas.create_window((0, 0), window=frame, anchor='nw')

        def on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox('all'))
        frame.bind('<Configure>', on_frame_configure)

        def on_canvas_configure(event):
            canvas.itemconfig(frame_id, width=event.width)
        canvas.bind('<Configure>', on_canvas_configure)

        # Title
        title = ttk.Label(frame, text="Epstein Court Records Downloader", font=("Segoe UI", 20, "bold"))
        title.grid(row=0, column=0, columnspan=4, pady=(0, 20), sticky="nsew")

        # URLs Section
        url_section = ttk.LabelFrame(frame, text="Download URLs", padding=(10, 10))
        url_section.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(0, 10))
        url_section.columnconfigure(1, weight=1)
        self.url_listbox = tk.Listbox(url_section, height=5, width=80)
        self.url_listbox.grid(row=0, column=0, columnspan=3, sticky="ew")
        for url in self.urls:
            self.url_listbox.insert(tk.END, url)
        self.url_entry = ttk.Entry(url_section, width=60)
        self.url_entry.grid(row=1, column=0, sticky="ew", pady=5)
        add_url_btn = ttk.Button(url_section, text="Add URL", command=self.add_url)
        add_url_btn.grid(row=1, column=1, sticky="w", padx=(5, 0))
        self.add_tooltip(add_url_btn, "Add a new download URL")
        self.add_tooltip(self.url_entry, "Paste a new URL and click 'Add URL'")

        # Remove URL Button (move to main frame for visibility)
        remove_url_btn = ttk.Button(frame, text="Remove URL", command=self.remove_url)
        remove_url_btn.grid(row=2, column=0, pady=(0, 10), sticky="ew")
        self.add_tooltip(remove_url_btn, "Remove the selected URL from the list")

        # Download Folder Section
        dir_section = ttk.LabelFrame(frame, text="Download Folder", padding=(10, 10))
        dir_section.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(0, 10))
        dir_section.columnconfigure(1, weight=1)
        dir_entry = ttk.Entry(dir_section, textvariable=self.base_dir, width=60)
        dir_entry.grid(row=0, column=0, sticky="ew")
        dir_btn = ttk.Button(dir_section, text="Browse", command=self.browse_dir)
        dir_btn.grid(row=0, column=1, sticky="w", padx=(5, 0))
        self.add_tooltip(dir_btn, "Choose the download destination folder")
        self.add_tooltip(dir_entry, "Edit or paste the download folder path")

        # Action Buttons

        self.download_btn = ttk.Button(frame, text="Start Download", command=self.start_download_all_thread)
        self.download_btn.grid(row=4, column=0, pady=10, sticky="ew")
        self.add_tooltip(self.download_btn, "Start downloading all files from the URLs above (runs in background, UI stays responsive)")

        self.schedule_btn = ttk.Button(frame, text="Schedule Download", command=self.open_schedule_window)
        self.schedule_btn.grid(row=4, column=1, pady=10, sticky="ew")
        self.add_tooltip(self.schedule_btn, "Schedule downloads for specific days and times")

        self.json_btn = ttk.Button(frame, text="Show Downloaded JSON", command=self.show_json)
        self.json_btn.grid(row=4, column=2, pady=10, sticky="ew")
        self.add_tooltip(self.json_btn, "Show the JSON file of downloaded files")

        self.skipped_btn = ttk.Button(frame, text="Show Skipped Files", command=self.show_skipped)
        self.skipped_btn.grid(row=4, column=3, pady=10, sticky="ew")
        self.add_tooltip(self.skipped_btn, "Show files that were skipped (already exist or duplicate)")

        # Progress Section
        progress_label = ttk.Label(frame, text="Progress:")
        progress_label.grid(row=5, column=0, sticky="w", pady=(10, 0))
        self.progress = ttk.Progressbar(frame, orient='horizontal', length=400, mode='determinate')
        self.progress.grid(row=6, column=0, columnspan=4, pady=(0, 10), sticky="ew")

        # Status Pane (ScrolledText)
        import tkinter.scrolledtext as st
        status_pane_label = ttk.Label(frame, text="Status Pane:")
        status_pane_label.grid(row=7, column=0, sticky="w", pady=(10, 0))
        self.status_pane = st.ScrolledText(frame, height=10, width=100, state='disabled', wrap='word')
        self.status_pane.grid(row=8, column=0, columnspan=4, sticky="nsew", pady=(0, 10))
        self.status_pane_visible = True

        # Status Bar
        self.status_label = ttk.Label(frame, textvariable=self.status, foreground='blue', anchor='w')
        self.status_label.grid(row=9, column=0, columnspan=4, sticky="ew", pady=(10, 0))

        # Quit Button (move to main frame for visibility)
        quit_btn = ttk.Button(frame, text="Quit", command=self.force_quit)
        quit_btn.grid(row=10, column=0, sticky="w", pady=(10, 0))
        self.add_tooltip(quit_btn, "Force quit the application immediately")

        # Dark Mode Toggle
        dark_btn = ttk.Button(frame, text="Toggle Dark Mode", command=self.toggle_dark_mode)
        dark_btn.grid(row=10, column=3, sticky="e", pady=(10, 0))
        self.add_tooltip(dark_btn, "Switch between light and dark mode")

        # Make widgets expand with window
        for i in range(4):
            frame.columnconfigure(i, weight=1)
        for i in range(11):
            frame.rowconfigure(i, weight=0)
        frame.rowconfigure(8, weight=1)

        # Store references for toggling log panel
        self._main_canvas = canvas
        self._main_frame = frame
        self._status_pane_label = status_pane_label

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
        # Simple tooltip implementation
        def on_enter(event):
            self.tooltip = tk.Toplevel(widget)
            self.tooltip.wm_overrideredirect(True)
            x = widget.winfo_rootx() + 20
            y = widget.winfo_rooty() + 20
            self.tooltip.wm_geometry(f"+{x}+{y}")
            label = tk.Label(self.tooltip, text=text, background="#333", foreground="#fff", relief='solid', borderwidth=1, font=("Segoe UI", 9))
            label.pack(ipadx=4, ipady=2)
        def on_leave(event):
            if hasattr(self, 'tooltip'):
                self.tooltip.destroy()
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
        threading.Thread(target=self.process_download_queue, daemon=True).start()

    def process_download_queue(self):
        """
        Implements a download queue system. Each URL is queued and processed in order, with progress bar updates.
        """
        import queue
        self.thread_safe_status("Preparing download queue...")
        url_queue = queue.Queue()
        for url in self.urls:
            url_queue.put(url)
        base_dir = self.base_dir.get()
        os.makedirs(base_dir, exist_ok=True)
        self.setup_logger(base_dir)
        total = url_queue.qsize()
        self.progress['maximum'] = total
        self.progress['value'] = 0
        self.logger.info(f"Download queue started. {total} URLs queued.")
        processed = 0
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                while not url_queue.empty():
                    url = url_queue.get()
                    self.thread_safe_status(f"Processing: {url}")
                    if url.startswith('https://drive.google.com/drive/folders/'):
                        credentials_path = self.config.get('credentials_path', None)
                        gdrive_dir = os.path.join(base_dir, 'GoogleDrive')
                        self.logger.info(f"Processing Google Drive folder: {url}")
                        self.download_gdrive_with_fallback(url, gdrive_dir, credentials_path)
                    else:
                        self.logger.info(f"Visiting: {url}")
                        s, t, a = self.download_files_threaded(page, url, base_dir, skipped_files=self.skipped_files, file_tree=self.file_tree)
                        self.skipped_files.update(s or set())
                        self.file_tree.update(t or {})
                    url_queue.task_done()
                    processed += 1
                    self.progress['value'] = processed
                    self.root.update_idletasks()
                browser.close()
        except Exception as e:
            self.logger.error(f"Exception in download queue: {e}", exc_info=True)
        self.progress['value'] = total
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
            # Scan for all files in the folder (metadata only)
            logger.info(f"Scanning Google Drive folder for file list: {folder_url}")
            file_list = gdown.download_folder(url=folder_url, output=output_dir, quiet=True, use_cookies=False, remaining_ok=True, return_filelist=True, skip_download=True)
            logger.info(f"Found {len(file_list)} files in Google Drive folder.")
            to_download = []
            for f in file_list:
                if not os.path.exists(f):
                    to_download.append(f)
                else:
                    logger.info(f"Skipping (already exists): {f}")
            logger.info(f"{len(to_download)} files to download (missing locally).")
            result = []
            failed = []
            max_retries = 3
            for dest_path in to_download:
                rel_path = os.path.relpath(dest_path, output_dir)
                for attempt in range(1, max_retries + 1):
                    try:
                        logger.info(f"Downloading {rel_path} (Attempt {attempt})")
                        gdown.cached_download(dest_path, quiet=False)
                        logger.info(f"Downloaded Google Drive file: {rel_path} to {dest_path}")
                        result.append((rel_path, dest_path))
                        break
                    except Exception as e:
                        logger.error(f"Failed to download {rel_path} (Attempt {attempt}): {e}")
                        if attempt == max_retries:
                            logger.error(f"Permanently failed to download {rel_path} after {max_retries} attempts.")
                            failed.append(rel_path)
            if failed:
                logger.error(f"Failed to download {len(failed)} files from Google Drive after retries: {failed}")
            logger.info(f"Completed Google Drive folder download: {folder_url}")
            return result
        except Exception as e:
            msg = f"Failed to process Google Drive folder: {e}"
            logger.error(msg)
            try:
                messagebox.showerror("Google Drive Error", msg)
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
                            with requests.get(url, stream=True) as r:
                                r.raise_for_status()
                                with open(local_path, 'wb') as f:
                                    for chunk in r.iter_content(chunk_size=8192):
                                        if chunk:
                                            f.write(chunk)
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
                try:
                    os.makedirs(os.path.dirname(local_path), exist_ok=True)
                    self.thread_safe_status(f"Downloading {abs_url} -> {local_path} (Attempt {attempt})")
                    self.logger.info(f"Downloading {abs_url} -> {local_path} (Attempt {attempt})")
                    with requests.get(abs_url, stream=True, timeout=300) as r:
                        r.raise_for_status()
                        with open(local_path, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192):
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

        # Multithreaded download (up to 6 at a time)
        failed_downloads = []
        with ThreadPoolExecutor(max_workers=6) as executor:
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
    root = tk.Tk()
    root.title("EpsteinFilesDownloader")
    try:
        root.iconbitmap("JosephThePlatypus.ico")
    except Exception as e:
        print(f"Warning: Could not set window icon: {e}")
    app = DownloaderGUI(root)
    root.mainloop()

if __name__ == '__main__':
    main()
