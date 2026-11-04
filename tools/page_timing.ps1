# Clicks a page tab, then measures how much of the canvas is drawn every second (share of non-background pixels).
param([int]$X, [int]$Y, [int]$Seconds = 20)
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public class V { [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint x, uint y, int d, IntPtr e);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h); }
"@
$p = Get-Process PBIDesktop | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
[V]::SetForegroundWindow($p.MainWindowHandle) | Out-Null; Start-Sleep -Milliseconds 300
[V]::SetCursorPos($X, $Y) | Out-Null; [V]::mouse_event(2,0,0,0,[IntPtr]::Zero); [V]::mouse_event(4,0,0,0,[IntPtr]::Zero)
[V]::SetCursorPos(700, 740) | Out-Null
$t0 = Get-Date; $out = @()
for ($i = 0; $i -lt $Seconds * 2; $i++) {
  Start-Sleep -Milliseconds 500
  $bmp = New-Object System.Drawing.Bitmap 860, 420; $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.CopyFromScreen(160, 215, 0, 0, $bmp.Size); $n = 0; $lit = 0
  for ($x = 0; $x -lt 860; $x += 10) { for ($y = 0; $y -lt 420; $y += 10) { $c = $bmp.GetPixel($x, $y); $n++; if (($c.R + $c.G + $c.B) -gt 120) { $lit++ } } }
  $g.Dispose(); $bmp.Dispose()
  $out += ('{0:N1}s {1:P0}' -f ((Get-Date) - $t0).TotalSeconds, ($lit / $n))
}
$out -join ' | '
