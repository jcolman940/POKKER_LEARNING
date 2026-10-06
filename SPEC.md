# Poker Study Tool — Especificación para implementación

## 1. Contexto

Herramienta **personal** de estudio de poker. Puede compartirse con unos pocos amigos, pero no es un producto comercial. El usuario es jugador y ex-crupier: conoce bien la mecánica del juego. La herramienta apunta a la **estrategia**: rangos, frecuencias, equity y EV.

**Restricción no negociable:** es una herramienta de **análisis post-sesión y práctica**. No incluye HUD, overlays, lectura de pantalla del cliente ni ningún tipo de asistencia en tiempo real (GGPoker y PokerStars prohíben la RTA).

Corre **localmente** (local-first) y no tiene multi-tenant.

## 2. Alcance funcional

1. **Motor de evaluación y equity** (mano vs mano, mano vs rango, rango vs rango, multiway).
2. **Simulador / modo práctica**: el usuario arma un escenario (o lo genera al azar) y recibe equity y recomendación.
3. **Motor de recomendación**: preflop por tablas, push/fold + ICM en torneos, solver postflop heads-up y heurísticas para multiway.
4. **Importación de historiales** de GGPoker y PokerStars.
5. **Estadísticas** sobre el historial propio.
6. **Hand replayer**.
7. **Entrenador y leak finder**.
8. **(Última fase)** Empaquetado desktop con pantalla de actualización al abrir.

Formatos soportados: **cash y torneos (MTT/SNG)**, mesas de **2 a 10 jugadores** (6-max, 8-max, 9-max, etc.), stacks variables, ante y BB ante.

## 3. Stack

| Capa | Tecnología | Responsabilidad |
|---|---|---|
| Núcleo | C++20 + CMake + pybind11 | Evaluador de manos, cálculo de equity |
| Backend | Python 3.12 + FastAPI + SQLAlchemy + Alembic | Parsers, estadísticas, recomendación, orquestación del solver |
| Base de datos | SQLite | Manos, estadísticas cacheadas, spots resueltos, rangos |
| Frontend | React + TypeScript + Vite | Simulador, replayer, gráficos, entrenador |
| Solver | TexasSolver (versión consola) como **binario externo** | Resolución postflop HU |

TexasSolver es AGPL. Se integra como proceso externo (subprocess) y su código no se copia dentro del repo.

## 4. Estructura del repo (monorepo)

```
/core        C++: evaluator, equity, bindings pybind11
/backend     FastAPI: api/, parsers/, stats/, recommend/, solver/, db/
/frontend    React + TS
/data        rangos preflop (JSON), spots precalculados
/tests       fixtures de historiales, tests de integración
```

Convenciones: código, identificadores y commits en **inglés**; **UI en español**.

## 5. Modelo de dominio

- `Card`, `HoleCards`, `Board`.
- `Range`: matriz de 169 manos canónicas con peso 0–1, que se expande a 1326 combos. Debe considerar card removal (bloqueos por cartas conocidas).
- `Position`: calculada **relativa al botón** según la cantidad de asientos ocupados (2–10). Nombres: UTG, UTG+1, UTG+2, LJ, HJ, CO, BTN, SB, BB. 6-max y 9-max usan la misma lógica.
- `Action`: fold / check / call / bet / raise / all-in. El monto se guarda en fichas y **normalizado en bb**.
- `Street`: preflop / flop / turn / river.
- `HandRecord`: sala, id de mano, tipo de juego (cash/MTT/SNG), ciegas/ante, info de torneo (buy-in, nivel, payouts si hay), asientos, stacks, hero, acciones por calle, board, showdown, resultado.
- `Scenario`: lo que recibe el simulador (formato, jugadores, posiciones, stacks efectivos, acción previa, pote, board, mano de hero, rango o mano opcional del rival).

## 6. Módulos y criterios de aceptación

### 6.1 Evaluador (C++)
- Evalúa manos de 5, 6 y 7 cartas.
- **Test obligatorio:** enumerar las 2.598.960 manos de 5 cartas y verificar la distribución por categoría: escalera de color 40, póker 624, full 3.744, color 5.108, escalera 10.200, trío 54.912, doble par 123.552, par 1.098.240, carta alta 1.302.540. Deben salir 7.462 rangos distintos.
- Benchmark de rendimiento en manos de 7 cartas por segundo.

