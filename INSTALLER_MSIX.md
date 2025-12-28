MSIX Packaging for EpsteinFilesDownloader (Guide)

Overview
--------
This document shows how to produce an MSIX package for EpsteinFilesDownloader using the repository's helper scripts.
The MSIX packaging method used here packages a PyInstaller-built executable into an MSIX that installs cleanly on Windows.

Prerequisites
-------------
- Windows 10/11 build machine (or runner) with Windows SDK tools installed (makeappx.exe and signtool.exe)
- Python 3.11+ (for building)
- PyInstaller (installed via pip)
- Code signing certificate (PFX) for signing MSIX (recommended)

Build steps (local)
-------------------
1) Build the standalone executable with PyInstaller:
   PowerShell:
     Set-Location 'C:\Projects\Website Downloader'
     .\scripts\build_pyinstaller.ps1 -Name "EpsteinFilesDownloader" -NoConsole

2) Build the MSIX package (optionally sign):
   PowerShell:
     .\scripts\build_msix.ps1 -Name "EpsteinFilesDownloader" -Version "1.04" -Publisher "CN=YourPublisher" -CertPath "C:\path\to\cert.pfx" -CertPassword "<pw>"

Notes:
- If you don't have a cert, omit -CertPath; you can sign packages later using SignTool.
- The scripts place outputs under `build\msix\`.

CI Integration
--------------
We added a workflow job `msix_build` that runs on `windows-latest` and performs the build steps. The job will sign the package only when the secrets `CODE_SIGN_CERT_PATH` and `CODE_SIGN_CERT_PASSWORD` are set in the repository.

Testing the package
-------------------
To test locally, you can run the produced executable directly (headless mode):
  $env:EPSTEIN_HEADLESS='1'; & .\dist\EpsteinFilesDownloader\EpsteinFilesDownloader.exe

To test the MSIX (installation requires developer mode or signing):
  Add-AppxPackage -Path .\build\msix\EpsteinFilesDownloader-1.04.msix
  # Run from Start Menu or installed path

Security
--------
- Do NOT embed credentials in the package. Provide `credentials.json` via Settings dialog or a secure path.
- Use code signing to avoid SmartScreen warnings.

Troubleshooting
---------------
- If `makeappx.exe` is not found, install the Windows 10/11 SDK or run script from Visual Studio developer command prompt.
- If signing fails, verify the certificate and timestamp server.

Questions
---------
If you want me to: create a signed package in CI (requires adding certificate secrets), or add an installer UI tweak (e.g., choose install location), tell me and I'll add it to the scripts and CI job.
