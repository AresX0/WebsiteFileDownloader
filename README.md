# Epstein Downloader

This project automates downloading all files (PDFs, videos, audio, etc.) from:
- https://www.justice.gov/epstein/foia
- https://www.justice.gov/epstein/court-records
- https://oversight.house.gov/release/oversight-committee-releases-epstein-records-provided-by-the-department-of-justice/
- https://www.justice.gov/epstein/doj-disclosures

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
   playwright install
   ```
2. Run the script:
   ```
   python playwright_epstein_downloader.py
   ```
   or for the GUI:
   ```
   python epstein_downloader_gui.py
   ```

## Usage
- Downloaded files are saved to `C:\Temp\Epstein` by default.
- The script will create a JSON file with the folder and file structure.
- The GUI allows adding URLs, scheduling downloads, and viewing status.

## License
MIT
