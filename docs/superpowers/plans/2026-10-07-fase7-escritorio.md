# Fase 7 — Escritorio y actualizaciones: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** POKKER empaquetado como zip portátil (lanzador C# + backend PyInstaller que sirve el frontend) que se actualiza solo desde GitHub Releases, con descarga de TexasSolver desde la app.

**Architecture:** El backend gana un "modo empaquetado" (recursos y web por variables de entorno, un solo puerto, filtro de Host, latido/apagado con clave, estado) y la instalación de TexasSolver. Un lanzador en C# (.NET Framework 4) maneja instancia única, actualización atómica con vuelta atrás, arranque del servidor, ícono y cierre. `scripts\package.ps1` arma y prueba el zip; `release.yml` publica al pushear un tag.

**Tech Stack:** Python 3.12 + FastAPI + PyInstaller; React + Vite; C# 5 / .NET Framework 4.x (`csc.exe`), WinForms; PowerShell; GitHub Actions (windows-latest).

**Spec:** `docs/superpowers/specs/2026-10-07-fase7-escritorio-design.md`

## Global Constraints

- El modo desarrollo no cambia: `scripts\dev.ps1`, `./var`, Vite en :5173 y todos los tests actuales siguen pasando sin variables nuevas.
- Datos del usuario empaquetado en `%LOCALAPPDATA%\POKKER\`; una actualización nunca toca esa carpeta salvo `updates\` y `datos.anterior\`.
- El servidor empaquetado escucha solo en `127.0.0.1`; rechaza `Host` ajenos (400); `/api/app/shutdown` exige `X-Pokker-Token` = `POKER_LAUNCH_TOKEN` (403).
- Vigilante de latido: tras el primer latido, 60 s sin latidos **y** solver sin trabajos corriendo/en cola (o cola pausada) → el servidor se apaga solo. Latido del frontend cada 10 s solo si `packaged`.
- Puertos 47900–47919; mutex `Local\POKKER`; zip `POKKER-X.Y.Z.zip` + `POKKER-X.Y.Z.zip.sha256`; feed por defecto `https://api.github.com/repos/jcolman940/POKKER_LEARNING/releases/latest`.
- Actualización: descarga solo desde `https://github.com/jcolman940/POKKER_LEARNING/releases/download/...` y las redirecciones de GitHub (`objects.githubusercontent.com`, `release-assets.githubusercontent.com`); la única excepción es `--permitir-feed-local` (solo pruebas, acepta `http://127.0.0.1`); SHA-256 obligatorio; renombres atómicos `app`/`app.nuevo`/`app.viejo`; truco `POKKER.exe.viejo`; cualquier falla → vuelta atrás completa y abrir la versión anterior.
- TexasSolver: URL `https://github.com/bupticybee/TexasSolver/releases/download/v0.2.0/TexasSolver-v0.2.0-Windows.zip`, SHA-256 `0A9122FA0CD9384E6C1CBE0492E8A3B8AC7809890C649E1A53F77A59D6D50A7C`; nunca dentro del zip de POKKER (AGPL).
- C#: compatible con el `csc.exe` de .NET Framework (`C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe`, C# 5: sin interpolación `$""`, sin `?.`, sin `nameof`); TLS 1.2 explícito (`ServicePointManager.SecurityProtocol = (SecurityProtocolType)3072`); JSON con `System.Web.Script.Serialization.JavaScriptSerializer` (`System.Web.Extensions.dll`); zip con `System.IO.Compression.ZipFile` (`System.IO.Compression.dll` + `System.IO.Compression.FileSystem.dll`).
- Mensajes al usuario en español (voseo); código y comentarios en inglés. Python: ruff (100, `E,F,I,UP,B`) + format. Frontend: tsc, oxlint, vitest.
- Commits con la identidad configurada y el trailer `Co-Authored-By` del modelo que escribe el commit.

---

### Task 1: Rutas de recursos para el modo empaquetado

**Files:** Modify `backend/app/config.py`, `backend/app/recommend/preflop_equity.py`, `backend/app/db/session.py`. Test `backend/tests/test_packaging_paths.py`.

