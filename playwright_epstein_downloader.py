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
import re
import urllib.parse
from pathlib import Path
from playwright.sync_api import sync_playwright
import requests
import json

def sanitize_path(path):
    # Remove illegal filename characters, but keep folder structure
    parts = path.split('/')
    return os.path.join(*[re.sub(r'[<>:"/\\|?*]', '_', p) for p in parts])

def download_files(page, base_url, base_dir, visited=None, skipped_files=None, file_tree=None, all_files=None):
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
    print(f"Visiting: {base_url}")
    try:
        page.goto(base_url)
    except Exception as e:
        print(f"Error loading {base_url}: {e}\nContinuing...")
        return skipped_files, file_tree, all_files
    links = page.query_selector_all('a')
    print(f"Found {len(links)} links on {base_url}")
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
            rel_path = sanitize_path(abs_url.replace('https://', ''))
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
            print(f"Downloading {abs_url} -> {local_path}")
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
            sub_skipped, sub_tree, sub_all = download_files(page, abs_url, base_dir, visited, skipped_files, file_tree, all_files)
            skipped_files.update(sub_skipped or set())
            file_tree.update(sub_tree or {})
            all_files.update(sub_all or set())
    return skipped_files, file_tree, all_files

def main():
    base_urls = [
        'https://www.justice.gov/epstein/foia',
        'https://www.justice.gov/epstein/court-records',
        'https://oversight.house.gov/release/oversight-committee-releases-epstein-records-provided-by-the-department-of-justice/',
        'https://www.justice.gov/epstein/doj-disclosures',
    ]
    base_dir = r'C:\Temp\Epstein'
    os.makedirs(base_dir, exist_ok=True)
    skipped_files = set()
    file_tree = {}
    all_files = set()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        for url in base_urls:
            s, t, a = download_files(page, url, base_dir, skipped_files=skipped_files, file_tree=file_tree, all_files=all_files)
            skipped_files.update(s or set())
            file_tree.update(t or {})
            all_files.update(a or set())
        browser.close()
    print(f"\nSummary: Skipped {len(skipped_files)} files (already existed):")
    for f in list(skipped_files)[:1000]:
        print(f)
    if len(skipped_files) > 1000:
        print(f"...and {len(skipped_files)-1000} more skipped files.")
    # Write file tree to JSON
    json_path = os.path.join(base_dir, 'epstein_file_tree.json')
    with open(json_path, 'w', encoding='utf-8') as jf:
        json.dump(file_tree, jf, indent=2)
    print(f"\nFile tree JSON written to: {json_path}")
    # Compare all_files to downloaded files
    downloaded_files = set()
    for files in file_tree.values():
        downloaded_files.update(files)
    missing_files = []
    for url in all_files:
        rel_path = sanitize_path(url.replace('https://', ''))
        local_path = os.path.join(base_dir, rel_path)
        if not os.path.exists(local_path):
            missing_files.append((url, local_path))
    if missing_files:
        print(f"\nMissing {len(missing_files)} files, attempting to download...")
        for url, local_path in missing_files:
            print(f"Downloading missing file: {url} -> {local_path}")
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
    else:
        print("\nNo missing files detected.")

if __name__ == '__main__':
    main()
