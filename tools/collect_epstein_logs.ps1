<#
Collect Epstein GUI logs and dumps into the repo for analysis.
Usage:
  From PowerShell (in any folder):
    powershell -NoProfile -ExecutionPolicy Bypass -File "tools\collect_epstein_logs.ps1"

Options (edit variables below or pass path args):
  -SourceDir  : root folder containing logs (default: C:\temp\Epstein\Logs)
  -DestDir    : destination in repo (default: ./collected_logs)
  -Zip        : create zip archive of collected files

Outputs:
  - Copies files into "$PSScriptRoot\..\collected_logs"
  - Writes a summary and created archive name (if -Zip)
#>

param(
    [string]$SourceDir = 'C:\temp\Epstein\Logs',
    [string]$DestDir = (Join-Path $PSScriptRoot '..\collected_logs'),
    [switch]$Zip
)

$ErrorActionPreference = 'Stop'

# Files to collect (add or modify as needed)
$files = @(
    'mainloop_unresponsive_marker.txt',
    'thread_dump_mainloop-unresponsive_20251228_210901_35456.txt',
    'button_audit.log',
    'epstein_downloader.log'
)

Write-Host "SourceDir: $SourceDir"
Write-Host "DestDir: $DestDir"

if (-not (Test-Path $SourceDir)) {
    Write-Error "Source dir not found: $SourceDir"; exit 2
}

New-Item -ItemType Directory -Path $DestDir -Force | Out-Null

$copied = @()
foreach ($f in $files) {
    $src = Join-Path $SourceDir $f
    if (Test-Path $src) {
        try {
            Copy-Item -Path $src -Destination $DestDir -Force
            $copied += $f
            Write-Host "Copied: $f"
        } catch {
            Write-Warning "Failed to copy $f: $_"
        }
    } else {
        Write-Warning "Not found: $src"
    }
}

if ($Zip -and $copied.Count -gt 0) {
    $archive = Join-Path $DestDir ('epstein_logs_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.zip')
    Compress-Archive -Path (Join-Path $DestDir '*') -DestinationPath $archive -Force
    Write-Host "Created archive: $archive"
}

Write-Host "Done. Collected files: $($copied -join ', ')"
Write-Host "You can now attach or paste the files from: $DestDir"