**Interfaces:**
- `Settings.resources_dir: Path` (env `POKER_RESOURCES_DIR`; default `REPO_ROOT`); `ranges_dir`, `spots_dir`, `solver_trees_file`, `solver_library_file` pasan a **propiedades** derivadas de `resources_dir` salvo que se definan explícitamente por env (mantener compatibilidad: si hoy existen como campos con env propio, conservar el override: campo `Path | None = None` + propiedad `resolved_*`; actualizar todos los usos con grep).
- `Settings.precomputed_dir` → `resources_dir / "data" / "precomputed"`; `preflop_equity.MATRIX_PATH` se resuelve en tiempo de carga desde `get_settings()` (función `matrix_path()`), no al importar.
- `read_app_version()` lee `resources_dir / "VERSION"` (con env `POKER_RESOURCES_DIR` si está) — sigue respetando `POKER_APP_VERSION`.
- `session.py`: `BACKEND_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))` para ubicar `alembic.ini` y `alembic/` dentro del paquete de PyInstaller.

- [ ] **Step 1:** Tests: con `POKER_RESOURCES_DIR=tmp` (que contiene `VERSION` = `9.9.9`, `data/solver/trees.json`, `data/precomputed/preflop_equity_169.npy` copiado del repo) → `get_settings().app_version == "9.9.9"`, las rutas derivadas apuntan a `tmp/data/...`, `load_presets()` lee ese trees.json, y la matriz de equity se carga desde ahí; sin la variable, todo apunta al repo (regresión). Limpiar los `lru_cache` (`get_settings`, presets, matriz) en el fixture.
- [ ] **Step 2:** RED. **Step 3:** implementar. **Step 4:** GREEN + suite completa + ruff.
- [ ] **Step 5:** Commit `feat(config): resource paths overridable for the packaged app`.

---

### Task 2: Modo empaquetado del servidor

**Files:** Create `backend/app/packaged.py` (estado, vigilante, middleware de Host), `backend/app/api/app_control.py` (router `/api/app`), `backend/app/server_main.py` (entrada del ejecutable). Modify `backend/app/main.py`, `backend/app/api/system.py`, `backend/app/config.py`. Test `backend/tests/test_packaged_mode.py`.

**Interfaces:**
- Settings: `web_dir: Path | None` (`POKER_WEB_DIR`), `launch_token: str | None` (`POKER_LAUNCH_TOKEN`), `host: str = "127.0.0.1"`, `port: int = 8000`, `heartbeat_timeout_s: float = 60`; propiedad `packaged = launch_token is not None`.
- `/api/version` agrega `packaged: bool`.
- Router `/api/app` (solo se registra si `packaged`): `POST /ping` → 204; `POST /shutdown` con `X-Pokker-Token` → 202 y apagado ordenado (403 si falta/no coincide); `GET /status` → `{packaged, heartbeat_age_s: float|null, solver_busy: bool, solver_pending: int}` (busy = hay un `running`; pending = `queued` no pausada).
- `packaged.Heartbeat`: `beat()`, `age()`; `Watchdog(check_every=5)` en un thread que llama a `request_shutdown()` si `age() > timeout` y no hay trabajo del solver. `request_shutdown()` dispara el apagado de uvicorn (el `server_main` registra un callback que pone `server.should_exit = True`).
- Middleware de Host (solo `packaged`): permitir `127.0.0.1`, `localhost`, con o sin `:port`; si no, 400 `{"detail": "Host no permitido"}`.
- Web: si `web_dir`, montar `StaticFiles(directory=web_dir, html=True)` en `/` **después** de los routers de `/api`, con un handler 404 que para rutas no-`/api` sin extensión de archivo devuelve `index.html`.
- `server_main.main()`: `uvicorn.Server(Config(create_app(), host=settings.host, port=settings.port, log_config=None, access_log=False))`; registra el callback de apagado; `run()`. Rechaza `host` distinto de `127.0.0.1` (sale con código 2).

- [ ] **Step 1:** Tests (TestClient con env `POKER_LAUNCH_TOKEN=t`, `POKER_WEB_DIR=tmp` con `index.html` y `assets/a.js`): `/` y `/simulador` sirven index.html; `/assets/a.js` sirve el archivo; `/api/version` sigue siendo JSON con `packaged: true`; `/api/nada` → 404 JSON (no index); Host `evil.com` → 400; `127.0.0.1:47900` → 200; ping 204; shutdown sin token 403, con token 202 y el callback se llamó; status refleja jobs `running`/`queued` y pausa; Watchdog con timeout chico: no apaga antes del primer latido, no apaga con solver ocupado, apaga después del timeout sin trabajo. Sin `POKER_LAUNCH_TOKEN`: `/api/app/*` → 404 y no hay middleware de Host (regresión del modo desarrollo).
- [ ] **Step 2:** RED. **Step 3:** implementar. **Step 4:** GREEN + suite + ruff.
- [ ] **Step 5:** Commit `feat(app): packaged mode (single port web, host check, heartbeat, shutdown)`.

