# capture_screenshots.ps1 — Launch the app and capture screenshots
# Requires: .NET System.Drawing, User32 P/Invoke

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

Add-Type @"
using System;
using System.Runtime.InteropServices;

public class Win32 {
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

    [DllImport("user32.dll")]
    public static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int nWidth, int nHeight, bool bRepaint);

    [StructLayout(LayoutKind.Sequential)]
    public struct RECT {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }
}
"@

function Capture-Window {
    param(
        [IntPtr]$hWnd,
        [string]$OutputPath
    )
    
    [Win32]::SetForegroundWindow($hWnd) | Out-Null
    Start-Sleep -Milliseconds 500
    
    $rect = New-Object Win32+RECT
    [Win32]::GetWindowRect($hWnd, [ref]$rect) | Out-Null
    
    $width = $rect.Right - $rect.Left
    $height = $rect.Bottom - $rect.Top
    
    $bitmap = New-Object System.Drawing.Bitmap($width, $height)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.CopyFromScreen($rect.Left, $rect.Top, 0, 0, (New-Object System.Drawing.Size($width, $height)))
    $graphics.Dispose()
    
    $bitmap.Save($OutputPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $bitmap.Dispose()
    
    Write-Host "Captured: $OutputPath ($width x $height)"
}

$outputDir = "c:\Projects\Website Downloader\dotnet\docs\screenshots"
if (-not (Test-Path $outputDir)) { New-Item -ItemType Directory -Path $outputDir | Out-Null }

# Build first
Write-Host "Building..."
Push-Location "c:\Projects\Website Downloader\dotnet"
$buildResult = dotnet build --configuration Release -v q 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed!"
    Pop-Location
    exit 1
}
Pop-Location

# Launch app
Write-Host "Launching app..."
$exe = "c:\Projects\Website Downloader\dotnet\WebsiteDownloader.UI\bin\Release\net10.0-windows10.0.19041.0\WebsiteDownloader.UI.exe"
$proc = Start-Process -FilePath $exe -PassThru

# Wait for the main window
$timeout = 15
$elapsed = 0
while ($proc.MainWindowHandle -eq [IntPtr]::Zero -and $elapsed -lt $timeout) {
    Start-Sleep -Seconds 1
    $elapsed++
    $proc.Refresh()
}

if ($proc.MainWindowHandle -eq [IntPtr]::Zero) {
    Write-Host "ERROR: Could not get window handle after $timeout seconds"
    $proc | Stop-Process -Force
    exit 1
}

Write-Host "Window found. Handle: $($proc.MainWindowHandle)"

# Position and resize window to a consistent size
[Win32]::ShowWindow($proc.MainWindowHandle, 1) | Out-Null  # SW_NORMAL
[Win32]::MoveWindow($proc.MainWindowHandle, 100, 50, 1280, 900, $true) | Out-Null
Start-Sleep -Seconds 2

# Screenshot 1: Main window (default state)
Write-Host "Capturing main window..."
Capture-Window -hWnd $proc.MainWindowHandle -OutputPath "$outputDir\01_main_window.png"

# Done with screenshots - close app
Start-Sleep -Seconds 1
$proc | Stop-Process -Force -EA 0
Write-Host "Done! Screenshots saved to: $outputDir"
