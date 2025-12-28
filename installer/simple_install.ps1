# Simple installer script (no external tools required).
# Run this PowerShell script as Administrator to install the application to C:\Program Files\PlatypusFiles\WebsiteFileDownloader

param(
    [string]$InstallDir = 'C:\Program Files\PlatypusFiles\WebsiteFileDownloader',
    [switch]$RunPostInstall
)

if (-not ([bool](New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))) {
    Write-Error "This script must be run as Administrator."
    exit 1
}

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$dist = Join-Path $repoRoot '..\dist\EpsteinDownloader.exe' | Resolve-Path -ErrorAction Stop
$config = Join-Path $repoRoot '..\config.json'
$queue = Join-Path $repoRoot '..\queue_state.json'
$assets = Join-Path $repoRoot '..\assets'

Write-Host "Installing to $InstallDir (existing files will be overwritten)"
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null

Write-Host "Copying files..."
Copy-Item -Path $dist -Destination $InstallDir -Force
Copy-Item -Path $config -Destination $InstallDir -Force
Copy-Item -Path $queue -Destination $InstallDir -Force
if (Test-Path $assets) {
    Copy-Item -Path $assets -Destination (Join-Path $InstallDir 'assets') -Recurse -Force
}

# Create Start Menu shortcut
$WScriptShell = New-Object -ComObject WScript.Shell
$startMenu = [Environment]::GetFolderPath('Programs')
$shortcut = $WScriptShell.CreateShortcut((Join-Path $startMenu 'EpsteinFilesDownloader.lnk'))
$shortcut.TargetPath = Join-Path $InstallDir 'EpsteinDownloader.exe'
$shortcut.IconLocation = Join-Path $InstallDir 'JosephThePlatypus.ico'
$shortcut.WorkingDirectory = $InstallDir
$shortcut.Save()

# Optionally run post-install steps to install prereqs and Playwright browsers
if ($RunPostInstall) {
    Write-Host "Running post-install steps: installing runtime prerequisites..."
    & (Join-Path $InstallDir 'EpsteinDownloader.exe') --install-prereqs
    Write-Host "Installing Playwright browsers (may take a while and requires internet)..."
    & (Join-Path $InstallDir 'EpsteinDownloader.exe') --install-browsers
}

Write-Host "Install complete. Shortcut created in Start Menu."
Write-Host "To uninstall, run: installer\uninstall.ps1"
