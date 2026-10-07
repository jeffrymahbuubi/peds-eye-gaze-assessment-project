# Save a PNG of the app window, captured by the OS (PrintWindow), into docs\design\screenshots.
# Works while the window is behind other windows, so a mid-capture focus change can never
# capture the wrong window. A modal dialog is a separate window: pass its title.
#
#   tools\qa\capture_window.ps1 04-test-list
#   tools\qa\capture_window.ps1 03-add-test-dialog "Add New Test"
param(
    [Parameter(Mandatory = $true)][string]$Name,
    [string]$Title = "Gaze Assessment"
)
Add-Type -AssemblyName System.Drawing
if (-not ("QaPrintWindow" -as [type])) {
    Add-Type @'
using System; using System.Runtime.InteropServices;
public class QaPrintWindow {
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern IntPtr FindWindow(string c, string t);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  public struct RECT { public int L, T, R, B; }
}
'@
}
$handle = [QaPrintWindow]::FindWindow($null, $Title)
if ($handle -eq [IntPtr]::Zero) {
    $proc = Get-Process python -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowTitle -like "*$Title*" } | Select-Object -First 1
    if ($proc) { $handle = $proc.MainWindowHandle }
}
if ($handle -eq [IntPtr]::Zero) { Write-Output "window not found: $Title"; exit 1 }
$rect = New-Object QaPrintWindow+RECT
[QaPrintWindow]::GetWindowRect($handle, [ref]$rect) | Out-Null
$bmp = New-Object System.Drawing.Bitmap ($rect.R - $rect.L), ($rect.B - $rect.T)
$graphics = [System.Drawing.Graphics]::FromImage($bmp)
$dc = $graphics.GetHdc()
[QaPrintWindow]::PrintWindow($handle, $dc, 2) | Out-Null   # 2 = PW_RENDERFULLCONTENT
$graphics.ReleaseHdc($dc)
$outDir = Join-Path $PSScriptRoot "..\..\docs\design\screenshots"
$out = Join-Path (Resolve-Path $outDir) "$Name.png"
$bmp.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
Write-Output "saved $Name $($bmp.Width)x$($bmp.Height)"