### 6.2 Equity (C++)
- Usa enumeración exacta cuando la cantidad de combinaciones es manejable y Monte Carlo cuando no. Las iteraciones son configurables y se **reporta el error estándar**.
- Soporta mano vs mano, mano vs rango, rango vs rango y multiway (hasta 6 jugadores como mínimo).
- Devuelve win / tie / lose por jugador.
- Tests contra valores conocidos (por ejemplo, AA vs KK preflop ≈ 82/18) y simetría (A vs B == 1 − (B vs A) descontando empates).

### 6.3 Simulador / práctica
- El usuario puede elegir **manualmente** su mano, la del rival (opcional), flop, turn y river, o **generar todo al azar**. También puede generar al azar solo una parte (por ejemplo, fijar su mano y randomizar el resto).
- Configura formato, cantidad de jugadores, posiciones, stacks efectivos, acción previa y pote.
- Muestra equity, outs, pot odds, equity requerida, MDF y SPR.
- **Regla clave:** la recomendación se calcula **siempre contra el rango** del rival, nunca contra su mano exacta. Si el usuario fijó la mano del rival, esa equity se muestra **por separado**, como dato informativo ("contra esta mano puntual tenías X%").

### 6.4 Motor de recomendación
Salida común para todas las fuentes:
- **Estrategia mixta**: acciones con frecuencia (ej.: bet 33% → 60%, check → 40%).
- **EV por acción** cuando la fuente lo permita.
- **Fuente** del resultado: `chart` / `nash` / `solver` / `heuristic`.
- **Nivel de confianza**: los resultados heurísticos se marcan como "aproximado".
- **Explicación corta**: valor, protección, bluff, blockers, equity realization.

Fuentes:
1. **Preflop (cash y MTT con stacks profundos):** rangos en JSON por formato, cantidad de jugadores, posición, profundidad de stack y situación (RFI, vs open, vs 3-bet, vs 4-bet, squeeze, blind vs blind). Se pueden **editar e importar desde la UI**. No presentar datos inventados como si fueran GTO.

   **Fuentes iniciales (decididas):**
   - **Cash:** Pokalab (pokalab.com/tools/preflop-charts). Son rangos 6-max a 100bb resueltos con el rake de GGPoker NL50: aperturas por posición y defensa de BB.
   - **MTT:** preflopranges.app. Cubre MTT 9-max, cash 6-max y Spin & Go por posición, profundidad de stack y respuesta, con frecuencias por mano.
   - **Push/fold (≲15–20bb):** lo **calcula el propio sistema** (ver punto 2), sin depender de tablas externas.

   **Carga de los rangos:**
   - El usuario carga los rangos **a mano** desde la UI, con un editor de matriz 13×13 que acepta frecuencias mixtas. Alternativamente, se pegan en notación estándar de rangos (`22+, A2s+, KTo+...`) y el sistema los parsea. **No hacer scraping** de esos sitios.
   - Cada rango guarda metadatos: `source` (`pokalab` / `preflopranges` / `custom` / `computed`), formato, jugadores, posición, stack, situación, sizing de apertura, rake y ante, más una nota libre.
   - En la UI, la recomendación muestra la fuente ("fuente externa: Pokalab") y avisa si el escenario no coincide con las condiciones del rango (otro stack, otro tamaño de mesa, sin ante, etc.). En ese caso se usa el rango más cercano, marcado como "aproximado".
   - Los rangos externos son para **uso personal**. Al empaquetar la app para compartir (fase 7), el set de rangos externos **no se incluye por defecto**: se distribuye solo el formato vacío y los rangos calculados por el sistema.
   - Agregar un importador de archivos .txt en formato PioViewer/ProPokerTools (`AA:1.0,AKs:0.5,...`), para poder sumar packs comprados a futuro (por ejemplo, de MonkerGuy).
