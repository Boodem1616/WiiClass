# Revisión de diseño y errores — WiiClass

> **Importante:** en mi entorno no pude instalar Kivy/KivyMD, así que **no ejecuté la app**.
> Verifiqué que todo el Python compila, que la indentación de los `.kv` es válida, que cada
> `ids.xxx` que usa el código existe en su `.kv`, y probé las consultas nuevas de `db.py`
> con una base temporal. El aspecto visual y los puntos marcados con ⚠️ hay que revisarlos
> corriendo `python3 main.py`.

## 1. Rediseño (azul, "tinta sobre papel")

- **`theme.py` (nuevo):** toda la paleta en un solo lugar. Antes `0.09, 0.16, 0.55` estaba
  copiado decenas de veces en los `.kv`. En los `.kv` se usa `#:import T theme` → `T.PRIMARY`.
- **`screens/common.kv` (nuevo):** componentes compartidos (`Tarjeta`, `TarjetaToque`, `Hoja`,
  textos y botones de cabecera).
- **`screens/widgets.py` (nuevo):** `CabeceraDegradada`, `Waveform` (onda que se ilumina con
  el progreso) y `mostrar_aviso()` (toast reutilizable).
- **Cabecera con degradado azul + hoja redondeada** en Inicio, Descargas, Alertas, Perfil,
  Categoría, Reproductor y "Todas las notificaciones".
- **Reproductor:** portada con forma de onda (una "huella" distinta por clase), botón play
  grande relleno, y nuevos botones **−10 s / +10 s**.
- **Inicio:** la tarjeta "Clases Recientes" no mostraba ninguna clase; ahora hay una lista real
  de las 3 últimas. Las categorías muestran su cantidad de clases.
- **Categoría:** una sola cabecera (antes eran dos barras que se intercambiaban poniendo
  `height: 0`), chips de semana propios, fechas legibles ("15 ago 2026") y duración ("45 min").
- **Perfil:** avatar circular real, ícono en "Cerrar sesión".

## 2. Errores encontrados y corregidos

