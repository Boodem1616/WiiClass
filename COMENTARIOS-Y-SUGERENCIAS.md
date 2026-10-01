# Comentarios y sugerencias — E2 WiiClass

Revisión hecha ejecutando la app de verdad (Kivy/KivyMD en un entorno
con display virtual), no solo leyendo el código. Actualizado tras
revisar el commit `f6a2b96` ("Las categorías de matemáticas ahora se
muestran correctamente").

## ✅ Bug de tarjetas en Categoría — confirmado resuelto

Probé la categoría "Matemáticas" (5 clases) con el fix de
`category_screen.py`/`.kv` y las 5 tarjetas se ven completas (título,
fecha, ícono). El cambio clave: `ClaseRowSlot` es un `FloatLayout`, que
**no** redimensiona a sus hijos automáticamente — antes, `ClaseRow`
podía quedar con un tamaño obsoleto si se creaba antes de que el
contenedor tuviera su ancho definitivo. El fix agrega un `bind(size=...,
pos=...)` que sincroniza `ClaseRow` con su `ClaseRowSlot` cada vez que
cambia, más tamaños explícitos (`size_hint_y: None`, `height: dp(76)`)
en vez de depender de valores por defecto. Buen diagnóstico y buena
solución — determinística, no basada en "esperar lo suficiente" (que
es justo el tipo de solución fràgil que ya habían descartado antes con
`MDCard`, según `README2.md`).

## Cambios que apliqué sobre esta versión

- **`main.py` — fix de rendimiento:** `is_online()` abría un socket
  con timeout de 1.5s **en el hilo principal**, tanto en el login como
  cada 5s. Se movió a un hilo de fondo (mismo patrón que
  `downloads_manager.py`). Antes tardaba ~1.5–2.5s en mostrar Inicio
  tras el login; ahora es inmediato.
- **`.gitignore` agregado** — el commit `f6a2b96` subió por error
  `__pycache__/*.pyc` (6 archivos) y `descargas/6_fis1.mp3` (una
  descarga generada en tiempo de ejecución, no código fuente). Los
  destraqueé y agregué `.gitignore` para que no vuelva a pasar.
- **`README.md`** reescrito con lo que pide la pauta (problema,
  usuario objetivo, capturas, declaración de IA). Dejé `README2.md`
  intacto como documentación técnica extendida, enlazado desde el
  nuevo README.
- **`FUNDAMENTACION-UX-UI.md`** — plantilla con la estructura exacta
  A1–A5 de la pauta.

## Lo más importante y pendiente: A — Fundamentación UX/UI (30 %)

Sigue siendo lo más urgente. No lo puedo completar por ustedes — los
hallazgos con evidencia (citas, porcentajes) tienen que salir de sus
entrevistas/encuestas reales. La plantilla en `FUNDAMENTACION-UX-UI.md`
ya tiene la estructura exacta de la pauta (A1–A5) y una sugerencia
concreta: conectar cada decisión que YA tomaron en el código (filtro
por semana, descarga offline, selección múltiple, velocidad de
reproducción) con el hallazgo que la motivó.

## Resto de criterios (B/C/D)

Sin cambios respecto a la revisión anterior: la maqueta ejecuta bien,
la estructura `.py`/`.kv` y la navegación están sólidas. Para la demo,
sigo recomendando mostrar "Ciencias" (1 clase) o "Matemáticas" (5,
ahora ya arreglada) sin apuro — ambas se ven bien.
