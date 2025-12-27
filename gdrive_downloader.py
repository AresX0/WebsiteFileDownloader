# gdrive_downloader.py
"""
Download all files from a public Google Drive folder using gdown.
Usage:
    pip install gdown
    python gdrive_downloader.py <folder_url> <output_dir>
"""
import sys
import os
import gdown

def download_gdrive_folder(folder_url, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    print(f"Downloading Google Drive folder: {folder_url} to {output_dir}")
    gdown.download_folder(folder_url, output=output_dir, quiet=False, use_cookies=False)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python gdrive_downloader.py <folder_url> <output_dir>")
        sys.exit(1)
    folder_url = sys.argv[1]
    output_dir = sys.argv[2]
    download_gdrive_folder(folder_url, output_dir)
