# Builds the portable POKKER package (phase 7, spec 5.2) on Windows.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\package.ps1 [-Version X.Y.Z] [-SkipTests]
#
#   1. core (C++, Release; ctest unless -SkipTests)
#   2. backend: uv sync --group package + PyInstaller (backend\pokker-server.spec) -> build\server
#   3. frontend: npm ci + npm run build -> frontend\dist
#   4. launcher: launcher\build.ps1 -Out build\launcher
#   5. dist\POKKER\ (POKKER.exe + app\{VERSION, update.json, server, web, data})
#   6. smoke test on a temp copy with a temp --datos (never %LOCALAPPDATA%\POKKER)
#   7. dist\POKKER-X.Y.Z.zip + dist\POKKER-X.Y.Z.zip.sha256 (uppercase hex, no BOM)
#
# When cl.exe is not on PATH, loads the MSVC dev shell found with vswhere (or warns and goes on:
# CMake finds MSVC itself); prepends uv's folder when uv is missing.
param(
    [string]$Version,
    [switch]$SkipTests
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Build = Join-Path $Root 'build'
$Dist = Join-Path $Root 'dist'
$Feed = 'https://api.github.com/repos/jcolman940/POKKER_LEARNING/releases/latest'
$UvDir = Join-Path $env:APPDATA 'Python\Python314\Scripts'
$Utf8NoBom = New-Object System.Text.UTF8Encoding $false

function Step([string]$Message) { Write-Host "==> $Message" -ForegroundColor Cyan }

function Fail([string]$Message) { throw "package.ps1: $Message" }

function Invoke-Checked {
    param([string]$What, [scriptblock]$Command)
    & $Command
    if ($LASTEXITCODE -ne 0) { Fail "$What fallo (codigo $LASTEXITCODE)" }
}

function Find-VsDevShell {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (-not (Test-Path $vswhere)) { return $null }
    $install = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if ($LASTEXITCODE -ne 0 -or -not $install) { return $null }
    $shell = Join-Path (@($install)[0].Trim()) 'Common7\Tools\Launch-VsDevShell.ps1'
    if (Test-Path $shell) { return $shell }
    return $null
}

function Initialize-Toolchain {
    # cl.exe on PATH is a convenience, not a requirement: CMake's Visual Studio generator and
    # scikit-build find MSVC by themselves (e.g. on GitHub's windows-latest).
    if (-not (Get-Command cl.exe -ErrorAction SilentlyContinue)) {
        $devShell = Find-VsDevShell
        if ($devShell) {
            Write-Host "Cargando el entorno de MSVC ($devShell)"
            # The dev shell may print a harmless "vswhere.exe not recognized" error: do not stop on it.
            $prev = $ErrorActionPreference
            $ErrorActionPreference = 'Continue'
            try { & $devShell -Arch amd64 -HostArch amd64 -SkipAutomaticLocation 2>$null | Out-Null }
            finally { $ErrorActionPreference = $prev }
        }
        if (-not (Get-Command cl.exe -ErrorAction SilentlyContinue)) {
            Write-Warning 'cl.exe no esta en el PATH (no encontre el entorno de MSVC con vswhere): sigo, CMake busca el compilador solo.'
        }
    }
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        $env:Path = "$UvDir;$env:Path"
        if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { Fail "no encuentro uv (ni en $UvDir)" }
    }
    foreach ($tool in 'cmake', 'npm') {
        if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { Fail "no encuentro $tool en el PATH" }
    }
}

function Get-PackageVersion {
    if (-not $Version) { $script:Version = (Get-Content (Join-Path $Root 'VERSION') -Raw).Trim() }
    if ($Version -notmatch '^\d+\.\d+\.\d+$') { Fail "version invalida '$Version' (se espera X.Y.Z)" }
}

function Build-Core {
    Step 'core (C++, Release)'
    $out = Join-Path $Root 'core/build/dev'
    Invoke-Checked 'cmake (configurar)' { cmake -S (Join-Path $Root 'core') -B $out }
    Invoke-Checked 'cmake (compilar)' { cmake --build $out --config Release }
    if (-not $SkipTests) {
        Invoke-Checked 'ctest' { ctest --test-dir $out -C Release --output-on-failure }
    }
}

function Build-Server {
    Step 'servidor (PyInstaller)'
    Push-Location (Join-Path $Root 'backend')
    try {
        # Also (re)builds pokercore from core\ into .venv when its sources changed.
        Invoke-Checked 'uv sync --group package' { uv sync --group package }
        Invoke-Checked 'pyinstaller' {
            uv run pyinstaller --noconfirm --log-level WARN `
                --distpath (Join-Path $Build 'server') --workpath (Join-Path $Build 'pyinstaller') `
                pokker-server.spec
        }
    } finally { Pop-Location }
    $exe = Join-Path $Build 'server\pokker-server\pokker-server.exe'
    if (-not (Test-Path $exe)) { Fail "PyInstaller no genero $exe" }
}

