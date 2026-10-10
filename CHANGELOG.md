# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [0.8.0] - 2026-10-10

### Cambiado
- **Nuevo diseño "Paño y oro":** toda la app pasa a un tema oscuro verde de mesa con detalles dorados, con mejor contraste y una tipografía más clara.
- **Menú lateral agrupado** en Estudiar (Preflop, Simulador, Push/Fold, Entrenador) y Analizar (Manos, Replayer, Estadísticas, Solver). Se puede plegar a solo íconos y recuerda cómo lo dejaste. "Rangos preflop" ahora se llama **Preflop** e "Historiales" se llama **Manos**.
- **Preflop:** primero elegís los filtros (juego, fuente, stake y jugadores, con cuántos rangos hay de cada uno) y después ves el visor con secuencia, posición, rival, stack efectivo, la matriz con la leyenda y el % del rango y combos. Desde el visor podés copiar el rango, editarlo, crear uno nuevo, abrir el spot en el Simulador o entrenarlo. Importar, exportar y la tabla de rangos están en "Importar / exportar".
- **Simulador con mesa ovalada:** vos siempre abajo y los asientos según 6-max o 9-max. Tocando un asiento marcás rival, fold o vacío, la apuesta (⅓, ½, ⅔, Pot, All-in), el stack, el rango y las cartas. El pozo, lo que pagás y la acción previa se calculan solos a partir de la mesa, y la mesa se guarda entre sesiones. Las opciones avanzadas (situación, antes, premios de ICM, solver) quedan en un panel desplegable.

### Corregido
- Los checkboxes del Entrenador quedaban encima de su texto.

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
