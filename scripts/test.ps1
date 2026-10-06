# Runs every test suite in the monorepo on Windows.
# Usage: scripts\test.ps1 [core] [backend] [frontend] [integration]
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
    $build = Join-Path $Root 'core/build/dev'
    Invoke-Checked { cmake -S (Join-Path $Root 'core') -B $build }
    Invoke-Checked { cmake --build $build --config Release }
    Invoke-Checked { ctest --test-dir $build -C Release --output-on-failure }
}

function Test-Backend {
    Write-Host '==> backend (Python)'
    Push-Location (Join-Path $Root 'backend')
    try {
        Invoke-Checked { uv sync --quiet }
        Invoke-Checked { uv run ruff check . }
        Invoke-Checked { uv run ruff format --check . }
        Invoke-Checked { uv run pytest -q }
    } finally { Pop-Location }
}

function Test-Frontend {
    Write-Host '==> frontend (TypeScript)'
    Push-Location (Join-Path $Root 'frontend')
    try {
        Invoke-Checked { npm ci --silent }
        Invoke-Checked { npm run typecheck }
        Invoke-Checked { npm run lint }
        Invoke-Checked { npm test }
    } finally { Pop-Location }
}

function Test-Integration {
    Write-Host '==> integration'
    Push-Location (Join-Path $Root 'backend')
    try {
        Invoke-Checked { uv sync --quiet }
        Invoke-Checked { uv run pytest -q (Join-Path $Root 'tests/integration') }
    } finally { Pop-Location }
}

foreach ($t in $Targets) {
    switch ($t) {
        'core' { Test-Core }
        'backend' { Test-Backend }
        'frontend' { Test-Frontend }
        'integration' { Test-Integration }
        default { throw "Unknown target: $t" }
    }
}
Write-Host 'All requested suites passed.'