---

### Task 3: Instalación de TexasSolver desde la app

**Files:** Create `backend/app/solver/install.py`. Modify `backend/app/api/solver.py`, `backend/app/solver/worker_registry.py`, `backend/app/config.py`. Test `backend/tests/test_solver_install.py`.

**Interfaces:**
- Constantes: `TEXASSOLVER_URL`, `TEXASSOLVER_SHA256` (Global Constraints), `TOOLS_SUBDIR = "tools/TexasSolver"`, `EXE_RELATIVE = "TexasSolver-v0.2.0-Windows/console_solver.exe"`.
- `detected_solver_path(settings) -> Path | None`: `settings.solver_path` si existe; si no `data_dir / TOOLS_SUBDIR / EXE_RELATIVE` si existe. `worker_registry.solver_available()`/`start_worker()` usan esta función.
- `Installer` (singleton por proceso, thread de fondo): `start(url=TEXASSOLVER_URL, sha256=TEXASSOLVER_SHA256) -> InstallStatus`; `status() -> InstallStatus(state, bytes, total, error)` con `state ∈ {idle, downloading, verifying, extracting, done, error}`. Descarga con `urllib.request` a `data_dir/tools/.tmp/…`, verifica hash (mayúsculas/minúsculas indistintas), descomprime en `tools/.tmp/extract`, renombra a `tools/TexasSolver` (borrando una instalación vieja), limpia temporales; al terminar llama `start_worker()`. Errores en español: "No se pudo descargar TexasSolver (sin conexión o GitHub no respondió).", "La descarga no coincide con el archivo oficial (hash distinto); no se instaló.", "No se pudo descomprimir TexasSolver: …". Un segundo `start` mientras corre devuelve el estado actual.
- API: `POST /api/solver/install` → 202 + estado; `GET /api/solver/install` → estado. `GET /api/solver/status` usa la ruta detectada.
- Los tests inyectan URL y hash (parámetros de `start`) y sirven un zip de prueba con `http.server` en un thread local.

- [ ] **Step 1:** Tests: zip válido (contiene `TexasSolver-v0.2.0-Windows/console_solver.exe` falso) → `done`, archivo en su lugar, `detected_solver_path` lo encuentra, `solver_available()` true; hash incorrecto → `error` y nada en `tools/TexasSolver`; servidor caído → `error`; detección con `POKER_SOLVER_PATH` tiene prioridad.
- [ ] **Step 2–4:** RED, implementar, GREEN + suite + ruff.
- [ ] **Step 5:** Commit `feat(solver): download and install TexasSolver from the app`.

---

### Task 4: Frontend — latido y descarga del solver

**Files:** Create `frontend/src/app/heartbeat.ts`. Modify `frontend/src/App.tsx`, `frontend/src/api/client.ts` (`VersionInfo.packaged`), `frontend/src/solver/SettingsPanel.tsx`, `frontend/src/solver/api.ts`, tests.

**Interfaces:** `startHeartbeat(intervalMs = 10000): () => void` (POST `/api/app/ping`; errores ignorados); `App` lo inicia solo si `version.packaged` y lo limpia al desmontar. SettingsPanel: si el solver no está configurado, botón **"Descargar TexasSolver (39 MB)"** con la nota "Programa de otro autor (licencia AGPL); se baja de su página oficial." → `POST /api/solver/install`, polling de `GET /api/solver/install` cada 1 s con barra de progreso (bytes/total), mensaje de error si `error`, y al `done` refrescar el estado ("Solver listo").

- [ ] **Step 1:** Tests (vitest, fake timers): latido solo con `packaged: true` y se detiene al desmontar; botón visible sin solver, progreso, error mostrado, éxito refresca el estado.
- [ ] **Step 2–4:** RED, implementar, GREEN (`npm test`, `typecheck`, `lint`).
- [ ] **Step 5:** Commit `feat(ui): heartbeat in packaged mode and TexasSolver download`.

