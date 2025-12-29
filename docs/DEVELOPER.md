EpsteinFilesDownloader — Developer Notes

Quick startup & test guidance

- Environment flags used by the codebase:
  - EPISTEIN_SKIP_INSTALL=1 : skip auto-installing pip packages and Playwright browsers (CI/test convenience)
  - EPISTEIN_NO_SINGLE_INSTANCE_LOCK=1 : use in-memory single-instance lock instead of system-wide mutex/file (test convenience)
  - EPSTEIN_HEADLESS=1 : initialize GUI but do not enter mainloop (used for CI smoke tests)
  - PYTEST_CURRENT_TEST : set by pytest; the code uses this to detect tests and avoid aggressive side-effects

- Running the GUI manually (recommended):
  - Use the launcher script to bypass single-instance lock and skip installs:
    $env:EPISTEIN_SKIP_INSTALL=1; $env:PYTHONPATH='.'; py -3 tools/run_epstein_gui.py

- Import-time side-effects to be aware of:
  - The module tries to be import-safe but some initializers (dependency checks) may be triggered if flags are not set. Prefer setting EPISTEIN_SKIP_INSTALL=1 in test environments.

- Tests & debugging artifacts:
  - During debugging we sometimes create thread dumps (thread_dump_*.txt) and marker files (mainloop_unresponsive_marker.txt). These are now ignored by .gitignore and should be moved to tools/collected_logs when persisting them for analysis.

- Where to look for common subsystems:
  - GUI: epstein_downloader_gui.py (main application class: DownloaderGUI)
  - Playwright crawling: playwright_epstein_downloader.py
  - Google Drive helpers: download_drive_folder_api (API) and gdown fallback code in epstein_downloader_gui.py
  - Diagnostics: _write_thread_dump(), _dump_thread_stacks(), and logging helpers

Contact & contribution notes

- Keep changes incremental and add tests when refactoring download logic.
- For help, contact the repo owner or review the CHANGELOG in tools/CHANGES.md.
