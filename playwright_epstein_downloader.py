# playwright_epstein_downloader.py
"""
Automate downloading all files from https://www.justice.gov/epstein/court-records
Maintains folder structure using Playwright (Python).

Usage:
  1. Install Playwright and dependencies:
     pip install playwright
     playwright install
  2. Run the script:
     python playwright_epstein_downloader.py
"""

import os
import sys
import re
import urllib.parse
import json
from playwright.sync_api import sync_playwright
import requests
import importlib.util
import subprocess
import io
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaIoBaseDownload

# Global logger variable
import logging

logger = logging.getLogger("epstein_downloader")


def validate_url(url, timeout=10):
    try:
        response = requests.head(url, allow_redirects=True, timeout=timeout)
        if response.status_code == 200:
            return True
        else:
            logger.warning(f"URL not valid (status {response.status_code}): {url}")
            return False
    except Exception as e:
        logger.error(f"Error validating URL {url}: {e}")
        return False


def sanitize_path(path):
    # Remove illegal filename characters, but keep folder structure
    parts = path.split("/")
    return os.path.join(*[re.sub(r'[<>:"/\\|?*]', "_", p) for p in parts])


def download_files(
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
    print(f"Visiting: {base_url}")
    try:
        page.goto(base_url)
    except Exception as e:
        print(f"Error loading {base_url}: {e}\nContinuing...")
        return skipped_files, file_tree, all_files
    links = page.query_selector_all("a")
    print(f"Found {len(links)} links on {base_url}")
    hrefs = []
    for link in links:
        try:
            href = link.get_attribute("href")
            if href:
                hrefs.append(href)
        except Exception as e:
            print(f"Error reading link attribute: {e}")
    from concurrent.futures import ThreadPoolExecutor, as_completed

    download_args = []
    num_threads = 6

    # Collect all download tasks and batch validate URLs first
    for href in hrefs:
        if href.startswith("#"):
            continue
        abs_url = urllib.parse.urljoin(base_url, href)
        # Skip search links
        if "/search" in abs_url:
            continue
        # If it's a downloadable file, add to all_files and download if needed
        if re.search(
            r"\.(pdf|docx?|xlsx?|zip|txt|jpg|png|csv|mp4|mov|avi|wmv|wav|mp3|m4a)$",
            abs_url,
            re.IGNORECASE,
        ):
            rel_path = sanitize_path(abs_url.replace("https://", ""))
            local_path = os.path.join(base_dir, rel_path)
            folder = os.path.dirname(local_path)
            if folder not in file_tree:
                file_tree[folder] = []
            file_tree[folder].append(local_path)
            all_files.add(abs_url)
            download_args.append((abs_url, rel_path, local_path))
        # If it's a subfolder, recurse if in allowed domains and not the root page and not already visited
        elif (
            abs_url != base_url
            and any(abs_url.startswith(domain) for domain in allowed_domains)
            and abs_url != "https://www.justice.gov/epstein"
            and abs_url not in visited
        ):
            sub_skipped, sub_tree, sub_all = download_files(
                page, abs_url, base_dir, visited, skipped_files, file_tree, all_files
            )
            skipped_files.update(sub_skipped or set())
            file_tree.update(sub_tree or {})
            all_files.update(sub_all or set())

    def download_file_task(abs_url, rel_path, local_path):
        try:
            if not validate_url(abs_url):
                logger.warning(f"Skipping invalid URL: {abs_url}")
                skipped_files.add(abs_url)
                return
            if os.path.exists(local_path):
                logger.info(f"Skipping (already exists): {local_path}")
                skipped_files.add(local_path)
                return
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            logger.info(f"Downloading {abs_url} -> {local_path}")
            with requests.get(abs_url, stream=True, timeout=300) as r:
                r.raise_for_status()
                with open(local_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
        except Exception as e:
            logger.error(f"Failed to download {abs_url}: {e}\nContinuing...")
            skipped_files.add(abs_url)

    try:
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(download_file_task, *args) for args in download_args
            ]
            for future in as_completed(futures):
                pass  # All output is handled in download_file_task
    except KeyboardInterrupt:
        logger.warning("Download interrupted by user. Waiting for threads to finish...")
        # ThreadPoolExecutor will clean up threads on exit
    return skipped_files, file_tree, all_files


def check_and_install(package, pip_name=None):
    pip_name = pip_name or package
    if importlib.util.find_spec(package) is None:
        print(f"Missing required package: {pip_name}. Installing...")
        subprocess.check_call(["python", "-m", "pip", "install", pip_name])


# Check and install prerequisites
check_and_install("playwright")
check_and_install("requests")
check_and_install("gdown")


def download_drive_folder_api(folder_id, output_dir, credentials_path):
    SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
    creds = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=SCOPES
    )
    service = build("drive", "v3", credentials=creds)
    query = f"'{folder_id}' in parents and trashed=false"
    results = (
        service.files().list(q=query, fields="files(id, name, mimeType)").execute()
    )
    files = results.get("files", [])
    os.makedirs(output_dir, exist_ok=True)

    def download_file(file, current_output_dir):
        file_id = file["id"]
        file_name = file["name"]
        mime_type = file.get("mimeType", "")
        try:
            exportable_types = {
                "application/vnd.google-apps.document",
                "application/vnd.google-apps.spreadsheet",
                "application/vnd.google-apps.presentation",
            }
            # If it's a shortcut, follow the target and download recursively
            if mime_type == "application/vnd.google-apps.shortcut":
                target_id = file.get("shortcutDetails", {}).get("targetId")
                if target_id:
                    logger.info(f"Following shortcut {file_name} to target {target_id}")
                    # Get target file metadata
                    target_file = (
                        service.files()
                        .get(
                            fileId=target_id,
                            fields="id, name, mimeType, shortcutDetails",
                        )
                        .execute()
                    )
                    # Recursively call download_file on the target
                    download_file(target_file, current_output_dir)
                else:
                    logger.warning(f"Shortcut {file_name} has no targetId, skipping.")
                return
            # If it's a folder, list its contents and recurse
            if mime_type == "application/vnd.google-apps.folder":
                folder_path = os.path.join(current_output_dir, file_name)
                # If a file exists with the same name, rename the folder
                if os.path.isfile(folder_path):
                    folder_path += "_folder"
                os.makedirs(folder_path, exist_ok=True)
                logger.info(f"Recursively browsing folder: {file_name} ({file_id})")
                # List all files in the folder
                query = f"'{file_id}' in parents and trashed=false"
                results = (
                    service.files()
                    .list(q=query, fields="files(id, name, mimeType, shortcutDetails)")
                    .execute()
                )
                subfiles = results.get("files", [])
                for subfile in subfiles:
                    download_file(subfile, folder_path)
                return
            # Only export as PDF for Docs, Sheets, Slides
            if mime_type in exportable_types:
                export_mime = "application/pdf"
                export_name = file_name
                if not export_name.lower().endswith(".pdf"):
                    export_name += ".pdf"
                export_path = os.path.join(current_output_dir, export_name)
                # If a directory exists with the same name, rename the file
                if os.path.isdir(export_path):
                    export_path += "_file"
                request = service.files().export_media(
                    fileId=file_id, mimeType=export_mime
                )
                fh = io.FileIO(export_path, "wb")
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    logger.info(
                        f"Exporting {file_name} as PDF: {int(status.progress() * 100)}%"
                    )
                return
            # If it's a non-downloadable Google file (Forms, Maps, etc.), skip
            if mime_type.startswith("application/vnd.google-apps."):
                logger.warning(
                    f"Skipping non-downloadable Google Drive file: {file_name} (type: {mime_type})"
                )
                return
            # Otherwise, download as binary
            file_path = os.path.join(current_output_dir, file_name)
            # If a directory exists with the same name, rename the file
            if os.path.isdir(file_path):
                file_path += "_file"
            request = service.files().get_media(fileId=file_id)
            fh = io.FileIO(file_path, "wb")
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                logger.info(f"Downloading {file_name}: {int(status.progress() * 100)}%")
        except Exception as e:
            logger.error(f"Error downloading {file_name}: {e}")

    import threading
    from queue import Queue

    q = Queue()
    threads = []
    num_threads = 6

    def worker():
        while True:
            file = q.get()
            if file is None:
                break
            download_file(file, output_dir)
            q.task_done()

    for i in range(num_threads):
        t = threading.Thread(target=worker)
        t.start()
        threads.append(t)
    for file in files:
        q.put(file)
    q.join()
    for i in range(num_threads):
        q.put(None)
    for t in threads:
        t.join()
    logger.info("Download complete.")


