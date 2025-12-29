$templatePath = 'C:\Projects\Website Downloader\installer\AppxManifest.template.xml'
$stagingManifest = 'C:\Projects\Website Downloader\installer\msix_staging\AppxManifest.xml'

if (-not (Test-Path $templatePath)) { Write-Error "Template not found: $templatePath"; exit 1 }
$tpl = Get-Content -Path $templatePath -Raw
$manifest = $tpl.Replace('%PUBLISHER_CN%','CN=PlatypusFiles').Replace('%VERSION%','1.0.0.0')

# Ensure staging dir exists
$stagingDir = Split-Path $stagingManifest -Parent
if (-not (Test-Path $stagingDir)) { New-Item -ItemType Directory -Path $stagingDir | Out-Null }

# Write manifest with proper UTF-8 BOM
[System.IO.File]::WriteAllText($stagingManifest, $manifest, [System.Text.Encoding]::UTF8)
Write-Host "Wrote manifest to: $stagingManifest"
Get-Content -Path $stagingManifest -TotalCount 40 | ForEach-Object { Write-Host $_ }
