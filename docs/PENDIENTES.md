# Pendientes

Lo que sigue en la hoja de ruta, y los detalles que las revisiones dejen pendientes. Cuando resuelvas uno, borralo de esta lista en el mismo commit.

## Hoja de ruta

1. **Parsers que faltan:** PokerStars y GGPoker cash esperan historiales reales de muestra. Los resultados de torneos de GG (inscripción, puesto y premio, para ROI e ITM) vienen en los resúmenes de torneo de PokerCraft, que todavía no se importan.
2. **Diferidos del entrenador:** racha y meta diaria, y un explicador conversacional con LLM (spec fase 6 §9).
3. **`POKKER.exe` en la raíz del repo:** quedó postergado. La complejidad es que el exe necesita las piezas armadas de `app\`, y el actualizador reescribiría archivos versionados. La idea preferida es un exe de arranque que instale y actualice la app en `%LOCALAPPDATA%`.

## Detalles menores

- **Campo "Stack efectivo por defecto"** (Simulador → Cambiar): es un input controlado, así que no se puede vaciar mientras escribís. Al tipear "15" pasa por "1", y un asiento que tenías en 1 bb termina en 15. Además muestra tu stack: si solo cambiaste el tuyo (por ejemplo, a 37), editar el campo mueve solo tu asiento.
- **`data-popover-keep` vale para todos los popovers abiertos:** un clic en el selector de cartas también mantiene abierto el popover "Mesa" (configuración).
