param(
    [string]$Name = "EpsteinFilesDownloader",
    [string]$Version = "1.0.0",
    [string]$Publisher = "CN=EpsteinFiles",
    [string]$DisplayName = "Epstein Files Downloader",
    [string]$PublisherDisplay = "EpsteinFiles",
    [string]$Description = "Downloader for Epstein Court Records",
    [string]$CertPath = "",
    [string]$CertPassword = "",
    [string]$IdentityName = "com.platypus.epstein"
)

Set-Location -LiteralPath (Split-Path -Path $MyInvocation.MyCommand.Definition -Parent)\..\

$staging = Join-Path -Path (Get-Location) -ChildPath "build\msix_staging"
$packdir = Join-Path -Path (Get-Location) -ChildPath "build\msix"
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $staging, $packdir
New-Item -ItemType Directory -Path $staging -Force | Out-Null
New-Item -ItemType Directory -Path $packdir -Force | Out-Null

# Copy built exe (from pyinstaller) into staging
$exeSource = Join-Path -Path (Get-Location) -ChildPath ("dist\$Name\$Name.exe")
if (-not (Test-Path $exeSource)) {
    throw "Executable not found at $exeSource. Run build_pyinstaller first."
}
New-Item -ItemType Directory -Path (Join-Path $staging "Assets") -Force | Out-Null
Copy-Item $exeSource -Destination (Join-Path $staging $Name + ".exe") -Force
# Copy runtime files and assets
if (Test-Path assets) { Copy-Item assets -Destination (Join-Path $staging "assets") -Recurse -Force }
if (Test-Path RUNNING.md) { Copy-Item RUNNING.md -Destination $staging -Force }

# Generate AppxManifest from template
$tmpl = Get-Content -Raw -Path scripts\msix\AppxManifest.xml.template
$manifest = $tmpl -replace '{{IDENTITY_NAME}}',$IdentityName -replace '{{PUBLISHER}}',$Publisher -replace '{{VERSION}}',$Version -replace '{{DISPLAY_NAME}}',$DisplayName -replace '{{PUBLISHER_DISPLAY}}',$PublisherDisplay -replace '{{DESCRIPTION}}',$Description -replace '{{EXECUTABLE_NAME}}',"$Name.exe"
$manifestPath = Join-Path $staging 'AppxManifest.xml'
$manifest | Out-File -FilePath $manifestPath -Encoding utf8

# Pack into MSIX using MakeAppx.exe
$makeappx = "makeappx.exe"
$output = Join-Path $packdir "$Name-$Version.msix"
Write-Host "Packing MSIX -> $output"
& $makeappx pack /d $staging /p $output
if (-not (Test-Path $output)) { throw "makeappx failed to create MSIX package" }

# Sign if certificate provided
if ($CertPath -and (Test-Path $CertPath)) {
    Write-Host "Signing package with cert: $CertPath"
    $signtool = "signtool.exe"
    & $signtool sign /fd sha256 /a /f $CertPath /p $CertPassword /tr http://timestamp.digicert.com /td sha256 $output
    Write-Host "Signed: $output"
} else {
    Write-Host "No certificate provided or path invalid: skipping signing. You can sign the MSIX later with SignTool."
}

Write-Host "MSIX package created at: $output"
