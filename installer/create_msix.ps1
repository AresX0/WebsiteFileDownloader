<#
Create an MSIX package (unsigned by default) for EpsteinFilesDownloader.

Usage examples:
  # Create unsigned package (requires makeappx.exe on PATH)
  .\create_msix.ps1 -PackageName "PlatypusFiles.EpsteinDownloader" -Version "1.0.0.0" -PublisherCN "CN=MyPublisher" -OutDir "..\\output"

  # Create and sign (requires signtool.exe and a .pfx certificate)
  .\create_msix.ps1 -PackageName "PlatypusFiles.EpsteinDownloader" -Version "1.0.0.0" -PublisherCN "CN=MyPublisher" -OutDir "..\\output" -Sign -PfxPath "C:\\certs\\code.pfx" -PfxPassword "password"

Notes:
- makeappx.exe is part of the Windows 10+ SDK (Windows Kits) and must be available on PATH.
- Signing is optional; Windows will require the package to be signed or the machine to have developer mode & trust the signing cert to install.
- MSIX installs to the Windows Packaged Apps location (not arbitrary Program Files). If you require the exact path C:\\Program Files\\PlatypusFiles\\WebsiteFileDownloader, prefer the Inno Setup or simple PowerShell installer.
#>
param(
    [string]$PackageName = "PlatypusFiles.EpsteinDownloader",
    [string]$Version = "1.0.0.0",
    [string]$PublisherCN = "CN=PlatypusFiles, O=PlatypusFiles, L=City, S=State, C=US",
    [string]$StagingDir = "$PSScriptRoot\\msix_staging",
    [string]$OutDir = "$PSScriptRoot\\..\\output",
    [switch]$Sign,
    [string]$PfxPath,
    [string]$PfxPassword
)

Set-StrictMode -Version Latest

# Find makeappx
$makeappx = Get-Command makeappx -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Definition -ErrorAction SilentlyContinue
if (-not $makeappx) {
    # Try common SDK locations
    $candidates = @(
        'C:\\Program Files (x86)\\Windows Kits\\10\\bin',
        'C:\\Program Files\\Windows Kits\\10\\bin'
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) {
            $exe = Get-ChildItem -Path $c -Recurse -Filter makeappx.exe -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($exe) { $makeappx = $exe.FullName; break }
        }
    }
}
if (-not $makeappx) { Write-Error "makeappx.exe not found. Install Windows SDK or add makeappx to PATH."; exit 2 }

# Prepare staging dir
if (Test-Path $StagingDir) { Remove-Item $StagingDir -Recurse -Force }
New-Item -ItemType Directory -Path $StagingDir | Out-Null

$distExe = Join-Path $PSScriptRoot "..\\dist\\EpsteinDownloader.exe" | Resolve-Path -ErrorAction Stop
Copy-Item -Path $distExe -Destination $StagingDir -Force
# Copy config and assets
Copy-Item -Path (Join-Path $PSScriptRoot "..\\config.json") -Destination $StagingDir -Force
Copy-Item -Path (Join-Path $PSScriptRoot "..\\queue_state.json") -Destination $StagingDir -Force
if (Test-Path (Join-Path $PSScriptRoot "..\\assets")) {
    New-Item -ItemType Directory -Path (Join-Path $StagingDir 'assets') -Force | Out-Null
    Copy-Item -Path (Join-Path $PSScriptRoot "..\\assets\\*") -Destination (Join-Path $StagingDir 'assets') -Recurse -Force
}

# Generate AppxManifest from template
$template = Get-Content -Path (Join-Path $PSScriptRoot 'AppxManifest.template.xml') -Raw
$manifest = $template -replace '%PUBLISHER_CN%', ($PublisherCN -replace '^CN=','') -replace '%VERSION%', $Version
$manifestPath = Join-Path $StagingDir 'AppxManifest.xml'
Set-Content -Path $manifestPath -Value $manifest -Encoding UTF8

# Pack MSIX
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }
$msixPath = Join-Path (Resolve-Path $OutDir) "${PackageName}_${Version}.msix"
Write-Host "Packing MSIX into: $msixPath"
& $makeappx pack /d $StagingDir /p $msixPath
if ($LASTEXITCODE -ne 0) { Write-Error "makeappx failed with exit code $LASTEXITCODE"; exit $LASTEXITCODE }

if ($Sign) {
    $signtool = Get-Command signtool -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Definition -ErrorAction SilentlyContinue
    if (-not $signtool) { Write-Error "signtool.exe not found on PATH; cannot sign package."; exit 3 }
    if (-not (Test-Path $PfxPath)) { Write-Error "PFX file not found at $PfxPath"; exit 4 }

    Write-Host "Signing MSIX: $msixPath"
    & $signtool sign /fd sha256 /a /f $PfxPath /p $PfxPassword /tr http://timestamp.digicert.com /td sha256 $msixPath
    if ($LASTEXITCODE -ne 0) { Write-Error "signtool failed with exit code $LASTEXITCODE"; exit $LASTEXITCODE }
}

Write-Host "MSIX package created: $msixPath"
Write-Host "To install unsigned on a developer machine: enable Developer Mode (Settings → For developers) and run:`Add-AppxPackage -Path '$(Split-Path $msixPath -Leaf)'` from the package directory, or use: `Add-AppxPackage -Path "$msixPath"`"