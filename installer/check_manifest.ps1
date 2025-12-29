$path = 'C:\Projects\Website Downloader\installer\msix_staging\AppxManifest.xml'
if (-not (Test-Path $path)) { Write-Error "Missing manifest: $path"; exit 1 }
$c = Get-Content -Raw -Path $path
$m1 = ([regex]::Matches($c, '<Package')).Count
$m2 = ([regex]::Matches($c, '</Package>')).Count
Write-Host "Count '<Package': $m1"
Write-Host "Count '</Package>': $m2"
Write-Host "Length chars: $($c.Length)"
Write-Host "Last 200 chars:"; $t = $c.Substring([Math]::Max(0, $c.Length - 200)); Write-Host $t
