# Release v0.5 — UI polish and UX improvements

Release date: 2025-12-27

Highlights:

- Modernized progress UI: new `Modern.Horizontal.TProgressbar` and `ModernFile.Horizontal.TProgressbar` styles with a blue, 3D-like appearance.
- Animated status indicator: two-ball orbital spinner (blue + red) on the progress panel to show active downloads.
- Download History: added a searchable/filterable history tab with refresh and filter box.
- Settings: new tabbed Advanced Settings dialog (General / Network / Appearance / Advanced) and support for additional theme names (azure, sun-valley, forest).
- Theme handling: improved dark/light handling and optional use of `ttkbootstrap` when available.
- URL listbox: consistent control sizing and a right-click context menu (Remove / Move Up / Move Down / Copy / Open).
- Google Drive handling: improved `validate_credentials()` to refresh service-account credentials with Drive readonly scope; added gdown fallback handling and clearer messages.
- Update-check diagnostics: `check_for_updates()` surfaces HTTP status, URL and response snippet when the remote check fails.
- Packaging: prepared `C:\Projects\Website Downloader` snapshot for release; removed `credentials.json` from the package before pushing.

Notes for reviewers:

- The spinner uses a Canvas-based orbital animation at ~30 FPS; color/size/speed can be tweaked in `epstein_downloader_gui.py`.
- Please verify the interactive UI (progress bar, spinner, History filtering) on Windows.
- The branch for these changes is `release/v0.5-ui` (PR suggested automatically on push).

Changelog (technical):

- Updated `epstein_downloader_gui.py` — added progressbar styles, history tab, settings tabs, spinner helpers (`start_spinner`, `_spinner_step`, `stop_spinner`), and associated UI wiring.
- Added scripted packaging files and release helpers in the packaged directory.

Contact: JosephThePlatypus (maintainer)
