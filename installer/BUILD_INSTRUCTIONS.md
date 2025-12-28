EpsteinFilesDownloader — Installer Build Instructions (with Playwright browsers bundled)

Purpose
-------
This document explains, step-by-step, how to build the Windows installer (Inno Setup) that contains the application (PyInstaller one-dir) and bundles Playwright browsers so the installed app can scan pages without requiring users to manually run `playwright install`.

Audience
--------
These instructions are written for contributors or maintainers who may not be familiar with the project or build tools. They assume you have basic familiarity with Windows and can run PowerShell commands.

Prerequisites (what you need to install first)
----------------------------------------------
- Windows 10/11 machine with Admin access
- Python 3.10+ installed and available on PATH
  - Recommended: create and use a virtual environment for the build
- Git
- PowerShell (default on Windows)
- Node.js (Playwright's installer may need it)
- Inno Setup (ISCC.exe) installed
- A stable internet connection (Playwright browsers are large downloads)

Files required in this repository (manifest)
--------------------------------------------
See `BUILD_MANIFEST.md` (in the same folder) for the exact list of files required and their roles.

Step-by-step build (simple)
---------------------------
WARNING: Always perform builds from the repository located at C:\Projects\Website Downloader. Running the build from any other path (for example C:\Path) is not supported and may put build artifacts in the wrong place.

1. Open PowerShell as Administrator
2. Clone the repository (if not already cloned) into the required location (exact path):
   git clone https://github.com/YOUR_ORG/WebsiteFileDownloader.git "C:\Projects\Website Downloader"
   Set-Location "C:\Projects\Website Downloader"
3. (Optional but recommended) Create and activate a virtual environment:
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
4. Install Python dependencies and PyInstaller:
   python -m pip install -r requirements.txt
   python -m pip install pyinstaller
5. Build the app and bundle Playwright browsers (this will take time):
   .\installer\build_installer.ps1 -Clean -InstallDeps -IncludePlaywrightBrowsers
   Notes:
   - The script defaults to including Playwright browsers in the installer. If your environment blocks installs or you want to skip, add `-ExcludePlaywrightBrowsers` (not present in older versions).
   - The script will create `dist\epstein_downloader_gui` and then compile an Inno Setup installer; the setup EXE will be in `installer\output`.
6. Verify the dist directory contains the Playwright browsers cache:
   Example: `dist\epstein_downloader_gui\playwright_browsers\chromium_headless_shell-*` should exist.
7. Test the installer (silent install to a temp dir):
   & 'installer\inno\installer\output\EpsteinFilesDownloader_Installer.exe' /VERYSILENT /DIR='C:\Temp\EpsteinTest' /NORESTART /SP-
   Then run the installed exe and perform a scan or just verify Playwright availability.

How to run the app without packaging (developer run)
----------------------------------------------------
If you want to run the application directly from source (no PyInstaller) for quick checks:
1. Activate your virtualenv and install dependencies:
   python -m pip install -r requirements.txt
   python -m pip install playwright
2. Install Playwright browsers for the interpreter you will run with:
   python -m playwright install
3. From repository root, run:
   python epstein_downloader_gui.py
4. If you need to simulate the installed environment's paths, set:
   $env:EPISTEIN_INSTALL_DIR = 'C:\Temp\EpsteinTest' (PowerShell)
   or
   setx EPISTEIN_INSTALL_DIR "C:\Temp\EpsteinTest" (persist)

Directory layout expected by the build
-------------------------------------
- WebsiteFileDownloader/ (repo root)
  - epstein_downloader_gui.py (main app)
  - requirements.txt
  - epstein_downloader_gui.spec (PyInstaller spec)
  - installer/ (build helpers and Inno script)
    - build_installer.ps1
    - inno/installer.iss
  - assets/ (icons & images)
  - README.md, LICENSE, JosephThePlatypus.ico

Notes on GitHub token / pushing to remote
----------------------------------------
- If you will push branches or merge to `main` from an automated process or CI, create a GitHub Personal Access Token with `repo` scopes.
  1. Go to https://github.com/settings/tokens
  2. Click "Generate new token (classic)" or the newer fine-grained token path
  3. Choose `repo` scope (and `workflow` if CI will run with it)
  4. Copy the token and store it securely
- To use locally with Git from PowerShell:
  git remote set-url origin https://<TOKEN>@github.com/YOUR_ORG/WebsiteFileDownloader.git
  (Using HTTPS with token in URL is convenient but be careful not to check the token into files.)
- Alternatively use Git Credential Manager (recommended) and authenticate with your account instead of embedding tokens.

Troubleshooting tips
--------------------
- If Playwright shows missing browser errors at runtime, inspect `dist\epstein_downloader_gui\playwright_browsers` or set `PLAYWRIGHT_BROWSERS_PATH` to point to a playwright cache where browsers were installed.
- If Inno Setup compiler isn't found, install Inno Setup and ensure `ISCC.exe` exists under `C:\Program Files (x86)\Inno Setup 6\ISCC.exe` or set PATH.

Contact
-------
If you run into problems, share the exact terminal output and the log files under the installed app's `logs` folder so we can triage fast.
