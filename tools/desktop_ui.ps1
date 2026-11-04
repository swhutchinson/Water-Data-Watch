# Drives Power BI Desktop for visual checks: brings it to the front, then runs actions and saves a screenshot.
# Actions (comma-separated): click:X:Y  move:X:Y  type:TEXT  key:{ENTER}  wait:MS  wheel:X:Y:NOTCHES
param([string]$Actions = '', [string]$Shot = '')
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public class U {
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint x, uint y, int d, IntPtr e);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
}
"@
$p = Get-Process PBIDesktop -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if ($p) { [U]::ShowWindow($p.MainWindowHandle, 3) | Out-Null; [U]::SetForegroundWindow($p.MainWindowHandle) | Out-Null; Start-Sleep -Milliseconds 400 }
foreach ($a in ($Actions -split ',(?=(click|move|type|key|wait|wheel):)')) {
  if (-not $a -or $a -match '^(click|move|type|key|wait|wheel)$') { continue }
  $parts = $a -split ':', 2; $arg = $parts[1]
  switch ($parts[0]) {
    'click' { $xy = $arg -split ':'; [U]::SetCursorPos([int]$xy[0], [int]$xy[1]) | Out-Null; Start-Sleep -Milliseconds 120; [U]::mouse_event(2, 0, 0, 0, [IntPtr]::Zero); [U]::mouse_event(4, 0, 0, 0, [IntPtr]::Zero); Start-Sleep -Milliseconds 300 }
    'move'  { $xy = $arg -split ':'; [U]::SetCursorPos([int]$xy[0], [int]$xy[1]) | Out-Null; Start-Sleep -Milliseconds 300 }
    'wheel' { $xy = $arg -split ':'; [U]::SetCursorPos([int]$xy[0], [int]$xy[1]) | Out-Null; for ($i = 0; $i -lt [math]::Abs([int]$xy[2]); $i++) { [U]::mouse_event(0x800, 0, 0, $(if ([int]$xy[2] -lt 0) { -120 } else { 120 }), [IntPtr]::Zero); Start-Sleep -Milliseconds 150 } }
    'type'  { [System.Windows.Forms.SendKeys]::SendWait($arg); Start-Sleep -Milliseconds 200 }
    'key'   { [System.Windows.Forms.SendKeys]::SendWait($arg); Start-Sleep -Milliseconds 300 }
    'wait'  { Start-Sleep -Milliseconds ([int]$arg) }
  }
}
if ($Shot) {
  $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
  $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
  $g = [System.Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
  $bmp.Save($Shot, [System.Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $bmp.Dispose()
}
