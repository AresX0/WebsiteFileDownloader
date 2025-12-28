<#
build_installer.ps1

Build helper to create a PyInstaller one-dir distribution and compile an Inno Setup installer.

Usage examples:
  # Clean build, install optional deps, and build installer (run as dev, ensure venv is activated)
  .\build_installer.ps1 -InstallDeps -IncludePlaywrightBrowsers

  # Just build the app and create installer
  .\build_installer.ps1

Notes:
- This script expects to be run from the repository root or will force the working dir to:
  C:\Projects\Website Downloader
- Requires Python (and optionally PyInstaller and Inno Setup) in PATH.
- If Inno Setup (ISCC.exe) is not found, the script will ask you to install it.
#>

param(
    [switch]$InstallDeps,
    [switch]$Clean,
    [switch]$IncludePlaywrightBrowsers
)

# Ensure we operate from the expected project directory
$RepoRoot = "C:\Projects\Website Downloader"
if (-not (Test-Path $RepoRoot)) {
    Write-Error "Expected repo root '$RepoRoot' not found. Update the script or run from the correct directory."
    exit 1
}

Push-Location $RepoRoot
Write-Host "Working directory: $(Get-Location)"

$python = "python"

if ($InstallDeps) {
    Write-Host "Installing Python dependencies (requirements.txt) and PyInstaller..."
    & $python -m pip install -r "requirements.txt"
    & $python -m pip install pyinstaller
}

if ($Clean) {
    Write-Host "Cleaning previous builds..."
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue "dist\epstein_downloader_gui","build\epstein_downloader_gui","installer\output"
}

# Build with PyInstaller (one-dir recommended for Playwright and external assets)
$specFile = Join-Path $RepoRoot "epstein_downloader_gui.spec"
if (Test-Path $specFile) {
    Write-Host "Found spec file: $specFile - running PyInstaller with spec..."
    & $python -m PyInstaller $specFile
    if ($LASTEXITCODE -ne 0) { Write-Error "PyInstaller (spec) build failed with exit code $LASTEXITCODE"; Pop-Location; exit 1 }
} else {
    $addData = @(
        "--add-data","assets;assets",
        "--add-data","README.md;.",
        "--add-data","LICENSE;.",
        "--add-data","JosephThePlatypus.ico;.",
        "--add-data","config.json;.",
        "--add-data","queue_state.json;."
    )

    $pyArgs = @(
        "-m","PyInstaller","--clean","--noconfirm","--onedir","--name","epstein_downloader_gui"
    ) + $addData + @("epstein_downloader_gui.py")

    Write-Host "Running PyInstaller (one-dir)..."
    & $python @pyArgs
    if ($LASTEXITCODE -ne 0) { Write-Error "PyInstaller build failed with exit code $LASTEXITCODE"; Pop-Location; exit 1 }
}

# Optionally install Playwright browsers (this is large and may take time)
if ($IncludePlaywrightBrowsers) {
    Write-Host "Installing Playwright browsers into the dist output (this will download the browser binaries)..."
    $pwPath = Join-Path $RepoRoot "dist\epstein_downloader_gui\playwright_browsers"
    if (-not (Test-Path $pwPath)) { New-Item -ItemType Directory -Path $pwPath -Force | Out-Null }
    # Set env var so playwright installs into the target folder
    $old = $env:PLAYWRIGHT_BROWSERS_PATH
    $env:PLAYWRIGHT_BROWSERS_PATH = $pwPath
    try {
        & $python -m playwright install
        if ($LASTEXITCODE -ne 0) { Write-Warning "playwright install failed (exit code $LASTEXITCODE). The app may prompt to install browsers on first run." }
    } finally {
        # restore env var
        if ($null -ne $old) { $env:PLAYWRIGHT_BROWSERS_PATH = $old } else { Remove-Item Env:PLAYWRIGHT_BROWSERS_PATH -ErrorAction SilentlyContinue }
    }
    # Quick runtime smoke test to verify a headless launch using the installed browser
    $testCmd = "from playwright.sync_api import sync_playwright; import sys; print('PLAYWRIGHT_TEST_START');
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    b.close()
print('PLAYWRIGHT_TEST_OK')"
    Write-Host "Running Playwright smoke test to verify installation..."
    $rc = & $python -c $testCmd 2>&1
    if ($LASTEXITCODE -ne 0 -or $rc -notlike '*PLAYWRIGHT_TEST_OK*') {
        Write-Warning "Playwright smoke test did not return expected success message. Output:\n$rc"
    } else {
        Write-Host "Playwright browsers installed and smoke test passed."
    }
}

# Locate Inno Setup (ISCC.exe)
$possibleIscc = @("C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe","C:\\Program Files\\Inno Setup 6\\ISCC.exe")
$ISCC = $possibleIscc | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $ISCC) {
    Write-Warning "ISCC.exe (Inno Setup compiler) not found. Please install Inno Setup to compile the installer. You can download it from: https://jrsoftware.org/"
    Write-Host "PyInstaller build completed. You can run Inno Setup manually with: ISCC installer\inno\installer.iss"
    Pop-Location
    exit 0
}

# Run ISCC
$iss = Join-Path $RepoRoot "installer\inno\installer.iss"
if (-not (Test-Path $iss)) { Write-Error "Installer script not found: $iss"; Pop-Location; exit 1 }

Write-Host "Running Inno Setup Compiler: $ISCC $iss"
& $ISCC $iss
if ($LASTEXITCODE -ne 0) { Write-Error "Inno Setup compilation failed with exit code $LASTEXITCODE"; Pop-Location; exit 1 }

Write-Host "Installer build finished. Output directory: $RepoRoot\installer\output"

Pop-Location
