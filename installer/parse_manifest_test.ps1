$path = 'C:\Projects\Website Downloader\installer\msix_staging\AppxManifest.xml'
try {
    $s = Get-Content -Raw -Path $path
    $xml = [xml]$s
    Write-Host "Parsed OK. Root: $($xml.DocumentElement.Name)"
} catch {
    Write-Host "Parse failed: $($_.Exception.GetType().FullName)"
    Write-Host "Message: $($_.Exception.Message)"
    Write-Host "Stack: $($_.Exception.StackTrace)"
    if ($_.Exception.InnerException) { Write-Host "Inner: $($_.Exception.InnerException.Message)" }
    exit 1
}