<#
.SYNOPSIS
    Builds the Website File Downloader MSI installer using WiX v6.
.DESCRIPTION
    1. Publishes the .NET app as self-contained win-x64
    2. Harvests all published files into a WiX fragment
    3. Builds the MSI with WiX 6
#>
param(
    [string]$Version = "2.1.1",
    [string]$Configuration = "Release"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$dotnetDir = Split-Path -Parent $scriptDir
$publishDir = Join-Path $dotnetDir "publish\win-x64"
$outputDir = Join-Path $scriptDir "output"

Write-Host "=== Website File Downloader MSI Builder ===" -ForegroundColor Cyan
Write-Host "Version: $Version"

# Step 1: Publish
Write-Host "`n[1/4] Publishing .NET app..." -ForegroundColor Yellow
Push-Location $dotnetDir
dotnet publish WebsiteDownloader.UI -c $Configuration -r win-x64 --self-contained -p:PublishSingleFile=false -o $publishDir
if ($LASTEXITCODE -ne 0) { throw "Publish failed" }
Pop-Location

# Step 2: Generate file harvest
Write-Host "`n[2/4] Harvesting files..." -ForegroundColor Yellow
$files = Get-ChildItem $publishDir -Recurse -File
$componentRefs = @()
$components = @()
$dirStack = @{}
$fileIndex = 0

foreach ($file in $files) {
    $fileIndex++
    $relPath = $file.FullName.Substring($publishDir.Length + 1)
    $relDir = Split-Path $relPath -Parent
    $id = "f$fileIndex"
    $compId = "c$fileIndex"
    
    $componentRefs += "      <ComponentRef Id=`"$compId`" />"
    
    if ([string]::IsNullOrEmpty($relDir)) {
        # Root directory file
        $components += @"
    <Component Id="$compId" Directory="INSTALLFOLDER" Guid="*">
      <File Id="$id" Source="$($file.FullName)" KeyPath="yes" />
    </Component>
"@
    } else {
        # Subdirectory file - create directory ID from path
        $dirId = "d_" + ($relDir -replace '[\\\/\.\- ]', '_')
        if (-not $dirStack.ContainsKey($dirId)) {
            $dirStack[$dirId] = $relDir
        }
        $components += @"
    <Component Id="$compId" Directory="$dirId" Guid="*">
      <File Id="$id" Source="$($file.FullName)" KeyPath="yes" />
    </Component>
"@
    }
}

# Build directory tree XML
$dirXml = @()
foreach ($entry in $dirStack.GetEnumerator()) {
    $dirId = $entry.Key
    $relDir = $entry.Value
    $dirXml += "      <Directory Id=`"$dirId`" Name=`"$relDir`" />"
}

Write-Host "  Harvested $fileIndex files in $($dirStack.Count) directories"

# Step 3: Write WiX source
Write-Host "`n[3/4] Generating WiX source..." -ForegroundColor Yellow

$wxsContent = @'
<?xml version="1.0" encoding="UTF-8"?>
<Wix xmlns="http://wixtoolset.org/schemas/v4/wxs"
     xmlns:ui="http://wixtoolset.org/schemas/v4/wxs/ui">
  
  <Package Name="Website File Downloader"
           Manufacturer="AresX0"
           Version="VERSION_PLACEHOLDER"
           UpgradeCode="8E2F4A1B-3C5D-4E6F-A7B8-9C0D1E2F3A4B"
           Scope="perUser"
           InstallerVersion="500">

    <MajorUpgrade DowngradeErrorMessage="A newer version of Website File Downloader is already installed." />
    <MediaTemplate EmbedCab="yes" CompressionLevel="high" />
    
    <ui:WixUI Id="WixUI_InstallDir" InstallDirectory="INSTALLFOLDER" />
    <WixVariable Id="WixUILicenseRtf" Value="$(var.LicenseFile)" />

    <StandardDirectory Id="LocalAppDataFolder">
      <Directory Id="INSTALLFOLDER" Name="WebsiteFileDownloader">
DIRS_PLACEHOLDER
      </Directory>
    </StandardDirectory>

    <Feature Id="MainFeature" Title="Website File Downloader" Level="1">
COMPREFS_PLACEHOLDER
    </Feature>

    <!-- Start Menu shortcut -->
    <StandardDirectory Id="ProgramMenuFolder">
      <Directory Id="ProgramMenuDir" Name="Website File Downloader" />
    </StandardDirectory>

    <ComponentGroup Id="Shortcuts">
      <Component Id="StartMenuShortcut" Directory="ProgramMenuDir" Guid="*">
        <Shortcut Id="ApplicationStartMenuShortcut"
                  Name="Website File Downloader"
                  Target="[INSTALLFOLDER]WebsiteDownloader.UI.exe"
                  WorkingDirectory="INSTALLFOLDER" />
        <RemoveFolder Id="RemoveProgramMenuDir" On="uninstall" />
        <RegistryValue Root="HKCU" Key="Software\AresX0\WebsiteFileDownloader" 
                       Name="installed" Type="integer" Value="1" KeyPath="yes" />
      </Component>

      <Component Id="DesktopShortcut" Directory="DesktopFolder" Guid="*">
        <Shortcut Id="ApplicationDesktopShortcut"
                  Name="Website File Downloader"
                  Target="[INSTALLFOLDER]WebsiteDownloader.UI.exe"
                  WorkingDirectory="INSTALLFOLDER" />
        <RegistryValue Root="HKCU" Key="Software\AresX0\WebsiteFileDownloader"
                       Name="desktop_shortcut" Type="integer" Value="1" KeyPath="yes" />
      </Component>
    </ComponentGroup>

    <Feature Id="ShortcutFeature" Title="Shortcuts" Level="1">
      <ComponentGroupRef Id="Shortcuts" />
    </Feature>

  </Package>

  <Fragment>
COMPONENTS_PLACEHOLDER
  </Fragment>

</Wix>
'@

$wxsContent = $wxsContent -replace 'VERSION_PLACEHOLDER', $Version
$wxsContent = $wxsContent -replace 'DIRS_PLACEHOLDER', ($dirXml -join "`n")
$wxsContent = $wxsContent -replace 'COMPREFS_PLACEHOLDER', ($componentRefs -join "`n")
$wxsContent = $wxsContent -replace 'COMPONENTS_PLACEHOLDER', ($components -join "`n")

$wxsPath = Join-Path $scriptDir "WebsiteDownloader.wxs"
$wxsContent | Set-Content -Path $wxsPath -Encoding UTF8
Write-Host "  Written $wxsPath"

# Create license RTF
$licenseRtf = Join-Path $scriptDir "License.rtf"
if (-not (Test-Path $licenseRtf)) {
    $licText = Get-Content (Join-Path $dotnetDir "..\LICENSE") -Raw -ErrorAction SilentlyContinue
    if (-not $licText) { $licText = "MIT License - See https://github.com/AresX0/WebsiteFileDownloader for details." }
    @"
{\rtf1\ansi\deff0
{\fonttbl{\f0 Consolas;}}
\f0\fs18
$($licText -replace "`n", "\par`n")
}
"@ | Set-Content -Path $licenseRtf -Encoding ASCII
}

# Step 4: Build MSI
Write-Host "`n[4/4] Building MSI..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

$msiPath = Join-Path $outputDir "WebsiteFileDownloader-$Version-win-x64.msi"

wix build $wxsPath `
    -ext WixToolset.UI.wixext `
    -d "LicenseFile=$licenseRtf" `
    -o $msiPath `
    2>&1

if ($LASTEXITCODE -ne 0) { 
    Write-Host "WiX build failed with exit code $LASTEXITCODE" -ForegroundColor Red
    exit 1
}

$msiSize = [math]::Round((Get-Item $msiPath).Length / 1MB, 1)
Write-Host "`n=== MSI built successfully ===" -ForegroundColor Green
Write-Host "  Path: $msiPath"
Write-Host "  Size: $msiSize MB"
Write-Host ""
