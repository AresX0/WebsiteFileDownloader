$path = 'C:\Projects\Website Downloader\installer\msix_staging\AppxManifest.xml'
$s = Get-Content -Path $path -Raw
$enc = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($path, $s, $enc)
$b = [System.IO.File]::ReadAllBytes($path)
Write-Host "Wrote no-BOM file: length=$($b.Length); first bytes=" + (($b[0..5] | ForEach-Object { $_.ToString('X2') }) -join ' ')
