Build Manifest — Files required to build the Windows installer

Required repo files and their roles
----------------------------------
- `epstein_downloader_gui.py` — main application entrypoint (source used by PyInstaller)
- `epstein_downloader_gui.spec` — PyInstaller spec (defines what to bundle and how)
- `requirements.txt` — Python dependencies required at build/runtime
- `installer/build_installer.ps1` — PowerShell wrapper to run PyInstaller, optionally install Playwright browsers, and run Inno Setup
- `installer/inno/installer.iss` — Inno Setup script used to create the final Setup.exe
- `JosephThePlatypus.ico` — installer and app icon
- `assets/` — images and assets that should be `--add-data`'d into the application bundle
- `README.md`, `LICENSE` — included files in the installer top-level
- `playwright_browsers/` — OPTIONAL: when present, this is the directory with Playwright browser binaries to include in the installer; the build script will populate this when `-IncludePlaywrightBrowsers` is used

Notes
-----
- The Playwright browsers directory can be large (hundreds of MBs to many GBs if all browsers are included).
- The `installer/build_installer.ps1` script downloads Playwright browsers into `dist\epstein_downloader_gui\playwright_browsers` when `-IncludePlaywrightBrowsers` is specified or when default behavior is to include them.
