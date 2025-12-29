<#
Run EpsteinFilesDownloader GUI (developer-friendly launcher)

Usage examples:
  # Launch normally (will attempt to use .venv/python if present)
  .\run_epstein_gui.ps1

  # Launch and bypass auto-installer (useful for dev/test)
  .\run_epstein_gui.ps1 -SkipInstall

  # Launch and bypass single-instance mutex (developer convenience)
  .\run_epstein_gui.ps1 -BypassSingleInstance

  # Launch headless (sets EPISTEIN_HEADLESS=1)
  .\run_epstein_gui.ps1 -Headless

Options:
  -SkipInstall           Set EPISTEIN_SKIP_INSTALL=1 (skip runtime installs)
  -BypassSingleInstance  Patch single-instance lock (temporary, for dev only)
  -Headless              Set EPISTEIN_HEADLESS=1 in env
  -NoActivate            Do not attempt to activate .venv Activate.ps1 (useful in CI)
#>

param(
    [switch]$SkipInstall,
    [switch]$BypassSingleInstance,
    [switch]$Headless,
    [switch]$NoActivate,
    [switch]$Validate
)

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

# Determine python executable (prefer repo .venv)
$venvPython = Join-Path $scriptDir '.venv\Scripts\python.exe'
if (Test-Path $venvPython) {
    $python = $venvPython
} else {
    $pyCmd = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCmd) { $python = $pyCmd.Source } else {
        $pyCmd = Get-Command python -ErrorAction SilentlyContinue
        if ($pyCmd) { $python = $pyCmd.Source } else {
            Write-Error "Python interpreter not found. Install Python or create a .venv in the repo root."
            exit 1
        }
    }
}

# Environment switches
if ($SkipInstall) { $env:EPISTEIN_SKIP_INSTALL = '1' } else { if ($env:EPISTEIN_SKIP_INSTALL) { Remove-Item Env:\EPISTEIN_SKIP_INSTALL -ErrorAction SilentlyContinue } }
if ($Headless) { $env:EPISTEIN_HEADLESS = '1' } else { if ($env:EPISTEIN_HEADLESS) { Remove-Item Env:\EPISTEIN_HEADLESS -ErrorAction SilentlyContinue } }

# Optionally activate .venv for convenience (does not change python chosen above)
if (-not $NoActivate) {
    $activate = Join-Path $scriptDir '.venv\Scripts\Activate.ps1'
    if (Test-Path $activate) {
        try { & $activate } catch { Write-Host "Failed to source Activate.ps1 (continuing): $_" }
    }
}

# Helper to write a small temp python launcher file (avoids quoting headaches)
function New-TempLauncher {
    param([string]$Body)
    $tmp = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), ('epstein_launch_' + [System.Guid]::NewGuid().ToString() + '.py'))
    $Body | Out-File -FilePath $tmp -Encoding UTF8
    return $tmp
}

# Optional validation mode: confirm import works before launching
if ($Validate) {
    $testBody = @"
import sys
sys.path.insert(0, r"${scriptDir}")
try:
    import importlib.util
    found = importlib.util.find_spec('epstein_downloader_gui') is not None
    print('IMPORT_OK' if found else 'IMPORT_FAIL')
except Exception as e:
    print('IMPORT_ERROR', e)
"@
    $testFile = New-TempLauncher -Body $testBody
    Write-Host "Running validation test with python: $python"
    $out = & $python $testFile 2>&1
    Remove-Item $testFile -ErrorAction SilentlyContinue
    Write-Host "Validation output:`n$out"
    if ($out -match 'IMPORT_OK') {
        Write-Host "Validation succeeded: module importable."
        exit 0
    } else {
        Write-Error "Validation failed. Check that the repo path is correct and try running with -BypassSingleInstance or -SkipInstall as needed."
        exit 1
    }
}

if ($BypassSingleInstance) {
    $pyBody = @"
import sys
# Ensure repo root is on sys.path so imports resolve when running a temp script
sys.path.insert(0, r"${scriptDir}")
import epstein_downloader_gui as gui
# Developer convenience: bypass named mutex / file lock so you can open multiple instances
try:
    gui.acquire_single_instance_lock = lambda *a,**k: ('noop', None)
    gui.release_single_instance_lock = lambda *a,**k: None
except Exception:
    pass
# Launch GUI
if hasattr(gui, 'main'):
    gui.main()
else:
    # fallback if module structure is different
    from epstein_downloader_gui import DownloaderGUI
    import tkinter as tk
    r = tk.Tk()
    DownloaderGUI(r)
    r.mainloop()
"@
    $launcher = New-TempLauncher -Body $pyBody
    Write-Host "Launching app (single-instance bypass) with python: $python"
    & $python $launcher
    Remove-Item $launcher -ErrorAction SilentlyContinue
}   else {
    $pyBody = @"
import sys
# Ensure repo root is on sys.path so imports resolve when running a temp script
sys.path.insert(0, r"${scriptDir}")
import epstein_downloader_gui as gui
if hasattr(gui, 'main'):
    gui.main()
else:
    from epstein_downloader_gui import DownloaderGUI
    import tkinter as tk
    r = tk.Tk()
    DownloaderGUI(r)
    r.mainloop()
"@
    $launcher = New-TempLauncher -Body $pyBody
    Write-Host "Launching app with python: $python"
    & $python $launcher
    Remove-Item $launcher -ErrorAction SilentlyContinue
}
