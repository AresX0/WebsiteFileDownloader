# Setup environment variables for EpsteinFilesDownloader dev & test
# Usage: Run this script in PowerShell in this repo root (or dot-source it to keep env in session):
#   PS> .\tools\setup_env.ps1

$projectRoot = "C:\Projects\Website Downloader"
# Set session env vars
$env:EPISTEIN_INSTALL_DIR = $projectRoot
$env:EPISTEIN_PROJECT_DIR = $projectRoot
$env:EPISTEIN_TEST_SCRIPTS_DIR = Join-Path $projectRoot 'tools'
# Recommended: set skip installs in CI to avoid interactive installers
$env:EPISTEIN_SKIP_INSTALL = '1'
# Skip Google Drive credential validation tests by default in CI/dev
$env:EPISTEIN_SKIP_GDRIVE_VALIDATION = '1'

Write-Host "Environment variables set for session:" -ForegroundColor Green
Write-Host "EPISTEIN_INSTALL_DIR = $env:EPISTEIN_INSTALL_DIR"
Write-Host "EPISTEIN_PROJECT_DIR = $env:EPISTEIN_PROJECT_DIR"
Write-Host "EPISTEIN_TEST_SCRIPTS_DIR = $env:EPISTEIN_TEST_SCRIPTS_DIR"
Write-Host "EPISTEIN_SKIP_INSTALL = $env:EPISTEIN_SKIP_INSTALL"

Write-Host "Note: Use 'setx' to persist variables system/user-wide if desired (requires new sessions)." -ForegroundColor Yellow
Write-Host "To run tests from tools/, use: .\tools\run_tests.ps1" -ForegroundColor Cyan
