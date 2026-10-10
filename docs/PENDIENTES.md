# Pendientes

Detalles detectados en las revisiones finales de la fase 8 que quedaron sin resolver a propósito, más lo que sigue en la hoja de ruta. Cuando resuelvas uno, borralo de esta lista en el mismo commit.

## Hoja de ruta

1. **Fase 8, parte 3: Simulador con mesa ovalada** (spec `docs/superpowers/specs/2026-10-10-rediseno-ui-design.md` §5). Incluye que el Simulador lea los filtros guardados de Preflop (`localStorage` `pokker.preflop.filters`) para arrancar con 6 o 9 asientos.
2. **Parsers de GGPoker y PokerStars:** esperan una historia de manos real de un torneo.
3. **Diferidos del entrenador:** racha y meta diaria, y un explicador conversacional con LLM (spec fase 6 §9).
4. **`POKKER.exe` en la raíz del repo:** quedó postergado. La complejidad es que el exe necesita las piezas armadas de `app\`, y el actualizador reescribiría archivos versionados. La idea preferida es un exe de arranque que instale y actualice la app en `%LOCALAPPDATA%`.

## Fase 8, parte 1: base visual

- **Vista previa de rangos del Simulador:** las celdas con peso entre 0,5 y 0,65 quedan con el texto a ~3,7:1 (la mezcla dorado/fondo es más oscura que el dorado puro).
- **Backend:** el Entrenador todavía dice "sección Rangos preflop" en los motivos de las fuentes (texto del backend). La sección ahora se llama "Preflop".
- **Título de la pestaña:** el navegador sigue mostrando "Poker Study" (`src/frontend/index.html`).
- **Popover:** Escape no lo cierra si no tiene nada enfocable adentro.
- **Popover:** `FOCUSABLE` no incluye los enlaces `a[href]`.
- **Menú lateral:** `writeStored` se llama dentro del actualizador de `setCollapsed`, así que en StrictMode (desarrollo) escribe dos veces.
- **Cortes de pantalla:** los de Simulador y Entrenador (860 y 640 px) no tienen en cuenta los 170 px del menú, así que entre unos 860 y 1030 px quedan apretados.
- **Chip:** el "Cambiar" (`.ui-chip-action`) se aclara al pasar el mouse por el brillo global de los botones.
- **Barras de frecuencias** (Recomendación y Entrenador): el segmento de fold casi no se ve sobre la superficie, porque fold usa el mismo color que una celda vacía, como pide el spec.

## Fase 8, parte 2: Preflop

- **Acción desconocida en un rango:** `var(--action-x)` sin fallback deja toda la celda sin color. El backend solo guarda acciones conocidas.
- **Mensajes de `PreflopPage`:** los de error y "Rango guardado." solo se borran al importar, así que quedan visibles mientras navegás.
- **Rangos repetidos:** el que elegiste no se recuerda al volver del editor o de "Importar / exportar". Además, "Rango copiado." no se borra al cambiar de repetido.
- **Accesibilidad del visor:**
  - el detalle de la mano solo funciona con el mouse (las celdas de solo lectura no son enfocables);
  - el `role="status"` se monta junto con su texto, y algunos lectores no lo anuncian;
  - los íconos decorativos (⧉ ✎ ＋ ⇅ ⬭) quedan dentro del nombre accesible de los botones.
- **Copiar rango:** incluye una línea "Fold" si el rango tiene esa capa guardada, aunque las estadísticas no cuentan el fold.
- **Formato guardado desconocido:** si el filtro guardado tiene un formato fuera de los 4 conocidos (solo con datos corruptos), la tarjeta Juego queda sin ninguna opción marcada.
- **Posiciones fuera de la lista del Entrenador:** si un rango usa posiciones que el Entrenador no lista (por ejemplo "EP" o "MP"), "Entrenar este spot" le pasa un filtro que no se ve.
