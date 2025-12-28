# Building the Windows Installer (EpsteinFilesDownloader)

This document shows two simple ways to produce a Windows installer that installs the standalone application into:

    C:\Program Files\PlatypusFiles\WebsiteFileDownloader

Two parts:
- Build a standalone EXE using PyInstaller (one-file, GUI)
- Create an Inno Setup installer that copies the EXE to Program Files, overwriting previous installs, and runs post-install steps to fetch Playwright browsers.

Prerequisites (on your Windows build machine):
- Python 3.10+ (the project was tested on 3.14)
- Git and repository checked out
- PyInstaller (pip install pyinstaller)
- Inno Setup (for compiling .iss to .exe) — optional if you prefer MSIX/Wix
- Recommended: a code signing certificate (.pfx) and `signtool.exe` (Windows SDK) for signing the installer

Steps — Build the standalone EXE

1. Ensure dependencies are installed (in the environment used to build):
   - pip install -r requirements.txt
   - py -3 -m pip install --upgrade pyinstaller

2. From the repo root run:

   py -3 -m PyInstaller --noconfirm --onefile --windowed --name EpsteinDownloader \
       --add-data "config.json;." \
       --add-data "queue_state.json;." \
       --add-data "assets;assets" \
       --hidden-import google --hidden-import google.oauth2 --hidden-import googleapiclient \
       --hidden-import gdown --hidden-import playwright epstein_downloader_gui.py

   Output will be in `dist\EpsteinDownloader.exe`.

Notes:
- The build includes the Python runtime and Python packages so the result is a single EXE. Playwright's browser binaries are not embedded (they are large and typically downloaded at first-run). The installer will run post-install steps to download them.

Steps — Build an installer (Inno Setup)

1. Ensure Inno Setup (ISCC.exe) is installed and on PATH.
2. The repo includes `installer\epstein_installer.iss` and `installer\build_installer.ps1`.
3. Run the helper (run as Administrator):
   - Open an elevated PowerShell and run: `.	ester\installer\build_installer.ps1` (or run ISCC manually on `installer\epstein_installer.iss`)
4. The installer will place files into:
   - `C:\Program Files\PlatypusFiles\WebsiteFileDownloader` and will **overwrite** existing files (the .iss script sets overwrite policies).
5. Post-install, the installer will execute two hidden steps:
   - Run `{app}\EpsteinDownloader.exe --install-prereqs` to ensure runtime pip-installed packages are present
   - Run `{app}\EpsteinDownloader.exe --install-browsers` to download Playwright Chromium browser binaries

Signing the installer (recommended)
- To avoid SmartScreen and trust prompts, sign both the installer EXE and the application EXE with a code-signing certificate (.pfx). Use `signtool.exe sign /f cert.pfx /p <password> /tr http://timestamp.digicert.com /td sha256 /fd sha256 <file>`

Notes & Troubleshooting
- The Inno Setup script includes a post-install run of the installed EXE that will attempt to install packages and download Playwright browsers. Internet access is required for these steps.
- If Playwright browser download fails due to permissions or network constraints, you can run the installed EXE manually as Administrator and rerun `EpsteinDownloader.exe --install-browsers`.
- If you need an MSIX packaged installer (store-style), we have MSIX helpers in `installer/` but signing and Windows SDK tools are required; tell me if you want me to help generate an unsigned MSIX package or wire CI for MSIX.

If you want, I can:
- Build the single-file EXE for you now (I have already done so in `dist\EpsteinDownloader.exe`).
- Generate the Inno Setup installer (requires ISCC.exe to be on PATH; I can run it here if you install Inno Setup on this machine or give me access to a runner with ISCC).
- Help sign the EXE/installer (requires your signing certificate and password).

Let me know which of the following you want next:
1) Produce the final Inno Setup installer locally (I will need ISCC available here). 
2) I package an unsigned MSIX instead (requires makeappx / Windows SDK, and optional signing step).
3) Just provide these artifacts and instructions and let you build on your machine.

