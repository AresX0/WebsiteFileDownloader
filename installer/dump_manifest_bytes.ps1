$path = 'C:\Projects\Website Downloader\installer\msix_staging\AppxManifest.xml'
$b = [System.IO.File]::ReadAllBytes($path)
Write-Host "Length:" $b.Length
Write-Host "First 16 bytes (decimal):" ($b[0..15] -join ' ')
Write-Host "First 16 bytes (hex):" (($b[0..15] | ForEach-Object { $_.ToString('X2') }) -join ' ')
Write-Host "File preview (raw start):"
[System.Text.Encoding]::UTF8.GetString($b[0..255]) | ForEach-Object { Write-Host $_ }
