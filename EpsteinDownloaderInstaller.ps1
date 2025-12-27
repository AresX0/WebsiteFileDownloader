<#
EpsteinDownloaderInstaller.ps1

PowerShell installer for EpsteinFilesDownloader
- Creates install directory (default: C:\Program Files\PlatypusFiles\WebsiteFileDownloader)
- Copies scripts, assets, tests, and README
- Prompts to install dependencies (Yes => pip installs requirements and PyInstaller, No => exit)
- Optionally builds a one-file executable using PyInstaller
#>

param(
    [string]$InstallDir = "C:\Program Files\PlatypusFiles\WebsiteFileDownloader",
    [switch]$Force
)

function Is-Admin {
    $current = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($current)
    return $principal.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
}

if (-not (Is-Admin)) {
    Write-Host "This installer requires administrative privileges to install into Program Files."
    Write-Host "The installer will re-launch as administrator now..."
    Start-Process -FilePath pwsh -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

Write-Host "Installer starting. Target install directory: $InstallDir"
if (-not (Test-Path -Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    Write-Host "Created: $InstallDir"
} else {
    Write-Host "Install directory already exists. Files may be overwritten."
}

# Files and directories to copy (relative to repository root)
$toCopy = @(
    "epstein_downloader_gui.py",
    "playwright_epstein_downloader.py",
    "requirements.txt",
    "README.md",
    ".gitignore",
    "assets"
)

# Copy files
foreach ($item in $toCopy) {
    $src = Join-Path -Path (Get-Location) -ChildPath $item
    $dst = Join-Path -Path $InstallDir -ChildPath $item
    try {
        if (Test-Path -Path $src) {
            if ((Get-Item $src).PSIsContainer) {
                Write-Host "Copying folder $item..."
                Copy-Item -Path $src -Destination $dst -Recurse -Force
            } else {
                Write-Host "Copying file $item..."
                Copy-Item -Path $src -Destination $dst -Force
            }
        } else {
            Write-Host "Warning: $item not found in repository root. Skipping."
        }
    } catch {
        Write-Host "Failed to copy $item: $_"
    }
}

# Ensure logs directory exists under install dir
$logsDir = Join-Path $InstallDir "logs"
if (-not (Test-Path -Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir -Force | Out-Null }

# Prompt to install dependencies
if (-not $Force) {
    $ans = Read-Host "Install Python dependencies (requirements.txt) and optionally build executable? (Y/N)"
    if ($ans -notin @('Y','y')) {
        Write-Host "Dependencies not installed. Installer exiting."
        exit 0
    }
}

# Run pip install
Write-Host "Installing Python dependencies from requirements.txt..."
$python = "python"
try {
    & $python -m pip install -r "$(Join-Path (Get-Location) 'requirements.txt')"
    if ($LASTEXITCODE -ne 0) { throw "pip install returned exit code $LASTEXITCODE" }
    Write-Host "Dependencies installed."
} catch {
    Write-Host "Failed to install dependencies: $_"
    Write-Host "Please ensure Python and pip are available in PATH and re-run this installer."
    exit 1
}

# Ensure PyInstaller is installed
Write-Host "Installing PyInstaller for creating an executable..."
try {
    & $python -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) { throw "pyinstaller pip install failed" }
} catch {
    Write-Host "Failed to install PyInstaller: $_"
    Write-Host "You can build the exe later by running: python -m PyInstaller --onefile epstein_downloader_gui.py"
}

# Optionally build executable
$buildAns = Read-Host "Build a one-file executable now? (Y/N)"
if ($buildAns -in @('Y','y')) {
    Push-Location $InstallDir
    try {
        Write-Host "Running: python -m PyInstaller --onefile --name epstein_downloader_gui epstein_downloader_gui.py"
        & $python -m PyInstaller --onefile --name epstein_downloader_gui epstein_downloader_gui.py
        if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }
        $distExe = Join-Path $InstallDir "dist\epstein_downloader_gui.exe"
        if (Test-Path $distExe) {
            Copy-Item -Path $distExe -Destination (Join-Path $InstallDir "epstein_downloader_gui.exe") -Force
            Write-Host "Executable created at: $(Join-Path $InstallDir 'epstein_downloader_gui.exe')"
        } else {
            Write-Host "Build completed but expected exe not found under dist\"
        }
    } catch {
        Write-Host "Failed to build executable: $_"
    } finally {
        Pop-Location
    }
} else {
    Write-Host "Skipping exe build as requested."
}

Write-Host "Installation complete. To run the GUI as an installed app, run:"
Write-Host "  $InstallDir\epstein_downloader_gui.exe  (if built) or"
Write-Host "  python $InstallDir\epstein_downloader_gui.py"

# Optionally create a start-menu shortcut (best-effort)
try {
    $shell = New-Object -ComObject WScript.Shell
    $lnk = $shell.CreateShortcut((Join-Path $Env:APPDATA "Microsoft\Windows\Start Menu\Programs\EpsteinFilesDownloader.lnk"))
    $exePath = if (Test-Path (Join-Path $InstallDir 'epstein_downloader_gui.exe')) { Join-Path $InstallDir 'epstein_downloader_gui.exe' } else { "$python $InstallDir\epstein_downloader_gui.py" }
    $lnk.TargetPath = $exePath
    $lnk.Save()
    Write-Host "Start Menu shortcut created."
} catch {
    Write-Host "Could not create Start Menu shortcut: $_"
}

Write-Host "Done."