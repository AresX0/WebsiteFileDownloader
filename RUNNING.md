EpsteinFilesDownloader — How to run and dependencies

Overview
--------
This document explains how to run the app on Windows (system Python or repository `.venv`) and lists runtime dependencies.

Prerequisites
-------------
- Windows (tested on Windows 10/11)
- Python 3.10+ (3.14 tested locally)
- Git (to clone repo)

Recommended: Use the repository `.venv` for isolation. However the app is also set up to run using system Python.

Install dependencies (system Python)
-----------------------------------
PowerShell (as a non-admin user):

1) Ensure pip is up-to-date and install packages to your user site:

    py -3 -m pip install --upgrade pip --user
    py -3 -m pip install -r requirements.txt --user

2) Install Playwright browsers (used for site crawling features):

    py -3 -m playwright install chromium

Install dependencies (repo virtualenv)
-------------------------------------
From repo root:

    python -m venv .venv
    & .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    python -m playwright install chromium

Commands to launch
------------------
- System Python:

    Set-Location 'C:\Projects\Website Downloader'
    py -3 epstein_downloader_gui.py

- Repo `.venv`:

    & .\.venv\Scripts\Activate.ps1
    python epstein_downloader_gui.py

- Headless (CI/test):

    $env:EPSTEIN_HEADLESS='1'; $env:EPISTEIN_SKIP_INSTALL='1'
    py -3 epstein_downloader_gui.py

Notes on behavior
-----------------
- Settings persistence: changes in Advanced Settings are saved immediately and applied to the running app.
- Google Drive: If using Google Drive API, provide a service account `credentials.json` via Settings or drag-and-drop. `gdown` fallback is available.
- Developer tooling:
  - `scripts/strip_bom.py` and `scripts/check_bom_present.py` to clean and detect UTF-8 BOMs.
  - `scripts/check_deferred_exceptions.py` detects lambdas deferring exception references that will fail when run later (e.g., in `root.after`).

Running tests
-------------
- Run all tests (skips GUI when Tk not available):

    py -3 -m pytest -q

CI
--
A GitHub Actions workflow runs tests on push/PR across Python versions and includes a deferred-exception check.

Support
-------
Open an issue: https://github.com/AresX0/WebsiteFileDownloader/issues