---

### Task 5: Lanzador — arranque, servidor, ícono y cierre

**Files:** Create `launcher/POKKER.cs`, `launcher/pokker.ico` (ícono simple generado: fondo verde oscuro con "P", 16/32/48 px), `launcher/build.ps1` (compila con `csc.exe`). Test manual + diagnóstico (Task 8 lo automatiza).

**Interfaces / comportamiento:** exactamente §3 del spec. Estructura sugerida en un archivo (clases `Program`, `Paths`, `ServerProcess`, `Tray`, `Diagnostics`, `Log`), C# 5. Puntos críticos:
- Rutas: `Root` = carpeta del exe; `AppDir = Root\app`; `DataDir` = `--datos=` o `%LOCALAPPDATA%\POKKER`.
- Instancia única con `Mutex("Local\\POKKER")`; si no es el primero: leer `running.json` (`{"port":…, "pid":…}`), verificar que el PID vive, abrir `http://127.0.0.1:<port>/`, salir 0.
- Limpieza de `.viejo` en thread de fondo (20 reintentos × 500 ms).
- Puerto: `TcpListener(IPAddress.Loopback, p)` start/stop para probar 47900–47919.
- Servidor: `ProcessStartInfo(AppDir\server\pokker-server.exe)` con `UseShellExecute=false`, `CreateNoWindow=true`, `RedirectStandardOutput/Error` → append a `pokker.log` (rotación: si > 5 MB al arrancar, renombrar a `pokker.1.log`), variables de entorno del §3.1. Espera `GET /api/version` (WebClient, timeout 2 s, reintento cada 500 ms, total 60 s).
- Ícono (`NotifyIcon`) con menú del spec; tooltip actualizado cada 15 s con `GET /api/app/status` (`"POKKER · resolviendo N spots"` si `solver_busy || solver_pending>0`, si no `"POKKER"`).
- Cierre: diálogo si el solver trabaja; `POST /api/app/shutdown` con el token; esperar 10 s; si sigue vivo `taskkill /T /F /PID`. Si el servidor muere solo, borrar `running.json`, ocultar ícono, salir.
- `--diagnostico=<archivo>`: JSON con `version`, `faltantes` (lista), `data_dir`, `app_escribible` (bool, probando crear y borrar un archivo en `Root`); sin UI; código 0.
- `--sin-navegador`, `--sin-actualizar`, `--actualizado=X` (globito), `--datos=<carpeta>`.
- Todos los carteles con `MessageBox` en español; el log registra cada paso con hora.
- `launcher/build.ps1 [-Out <dir>]`: compila con `csc.exe /nologo /target:winexe /win32icon:launcher\pokker.ico /r:System.Windows.Forms.dll /r:System.Drawing.dll /r:System.Web.Extensions.dll /r:System.IO.Compression.dll /r:System.IO.Compression.FileSystem.dll /out:<Out>\POKKER.exe launcher\POKKER.cs`; falla si el compilador devuelve error.