2. **Push/fold en torneos (≲15–20bb):** equilibrio de Nash calculado (por ejemplo, con fictitious play iterativo) más **ICM (Malmuth-Harville)** según la estructura de premios.
3. **Postflop heads-up:** TexasSolver por subprocess. Incluye un generador de configuraciones con árboles de apuesta simplificados y configurables, y un parser del output. Los resultados se cachean en SQLite usando como clave un hash del spot. Hay una **cola de solves en lote** para dejar spots resolviéndose (por ejemplo, de noche) y una biblioteca de spots comunes precalculados.
4. **Postflop multiway (3+ jugadores):** heurísticas basadas en equity contra rangos, siempre marcadas como "aproximado".

### 6.5 Importación de historiales
- Interfaz de parser por sala (patrón plugin). Detecta la sala automáticamente por contenido.
- Acepta archivos `.txt` sueltos y `.zip`.
- **Importación idempotente**: deduplica por (sala, id de mano).
- Detecta a Hero. GGPoker **anonimiza a los rivales**, así que las estadísticas por oponente se limitan a lo que permita cada sala.
- El parser es tolerante a errores: si una mano falla, no se aborta el lote. Se genera un reporte con las manos y líneas que fallaron.
- **No inventar el formato de memoria.** Primero se define la interfaz y los tests. Antes de cerrar cada parser, **pedirle al usuario archivos de muestra reales** de cada sala (cash y torneo) y usarlos como fixtures.

### 6.6 Estadísticas
- VPIP, PFR, 3-bet, fold to 3-bet, c-bet (flop/turn), fold to c-bet, WTSD, W$SD, AF / AFq, winrate en bb/100.
- Se pueden cortar por posición, mano, profundidad de stack, tamaño de mesa, formato y fecha.
- **All-in EV adjusted** (líneas roja/azul/verde).
- Para torneos: ROI, ITM y chip EV.
- **Cada métrica muestra el tamaño de muestra y un intervalo de confianza del 95%.** Las métricas con muestra insuficiente se señalan visualmente.

### 6.7 Hand replayer
- Reproduce la mano calle por calle, con la equity de Hero en cada punto (contra rangos asignados).
- Tiene un botón "Analizar este spot" que lleva el escenario al simulador y al motor de recomendación.

### 6.8 Entrenador y leak finder
- **Entrenador:** presenta spots generados al azar o tomados del historial propio. El usuario elige una acción y se compara con la recomendación. El puntaje se calcula por **pérdida de EV**. Los errores se repiten con frecuencia creciente (repetición espaciada).
- **Leak finder:** compara las frecuencias reales del usuario por posición y spot contra los rangos y soluciones de referencia. Marca los desvíos significativos, con un mínimo de muestra configurable.

### 6.9 (Última fase) Desktop + actualizaciones
- Empaquetar como app de escritorio (Tauri o Electron + backend Python como sidecar con PyInstaller). La decisión queda pendiente.
- Al abrir, consultar si hay una versión nueva (por ejemplo, en GitHub Releases). Si la hay, mostrar una pantalla con el changelog y aplicar la actualización. Así los amigos del usuario reciben los cambios.
- Desde la fase 0, la app debe exponer su versión y tener la configuración centralizada, para que esto se pueda agregar sin refactors.

## 7. Fases

| Fase | Contenido |
|---|---|
| 0 | Scaffold del monorepo, CMake + pybind11, FastAPI, Vite, SQLite + Alembic, scripts de test |
| 1 | Evaluador + equity con sus tests |
| 2 | Simulador (UI + API) |
| 3 | Rangos preflop editables, push/fold Nash + ICM |
| 4 | Parsers GG/PS, estadísticas, replayer |
| 5 | Integración de TexasSolver, caché, cola de solves y biblioteca de spots |
| 6 | Entrenador + leak finder |
| 7 | Empaquetado desktop + actualizaciones |

## 8. Cómo trabajar

- Trabajar **una fase por vez**. Al terminar cada fase, parar, resumir lo hecho y lo pendiente, y esperar confirmación antes de seguir.
- En el núcleo, escribir los tests antes de la implementación (o junto con ella). Ninguna fase se da por cerrada con tests fallando.
- Ante una decisión abierta (sección 9), **preguntar** en vez de asumir.
- Cuando un número estratégico no salga de un cálculo, marcarlo como aproximado.

## 9. Decisiones abiertas

- Formato exacto de los historiales de GG y PS: el usuario va a proveer muestras.
- Tauri vs Electron para el empaquetado.
- Sistema operativo objetivo (principalmente Windows, Linux, etc.).