| # | Gravedad | Dónde | Problema | Arreglo |
|---|---|---|---|---|
| 1 | Alta | `audio_player.py` | En `except Exception as exc:` se agendaba `lambda: ...(exc)`. Python borra `exc` al salir del `except`, así que la lambda daba `NameError` y `is_loading` quedaba en `True` para siempre (botón atascado en ⌛). | Se copia a `error = exc` antes de agendar. |
| 2 | Alta | `downloads_manager.py` | Mismo bug: un error de descarga nunca llegaba a `on_error`. | Igual. Además ahora se avisa al usuario. |
| 3 | Media | `main_screen.kv` | `md_bg_color` sin `theme_bg_color: "Custom"` se ignora → la barra inferior salía rosada/lavanda (se ve en tus capturas). La paleta `Indigo` también teñía íconos y contornos. | `theme_bg_color: "Custom"` y paleta `Blue`. |
| 4 | Media | `main_screen.py` | Al volver de Categoría/Reproductor, la pestaña activa no se refrescaba (una descarga nueva no aparecía en "Descargas" hasta cambiar de pestaña). | `on_pre_enter` de `MainScreen` refresca la pestaña actual. |
| 5 | Media | `main_screen.py` | Cada cambio de red reconstruía los tabs y te devolvía a "Inicio". | `build_tabs` conserva la pestaña actual. |
| 6 | Media | `main.py` | `is_online()` no cerraba el socket (fuga cada 5 s) y `setdefaulttimeout` cambiaba el timeout de **todos** los sockets. | `with socket...` y `settimeout` local. |
| 7 | Media | `player_screen.py` | Cada 0.3 s se reescribía el valor del slider aunque el dedo lo estuviera arrastrando (la perilla saltaba); y si soltabas fuera de la barra, el salto se perdía. | Bandera `_arrastrando_slider`. |
| 8 | Media | `player_screen.py` | "Siguiente" ignoraba la copia descargada y, sin conexión, saltaba a clases que no estaban en el teléfono. | Usa `db.get_ruta_local` y filtra por descargadas si `app.offline`. |
| 9 | Baja | `audio_player.py` | Al terminar la pista, el ícono seguía en "pausa" y `play` no hacía nada. | Detección de fin y reinicio al pulsar play. |
| 10 | Media | varios `.kv` | `radius: [48, 48, 48, 48]` está en **píxeles**, no dp: en pantallas densas el avatar no era un círculo (y las tarjetas se veían menos redondeadas). | Se usa `dp()` / `Ellipse`. |
| 11 | Baja | `notification_widgets.py` | `fecha_txt = ""` fijo: la fecha existía en la BD pero nunca se mostraba (y reservaba 70dp vacíos). `marcar_notificacion_leida` no se usaba nunca. | "hace 5 min" + marcar leídas al salir de Alertas. |
| 12 | Baja | `login_screen.py` | Al salir del Login se quitaban los cuadernos pero sus `Clock.schedule_interval` seguían corriendo. | Se guardan y cancelan. |
| 13 | Media | `login_screen.py` / `db.py` | `password.strip()` descartaba espacios de la contraseña; el correo distinguía mayúsculas (el teclado del móvil suele capitalizar); "¿Olvidaste tu contraseña?" no hacía nada; Enter no enviaba; en Android el teclado tapaba los campos. | Corregido; `Window.softinput_mode = "below_target"`. |
| 14 | Baja | `category_screen.py` | Una consulta a la BD **por fila** (`esta_descargada`) en cada refresco. | `db.get_ids_descargados()` (una sola). |
| 15 | Baja | `db.py` | `Descargas_offline` sin `UNIQUE`; "consultar y luego insertar" tenía carrera. | Índice único + `INSERT OR IGNORE`. |
| 16 | Baja | `main.py` | `maxfps = 30` también en Android: el scroll se ve entrecortado en un teléfono real. | Solo se limita en escritorio. |
| 17 | Baja | `downloads_tab.py` | Un audio de 60 KB se mostraba como "0 MB". | `theme.fmt_peso`. |

## 3. Pendiente / sugerencias (no lo cambié sin consultarte)

1. **Las descargas no son por usuario.** `Descargas_offline` no tiene `usuario_id`: si dos cuentas
   usan el mismo teléfono, comparten descargas.
2. **Hash de contraseña:** `sha256` sin sal (el propio código dice que es provisional). Con servidor:
   `bcrypt`/`argon2` y verificación del lado del servidor.
3. **`is_online()` consulta 8.8.8.8:53.** Tu caso de uso es WiFi de campus con internet malo o
   restringido: podría marcar "offline" estando en el campus (o al revés). Mejor comprobar
   el servidor de WiFi/backend propio.
4. **Tab "Descargas" solo offline** es requisito de la pauta, pero según tu propia fundamentación
   (poco almacenamiento, mala conexión) el usuario querría *ver y borrar* sus descargas también
   estando en el campus. Y hoy **no hay forma de borrar una descarga**.
5. **"Continuar donde quedaste":** guardar la posición por clase (muy útil para clases de 45 min).
6. **Datos de ejemplo incoherentes:** las notificaciones mencionan "Cálculo II", "Física I",
   "Clase 3 - Derivadas", que no existen en las categorías del seed.
7. "Estudiante de Pregrado" está fijo en el código; debería venir de la BD.
8. Falta `buildozer.spec` (el README lo menciona pero no está en el zip).

## 4. ⚠️ Puntos a verificar al ejecutar

- Indicador/colores de la pestaña activa en la barra inferior: uso propiedades
  (`active_indicator_color`, `icon_color_active`, …) solo si existen en tu versión de KivyMD.
- El botón play usa `theme_font_size: "Custom"`; si tu versión no lo soporta, el ícono se verá
  del tamaño por defecto dentro del círculo (no rompe nada).
- La "hoja redondeada" (`<Hoja>` en `common.kv`) pinta un rectángulo redondeado que se extiende
  30 dp hacia abajo para ocultar sus esquinas inferiores tras la barra de navegación.
