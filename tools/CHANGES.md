Change log - Epstein Downloader

2025-12-27  - Consolidated dependency helpers and added EPISTEIN_SKIP_INSTALL guard
- File: `epstein_downloader_gui.py`
  - Replaced duplicate `ensure_pip()` and `check_and_install()` definitions with consolidated helpers.
  - Added `ensure_playwright_browsers()` and `ensure_runtime_dependencies()` helpers.
  - Removed import-time calls to `ensure_pip()` / `check_and_install()` / `ensure_playwright_browsers()` to prevent side effects on import.
  - Modified `main()` startup logic to skip interactive installer when `EPISTEIN_SKIP_INSTALL=1` or run installer via `install_dependencies_with_progress()` only in interactive mode.

- File: `playwright_epstein_downloader.py`
  - Wrapped package install calls in an `if os.environ.get('EPISTEIN_SKIP_INSTALL') != '1'` guard so imports in CI/tests won't trigger package installations.

- CI: Added GitHub Actions workflow (`.github/workflows/ci.yml`) to run tests on pushes and PRs. CI sets `EPISTEIN_SKIP_INSTALL=1` to prevent import-time installers, runs the test suite, and performs a small headless smoke-test of GUI init.

- Tests: Added `tests/test_playwright_mock.py` — a small unit test that mocks a Playwright page object to validate `download_files` handles pages with no links without networking.

- File: `tests/test_skip_install_import.py` (new)
  - Added test that importing `epstein_downloader_gui` with `EPISTEIN_SKIP_INSTALL=1` succeeds and does not attempt installation (isolated Python process).

Notes:
- The above changes are backward-compatible: by default installs still run during interactive startup; tests and CI can opt-out via EPISTEIN_SKIP_INSTALL=1.
- If you want explicit backups of previous file contents (pre-change), I can create `.orig` copies or commit the current state to a branch or create a patch/diff file for undo. Let me know which you prefer.
