try {
    $templatePath = 'C:\Projects\Website Downloader\installer\AppxManifest.template.xml'
    $stagingManifest = 'C:\Projects\Website Downloader\installer\msix_staging\AppxManifest.xml'
    Write-Host "Template exists: " (Test-Path $templatePath)
    $tpl = Get-Content -Path $templatePath -Raw -ErrorAction Stop
    Write-Host "Template length:" $tpl.Length
    $manifest = $tpl.Replace('%PUBLISHER_CN%','CN=PlatypusFiles').Replace('%VERSION%','1.0.0.0')
    $stagingDir = Split-Path $stagingManifest -Parent
    if (-not (Test-Path $stagingDir)) { Write-Host "Creating staging dir: $stagingDir"; New-Item -ItemType Directory -Path $stagingDir | Out-Null }
    Write-Host "Writing manifest to $stagingManifest"
    [System.IO.File]::WriteAllText($stagingManifest, $manifest, [System.Text.Encoding]::UTF8)
    $fi = Get-Item $stagingManifest -ErrorAction Stop
    Write-Host "Wrote file, size:" $fi.Length
    Write-Host "Preview (first 20 lines):"
    Get-Content -Path $stagingManifest -TotalCount 20 | ForEach-Object { Write-Host $_ }
    exit 0
} catch {
    Write-Host "ERROR: $($_.Exception.Message)"
    Write-Host "Stack:" $_.ScriptStackTrace
    exit 1
}