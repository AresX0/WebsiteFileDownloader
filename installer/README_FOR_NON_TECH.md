Simple, step-by-step instructions for non-technical users to rebuild the installer

Goal: Create an installer for Epstein Files Downloader that already contains the web browser components Playwright needs so you don't have to install anything extra after installing the app.

1) Get the code
- Ask the project maintainer to provide the repository as a ZIP or use Git:
  - If Git is available: open PowerShell and run:
    git clone https://github.com/YOUR_ORG/WebsiteFileDownloader.git
    cd "WebsiteFileDownloader"

2) Prepare your system
- Install Python 3.10+ from https://python.org
- Install Node.js installer from https://nodejs.org (Playwright uses it)
- Install Inno Setup from https://jrsoftware.org/

3) Build (very simple)
- Open PowerShell as Administrator
- From the repo folder run (recommended script):
  .\installer\build_with_browsers.ps1 -Clean -InstallDeps
- Wait: this will download Playwright browsers and produce a Setup EXE in `installer\output`.

4) Test the installer
- Run the EXE and choose a temporary installation directory (or run silent install):
  & 'installer\inno\installer\output\EpsteinFilesDownloader_Installer.exe' /VERYSILENT /DIR='C:\Temp\EpsteinTest' /NORESTART /SP-
- Launch the app from the installed folder and run a scan.

If you get stuck, copy any terminal output and the log files (see `logs` folder in the installed app) and share with the maintainer.

If you want me to push these changes to the project remote for you, I may need permission (GitHub token or contributor rights) — see next file for instructions on tokens.