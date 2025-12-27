# Epstein Downloader

This project automates downloading all files (PDFs, videos, audio, etc.) from the following default URLs:
- https://www.justice.gov/epstein/foia
- https://www.justice.gov/epstein/court-records
- https://oversight.house.gov/release/oversight-committee-releases-epstein-records-provided-by-the-department-of-justice/
- https://www.justice.gov/epstein/doj-disclosures
- https://drive.google.com/drive/folders/1TrGxDGQLDLZu1vvvZDBAh-e7wN3y6Hoz?usp=sharing

You can change the URLs in the GUI or by editing the `default_urls` list in `epstein_downloader_gui.py`.

## Features
- Maintains folder structure
- Skips files that already exist
- Tracks and retries missing files
- Outputs a JSON file listing all downloaded files
- GUI version available with scheduling and status display

## Requirements
- Python 3.8+
- See requirements.txt for dependencies

## Setup
1. Install dependencies:
   ```
   pip install -r requirements.txt
   python -m playwright install
   ```
2. Run the script:
   ```
   python playwright_epstein_downloader.py
   ```
   or for the GUI:
   ```
   python epstein_downloader_gui.py
   ```

## CI / Tests
- The repository includes a GitHub Actions workflow (`.github/workflows/ci.yml`) that runs the test suite on pushes and pull requests.
- CI sets `EPISTEIN_SKIP_INSTALL=1` to avoid running import-time installers during test runs; you can run tests locally the same way:
  ```bash
  export EPISTEIN_SKIP_INSTALL=1
  pytest -q
  ```

## Installer
A PowerShell installer `EpsteinDownloaderInstaller.ps1` has been added to create an installed copy under `C:\Program Files\PlatypusFiles\WebsiteFileDownloader` by default.

Usage (PowerShell, run as Administrator):

```powershell
# Run default installer and be prompted to install dependencies and optionally build an .exe
pwsh -ExecutionPolicy Bypass -File EpsteinDownloaderInstaller.ps1

# Or provide a custom install location
pwsh -ExecutionPolicy Bypass -File EpsteinDownloaderInstaller.ps1 -InstallDir "C:\Your\Install\Path"
```

The installer will:
- Copy `epstein_downloader_gui.py`, assets, `requirements.txt`, and other runtime files to the install folder
- Prompt to install Python dependencies from `requirements.txt` (Yes => installs, No => exits)
- Offer to build a single-file executable using PyInstaller (requires PyInstaller to be installed; installer will attempt to install it)

After installation the app prefers to run from the install folder so assets, logs, and configuration are located under the install directory by default.

- If you need Playwright browsers for full end-to-end runs, install them explicitly with `python -m playwright install` prior to running those workflows or tests.

## Environment variables

- `EPISTEIN_SKIP_INSTALL=1` — skip the interactive dependency installer (useful for CI/test environments).
- `EPISTEIN_INSTALL_TIMEOUT` — number of seconds to wait for external installers (pip/playwright). Defaults to `300` seconds.

## Usage
- Downloaded files are saved to `C:\Temp\Epstein` by default.
- The script will create a JSON file with the folder and file structure.
- The GUI allows adding URLs, scheduling downloads, and viewing status.

## License
MIT
