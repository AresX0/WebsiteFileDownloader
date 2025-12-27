<#
PowerShell helper to create a local virtual environment (.venv) and install project dependencies.
Usage:
  .\scripts\setup_env.ps1          # create .venv and install base deps
  .\scripts\setup_env.ps1 -InstallPlaywright  # also install Playwright browsers
#>
param(
    [switch]$InstallPlaywright
)

$ErrorActionPreference = 'Stop'
$venv = Join-Path $PSScriptRoot ".." -Resolve
$venv = Join-Path $venv ".venv"
if (-not (Test-Path $venv)) {
    Write-Host "Creating virtual environment at $venv"
    python -m venv $venv
}

Write-Host "Activating virtual environment"
& "$venv\Scripts\Activate.ps1"

Write-Host "Upgrading pip and installing requirements"
python -m pip install --upgrade pip
pip install -r ..\requirements.txt
# Extra dev/test dependencies
pip install pytest google-api-python-client google-auth google-auth-httplib2 google-auth-oauthlib gdown httplib2 Pillow

if ($InstallPlaywright) {
    Write-Host "Installing Playwright and browsers"
    python -m pip install playwright
    playwright install chromium
}

Write-Host "Done. Activate the venv with: & .\.venv\Scripts\Activate.ps1"