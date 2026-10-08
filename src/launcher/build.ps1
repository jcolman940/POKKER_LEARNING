# Compiles the POKKER.exe launcher with the .NET Framework 4 C# compiler (C# 5).
# Usage (from anywhere): powershell -ExecutionPolicy Bypass -File src\launcher\build.ps1 [-Out <dir>]
# Default output: src\launcher\out\POKKER.exe (ignored by git).
param([string]$Out = (Join-Path $PSScriptRoot 'out'))
$ErrorActionPreference = 'Stop'

$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path $csc)) { $csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe' }
if (-not (Test-Path $csc)) { throw "No encuentro csc.exe de .NET Framework 4" }

$repo = Split-Path $PSScriptRoot -Parent
New-Item -ItemType Directory -Force $Out | Out-Null
$Out = (Resolve-Path $Out).Path
$exe = Join-Path $Out 'POKKER.exe'

Push-Location $repo
try {
    # /resource: the tray loads the 16 px frame of the same icon (Tray.LoadIcon).
    & $csc /nologo /target:winexe /win32icon:launcher\pokker.ico /resource:launcher\pokker.ico,pokker.ico `
        /r:System.Windows.Forms.dll /r:System.Drawing.dll /r:System.Web.Extensions.dll `
        /r:System.IO.Compression.dll /r:System.IO.Compression.FileSystem.dll `
        "/out:$exe" launcher\POKKER.cs
    if ($LASTEXITCODE -ne 0) { throw "csc.exe fallo con codigo $LASTEXITCODE" }
} finally {
    Pop-Location
}
Write-Host "Compilado: $exe"
