# Runs every test suite in the monorepo on Windows.
# Usage: scripts\test.ps1 [core] [backend] [frontend] [integration] [launcher]
#   launcher (not in the default set) runs tests\launcher against dist\POKKER, which
#   scripts\package.ps1 builds; without it those tests are skipped.
param([string[]]$Targets = @('core', 'backend', 'frontend', 'integration'))

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot

function Invoke-Checked {
    param([scriptblock]$Command)
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "Command failed with exit code ${LASTEXITCODE}: $Command" }
}

function Test-Core {
    Write-Host '==> core (C++)'
    $build = Join-Path $Root 'src/core/build/dev'
    Invoke-Checked { cmake -S (Join-Path $Root 'src/core') -B $build }
    Invoke-Checked { cmake --build $build --config Release }
    Invoke-Checked { ctest --test-dir $build -C Release --output-on-failure }
}

function Test-Backend {
    Write-Host '==> backend (Python)'
    Push-Location (Join-Path $Root 'src/backend')
    try {
        Invoke-Checked { uv sync --quiet }
        Invoke-Checked { uv run ruff check . }
        Invoke-Checked { uv run ruff format --check . }
        Invoke-Checked { uv run pytest -q }
    } finally { Pop-Location }
}

function Test-Frontend {
    Write-Host '==> frontend (TypeScript)'
    Push-Location (Join-Path $Root 'src/frontend')
    try {
        Invoke-Checked { npm ci --silent }
        Invoke-Checked { npm run typecheck }
        Invoke-Checked { npm run lint }
        Invoke-Checked { npm test }
    } finally { Pop-Location }
}

function Test-Integration {
    Write-Host '==> integration'
    Push-Location (Join-Path $Root 'src/backend')
    try {
        Invoke-Checked { uv sync --quiet }
        Invoke-Checked { uv run pytest -q (Join-Path $Root 'tests/integration') }
    } finally { Pop-Location }
}

function Test-Launcher {
    Write-Host '==> launcher (packaged POKKER.exe, local update feed)'
    if (-not (Test-Path (Join-Path $Root 'dist/POKKER/POKKER.exe'))) {
        Write-Warning 'No existe dist\POKKER\POKKER.exe: corre scripts\package.ps1 antes (las pruebas se saltean).'
    }
    Push-Location (Join-Path $Root 'src/backend')
    try {
        Invoke-Checked { uv sync --quiet }
        Invoke-Checked { uv run pytest -q -rs (Join-Path $Root 'tests/launcher') }
    } finally { Pop-Location }
}

foreach ($t in $Targets) {
    switch ($t) {
        'core' { Test-Core }
        'backend' { Test-Backend }
        'frontend' { Test-Frontend }
        'integration' { Test-Integration }
        'launcher' { Test-Launcher }
        default { throw "Unknown target: $t" }
    }
}
Write-Host 'All requested suites passed.'
