# Starts backend (http://127.0.0.1:8000) and frontend dev server (http://localhost:5173) on Windows.
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot

Push-Location (Join-Path $Root 'backend')
uv sync --quiet
$backend = Start-Process -FilePath 'uv' -ArgumentList 'run', 'uvicorn', 'app.main:app', '--reload', '--host', '127.0.0.1', '--port', '8000' -PassThru -NoNewWindow
Pop-Location

try {
    Push-Location (Join-Path $Root 'frontend')
    npm install --silent
    npm run dev
} finally {
    Pop-Location
    if ($backend -and -not $backend.HasExited) { Stop-Process -Id $backend.Id -Force }
}
