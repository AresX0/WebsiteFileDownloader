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

class DownloaderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Epstein Downloader")
        self.urls = [
            'https://www.justice.gov/epstein/foia',
            'https://www.justice.gov/epstein/court-records',
            'https://oversight.house.gov/release/oversight-committee-releases-epstein-records-provided-by-the-department-of-justice/',
            'https://www.justice.gov/epstein/doj-disclosures',
        ]
        self.base_dir = tk.StringVar(value=r'C:\Temp\Epstein')
        self.status = tk.StringVar()
        self.downloaded_json = tk.StringVar()
        self.skipped_files = []
        self.file_tree = {}
        self.scheduler = sched.scheduler(time.time, time.sleep)
        self.scheduled = False
        self.create_widgets()

    def create_widgets(self):
        frame = ttk.Frame(self.root)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        url_label = ttk.Label(frame, text="Download URLs:")
        url_label.grid(row=0, column=0, sticky=tk.W)
        self.url_listbox = tk.Listbox(frame, height=5, width=80)
        self.url_listbox.grid(row=1, column=0, columnspan=3, sticky=tk.W)
        for url in self.urls:
            self.url_listbox.insert(tk.END, url)
        add_url_btn = ttk.Button(frame, text="Add URL", command=self.add_url)
        add_url_btn.grid(row=2, column=0, sticky=tk.W)
        self.url_entry = ttk.Entry(frame, width=60)
        self.url_entry.grid(row=2, column=1, sticky=tk.W)

        dir_label = ttk.Label(frame, text="Download Folder:")
        dir_label.grid(row=3, column=0, sticky=tk.W)
        dir_entry = ttk.Entry(frame, textvariable=self.base_dir, width=60)
        dir_entry.grid(row=3, column=1, sticky=tk.W)
        dir_btn = ttk.Button(frame, text="Browse", command=self.browse_dir)
        dir_btn.grid(row=3, column=2, sticky=tk.W)

        self.status_label = ttk.Label(frame, textvariable=self.status, foreground='blue')
        self.status_label.grid(row=4, column=0, columnspan=3, sticky=tk.W)

        self.download_btn = ttk.Button(frame, text="Start Download", command=self.start_download_thread)
        self.download_btn.grid(row=5, column=0, pady=10, sticky=tk.W)

        self.schedule_btn = ttk.Button(frame, text="Schedule Download", command=self.open_schedule_window)
        self.schedule_btn.grid(row=5, column=1, pady=10, sticky=tk.W)

        self.json_btn = ttk.Button(frame, text="Show Downloaded JSON", command=self.show_json)
        self.json_btn.grid(row=5, column=2, pady=10, sticky=tk.W)

        self.skipped_btn = ttk.Button(frame, text="Show Skipped Files", command=self.show_skipped)
        self.skipped_btn.grid(row=6, column=0, pady=10, sticky=tk.W)

        self.progress = ttk.Progressbar(frame, orient='horizontal', length=400, mode='determinate')
        self.progress.grid(row=7, column=0, columnspan=3, pady=10, sticky=tk.W)

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
        threading.Thread(target=self.download_all, daemon=True).start()

    def download_all(self):
        self.status.set("Starting download...")
        urls = list(self.urls)
        base_dir = self.base_dir.get()
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        download_dir = os.path.join(base_dir, timestamp)
        os.makedirs(download_dir, exist_ok=True)
        self.skipped_files = []
        self.file_tree = {}
        all_files = set()
        total = len(urls)
        self.progress['maximum'] = total
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            for i, url in enumerate(urls):
                self.status.set(f"Visiting: {url}")
                self.progress['value'] = i
                self.root.update_idletasks()
                s, t, a = self.download_files(page, url, download_dir)
                self.skipped_files += s or []
                self.file_tree.update(t or {})
                all_files.update(a or set())
            browser.close()
        self.status.set("Download complete. Checking for missing files...")
        self.progress['value'] = total
        self.root.update_idletasks()
        # Save JSON
        json_path = os.path.join(download_dir, 'epstein_file_tree.json')
        with open(json_path, 'w', encoding='utf-8') as jf:
            json.dump(self.file_tree, jf, indent=2)
        self.downloaded_json.set(json_path)
        # Check for missing files
        missing_files = []
        for url in all_files:
            rel_path = self.sanitize_path(url.replace('https://', ''))
            local_path = os.path.join(download_dir, rel_path)
            if not os.path.exists(local_path):
                missing_files.append((url, local_path))
        if missing_files:
            self.status.set(f"Downloading {len(missing_files)} missing files...")
            for url, local_path in missing_files:
                try:
                    os.makedirs(os.path.dirname(local_path), exist_ok=True)
                    with requests.get(url, stream=True) as r:
                        r.raise_for_status()
                        with open(local_path, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                except Exception as e:
                    print(f"Failed to download missing file {url}: {e}\nContinuing...")
            self.status.set("Download complete (with missing files retried).")
        else:
            self.status.set("Download complete. No missing files.")

    def download_files(self, page, base_url, base_dir, visited=None, skipped_files=None, file_tree=None, all_files=None):
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
        self.status.set(f"Visiting: {base_url}")
        try:
            page.goto(base_url)
        except Exception as e:
            print(f"Error loading {base_url}: {e}\nContinuing...")
            return skipped_files, file_tree, all_files
        links = page.query_selector_all('a')
        self.status.set(f"Found {len(links)} links on {base_url}")
        hrefs = []
        for link in links:
            try:
                href = link.get_attribute('href')
                if href:
                    hrefs.append(href)
            except Exception as e:
                print(f"Error reading link attribute: {e}")
        for href in hrefs:
            if href.startswith('#'):
                continue
            abs_url = urllib.parse.urljoin(base_url, href)
            # Skip search links
            if '/search' in abs_url:
                continue
            # If it's a downloadable file, add to all_files and download if needed
            if re.search(r'\.(pdf|docx?|xlsx?|zip|txt|jpg|png|csv|mp4|mov|avi|wmv|wav|mp3|m4a)$', abs_url, re.IGNORECASE):
                rel_path = self.sanitize_path(abs_url.replace('https://', ''))
                local_path = os.path.join(base_dir, rel_path)
                folder = os.path.dirname(local_path)
                if folder not in file_tree:
                    file_tree[folder] = []
                file_tree[folder].append(local_path)
                all_files.add(abs_url)
                if os.path.exists(local_path):
                    print(f"Skipping (already exists): {local_path}")
                    skipped_files.add(local_path)
                    continue
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                self.status.set(f"Downloading {abs_url} -> {local_path}")
                try:
                    with requests.get(abs_url, stream=True) as r:
                        r.raise_for_status()
                        with open(local_path, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                except Exception as e:
                    print(f"Failed to download {abs_url}: {e}\nContinuing...")
            # If it's a subfolder, recurse if in allowed domains and not the root page and not already visited
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
        return skipped_files, file_tree, all_files

    def sanitize_path(self, path):
        parts = path.split('/')
        return os.path.join(*[re.sub(r'[<>:"/\\|?*]', '_', p) for p in parts])

def main():
    root = tk.Tk()
    app = DownloaderGUI(root)
    root.mainloop()

if __name__ == '__main__':
    main()