- [ ] **Step 1:** Compilar con `launcher\build.ps1` sin warnings que indiquen errores.
- [ ] **Step 2:** Prueba manual guiada (en el reporte): carpeta temporal con `POKKER.exe` y un `app\` mínimo cuyo `server\pokker-server.exe` aún no existe → `--diagnostico` lista el faltante; (el humo real con servidor se hace en Task 7).
- [ ] **Step 3:** Commit `feat(launcher): startup, server lifecycle, tray and diagnostics`.

---

### Task 6: Lanzador — actualización

**Files:** Modify `launcher/POKKER.cs` (clases `Updater`, `UpdateDialog`, `ProgressDialog`).

**Interfaces / comportamiento:** exactamente §4 del spec. Puntos críticos:
- Feed: `app\update.json` → `feed`; `HttpWebRequest` con `User-Agent: POKKER/<ver>`, `Accept: application/vnd.github+json`, timeout 8 s; parsear `tag_name`, `body`, `html_url`, `assets[].name/browser_download_url/size`.
- Versión: `X.Y.Z` (ignorar prefijo `v` y sufijos `-algo` comparando solo números; una prerelease nunca llega porque `latest` las excluye).
- `launcher.json` `{"skipped": "0.7.0"}`.
- URLs permitidas (Global Constraints), validando también tras redirecciones (`HttpWebResponse.ResponseUri.Host` ∈ {`github.com`, `objects.githubusercontent.com`, `release-assets.githubusercontent.com`}).
- Aplicación paso a paso del §4.3, con un objeto `Rollback` que registra cada paso hecho y lo deshace en orden inverso ante excepción. Escribir primero un archivo de prueba en `Root` para detectar falta de permisos.
- Copia de la base: `poker.sqlite3`, `-wal`, `-shm` a `datos.anterior\` (sobrescribe la copia anterior).
- `ProgressDialog` con barra, bytes y Cancelar (cancelar = rollback sin cartel de error).
- "Buscar actualizaciones" desde el ícono: si hay novedad y el usuario acepta → (si solver ocupado, confirmar) → apagar servidor → aplicar → relanzar `POKKER.exe` (nuevo o actual) con `--actualizado=X` → salir.
- `--actualizar-sin-preguntar` aplica sin cartel (pruebas).
- `--permitir-feed-local` (solo pruebas): acepta feed y descargas desde `http://127.0.0.1:<puerto>`; sin esta opción, cualquier host fuera de la lista se rechaza y se registra en el log.

- [ ] **Step 1:** Compilar. **Step 2:** prueba manual con un feed local (se automatiza en Task 8). **Step 3:** Commit `feat(launcher): GitHub Releases updater with atomic swap and rollback`.

---

### Task 7: Armado del paquete (PyInstaller + package.ps1)

**Files:** Create `backend/pokker-server.spec`, `scripts/package.ps1`, `backend/pyinstaller_hooks/` si hace falta. Modify `backend/pyproject.toml` (grupo `package = ["pyinstaller>=6"]`), `.gitignore` (`dist/`, `build/`).

**Interfaces:**
- `pokker-server.spec` (onedir, consola oculta no aplica: es un exe de consola lanzado sin ventana): entrada `app/server_main.py`; `datas`: `alembic.ini`, `alembic/` (en la raíz de `_internal` para que `BACKEND_ROOT` de Task 1 los encuentre); `hiddenimports`: `uvicorn.logging`, `uvicorn.loops.auto`, `uvicorn.protocols.http.auto`, `uvicorn.protocols.websockets.auto`, `uvicorn.lifespan.on`, módulos de `app.*` cargados dinámicamente (alembic env), `pokercore`; nombre `pokker-server`.
- `scripts\package.ps1 [-Version <x>] [-SkipTests]`: (1) compila el núcleo (como `test.ps1 core`, Release); (2) `uv sync --group package` y `uv run pyinstaller --noconfirm --distpath build\server pokker-server.spec`; (3) `npm ci && npm run build` en frontend; (4) `launcher\build.ps1 -Out build\launcher`; (5) arma `dist\POKKER\` (`POKKER.exe`, `app\VERSION`, `app\update.json` con el feed por defecto, `app\server\` = salida de PyInstaller, `app\web\` = `frontend\dist`, `app\data\` = `data\` del repo **sin** rangos externos: solo `data\ranges\empty.json` y README, `data\solver\`, `data\precomputed\`, `data\spots\`); (6) prueba de humo (§5.2 del spec) con `--datos` temporal y puerto real; (7) `Compress-Archive` → `dist\POKKER-<ver>.zip` y `.sha256` (hash en mayúsculas, solo el hash). Falla con mensaje claro en cualquier paso.

- [ ] **Step 1:** `scripts\package.ps1` completo en esta PC (MSVC dev shell + uv en PATH) → zip generado, humo OK; registrar tamaño del zip y tiempo de arranque.
- [ ] **Step 2:** Verificar a mano: descomprimir el zip en una carpeta temporal fuera del repo, abrir `POKKER.exe`, navegar Simulador/Entrenador, cerrar desde el ícono; ningún proceso `pokker-server` queda vivo.
- [ ] **Step 3:** Commit `build: PyInstaller server and package script for the portable zip`.

---

### Task 8: Pruebas automáticas del lanzador y CI/releases

**Files:** Create `tests/launcher/conftest.py`, `tests/launcher/test_launcher.py` (marca `launcher`), `.github/workflows/release.yml`. Modify `.github/workflows/ci.yml`, `scripts/test.ps1` (target `launcher`: corre `tests/launcher` contra `dist\POKKER` si existe), `backend/pyproject.toml` (marker `launcher`).

**Interfaces:**
- Arnés: copia `dist\POKKER` a `tmp/v1`; arma un paquete "nuevo" copiando `dist\POKKER` con `app\VERSION` = `9.9.9` y lo comprime como `POKKER-9.9.9.zip` + `.sha256`; levanta un servidor HTTP local que sirve `/releases/latest` (JSON con `tag_name: v9.9.9`, `body`, assets apuntando al mismo servidor) y los archivos. **Para las pruebas**, `update.json` de `tmp/v1` apunta al feed local y el lanzador acepta hosts `127.0.0.1` **solo** si arrancó con `--permitir-feed-local` (opción de pruebas; documentarla).
- Casos: actualizar con `--actualizar-sin-preguntar --sin-navegador --datos=<tmp>` → `app\VERSION` = 9.9.9, existe `datos.anterior\` si había base, `pokker.log` registra la actualización, se apagó todo; hash incorrecto → `app\VERSION` sigue 0.7.0, no quedan `app.nuevo`/`app.viejo`; carpeta de solo lectura (ACL de denegar escritura con `icacls` en `tmp/v1`) → log "No puedo actualizar" y versión vieja (si `icacls` no es posible en CI, saltear con razón); segunda instancia → no levanta otro servidor; `--diagnostico` sin faltantes.
- Las pruebas siempre terminan los procesos (`taskkill /T /F`) en el teardown.
- `ci.yml`: después de los tests actuales, `scripts\package.ps1 -SkipTests` y `scripts\test.ps1 launcher`; subir `dist\POKKER-*.zip` como artifact.
- `release.yml` (`on: push: tags: ['v*']`, `permissions: contents: write`): checkout; verificar `v$(Get-Content VERSION)` = tag; extraer la sección `## [X.Y.Z]` de `CHANGELOG.md` (falla si no existe); mismos pasos que CI (tests + package + launcher tests); `gh release create $tag dist\POKKER-X.Y.Z.zip dist\POKKER-X.Y.Z.zip.sha256 --title "POKKER X.Y.Z" --notes-file <sección>` con `GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}`.

