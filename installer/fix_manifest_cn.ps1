$m = 'C:\Projects\Website Downloader\installer\msix_staging\AppxManifest.xml'
if (-not (Test-Path $m)) { Write-Error "Manifest missing: $m"; exit 1 }
$content = Get-Content -Path $m -Raw
$new = $content -replace 'CN=CN=','CN='
Set-Content -Path $m -Value $new -Encoding UTF8
Write-Host 'Updated Identity line:'
Select-String -Path $m -Pattern '<Identity' | ForEach-Object { Write-Host $_.Line }
