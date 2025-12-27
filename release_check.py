"""
Simple release check script.
Reads local VERSION.txt and compares to the latest GitHub release for a given repo.
Exits:
 - 0 if up-to-date
 - 1 if update available
 - 2 on error

Configure target repo via env var GITHUB_REPO (owner/repo). Default: JosephThePlatypus/EpsteinFilesDownloader
"""
import os
import sys
import requests

GITHUB_REPO = os.environ.get('GITHUB_REPO', 'JosephThePlatypus/EpsteinFilesDownloader')
VERSION_FILE = os.environ.get('VERSION_FILE', 'VERSION.txt')

def read_local_version(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        print(f"Error reading local version file {path}: {e}")
        return None


def fetch_latest_release(repo):
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            tag = data.get('tag_name') or data.get('name')
            if tag:
                return tag.strip()
            else:
                print('Latest release has no tag/name')
                return None
        else:
            print(f'GitHub API returned HTTP {r.status_code}: {r.text[:200]}')
            return None
    except Exception as e:
        print(f'Error fetching latest release: {e}')
        return None


def normalize_version(v):
    if v is None:
        return None
    return v.lstrip('v').strip()


def main():
    local = read_local_version(VERSION_FILE)
    if local is None:
        sys.exit(2)
    latest = fetch_latest_release(GITHUB_REPO)
    if latest is None:
        print('Could not determine latest release (see message above).')
        sys.exit(2)
    local_n = normalize_version(local)
    latest_n = normalize_version(latest)
    print(f'Local version: {local_n}')
    print(f'Latest release: {latest_n}')
    if local_n == latest_n:
        print('Up to date.')
        sys.exit(0)
    else:
        print('Update available.')
        sys.exit(1)

if __name__ == '__main__':
    main()
