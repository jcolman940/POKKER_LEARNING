# Starts backend (http://127.0.0.1:8000) and frontend dev server (http://localhost:5173) on Windows.
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot

Push-Location (Join-Path $Root 'src/backend')
uv sync --quiet
$backend = Start-Process -FilePath 'uv' -ArgumentList 'run', 'uvicorn', 'app.main:app', '--reload', '--reload-dir', 'app', '--host', '127.0.0.1', '--port', '8000' -PassThru -NoNewWindow
Pop-Location

try {
    Push-Location (Join-Path $Root 'src/frontend')
    npm install --silent
    npm run dev
} finally {
    Pop-Location
    # uv spawns uvicorn as a child process; /T kills the whole tree so nothing keeps port 8000.
    if ($backend -and -not $backend.HasExited) { cmd /c "taskkill /T /F /PID $($backend.Id) >nul 2>&1" }
}
