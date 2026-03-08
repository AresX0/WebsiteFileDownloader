# capture3.ps1 — Screenshot capture using PrintWindow via pure PowerShell + minimal P/Invoke
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

$pinvoke = @"
using System;
using System.Runtime.InteropServices;
using System.Text;

public class WinU {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out int left, out int top, out int right, out int bottom);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
    [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int ht, bool r);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f);
    [DllImport("user32.dll")] public static extern bool UpdateWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr h);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)]
    public static extern int GetWindowText(IntPtr h, StringBuilder s, int m);

    public static string Title(IntPtr h) {
        int n = GetWindowTextLength(h);
        if (n == 0) return "";
        var sb = new StringBuilder(n + 1);
        GetWindowText(h, sb, sb.Capacity);
        return sb.ToString();
    }
}
"@

# Separate GetWindowRect with proper struct
$pinvoke2 = @"
using System;
using System.Runtime.InteropServices;

public class WinRect {
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, ref RECT lpRect);

    [DllImport("user32.dll")]
    public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdcBlt, uint nFlags);
}
"@

Add-Type -TypeDefinition $pinvoke
Add-Type -TypeDefinition $pinvoke2

$ssDir = "c:\Projects\Website Downloader\website-stuff\screenshots"
$exe   = "c:\Projects\Website Downloader\dotnet\WebsiteDownloader.UI\bin\Release\net10.0-windows10.0.19041.0\WebsiteDownloader.UI.exe"

function Take-Shot {
    param([IntPtr]$Handle, [string]$Path)

    [WinU]::SetForegroundWindow($Handle) | Out-Null
    [WinU]::UpdateWindow($Handle) | Out-Null
    Start-Sleep -Milliseconds 800

    $r = New-Object WinRect+RECT
    [WinRect]::GetWindowRect($Handle, [ref]$r) | Out-Null
    $w = $r.Right - $r.Left
    $h = $r.Bottom - $r.Top

    $bmp = New-Object System.Drawing.Bitmap($w, $h, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $gfx = [System.Drawing.Graphics]::FromImage($bmp)
    $hdc = $gfx.GetHdc()
    [WinRect]::PrintWindow($Handle, $hdc, [uint32]2) | Out-Null
    $gfx.ReleaseHdc($hdc)
    $gfx.Dispose()
    $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    Write-Host "  Saved: $Path ($w x $h)"
    $bmp.Dispose()
}

function Find-ChildWindow {
    param([int]$ProcessId, [string]$TitlePattern)
    $allProcs = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $allProcs) { return $null }

    # Enumerate windows belonging to this process ID
    Add-Type @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

public class WinEnum {
    [DllImport("user32.dll")] public static extern bool EnumWindows(CallBack cb, IntPtr p);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr h);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int m);
    public delegate bool CallBack(IntPtr h, IntPtr p);

    public static IntPtr[] GetVisibleWindows(int targetPid) {
        var results = new List<IntPtr>();
        EnumWindows((h, p) => {
            uint pid;
            GetWindowThreadProcessId(h, out pid);
            if ((int)pid == targetPid && IsWindowVisible(h) && GetWindowTextLength(h) > 0)
                results.Add(h);
            return true;
        }, IntPtr.Zero);
        return results.ToArray();
    }
}
"@ -ErrorAction SilentlyContinue

    $windows = [WinEnum]::GetVisibleWindows($ProcessId)
    foreach ($wh in $windows) {
        $title = [WinU]::Title($wh)
        Write-Host "  Window: '$title' (handle $wh)"
        if ($title -like $TitlePattern) { return $wh }
    }
    return $null
}

# --- Main ---
Write-Host "Launching app..."
Stop-Process -Name "WebsiteDownloader.UI" -Force -ErrorAction SilentlyContinue 2>$null
Start-Sleep 1
$proc = Start-Process $exe -PassThru
for ($i = 0; $i -lt 25 -and $proc.MainWindowHandle -eq [IntPtr]::Zero; $i++) { Start-Sleep 1; $proc.Refresh() }
$mh = $proc.MainWindowHandle
if ($mh -eq [IntPtr]::Zero) { Write-Host "ERROR: no window"; exit 1 }
Write-Host "Main window handle: $mh"

