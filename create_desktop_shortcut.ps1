# Creates a Desktop shortcut to launch the EpsteinFilesDownloader dev launcher
# Usage: run this script from PowerShell (it's safe and idempotent)
$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$launcher = Join-Path $scriptDir 'run_epstein_gui.ps1'
if (-not (Test-Path $launcher)) {
    Write-Error "Launcher not found at: $launcher"
    exit 2
}

# Determine powershell executable for target
$pwsh = (Get-Command powershell -ErrorAction SilentlyContinue) -or (Get-Command pwsh -ErrorAction SilentlyContinue)
if ($pwsh) { $pwshPath = $pwsh.Source } else { $pwshPath = "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" }

$desktop = [Environment]::GetFolderPath('Desktop')
$lnkPath = Join-Path $desktop 'EpsteinFilesDownloader.lnk'

try {
    $wsh = New-Object -ComObject WScript.Shell
    $shortcut = $wsh.CreateShortcut($lnkPath)
    $shortcut.TargetPath = $pwshPath
    # Arguments: use the launcher script by full path and set recommended dev flags
    $launcherQuoted = '"' + $launcher + '"'
    $shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File $launcherQuoted -BypassSingleInstance -SkipInstall -NoActivate"
    $shortcut.WorkingDirectory = $scriptDir
    # Prefer the GUI exe icon if present, otherwise use powershell icon
    $exeIcon = Join-Path $scriptDir 'epstein_downloader_gui.exe'
    if (Test-Path $exeIcon) {
        $shortcut.IconLocation = "$exeIcon,0"
    } else {
        $shortcut.IconLocation = "$pwshPath,0"
    }
    $shortcut.Description = 'Launch EpsteinFilesDownloader (development launcher)'
    $shortcut.Save()
    Write-Host "Desktop shortcut created at: $lnkPath"
} catch {
    Write-Error "Failed to create shortcut: $_"
    exit 1
}
