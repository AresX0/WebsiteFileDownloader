Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

# Use Add-Type with ReferencedAssemblies to resolve Bitmap
Add-Type -ReferencedAssemblies @("System.Drawing","System.Drawing.Primitives") -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Collections.Generic;
using System.Text;

public class Cap {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
    [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int ht, bool r);
    [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr h);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int m);
    [DllImport("user32.dll")] public static extern bool EnumWindows(Del f, IntPtr p);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint p);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f);
    [DllImport("user32.dll")] public static extern bool UpdateWindow(IntPtr h);
    public delegate bool Del(IntPtr h, IntPtr p);
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left, Top, Right, Bottom; }

    public static List<IntPtr> FindWindows(int pid) {
        var list = new List<IntPtr>();
        EnumWindows((h, p) => {
            uint wp; GetWindowThreadProcessId(h, out wp);
            if ((int)wp == pid && IsWindowVisible(h) && GetWindowTextLength(h) > 0) list.Add(h);
            return true;
        }, IntPtr.Zero);
        return list;
    }
    public static string Title(IntPtr h) {
        int n = GetWindowTextLength(h);
        if (n == 0) return "";
        var sb = new StringBuilder(n + 1);
        GetWindowText(h, sb, sb.Capacity);
        return sb.ToString();
    }
}
"@

$ssDir = "c:\Projects\Website Downloader\website-stuff\screenshots"
$exe = "c:\Projects\Website Downloader\dotnet\WebsiteDownloader.UI\bin\Release\net10.0-windows10.0.19041.0\WebsiteDownloader.UI.exe"

function Take-Screenshot([IntPtr]$hWnd, [string]$filePath) {
    [Cap]::SetForegroundWindow($hWnd) | Out-Null
    [Cap]::UpdateWindow($hWnd) | Out-Null
    Start-Sleep -Milliseconds 800

    # Get window rect
    $rect = New-Object Cap+RECT
    [Cap]::GetWindowRect($hWnd, [ref]$rect) | Out-Null
    $w = $rect.Right - $rect.Left
    $h = $rect.Bottom - $rect.Top

    # Use PrintWindow to capture just the window
    $bmp = New-Object System.Drawing.Bitmap($w, $h, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $hdc = $g.GetHdc()
    [Cap]::PrintWindow($hWnd, $hdc, 2) | Out-Null  # PW_RENDERFULLCONTENT = 2
    $g.ReleaseHdc($hdc)
    $g.Dispose()
    $bmp.Save($filePath, [System.Drawing.Imaging.ImageFormat]::Png)
    Write-Host "  OK: $filePath ($w x $h)"
    $bmp.Dispose()
}

Write-Host "Launching..."
$p = Start-Process $exe -PassThru
for ($i = 0; $i -lt 20 -and $p.MainWindowHandle -eq [IntPtr]::Zero; $i++) { Start-Sleep 1; $p.Refresh() }
$mh = $p.MainWindowHandle
if ($mh -eq [IntPtr]::Zero) { Write-Host "ERROR: no window"; exit 1 }
Write-Host "Main handle=$mh"

[Cap]::ShowWindow($mh, 1) | Out-Null
[Cap]::MoveWindow($mh, 80, 30, 1300, 920, $true) | Out-Null
Start-Sleep -Seconds 2

# 1) Main window dark theme
Write-Host "-- 01: Main Window (Dark) --"
Take-Screenshot -hWnd $mh -filePath "$ssDir\01_main_window.png"

# 2) Settings dialog
Write-Host "-- 02: Settings --"
[Cap]::SetForegroundWindow($mh) | Out-Null
Start-Sleep -Milliseconds 400
[System.Windows.Forms.SendKeys]::SendWait("%f")
Start-Sleep -Milliseconds 500
[System.Windows.Forms.SendKeys]::SendWait("s")
Start-Sleep -Seconds 2

$settingsH = $null
foreach ($w in [Cap]::FindWindows($p.Id)) {
    $t = [Cap]::Title($w)
    Write-Host "  found: '$t'"
    if ($t -like "*Setting*") { $settingsH = $w }
}
if ($settingsH) {
    Take-Screenshot -hWnd $settingsH -filePath "$ssDir\02_settings.png"
    [Cap]::SetForegroundWindow($settingsH) | Out-Null
    [System.Windows.Forms.SendKeys]::SendWait("{ESC}")
    Start-Sleep -Milliseconds 500
} else {
    Write-Host "  SETTINGS NOT FOUND!"
}

# 3) Schedule dialog
Write-Host "-- 03: Schedule --"
[Cap]::SetForegroundWindow($mh) | Out-Null
Start-Sleep -Milliseconds 400
[System.Windows.Forms.SendKeys]::SendWait("%f")
Start-Sleep -Milliseconds 500
[System.Windows.Forms.SendKeys]::SendWait("d")
Start-Sleep -Seconds 2

$schedH = $null
foreach ($w in [Cap]::FindWindows($p.Id)) {
    $t = [Cap]::Title($w)
    Write-Host "  found: '$t'"
    if ($t -like "*Schedule*") { $schedH = $w }
}
if ($schedH) {
    Take-Screenshot -hWnd $schedH -filePath "$ssDir\03_schedule.png"
    [Cap]::SetForegroundWindow($schedH) | Out-Null
    [System.Windows.Forms.SendKeys]::SendWait("{ESC}")
    Start-Sleep -Milliseconds 500
} else {
    Write-Host "  SCHEDULE NOT FOUND!"
}

# 4) Light theme
Write-Host "-- 04: Light Theme --"
[Cap]::SetForegroundWindow($mh) | Out-Null
Start-Sleep -Milliseconds 300
[System.Windows.Forms.SendKeys]::SendWait("^t")
Start-Sleep -Milliseconds 1500
[Cap]::MoveWindow($mh, 80, 30, 1300, 920, $true) | Out-Null
Start-Sleep -Milliseconds 800
Take-Screenshot -hWnd $mh -filePath "$ssDir\04_light_theme.png"

# Restore dark + close
[System.Windows.Forms.SendKeys]::SendWait("^t")
Start-Sleep -Milliseconds 300
Stop-Process -Name "WebsiteDownloader.UI" -Force -ErrorAction SilentlyContinue
Write-Host "=== ALL DONE ==="
