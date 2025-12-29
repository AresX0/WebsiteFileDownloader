$log = "C:\Temp\epstein_process_log.txt"
Remove-Item -Path $log -ErrorAction SilentlyContinue
$end = (Get-Date).AddSeconds(10)
while ((Get-Date) -lt $end) {
    Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -and $_.ExecutablePath -like '*epstein_downloader_gui.exe' } |
        Select-Object ProcessId,ParentProcessId,ExecutablePath,CommandLine | Out-File -FilePath $log -Append
    Start-Sleep -Seconds 1
}
Write-Host "Logged processes to: $log"