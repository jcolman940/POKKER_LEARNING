# Fase 7 — Empaquetado de escritorio y actualizaciones: diseño

Fecha: 2026-10-07 · Estado: aprobado por secciones, pendiente de revisión del documento.
Referencia: `SPEC.md` §6.9 y §7 (fase 7). Inspiración: lanzador de NewCampus (`Frann7/NewCampus`, `app/lanzador/NewCampus.cs`).

## 1. Objetivo y decisiones

- Que los amigos del usuario usen POKKER sin herramientas de desarrollo y reciban las versiones nuevas con un cartel de novedades al abrir.
- **Lanzador liviano** en C# (.NET Framework 4, `csc.exe`), ícono en la bandeja, la app se usa en el navegador predeterminado. Reemplaza la opción Tauri/Electron que dejaba abierta el SPEC.
- **Backend congelado con PyInstaller** (modo carpeta) que sirve también el frontend compilado: un solo puerto.
- **Distribución:** zip portátil (sin instalador ni permisos de administrador).
- **Actualizaciones por GitHub Releases** del repo público `jcolman940/POKKER_LEARNING`. Se publica con un **tag de versión**; lo que no tiene tag no les llega a los amigos.
- **TexasSolver** no va en el paquete (AGPL): la app ofrece bajarlo de su release oficial con verificación de hash.
- Lo que se copia de NewCampus: datos fuera de la carpeta de la app, cartel con novedades y Sí/No, globito después de actualizar, nunca dejar nada a medias, truco del `.exe.viejo`, una sola instancia, apagado al cerrar la pestaña, diagnóstico de piezas faltantes. Lo que no: actualizar con `git pull` (exigiría MSVC, Python, uv y Node en cada PC, y cada commit sería una actualización).

Fuera de alcance: firma de código (Authenticode) y firma de las releases; instalador; macOS/Linux empaquetados; volver atrás de versión automáticamente.

## 2. Estructura del paquete y datos

### 2.1 Zip de la release (`POKKER-X.Y.Z.zip`)

```
POKKER\
  POKKER.exe              lanzador
  app\                    se reemplaza entera en cada actualización
    VERSION
    update.json           {"feed": "https://api.github.com/repos/jcolman940/POKKER_LEARNING/releases/latest"}
    server\pokker-server.exe (+ _internal\ de PyInstaller, incluye pokercore)
    web\                  frontend compilado (Vite build)
    data\                 recursos: ranges (vacío/ejemplo), solver\trees.json, solver\library.json, precomputed\
```

### 2.2 Datos del usuario: `%LOCALAPPDATA%\POKKER\`

`poker.sqlite3`; `solver\jobs\`; `tools\TexasSolver\`; `pokker.log` (lanzador + servidor, rota a 5 MB, se conservan 2); `datos.anterior\` (copia de la base antes de cada actualización); `launcher.json` (versión salteada); `running.json` (puerto y PID de la instancia abierta); `updates\` (descargas temporales). Una actualización nunca toca esta carpeta salvo `updates\` y `datos.anterior\`.

### 2.3 Cambios en el backend (sin romper el modo desarrollo)

- `config.py`: `POKER_RESOURCES_DIR` (raíz de `data\` y `VERSION`; por defecto el repo, como hoy) y `POKER_WEB_DIR` (frontend compilado; por defecto `None`). `ranges_dir`, `spots_dir`, `solver_trees_file`, `solver_library_file`, precomputados y la lectura de `VERSION` se derivan de `POKER_RESOURCES_DIR`.
- Ejecutable del servidor (`app/server_main.py`, entrada de PyInstaller): lee `POKER_HOST` (solo `127.0.0.1`) y `POKER_PORT`, arranca uvicorn sin reload.
- Con `POKER_WEB_DIR`: FastAPI sirve el frontend en `/` (archivos estáticos con vuelta a `index.html` para rutas que no son archivos) y la API sigue en `/api`.
- Middleware de **Host**: rechaza (400) pedidos cuyo `Host` no sea `127.0.0.1[:puerto]` o `localhost[:puerto]` cuando corre empaquetado (`POKER_LAUNCH_TOKEN` definido).
- **Latido y apagado** (solo empaquetado): `POST /api/app/ping` (sin cuerpo); `POST /api/app/shutdown` con encabezado `X-Pokker-Token` = `POKER_LAUNCH_TOKEN` (403 si no coincide). Vigilante: tras el primer latido, si pasan 60 s sin latidos **y** el solver no tiene trabajos corriendo o en cola (o la cola está pausada), el servidor se apaga solo. `GET /api/app/status` → `{packaged, heartbeat_age_s, solver_busy, solver_pending}` para el ícono.
- El frontend manda el latido cada 10 s solo si `GET /api/version` indica `packaged: true`.
- Detección de TexasSolver: `POKER_SOLVER_PATH` si está; si no, `<data_dir>\tools\TexasSolver\TexasSolver-v0.2.0-Windows\console_solver.exe` si existe.
- El modo desarrollo (`scripts\dev.ps1`, `./var`, Vite en :5173) y los tests no cambian.

## 3. Lanzador (`launcher/POKKER.cs`)

### 3.1 Arranque

1. Mutex `Local\POKKER`. Si ya hay una instancia: leer `running.json`, abrir el navegador en su dirección y salir.
2. Borrar `POKKER.exe.viejo` y `app.viejo` (en segundo plano, con reintentos).
3. Actualización (§4), salvo `--sin-actualizar` o sin internet.
4. Revisión de piezas: `app\VERSION`, `app\server\pokker-server.exe`, `app\web\index.html`, `app\update.json`. Si falta algo: un cartel "Falta X: volvé a bajar POKKER desde la página de releases" con el link, y salir.
5. Puerto: primero libre en `127.0.0.1` entre 47900 y 47919 (si ninguno, cartel).
6. Lanzar el servidor sin ventana con: `POKER_DATA_DIR`, `POKER_RESOURCES_DIR=app`, `POKER_WEB_DIR=app\web`, `POKER_HOST`, `POKER_PORT`, `POKER_LAUNCH_TOKEN` (32 bytes al azar en hex), `POKER_UPDATE_FEED_URL` (de `update.json`), `POKER_SOLVER_PATH` si el solver está en `tools\`. Salida y errores → `pokker.log`.
7. Esperar `GET /api/version` hasta 60 s (globito "Abriendo POKKER…"); si no responde: cartel con las últimas 20 líneas del log y matar el árbol del servidor.
8. Escribir `running.json`, abrir el navegador en `http://127.0.0.1:<puerto>/` (salvo `--sin-navegador`), mostrar el ícono con menú: **Abrir POKKER** · **Buscar actualizaciones** · **Abrir carpeta de datos** · **Cerrar POKKER**. Si arrancó con `--actualizado=X`, globito "POKKER se actualizó a X".