[WinU]::ShowWindow($mh, 1) | Out-Null
[WinU]::MoveWindow($mh, 80, 30, 1300, 920, $true) | Out-Null
Start-Sleep -Seconds 3

# --- Screenshot 1: Main Window (Dark Theme) ---
Write-Host "`n--- 01: Main Window (Dark Theme) ---"
Take-Shot -Handle $mh -Path "$ssDir\01_main_window.png"

# --- Screenshot 2: Settings Dialog ---
Write-Host "`n--- 02: Settings Dialog ---"
[WinU]::SetForegroundWindow($mh) | Out-Null
Start-Sleep -Seconds 1
[System.Windows.Forms.SendKeys]::SendWait("%{f}")
Start-Sleep -Milliseconds 800
[System.Windows.Forms.SendKeys]::SendWait("s")
Start-Sleep -Seconds 3

$sh = Find-ChildWindow -ProcessId $proc.Id -TitlePattern "*Setting*"
# Retry if not found
if (-not $sh -or $sh -eq [IntPtr]::Zero) {
    Write-Host "  Retrying settings open..."
    [WinU]::SetForegroundWindow($mh) | Out-Null
    Start-Sleep -Milliseconds 500
    [System.Windows.Forms.SendKeys]::SendWait("%{f}")
    Start-Sleep -Milliseconds 800
    [System.Windows.Forms.SendKeys]::SendWait("s")
    Start-Sleep -Seconds 3
    $sh = Find-ChildWindow -ProcessId $proc.Id -TitlePattern "*Setting*"
}
if ($sh -and $sh -ne [IntPtr]::Zero) {
    Take-Shot -Handle $sh -Path "$ssDir\02_settings.png"
    [WinU]::SetForegroundWindow($sh) | Out-Null
    [System.Windows.Forms.SendKeys]::SendWait("{ESC}")
    Start-Sleep -Milliseconds 600
} else {
    Write-Host "  WARNING: Settings window not found"
}

# --- Screenshot 3: Schedule Dialog ---
Write-Host "`n--- 03: Schedule Dialog ---"
[WinU]::SetForegroundWindow($mh) | Out-Null
Start-Sleep -Seconds 1
[System.Windows.Forms.SendKeys]::SendWait("%{f}")
Start-Sleep -Milliseconds 800
[System.Windows.Forms.SendKeys]::SendWait("d")
Start-Sleep -Seconds 3

$sch = Find-ChildWindow -ProcessId $proc.Id -TitlePattern "*Schedule*"
# Retry if not found
if (-not $sch -or $sch -eq [IntPtr]::Zero) {
    Write-Host "  Retrying schedule open..."
    [WinU]::SetForegroundWindow($mh) | Out-Null
    Start-Sleep -Milliseconds 500
    [System.Windows.Forms.SendKeys]::SendWait("%{f}")
    Start-Sleep -Milliseconds 800
    [System.Windows.Forms.SendKeys]::SendWait("d")
    Start-Sleep -Seconds 3
    $sch = Find-ChildWindow -ProcessId $proc.Id -TitlePattern "*Schedule*"
}
if ($sch -and $sch -ne [IntPtr]::Zero) {
    Take-Shot -Handle $sch -Path "$ssDir\03_schedule.png"
    [WinU]::SetForegroundWindow($sch) | Out-Null
    [System.Windows.Forms.SendKeys]::SendWait("{ESC}")
    Start-Sleep -Milliseconds 600
} else {
    Write-Host "  WARNING: Schedule window not found"
}

# --- Screenshot 4: Main Window (Light Theme) ---
Write-Host "`n--- 04: Light Theme ---"
[WinU]::SetForegroundWindow($mh) | Out-Null
Start-Sleep -Milliseconds 400
[System.Windows.Forms.SendKeys]::SendWait("^t")
Start-Sleep -Milliseconds 1500
[WinU]::MoveWindow($mh, 80, 30, 1300, 920, $true) | Out-Null
Start-Sleep -Milliseconds 800
Take-Shot -Handle $mh -Path "$ssDir\04_light_theme.png"

# Restore dark and close
[System.Windows.Forms.SendKeys]::SendWait("^t")
Start-Sleep -Milliseconds 500
Stop-Process -Name "WebsiteDownloader.UI" -Force -ErrorAction SilentlyContinue
Write-Host "`n=== ALL SCREENSHOTS COMPLETE ==="