def download_gdrive_folder(folder_url, output_dir):
    # ...existing code...
    import gdown
    import logging

    os.makedirs(output_dir, exist_ok=True)
    logger = logging.getLogger()
    logger.info(f"Starting Google Drive folder download: {folder_url} to {output_dir}")
    try:
        # List all subfolders and files using gdown's API
        logger.info(f"Listing subfolders in Google Drive folder: {folder_url}")
        folder_list = gdown.download_folder(
            url=folder_url,
            output=output_dir,
            quiet=True,
            use_cookies=False,
            remaining_ok=True,
        )
        subfolders = set()
        files = []
        for item in folder_list:
            if item["mimeType"] == "application/vnd.google-apps.folder":
                subfolders.add(item["id"])
            else:
                files.append(item)
        logger.info(
            f"Found {len(subfolders)} subfolders and {len(files)} files in root folder."
        )
        # Download files in root folder in batches of 45
        batch_size = 45
        result = []
        for i in range(0, len(files), batch_size):
            batch = files[i : i + batch_size]
            logger.info(
                f"Downloading batch {i // batch_size + 1} in root: files {i + 1} to {min(i + batch_size, len(files))}"
            )
            for file_info in batch:
                file_id = file_info["id"]
                file_name = file_info["name"]
                dest_path = os.path.join(output_dir, file_name)
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
                if f["mimeType"] != "application/vnd.google-apps.folder"
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
                    logger.info(
                        f"Downloading Google Drive file: {file_name} to {dest_path}"
                    )
                    try:
                        gdown.download(
                            id=file_id, output=dest_path, quiet=False, use_cookies=False
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
        logger.error(f"Failed to process Google Drive folder: {e}")
        return []


def main():
    import logging

    base_urls = [
        "https://www.justice.gov/epstein/foia",
        "https://www.justice.gov/epstein/court-records",
        "https://oversight.house.gov/release/oversight-committee-releases-epstein-records-provided-by-the-department-of-justice/",
        "https://www.justice.gov/epstein/doj-disclosures",
        "https://drive.google.com/drive/folders/1TrGxDGQLDLZu1vvvZDBAh-e7wN3y6Hoz?usp=sharing",
    ]
    base_dir = r"C:\Temp\Epstein"
    credentials_path = "credentials.json"
    os.makedirs(base_dir, exist_ok=True)
    # Setup logging
    log_path = os.path.join(
        base_dir,
        f"epstein_downloader_{__import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
    )
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    if not logger.hasHandlers():
        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)
    else:
        logger.handlers.clear()
        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)
    logger.info("Logger initialized.")
    logger.info(f"Starting download. URLs: {base_urls}")
    skipped_files = set()
    file_tree = {}
    all_files = set()
    try:
        # Download all Google Drive folders first
        for url in base_urls:
            if url.startswith("https://drive.google.com/drive/folders/"):
                gdrive_dir = os.path.join(base_dir, "GoogleDrive")
                logger.info(f"Processing Google Drive folder: {url}")
                import re

                match = re.search(r"/folders/([a-zA-Z0-9_-]+)", url)
                if match:
                    folder_id = match.group(1)
                    if os.path.exists(credentials_path):
                        try:
                            download_drive_folder_api(
                                folder_id, gdrive_dir, credentials_path
                            )
                        except Exception as e:
                            logger.error(f"Google Drive API download failed: {e}")
                            logger.info("Falling back to gdown...")
                            try:
                                import gdown

                                gdown.download_folder(
                                    url=url,
                                    output=gdrive_dir,
                                    quiet=False,
                                    use_cookies=False,
                                    remaining_ok=True,
                                )
                            except Exception as e2:
                                logger.error(f"gdown fallback failed: {e2}")
                                print(
                                    "\nTo enable full Google Drive access, create a credentials.json file as follows:\n"
                                    "1. Go to https://console.cloud.google.com/\n"
                                    "2. Create/select a project, enable the Google Drive API.\n"
                                    "3. Go to 'APIs & Services > Credentials', create a Service Account, and download the JSON key.\n"
                                    "4. Save it as credentials.json in this folder.\n"
                                )
                    else:
                        logger.warning(
                            "credentials.json not found. Attempting gdown fallback..."
                        )
                        try:
                            import gdown

                            gdown.download_folder(
                                url=url,
                                output=gdrive_dir,
                                quiet=False,
                                use_cookies=False,
                                remaining_ok=True,
                            )
                        except Exception as e2:
                            logger.error(f"gdown fallback failed: {e2}")
                            print(
                                "\nTo enable full Google Drive access, create a credentials.json file as follows:\n"
                                "1. Go to https://console.cloud.google.com/\n"
                                "2. Create/select a project, enable the Google Drive API.\n"
                                "3. Go to 'APIs & Services > Credentials', create a Service Account, and download the JSON key.\n"
                                "4. Save it as credentials.json in this folder.\n"
                            )
                else:
                    logger.error("Google Drive folder ID not found in URL.")

        # Now download all other files
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            for url in base_urls:
                if url.startswith("https://drive.google.com/drive/folders/"):
                    continue
                logger.info(f"Visiting: {url}")
                s, t, a = download_files(
                    page,
                    url,
                    base_dir,
                    skipped_files=skipped_files,
                    file_tree=file_tree,
                    all_files=all_files,
                )
                skipped_files.update(s or set())
                file_tree.update(t or {})
                all_files.update(a or set())
            browser.close()
    except KeyboardInterrupt:
        logger.warning("Download interrupted by user. Exiting cleanly.")
        return
    logger.info(f"\nSummary: Skipped {len(skipped_files)} files (already existed):")
    for f in list(skipped_files)[:1000]:
        logger.info(f"Skipped: {f}")
    if len(skipped_files) > 1000:
        logger.info(f"...and {len(skipped_files) - 1000} more skipped files.")
    # Write file tree to JSON
    json_path = os.path.join(base_dir, "epstein_file_tree.json")
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(file_tree, jf, indent=2)
    logger.info(f"\nFile tree JSON written to: {json_path}")
    # Compare all_files to downloaded files
    downloaded_files = set()
    for files in file_tree.values():
        downloaded_files.update(files)
    missing_files = []
    for url in all_files:
        if url.startswith("gdrive://"):
            # Google Drive files: check in GoogleDrive folder
            rel_path = url.replace("gdrive://", "")
            local_path = os.path.join(base_dir, "GoogleDrive", rel_path)
        else:
            rel_path = sanitize_path(url.replace("https://", ""))
            local_path = os.path.join(base_dir, rel_path)
        if not os.path.exists(local_path):
            missing_files.append((url, local_path))
    failed_missing = []
    if missing_files:
        logger.warning(
            f"\nMissing {len(missing_files)} files, attempting to download..."
        )
        for url, local_path in missing_files:
            logger.info(f"Downloading missing file: {url} -> {local_path}")
            try:
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                if url.startswith("gdrive://"):
                    # Redownload Google Drive file by name (not implemented: would require mapping rel_path to file_id)
                    logger.error(
                        f"Cannot redownload missing Google Drive file automatically: {url}"
                    )
                    failed_missing.append((url, "Manual intervention required"))
                else:
                    with requests.get(url, stream=True) as r:
                        r.raise_for_status()
                        with open(local_path, "wb") as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
            except Exception as e:
                logger.error(
                    f"Failed to download missing file {url}: {e}\nContinuing..."
                )
                failed_missing.append((url, str(e)))
        if failed_missing:
            logger.warning(
                f"\nSummary: {len(failed_missing)} files could not be downloaded:"
            )
            for url, err in failed_missing:
                logger.warning(f"  {url}\n    Error: {err}")
        else:
            logger.info("\nAll missing files were downloaded successfully.")
    else:
        logger.info("\nNo missing files detected.")


if __name__ == "__main__":
    main()
