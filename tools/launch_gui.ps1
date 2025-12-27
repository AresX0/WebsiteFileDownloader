$Env:EPISTEIN_SKIP_INSTALL = '1'
$Env:EPSTEIN_HEADLESS = '0'
Set-Location 'C:\Projects\Website Downloader'
& 'C:\Path\.venv\Scripts\python.exe' -u epstein_downloader_gui.py