- [ ] **Step 1:** Tests del arnés; correrlos localmente contra el `dist` de Task 7 (RED si falta algo del lanzador → arreglar en el lanzador). **Step 2:** GREEN. **Step 3:** validar YAML. **Step 4:** Commit `test(launcher): end-to-end update tests; ci: package and release workflows`.

---

### Task 9: Versión, changelog, README y cierre

**Files:** Modify `VERSION` (`0.7.0`), `README.md`. Create `CHANGELOG.md`.

- [ ] **Step 1:** `CHANGELOG.md` en español ("Keep a Changelog"): `## [0.7.0] - 2026-10-07` (escritorio, actualizaciones, descarga del solver) y un resumen de 0.1.0–0.6.x (fases 0–6) agrupado por fase.
- [ ] **Step 2:** README: sección "Instalar y actualizar POKKER (para tus amigos)": bajar el zip de Releases, descomprimir en Documentos, doble clic, SmartScreen ("Más información → Ejecutar de todas formas", sin firma), dónde quedan los datos, cómo funciona el cartel de actualización, cómo volver atrás a mano con `datos.anterior\`, descarga de TexasSolver. Sección para el desarrollador: `scripts\package.ps1`, cómo publicar (subir `VERSION` + `CHANGELOG.md`, `git tag vX.Y.Z && git push origin vX.Y.Z`). Tabla de configuración: `POKER_RESOURCES_DIR`, `POKER_WEB_DIR`, `POKER_LAUNCH_TOKEN`, `POKER_HOST`, `POKER_PORT`.
- [ ] **Step 3:** `scripts\test.ps1` completo + `scripts\package.ps1` + `scripts\test.ps1 launcher` en verde.
- [ ] **Step 4:** Commit `docs: phase 7 desktop packaging and updates; version 0.7.0`. Sin push ni tag (decide el usuario).
- [ ] **Step 5:** Verificación manual del controlador (descomprimir, abrir, entrenador, bajar TexasSolver y resolver un river, actualización simulada) y cierre de fase.
