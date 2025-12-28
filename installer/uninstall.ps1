# Simple uninstall script to remove files installed by simple_install.ps1
param(
    [string]$InstallDir = 'C:\Program Files\PlatypusFiles\WebsiteFileDownloader'
)
if (-not ([bool](New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))) {
    Write-Error "This script must be run as Administrator."
    exit 1
}

if (-not (Test-Path $InstallDir)) {
    Write-Host "Install directory does not exist: $InstallDir"
    exit 0
}
Write-Host "Removing files from $InstallDir..."
Remove-Item -Path $InstallDir -Recurse -Force -ErrorAction SilentlyContinue

# Remove Start Menu shortcut
$startMenu = [Environment]::GetFolderPath('Programs')
$lnk = Join-Path $startMenu 'EpsteinFilesDownloader.lnk'
if (Test-Path $lnk) { Remove-Item $lnk -Force }

Write-Host "Uninstall complete."