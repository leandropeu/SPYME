Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$launcherPath = Join-Path $root 'SPYGYM Iniciar.cmd'
$iconDir = Join-Path $root 'assets\icons'
$iconPath = Join-Path $iconDir 'spygym-launcher.ico'
$shortcutPath = Join-Path $root 'SPYGYM.lnk'

if (-not (Test-Path $launcherPath)) {
    throw 'O launcher principal nao foi encontrado.'
}

if (-not (Test-Path $iconDir)) {
    New-Item -ItemType Directory -Path $iconDir -Force | Out-Null
}

Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class NativeIconMethods
{
    [DllImport("user32.dll", CharSet = CharSet.Auto)]
    public static extern bool DestroyIcon(IntPtr handle);
}
"@

$size = 256
$bitmap = [System.Drawing.Bitmap]::new($size, $size)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics.Clear([System.Drawing.Color]::FromArgb(5, 14, 22))

$backgroundRect = [System.Drawing.Rectangle]::new(0, 0, $size, $size)
$backgroundBrush = [System.Drawing.Drawing2D.LinearGradientBrush]::new(
    [System.Drawing.Point]::new(0, 0),
    [System.Drawing.Point]::new($size, $size),
    [System.Drawing.Color]::FromArgb(9, 28, 44),
    [System.Drawing.Color]::FromArgb(10, 78, 112)
)
$graphics.FillRectangle($backgroundBrush, $backgroundRect)

$framePen = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(120, 69, 208, 255), 8)
$graphics.DrawEllipse($framePen, 36, 36, 184, 184)

$lensBrush = [System.Drawing.Drawing2D.LinearGradientBrush]::new(
    [System.Drawing.Point]::new(74, 74),
    [System.Drawing.Point]::new(182, 182),
    [System.Drawing.Color]::FromArgb(26, 194, 255),
    [System.Drawing.Color]::FromArgb(7, 76, 122)
)
$graphics.FillEllipse($lensBrush, 74, 74, 108, 108)

$coreBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(222, 244, 255))
$graphics.FillEllipse($coreBrush, 109, 109, 38, 38)

$statusBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(104, 255, 168))
$graphics.FillEllipse($statusBrush, 178, 178, 42, 42)

$statusPen = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(220, 7, 14, 22), 6)
$graphics.DrawEllipse($statusPen, 178, 178, 42, 42)

$titleFont = [System.Drawing.Font]::new('Segoe UI Semibold', 20, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
$textBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(221, 244, 255))
$graphics.DrawString('SPY', $titleFont, $textBrush, 74, 198)

$iconHandle = $bitmap.GetHicon()
$icon = [System.Drawing.Icon]::FromHandle($iconHandle)
$fileStream = [System.IO.File]::Open($iconPath, [System.IO.FileMode]::Create)
$icon.Save($fileStream)
$fileStream.Close()
$icon.Dispose()
[NativeIconMethods]::DestroyIcon($iconHandle) | Out-Null

$graphics.Dispose()
$bitmap.Dispose()
$backgroundBrush.Dispose()
$framePen.Dispose()
$lensBrush.Dispose()
$coreBrush.Dispose()
$statusBrush.Dispose()
$statusPen.Dispose()
$titleFont.Dispose()
$textBrush.Dispose()

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $launcherPath
$shortcut.WorkingDirectory = $root
$shortcut.Description = 'Inicia backend, frontend e abre o painel do SPYGYM.'
$shortcut.IconLocation = "$iconPath,0"
$shortcut.Save()

Write-Host "Atalho criado em: $shortcutPath"
Write-Host "Icone criado em:  $iconPath"
