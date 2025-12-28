# Wrapper script to build the installer and explicitly include Playwright browsers
# Usage: Run in a PowerShell with the repository root as working directory

param(
    [switch]$Clean,
    [switch]$InstallDeps
)

$ScriptDir = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent$ExpectedRepoRoot = "C:\Projects\Website Downloader"
$Current = (Get-Location).ProviderPath
if ($Current -ne $ExpectedRepoRoot -and $env:EPISTEIN_ALLOW_PATH_OVERRIDE -ne "1") {
    Write-Error "Build wrapper must be run from '$ExpectedRepoRoot'. To override (advanced), set EPISTEIN_ALLOW_PATH_OVERRIDE=1."
    exit 1
}Push-Location $ScriptDir\..

$flags = @()
if ($Clean) { $flags += '-Clean' }
if ($InstallDeps) { $flags += '-InstallDeps' }
# Explicitly ensure browsers are included
$flags += '-IncludePlaywrightBrowsers'

Write-Host "Running build_installer.ps1 with flags: $flags"
& .\installer\build_installer.ps1 @flags

Pop-Location