### 3.2 Durante la sesión y cierre

- Cada 15 s consulta `GET /api/app/status`: tooltip del ícono "POKKER · resolviendo N spots" si el solver trabaja.
- Si el proceso del servidor termina (apagado por latido o error), el lanzador borra `running.json`, quita el ícono y sale.
- **Cerrar POKKER:** si el solver está trabajando, pregunta ("Hay N spots en cola; se retoman la próxima vez"); luego `POST /api/app/shutdown` con la clave; si en 10 s no terminó, `taskkill /T /F`.

### 3.3 Diagnóstico y opciones

- `--diagnostico=<archivo>`: escribe en JSON la versión, piezas encontradas/faltantes, carpeta de datos y si la carpeta de la app es escribible; no abre nada.
- `--sin-actualizar`, `--sin-navegador`, `--actualizado=<versión>`, `--actualizar-sin-preguntar` (solo pruebas), `--datos=<carpeta>` (solo pruebas: otra carpeta de datos).
- Seguridad: solo `127.0.0.1`; no toca el registro ni pide administrador; el token de apagado viaja solo por variable de entorno al hijo y por encabezado.

## 4. Actualización

### 4.1 Consulta

- `GET <feed>` (de `app\update.json`), `User-Agent: POKKER/<versión>`, 8 s de tope. Se usa `tag_name` (`vX.Y.Z`), `body` (novedades), `html_url` y los assets `POKKER-X.Y.Z.zip` y `POKKER-X.Y.Z.zip.sha256`.
- Comparación semántica con `app\VERSION`. Sin novedad, sin internet, respuesta inválida o assets faltantes → seguir sin avisar (se registra en el log).
- Si el usuario salteó esa versión (`launcher.json`), no se pregunta.

### 4.2 Cartel

Ventana propia (WinForms): "Hay una versión nueva de POKKER: X (tenés Y)", novedades en un cuadro con scroll, tamaño de la descarga, link "Ver todas las versiones" (`html_url` del repo de releases), botones **Actualizar ahora** · **Ahora no** · **Saltear esta versión**.

### 4.3 Aplicación

1. Descargar el zip a `updates\` con barra de progreso y botón Cancelar. Solo se aceptan URLs `https://github.com/<owner>/<repo>/releases/download/...` u `https://objects.githubusercontent.com/...` (redirecciones de GitHub). Descargar el `.sha256` y verificar.
2. Descomprimir en `POKKER\app.nuevo`; validar que trae `app\…` completo y que `VERSION` = tag.
3. Copiar `poker.sqlite3` (y `-wal`/`-shm` si existen) a `datos.anterior\` (el servidor aún no corre).
4. Renombrar `app` → `app.viejo`, `app.nuevo` → `app`.
5. Si el `POKKER.exe` del zip difiere (SHA-256) del actual: renombrar el actual a `POKKER.exe.viejo`, copiar el nuevo, lanzar el nuevo con `--sin-actualizar --actualizado=X` y salir. Si no difiere: seguir el arranque con `--actualizado=X`.
6. Cualquier falla: deshacer renombres, borrar `app.nuevo` y la descarga, cartel con el motivo, seguir con la versión que había.
- Carpeta sin escritura: cartel "No puedo actualizar en esta carpeta: mové POKKER a Documentos (u otra carpeta tuya)" y seguir con la versión actual.
- **Buscar actualizaciones** desde el ícono con POKKER abierto: si hay versión nueva, cartel; con Sí, preguntar por el solver si trabaja, apagar el servidor, aplicar y reabrir.
- Las migraciones de la base las corre la versión nueva al arrancar (como hoy). Volver atrás es manual (README: bajar el zip anterior y restaurar `datos.anterior\`).
- Limitación: el hash protege de descargas corruptas, no de una cuenta comprometida (sin firma).

## 5. CI y releases

### 5.1 Repo

`https://github.com/jcolman940/POKKER_LEARNING` (público). El feed por defecto en `update.json` usa ese owner/repo.

