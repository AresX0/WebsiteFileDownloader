param(
    [string]$InstallerPath = "installer\inno\installer\output\EpsteinFilesDownloader_Installer.exe",
    [string]$InstallDir = "C:\Temp\EpsteinInstallerTest",
    [int]$RunSeconds = 10,
    [switch]$NoCleanup
)

$scriptLog = Join-Path $env:TEMP "epstein_installer_test.log"
"--- Installer test run started: $(Get-Date) ---" | Out-File -FilePath $scriptLog -Encoding utf8

# Resolve installer path relative to repository root if needed
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
$instFull = if (Test-Path $InstallerPath) { Resolve-Path $InstallerPath } elseif (Test-Path (Join-Path $repoRoot $InstallerPath)) { Resolve-Path (Join-Path $repoRoot $InstallerPath) } else { Write-Error "Installer not found at '$InstallerPath' or under repo root"; "Installer not found" | Out-File -FilePath $scriptLog -Append; exit 1 }
"Installer: $instFull" | Out-File -FilePath $scriptLog -Append
"InstallDir: $InstallDir" | Out-File -FilePath $scriptLog -Append

# Clean target dir
if (Test-Path $InstallDir) { "Removing existing install dir: $InstallDir" | Out-File -FilePath $scriptLog -Append; Remove-Item -Recurse -Force $InstallDir -ErrorAction SilentlyContinue }

# Run installer silently
try {
    "Running installer..." | Out-File -FilePath $scriptLog -Append
    $proc = Start-Process -FilePath $instFull -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES',"/DIR=$InstallDir" -Wait -PassThru -ErrorAction Stop
    "Installer exit code: $($proc.ExitCode)" | Out-File -FilePath $scriptLog -Append
} catch {
    "Installer run failed: $_" | Out-File -FilePath $scriptLog -Append
    exit 2
}

if (-not (Test-Path $InstallDir)) {
    "Install directory not created; aborting" | Out-File -FilePath $scriptLog -Append
    exit 3
}

"Installed files:" | Out-File -FilePath $scriptLog -Append
Get-ChildItem -Path $InstallDir -Force -Recurse -Depth 2 | Select-Object FullName, Length | Out-String -Width 200 | Out-File -FilePath $scriptLog -Append

$exe = Join-Path $InstallDir 'epstein_downloader_gui.exe'
if (-not (Test-Path $exe)) { "Installed executable not found: $exe" | Out-File -FilePath $scriptLog -Append; exit 4 }

# Launch the installed EXE and monitor
try {
    "Launching installed exe: $exe" | Out-File -FilePath $scriptLog -Append
    $p = Start-Process -FilePath $exe -PassThru
} catch {
    "Failed to start exe: $_" | Out-File -FilePath $scriptLog -Append
    exit 5
}

$start = Get-Date
$deadline = $start.AddSeconds($RunSeconds)
while ((Get-Date) -lt $deadline) {
    # Collect process list for exe
    $procs = Get-CimInstance Win32_Process | Where-Object { ($_.ExecutablePath -ne $null) -and ($_.ExecutablePath -like "*epstein_downloader_gui.exe") }
    "[$(Get-Date -Format o)] Process count: $($procs.Count)" | Out-File -FilePath $scriptLog -Append
    if ($procs.Count -gt 1) {
        "Multiple running instances detected: $($procs | ForEach-Object { $_.ProcessId })" | Out-File -FilePath $scriptLog -Append
        "-- Instance details --" | Out-File -FilePath $scriptLog -Append
        $procs | Select-Object ProcessId, ParentProcessId, CreationDate, ExecutablePath, @{Name='Cmd';Expression={ ($_.CommandLine -replace '\n',' ' -replace '\r',' ') }} | Out-String | Out-File -FilePath $scriptLog -Append
    }
    Start-Sleep -Seconds 2
}

# Capture logs from install dir
$logdir = Join-Path $InstallDir 'logs'
if (Test-Path $logdir) {
    "Log files present:" | Out-File -FilePath $scriptLog -Append
    Get-ChildItem -Path $logdir -File | Select-Object Name, Length, LastWriteTime | Out-String | Out-File -FilePath $scriptLog -Append
    # include last 200 lines of error.log if present
    $errlog = Join-Path $logdir 'error.log'
    if (Test-Path $errlog) { "-- error.log tail --" | Out-File -FilePath $scriptLog -Append; Get-Content $errlog -Tail 200 | Out-File -FilePath $scriptLog -Append }
} else {
    "No logs directory found" | Out-File -FilePath $scriptLog -Append
}

# Stop any running processes
$procs2 = Get-CimInstance Win32_Process | Where-Object { ($_.ExecutablePath -ne $null) -and ($_.ExecutablePath -like "*epstein_downloader_gui.exe") }
if ($procs2.Count -gt 0) {
    "Stopping processes: $($procs2 | ForEach-Object { $_.ProcessId } | Out-String)" | Out-File -FilePath $scriptLog -Append
    foreach ($procItem in $procs2) {
        try { Stop-Process -Id $procItem.ProcessId -Force -ErrorAction SilentlyContinue; "Stopped PID: $($procItem.ProcessId)" | Out-File -FilePath $scriptLog -Append } catch { "Failed to stop PID $($procItem.ProcessId): $_" | Out-File -FilePath $scriptLog -Append }
    }
} else {
    "No running epstein processes found" | Out-File -FilePath $scriptLog -Append
}

if (-not $NoCleanup) {
    "Cleaning up install dir: $InstallDir" | Out-File -FilePath $scriptLog -Append
    Remove-Item -Recurse -Force $InstallDir -ErrorAction SilentlyContinue
}

"--- Installer test run finished: $(Get-Date) ---" | Out-File -FilePath $scriptLog -Append
Write-Host "Installer test completed. See log: $scriptLog"; exit 0
