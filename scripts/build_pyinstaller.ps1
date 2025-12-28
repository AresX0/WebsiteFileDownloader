param(
    [string]$Name = "EpsteinFilesDownloader",
    [string]$DistDir = "dist",
    [string]$SpecFile = "",
    [switch]$NoConsole
)

Set-Location -LiteralPath (Split-Path -Path $MyInvocation.MyCommand.Definition -Parent)\..\

Write-Host "Creating PyInstaller build for $Name"
# Ensure pyinstaller is available
python -m pip install --upgrade pip
pip install pyinstaller

# Clean previous builds
if (Test-Path build) { Remove-Item -Recurse -Force build }
if (Test-Path dist) { Remove-Item -Recurse -Force dist }
if (Test-Path "$Name.spec") { Remove-Item "$Name.spec" -Force }

# Prepare add-data strings for assets and README
$addData = @()
if (Test-Path assets) { $addData += "assets;assets" }
if (Test-Path RUNNING.md) { $addData += "RUNNING.md;." }

$addDataArgs = $addData | ForEach-Object { "--add-data `"$_`"" } | Out-String
$noConsoleArg = $NoConsole.IsPresent ? "--noconsole" : ""

$cmd = "pyinstaller --clean --noconfirm $noConsoleArg --name `"$Name`" $addDataArgs epstein_downloader_gui.py"
Write-Host "Running: $cmd"
Invoke-Expression $cmd

if (Test-Path "$DistDir\$Name\$Name.exe") {
    Write-Host "PyInstaller build succeeded: $DistDir\$Name\$Name.exe"
} else {
    throw "PyInstaller build did not produce expected executable."
}