### 5.2 Armado

- `scripts\package.ps1 [-Version X]`: compila el núcleo (MSVC), instala dependencias del backend (con PyInstaller como dependencia de desarrollo), corre PyInstaller con `backend\pokker-server.spec` (modo carpeta, incluye `pokercore` y los datos de Alembic), `npm ci && npm run build`, compila el lanzador con `csc.exe` (`/target:winexe`, ícono, `System.Windows.Forms`, `System.Drawing`, `System.IO.Compression`, `System.IO.Compression.FileSystem`), arma `dist\POKKER\`, corre la prueba de humo y genera `dist\POKKER-X.Y.Z.zip` + `.sha256`.
- Prueba de humo: `POKKER.exe --diagnostico=…` sin faltantes; luego `POKKER.exe --sin-navegador --sin-actualizar --datos=<temp>` levanta el servidor, `/api/version` responde con `packaged: true`, `/` sirve `index.html`, y el apagado con la clave termina todos los procesos.
- `ci.yml`: en cada push, además de lo actual, un paso que corre `package.ps1` (armado + humo, sin publicar).

### 5.3 Publicación (`release.yml`, tag `v*`)

Verifica tag = `VERSION` y que `CHANGELOG.md` tenga la sección `## [X.Y.Z]`; corre todos los tests; `package.ps1`; crea la release con `gh release create vX.Y.Z` usando el `GITHUB_TOKEN` del workflow (permiso `contents: write`), cuerpo = esa sección del changelog, assets = zip y `.sha256`.

### 5.4 Versión y changelog

`VERSION` pasa a `0.7.0`; se crea `CHANGELOG.md` (formato "Keep a Changelog" en español) con un resumen de las fases 0–7. La primera release la publica el usuario empujando el tag `v0.7.0`.

## 6. TexasSolver desde la app

- Solver → Configuración: botón **"Descargar TexasSolver (39 MB)"** con la nota "Programa de otro autor (AGPL), se baja de su página oficial".
- `POST /api/solver/install` inicia la descarga en segundo plano de `https://github.com/bupticybee/TexasSolver/releases/download/v0.2.0/TexasSolver-v0.2.0-Windows.zip`; `GET /api/solver/install` → `{state: idle|downloading|verifying|extracting|done|error, bytes, total, error}`.
- Verifica SHA-256 `0A9122FA0CD9384E6C1CBE0492E8A3B8AC7809890C649E1A53F77A59D6D50A7C`; descomprime en `<data_dir>\tools\TexasSolver\` vía carpeta temporal y renombre (nunca a medias); arranca el worker sin reiniciar (`start_worker()` con la ruta detectada).
- Errores (sin internet, hash distinto, disco): estado `error` con mensaje en español; se borra lo parcial.
- La URL y el hash son constantes del backend (no configurables desde la UI).

## 7. Tests

- **Backend (pytest):** rutas desde `POKER_RESOURCES_DIR`/`POKER_WEB_DIR`; frontend servido con vuelta a `index.html` sin pisar `/api`; middleware de Host; latido, apagado con clave correcta/incorrecta, vigilante que no apaga con el solver trabajando ni antes del primer latido; `/api/app/status`; instalación del solver contra un servidor HTTP local de prueba (zip válido, hash incorrecto, corte) y detección automática de la ruta; `packaged` en `/api/version`.
- **Lanzador (pytest, marca `launcher`, solo Windows con el paquete armado):** arnés en Python que arma un feed local (servidor HTTP en 127.0.0.1 con un JSON de release y un zip "nuevo"), apunta `update.json` a él y verifica: actualizar sin preguntar reemplaza `app\` y `POKKER.exe`, deja `datos.anterior\` y arranca con `--actualizado`; hash incorrecto → vuelta atrás completa; carpeta sin escritura → mensaje en el log y versión vieja; segunda instancia no levanta otra; humo y diagnóstico.
- **Frontend (vitest):** botón de descarga del solver (progreso, error, éxito); latido solo cuando `packaged`.
- **Manual:** `package.ps1`, descomprimir en otra carpeta, abrir, usar el entrenador, bajar TexasSolver y resolver un spot de river, simular una actualización con el feed local.

## 8. Cierre de fase

`VERSION` 0.7.0, `CHANGELOG.md`, README con "Instalar y actualizar POKKER" para los amigos. Parar, resumir y esperar confirmación (SPEC §8). La publicación del tag es decisión del usuario.
