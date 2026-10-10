# Pendientes

Lo que sigue en la hoja de ruta, y los detalles que las revisiones dejen pendientes. Cuando resuelvas uno, borralo de esta lista en el mismo commit.

## Hoja de ruta

1. **Parsers de GGPoker y PokerStars:** esperan una historia de manos real de un torneo.
2. **Diferidos del entrenador:** racha y meta diaria, y un explicador conversacional con LLM (spec fase 6 §9).
3. **`POKKER.exe` en la raíz del repo:** quedó postergado. La complejidad es que el exe necesita las piezas armadas de `app\`, y el actualizador reescribiría archivos versionados. La idea preferida es un exe de arranque que instale y actualice la app en `%LOCALAPPDATA%`.