function Build-Frontend {
    Step 'frontend (Vite build)'
    Push-Location (Join-Path $Root 'frontend')
    try {
        Invoke-Checked 'npm ci' { npm ci --silent }
        Invoke-Checked 'npm run build' { npm run build }
    } finally { Pop-Location }
    if (-not (Test-Path (Join-Path $Root 'frontend\dist\index.html'))) { Fail 'el build del frontend no genero index.html' }
}

function Build-Launcher {
    Step 'lanzador (csc.exe)'
    Invoke-Checked 'launcher\build.ps1' {
        powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root 'launcher\build.ps1') -Out (Join-Path $Build 'launcher')
    }
}

function Copy-Tree([string]$From, [string]$To) {
    if (-not (Test-Path $From)) { Fail "falta $From" }
    New-Item -ItemType Directory -Force (Split-Path -Parent $To) | Out-Null
    Copy-Item -Recurse -Force $From $To
}

function New-Package {
    Step "armado de dist\POKKER ($Version)"
    $pkg = Join-Path $Dist 'POKKER'
    if (Test-Path $pkg) { Remove-Item -Recurse -Force $pkg }
    $app = Join-Path $pkg 'app'
    New-Item -ItemType Directory -Force $app | Out-Null

    Copy-Item (Join-Path $Build 'launcher\POKKER.exe') (Join-Path $pkg 'POKKER.exe')
    [IO.File]::WriteAllText((Join-Path $app 'VERSION'), "$Version`n", $Utf8NoBom)
    [IO.File]::WriteAllText((Join-Path $app 'update.json'), "{`"feed`": `"$Feed`"}`n", $Utf8NoBom)
    Copy-Tree (Join-Path $Build 'server\pokker-server') (Join-Path $app 'server')
    Copy-Tree (Join-Path $Root 'frontend\dist') (Join-Path $app 'web')

    # Resources: never the user's external ranges, only the shipped placeholder and README.
    $data = Join-Path $app 'data'
    foreach ($dir in 'solver', 'precomputed', 'spots') {
        Copy-Tree (Join-Path $Root "data\$dir") (Join-Path $data $dir)
    }
    New-Item -ItemType Directory -Force (Join-Path $data 'ranges') | Out-Null
    foreach ($file in 'empty.json', 'README.md') {
        $src = Join-Path $Root "data\ranges\$file"
        if (-not (Test-Path $src)) { Fail "falta $src" }
        Copy-Item $src (Join-Path $data "ranges\$file")
    }
    return $pkg
}

# POKKER.exe / pokker-server.exe started from a folder whose path contains $Marker (matched by name
# because the temp path may come in 8.3 form while ExecutablePath is always the long form).
function Get-ServerProcesses([string]$Marker) {
    @(Get-CimInstance Win32_Process -Filter "Name = 'pokker-server.exe' OR Name = 'POKKER.exe'" |
        Where-Object { $_.ExecutablePath -and $_.ExecutablePath.IndexOf("\$Marker\",[StringComparison]::OrdinalIgnoreCase) -ge 0 })
}

function Invoke-Smoke([string]$Package) {
    Step 'prueba de humo'
    $marker = "pokker-smoke-" + [guid]::NewGuid().ToString("N").Substring(0, 8)
    $tmp = Join-Path ([IO.Path]::GetTempPath()) $marker
    $copy = Join-Path $tmp 'POKKER'
    $datos = Join-Path $tmp 'datos'
    $launcher = $null
    try {
        Copy-Item -Recurse $Package $copy
        New-Item -ItemType Directory -Force $datos | Out-Null
        $exe = Join-Path $copy 'POKKER.exe'

        # a) --diagnostico: every piece present, right version.
        $diag = Join-Path $tmp 'diagnostico.json'
        $p = Start-Process $exe -ArgumentList "--diagnostico=$diag", "--datos=$datos" -PassThru -Wait
        if ($p.ExitCode -ne 0) { Fail "--diagnostico termino con codigo $($p.ExitCode)" }
        $report = [IO.File]::ReadAllText($diag) | ConvertFrom-Json
        if (@($report.faltantes).Count -gt 0) { Fail "--diagnostico reporta faltantes: $($report.faltantes -join ', ')" }
        if ($report.version -ne $Version) { Fail "--diagnostico dice version '$($report.version)' y no '$Version'" }
        Write-Host "diagnostico OK: version $($report.version), $(@($report.encontradas).Count) piezas"

        # b) real start on a free port, then the tray's close path (token shutdown) after 20 s.
        $closeAfter = 20
        $clock = [Diagnostics.Stopwatch]::StartNew()
        $launcher = Start-Process $exe -PassThru -ArgumentList '--sin-navegador', '--sin-actualizar', "--datos=$datos", "--cerrar-tras=$closeAfter"
        $running = Join-Path $datos 'running.json'
        $port = 0
        while ($clock.Elapsed.TotalSeconds -lt 60 -and $port -eq 0) {
            if ($launcher.HasExited) { Fail "POKKER.exe termino antes de tiempo (codigo $($launcher.ExitCode))" }
            if (Test-Path $running) {
                try { $port = [int]([IO.File]::ReadAllText($running) | ConvertFrom-Json).port } catch { $port = 0 }
            }
            if ($port -eq 0) { Start-Sleep -Milliseconds 200 }
        }
        if ($port -eq 0) { Fail 'no aparecio running.json con el puerto en 60 s' }
        $base = "http://127.0.0.1:$port"
        $info = Invoke-RestMethod "$base/api/version" -TimeoutSec 10
        $script:ColdStart = $clock.Elapsed.TotalSeconds
        if ($info.packaged -ne $true) { Fail "/api/version no dice packaged: true ($($info | ConvertTo-Json -Compress))" }
        if ($info.app -ne $Version) { Fail "/api/version dice app '$($info.app)' y no '$Version'" }
        $index = Invoke-WebRequest "$base/" -UseBasicParsing -TimeoutSec 10
        if ($index.StatusCode -ne 200 -or $index.Content -notmatch '<div id="root">') { Fail "/ no sirve index.html (HTTP $($index.StatusCode))" }
        Write-Host ("servidor OK en el puerto {0}: /api/version {1}, / sirve index.html; arranque en frio {2:N1} s" -f $port, ($info | ConvertTo-Json -Compress), $script:ColdStart)

        # c) the launcher closes itself (--cerrar-tras) and nothing stays alive.
        if (-not $launcher.WaitForExit(($closeAfter + 40) * 1000)) { Fail 'POKKER.exe no termino tras --cerrar-tras' }
        Start-Sleep -Milliseconds 500
        $left = Get-ServerProcesses $marker
        if ($left.Count -gt 0) { Fail "quedaron procesos vivos: $(($left | ForEach-Object { "$($_.Name) ($($_.ProcessId))" }) -join ', ')" }
        if (Test-Path $running) { Fail 'running.json quedo despues de cerrar' }
        Write-Host 'cierre OK: sin procesos de POKKER ni running.json'
    } catch {
        $log = Join-Path $datos 'pokker.log'
        if (Test-Path $log) { Write-Host '--- pokker.log (final) ---'; Get-Content $log -Tail 40 | Write-Host }
        throw
    } finally {
        foreach ($proc in (Get-ServerProcesses $marker)) { Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue }
        if ($launcher -and -not $launcher.HasExited) { Stop-Process -Id $launcher.Id -Force -ErrorAction SilentlyContinue }
        Start-Sleep -Milliseconds 300
        Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
    }
}

function New-Zip([string]$Package) {
    Step 'zip + sha256'
    $zip = Join-Path $Dist "POKKER-$Version.zip"
    $sha = "$zip.sha256"
    foreach ($f in $zip, $sha) { if (Test-Path $f) { Remove-Item -Force $f } }
    # Entry by entry: Windows PowerShell's Compress-Archive and ZipFile.CreateFromDirectory write
    # '\' separators; this keeps the POKKER/ top folder with portable '/' names.
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $base = (Get-Item $Package).FullName.TrimEnd('\')
    $stream = [IO.File]::Open($zip, [IO.FileMode]::CreateNew)
    $archive = New-Object IO.Compression.ZipArchive($stream, [IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($file in (Get-ChildItem -Recurse -File $base)) {
            $name = 'POKKER/' + $file.FullName.Substring($base.Length + 1).Replace('\', '/')
            [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $file.FullName, $name, [IO.Compression.CompressionLevel]::Optimal) | Out-Null
        }
    } finally {
        $archive.Dispose()
        $stream.Dispose()
    }
    $hash = (Get-FileHash -Algorithm SHA256 $zip).Hash.ToUpperInvariant()
    [IO.File]::WriteAllText($sha, $hash, $Utf8NoBom)
    return $zip
}

$total = [Diagnostics.Stopwatch]::StartNew()
$script:ColdStart = $null
Initialize-Toolchain
Get-PackageVersion
Build-Core
Build-Server
Build-Frontend
Build-Launcher
$pkg = New-Package
Invoke-Smoke $pkg
$zip = New-Zip $pkg
$size = (Get-Item $zip).Length
Write-Host ''
Write-Host ("Listo: {0} ({1:N1} MB), sha256 {2}" -f $zip, ($size / 1MB), [IO.File]::ReadAllText("$zip.sha256")) -ForegroundColor Green
Write-Host ("Arranque en frio (prueba de humo): {0:N1} s; armado total: {1:N0} s" -f $script:ColdStart, $total.Elapsed.TotalSeconds)
