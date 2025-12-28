# PowerShell helper to build the Inno Setup installer if ISCC.exe is available
# Usage: Open an elevated PowerShell and run: .\build_installer.ps1

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$iss = Join-Path $scriptDir 'epstein_installer.iss'
$distExe = Join-Path $scriptDir '..\dist\EpsteinDownloader.exe'

if (-not (Test-Path $distExe)) {
    Write-Error "dist\EpsteinDownloader.exe not found. Build the standalone EXE first with PyInstaller."
    exit 1
}

# Locate ISCC.exe (Inno Setup Compiler)
$iscc = Get-Command ISCC -ErrorAction SilentlyContinue
if (-not $iscc) {
    Write-Host "ISCC.exe not found on PATH. Please install Inno Setup (https://jrsoftware.org/isinfo.php) and ensure ISCC.exe is on PATH."
    Write-Host "Once installed, run this script again to compile the installer."
    exit 2
}

Write-Host "Compiling installer with ISCC..."
& $iscc.Source $iss
if ($LASTEXITCODE -ne 0) {
    Write-Error "Inno Setup failed to build the installer. See ISCC output above."
    exit $LASTEXITCODE
}
Write-Host "Installer built successfully. Check the 'output' folder for the installer EXE."