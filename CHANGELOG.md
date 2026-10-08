# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [0.7.0] - 2026-10-07

### Agregado
- Paquete de escritorio para Windows: `POKKER-X.Y.Z.zip` con `POKKER.exe` (launcher), backend y frontend incluidos; no hace falta instalar Python ni Node.
- Launcher con ícono en la bandeja (Abrir POKKER, Buscar actualizaciones, Abrir carpeta de datos, Cerrar POKKER); se apaga solo unos 3 minutos después de cerrar la pestaña, salvo que el solver esté trabajando (tolera la suspensión de la PC y la pestaña avisa si POKKER ya se cerró).
- Actualizaciones automáticas desde GitHub Releases: cartel con las notas de la versión, descarga con verificación SHA-256, reemplazo atómico y vuelta atrás ante cualquier falla. Copia de seguridad de los datos en `datos.anterior\`.
- Descarga de TexasSolver desde Solver → Configuración (binario oficial, hash verificado, sin reiniciar).
- Modo empaquetado del backend (`POKER_RESOURCES_DIR`, `POKER_WEB_DIR`, `POKER_LAUNCH_TOKEN`, `POKER_HOST`, `POKER_PORT`).
- `scripts\package.ps1`, `scripts\test.ps1 launcher`, workflows `ci.yml` y `release.yml`.

## [0.6.0] - fase 6
- Entrenador de spots (preflop, push/fold, postflop) con feedback de EV y leak finder.

## [0.5.0] - fase 5
- Solver postflop (TexasSolver como proceso externo), cola de trabajos, heurística multiway y recomendación postflop.

## [0.4.0] - fase 4
- Importador de historiales, estadísticas (VPIP, PFR, 3-bet, etc.) y replayer de manos.

## [0.3.0] - fase 3
- Recomendación preflop con rangos y push/fold.

## [0.2.0] - fase 2
- Simulador de equity/EV y API `/api/simulator`.

## [0.1.0] - fases 0 y 1
- Estructura del repo, núcleo C++ (`pokercore`: evaluador y equity con bindings pybind11), backend FastAPI y frontend React.
