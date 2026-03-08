Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;
using System.Drawing;
using System.Drawing.Imaging;
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
    [DllImport("dwmapi.dll")] public static extern int DwmGetWindowAttribute(IntPtr h, int a, out RECT r, int s);
    public delegate bool Del(IntPtr h, IntPtr p);
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left, Top, Right, Bottom; }

    public static Bitmap Capture(IntPtr hWnd) {
        RECT r;
        int hr = DwmGetWindowAttribute(hWnd, 9, out r, Marshal.SizeOf(typeof(RECT)));
        if (hr != 0) GetWindowRect(hWnd, out r);
        int w = r.Right - r.Left, h = r.Bottom - r.Top;
        if (w <= 0 || h <= 0) return null;
        var bmp = new Bitmap(w, h, PixelFormat.Format32bppArgb);
        using (var g = Graphics.FromImage(bmp)) {
            IntPtr dc = g.GetHdc();
            PrintWindow(hWnd, dc, 2);
            g.ReleaseHdc(dc);
        }
        return bmp;
    }

    public static List<IntPtr> FindWindows(int pid) {
        var list = new List<IntPtr>();
        EnumWindows((h, p) => {
            uint wp; GetWindowThreadProcessId(h, out wp);
            if ((int)wp == pid && IsWindowVisible(h) && GetWindowTextLength(h) > 0)
                list.Add(h);
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

function Take([IntPtr]$h, [string]$f) {
    [Cap]::SetForegroundWindow($h) | Out-Null
    [Cap]::UpdateWindow($h) | Out-Null
    Start-Sleep -Milliseconds 800
    $bmp = [Cap]::Capture($h)
    if ($bmp) { $bmp.Save($f, [System.Drawing.Imaging.ImageFormat]::Png); Write-Host "  OK: $f ($($bmp.Width)x$($bmp.Height))"; $bmp.Dispose() }
    else { Write-Host "  FAIL: $f" }
}

Write-Host "Launching..."
$p = Start-Process $exe -PassThru
for ($i=0; $i -lt 20 -and $p.MainWindowHandle -eq [IntPtr]::Zero; $i++) { Start-Sleep 1; $p.Refresh() }
$mh = $p.MainWindowHandle
Write-Host "Main=$mh"
[Cap]::ShowWindow($mh, 1) | Out-Null
[Cap]::MoveWindow($mh, 80, 30, 1300, 920, $true) | Out-Null
Start-Sleep 2

Write-Host "-- 01 main dark --"
Take $mh "$ssDir\01_main_window.png"

Write-Host "-- 02 settings --"
[Cap]::SetForegroundWindow($mh) | Out-Null; Start-Sleep -Ms 400
[System.Windows.Forms.SendKeys]::SendWait("%f"); Start-Sleep -Ms 500
[System.Windows.Forms.SendKeys]::SendWait("s"); Start-Sleep 2
$sh = $null
foreach ($w in [Cap]::FindWindows($p.Id)) { $tt=[Cap]::Title($w); Write-Host "  >$tt"; if ($tt -like "*Setting*") {$sh=$w} }
if ($sh) { Take $sh "$ssDir\02_settings.png"; [System.Windows.Forms.SendKeys]::SendWait("{ESC}"); Start-Sleep -Ms 500 }

Write-Host "-- 03 schedule --"
[Cap]::SetForegroundWindow($mh) | Out-Null; Start-Sleep -Ms 400
[System.Windows.Forms.SendKeys]::SendWait("%f"); Start-Sleep -Ms 500
[System.Windows.Forms.SendKeys]::SendWait("d"); Start-Sleep 2
$sch = $null
foreach ($w in [Cap]::FindWindows($p.Id)) { $tt=[Cap]::Title($w); Write-Host "  >$tt"; if ($tt -like "*Schedule*") {$sch=$w} }
if ($sch) { Take $sch "$ssDir\03_schedule.png"; [System.Windows.Forms.SendKeys]::SendWait("{ESC}"); Start-Sleep -Ms 500 }

Write-Host "-- 04 light --"
[Cap]::SetForegroundWindow($mh) | Out-Null; Start-Sleep -Ms 300
[System.Windows.Forms.SendKeys]::SendWait("^t"); Start-Sleep -Milliseconds 1500
[Cap]::MoveWindow($mh, 80, 30, 1300, 920, $true) | Out-Null; Start-Sleep -Ms 800
Take $mh "$ssDir\04_light_theme.png"

[System.Windows.Forms.SendKeys]::SendWait("^t"); Start-Sleep -Ms 300
Stop-Process -Name "WebsiteDownloader.UI" -Force -EA 0
Write-Host "DONE"
