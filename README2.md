# WiiClass

App Android de grabaciones de clases, hecha con **Kivy 2.3 + KivyMD 2.0 + SQLite**.

## Requisitos
```bash
pip install -r requirements.txt
```
> `ffpyplayer` es necesario para el control real de velocidad de reproducción
> (0.5x / 1.0x / 1.5x / 2.0x). Si no está disponible, la app hace fallback
> automático a `kivy.core.audio` (sin cambio de velocidad).

## Ejecutar (escritorio, para desarrollo)
```bash
python3 main.py
```
La primera vez se crea `wiiclass.db` (SQLite) con datos de ejemplo:
- Institución: Universidad Central
- Usuario demo: `sflores@uct.cl` / contraseña `12345678`

## Empaquetar para Android
Este proyecto está listo para compilarse con **Buildozer**:
```bash
pip install buildozer
buildozer init      # genera buildozer.spec
# En buildozer.spec agrega como requirements:
#   python3,kivy,kivymd,ffpyplayer,sqlite3
buildozer -v android debug
```

## Estructura del proyecto
```
wiiclass_app/
├── main.py                 # Punto de entrada, navegación global
├── db.py                   # Esquema SQLite + consultas
├── audio_player.py         # Motor de audio (play/pause/seek/velocidad)
├── downloads_manager.py    # Descarga de audio a almacenamiento local (offline)
├── requirements.txt
├── assets/audio/           # Archivos de audio de ejemplo (placeholders)
├── descargas/               # (se crea sola en tiempo de ejecución) audios descargados
└── screens/
    ├── login_screen.py            + login_screen.kv            # Pantalla 1: Login
    ├── main_screen.py             + main_screen.kv              # Pantalla 2: Bottom Navigation (MDNavigationBar)
    ├── home_tab.py                + home_tab.kv                 # Tab Inicio: categorías (scroll horizontal)
    ├── category_screen.py         + category_screen.kv          # Clases grabadas: semanas, descarga, selección múltiple
    ├── player_screen.py           + player_screen.kv             # Reproductor de audio compartido
    ├── notifications_tab.py       + notifications_tab.kv        # Tab Alertas / Notificaciones (máx. 6)
    ├── notifications_all_screen.py + notifications_all_screen.kv # "Ver todas las notificaciones"
    ├── notification_widgets.py    + notification_widgets.kv     # Fila deslizable + diálogo, compartidos
    ├── notifications_state.py                                    # Ocultamiento de notificaciones (solo sesión)
    ├── profile_tab.py             + profile_tab.kv                # Tab Perfil
    └── downloads_tab.py           + downloads_tab.kv              # Tab Descargas (solo offline)
```


Cada pantalla tiene su lógica en `.py` y su diseño (widgets, layout, estilos) en
un `.kv` del mismo nombre, cargado con
`Builder.load_file(os.path.join(os.path.dirname(__file__), "xxx.kv"))` al
inicio del módulo — es la convención estándar de Kivy para separar diseño de
lógica. Al editar solo el aspecto visual de una pantalla, el archivo a tocar
es el `.kv`; los manejadores de eventos (`on_release: ...` etc.) siguen
haciendo referencia a métodos de la clase Python (`root.mi_metodo()`,
`app.mi_metodo()`), así que ambos archivos siguen conectados igual que antes.

## Notas de implementación

### Categoría Clases: semanas, descarga y selección múltiple

Implementado según `instrucciones.md` ("Mejoras en la Categoría Clases"):

- **Semanas calculadas por categoría, no globalmente.** `db.recalcular_semanas()`
  agrupa las grabaciones de CADA categoría por separado, en bloques de 7 días
  contados desde la fecha de la primera grabación de esa categoría (así lo
  muestra el mockup `Categoria_clases.png`: Álgebra Lineal con 5 clases queda
  en 3 semanas). Se recalcula en cada arranque (es barato e idempotente), así
  que agregar una grabación nueva no deja la numeración inconsistente.
- **Migración de base de datos**: `db._migrar_columna_semana()` agrega la
  columna `semana` con `ALTER TABLE` si la base de datos ya existía de una
  versión anterior de la app (una `wiiclass.db` creada antes de este cambio
  no tendría esa columna, y `CREATE TABLE IF NOT EXISTS` no modifica tablas
  existentes). Probado migrando una base de datos simulada sin la columna.
- **"Descargar" es una copia local simulada, no una descarga de red real**:
  esta app no tiene backend remoto — los audios ya vienen empaquetados en
  `assets/audio/`. `downloads_manager.py` copia el archivo a una carpeta
  `descargas/` persistente y registra el estado en `Descargas_offline`
  (tabla que ya existía). El día que haya un servidor real, solo hay que
  cambiar el origen del archivo (una URL en vez de una ruta local); el resto
  del flujo (registro, notificación, ícono, reproducción offline) no cambia.
  Igual que con el audio, la copia de archivo corre en un hilo de fondo —
  tocar disco en el hilo principal ya nos causó más de un congelamiento en
  este proyecto.
- **El reproductor prefiere la copia descargada automáticamente**
  (`main.abrir_reproductor`), tanto si se abre desde Categoría/Inicio como
  desde el Tab Descargas — así la descarga tiene un efecto real y no es solo
  cosmética.
- **Selección múltiple con "mantener presionado"**: se implementa a mano
  (Kivy no trae long-press incorporado), con el mismo patrón usado para el
  swipe-to-dismiss de notificaciones: se agenda un `Clock.schedule_once` al
  tocar la tarjeta, que se cancela si el dedo se levanta antes de tiempo o
  si se mueve más de cierto umbral (para no confundirlo con un scroll).
- **`MDCard` es en el fondo un `BoxLayout`**, así que no admite posicionar un
  hijo libremente con `pos_hint` (necesario para el botón de descarga en la
  esquina inferior derecha). Se resolvió envolviendo cada `ClaseRow` en un
  `FloatLayout` (`ClaseRowSlot`), igual que se hizo con las notificaciones
  deslizables — un patrón que ya se repite varias veces en este proyecto.
- **Bug encontrado y corregido — historia completa: tarjetas invisibles /
  "rotas" al entrar a una categoría, y además no se adaptaban al
  redimensionar la ventana.** Causa raíz confirmada con un script de
  diagnóstico (comparando `row.size` contra `row.fbo.size` en tiempo
  real): `MDCard` (vía `RippleBehavior`) arma un framebuffer interno UNA
  SOLA VEZ, con el tamaño que tenga el widget en el momento EXACTO de
  construirse, y nunca lo vuelve a redimensionar después — aunque el
  propio `size` del widget se corrija solo un instante más tarde.
  Se probaron **tres** soluciones sucesivas mientras se acotaba el
  problema:
  1. Esperar el ancho con `bind(width=...)`: no confiable, porque el
     ancho por defecto de Kivy (100) es indistinguible de un ancho
     "de paso" que también da 100 antes de asentarse en el valor final.
  2. Forzar `do_layout()` de forma síncrona en toda la cadena de
     ancestros: funcionaba en las pruebas automatizadas de este entorno,
     pero un usuario real reportó que el problema seguía intacto en su
     máquina — la temporización exacta depende del dispositivo/driver de
     GPU y no se pudo hacer 100% determinística con este enfoque.
  3. Sondear el ancho del contenedor cada 30ms hasta leer el mismo valor
     tres veces seguidas, recién en `on_enter`: mejoró la confiabilidad
     en las pruebas de este entorno, pero **tampoco resultó suficiente**
     en la máquina real del usuario (el mismo bug volvió a aparecer), y
     además dejó en evidencia un problema relacionado: como se le pasaba
     a `ClaseRow` un ancho fijo en píxeles (no reactivo), las tarjetas
     dejaban de ajustarse si la ventana se agrandaba o achicaba después.

  Dado que ninguna solución basada en "esperar lo suficiente" resultó
  100% confiable entre distintos dispositivos, la solución definitiva fue
  **eliminar la causa de raíz en vez de esquivarla**: `ClaseRow` ya NO
  hereda de `MDCard` (ni de `RippleBehavior` en general). Ahora es un
  `ButtonBehavior` + `BoxLayout` común, con el fondo redondeado dibujado
  a mano en `canvas.before` (`Color` + `RoundedRectangle`, reactivos a
  `pos`/`size` — se actualizan solos en cada resize, sin ningún
  framebuffer de por medio). Esto es determinístico por construcción, sin
  ninguna espera ni sondeo: no importa cuándo ni en qué dispositivo se
  construya el widget, porque no depende de que su tamaño ya sea
  definitivo en ese instante. Como beneficio adicional, las tarjetas
  ahora también se adaptan correctamente al agrandar/achicar la ventana
  (se probó explícitamente redimensionando la ventana en tiempo de
  ejecución: 800px → 1200px → 400px, y el ancho de cada tarjeta lo siguió
  correctamente en los tres casos). El costo es cosmético nada más: se
  pierde el efecto ripple de KivyMD al tocar la tarjeta.

### Tab Notificaciones: deslizar para eliminar, límite de 6, "Ver todas"

Implementado según `Categoria_notifaciones_update.md`, con estas decisiones
confirmadas explícitamente con el usuario (donde la especificación era
ambigua o tenía una inconsistencia):

- **"Eliminar" nunca borra de la base de datos.** Deslizar una notificación
  o usar "Limpiar todas" solo la oculta para la sesión actual (en memoria,
  ver `notifications_state.py`). Esto es intencional: la base de datos
  pronto pasará a ser un servidor SQL remoto, y no se quería perder datos
  reales por una acción de la UI. Al cerrar sesión, el ocultamiento se
  reinicia (una sesión nueva ve todas las notificaciones de nuevo).
- **Límite de 6 + botón "Mostrar todas" con 7 o más.** La especificación
  original decía "máximo 6 visibles" pero "el botón aparece al superar
  las 7", lo cual dejaba un caso (exactamente 7 notificaciones) sin forma
  de ver la 7ma. Se confirmó mantenerlo tal cual estaba escrito: se
  muestran 6, y el botón aparece con 7 o más.
- **"Limpiar todas" pide confirmación** (diálogo con `MDDialog`) antes de
  ocultar, para evitar toques accidentales.
- **Deslizar (swipe) es una implementación manual**, ya que KivyMD 2.0 no
  trae un componente de "swipe to dismiss" (existía `MDCardSwipe` en la
  serie 1.x, pero se quitó). Ver `SwipeToDismissRow` en
  `screens/notification_widgets.py`: en `on_touch_down` NO se agarra el
  touch todavía (así el `ScrollView` que contiene la lista también lo ve
  con normalidad); recién en `on_touch_move`, si el movimiento resulta
  claramente más horizontal que vertical, la fila agarra el touch para sí
  (robándoselo al `ScrollView`) y sigue el arrastre; si el movimiento es
  más vertical, nunca lo agarra y el `ScrollView` desplaza la lista como
  siempre. Deslizar hacia cualquiera de los dos lados descarta la fila.
- **"Categoría Notificaciones 2"** es `notifications_all_screen.py`: una
  pantalla a nivel de app (como `CategoryScreen`/`PlayerScreen`, con su
  propio botón "atrás"), no un tab más. Comparte el mismo estilo visual,
  la misma fila deslizable y el mismo diálogo de "Limpiar todas" que el
  Tab (ambos importan `notification_widgets.py`), y ambas leen/escriben
  el mismo estado compartido (`notifications_state.py`), así que ocultar
  o limpiar en una vista se refleja en la otra la próxima vez que se
  muestra.

- **Detección offline**: `main.is_online()` hace un chequeo de socket liviano
  cada 5s. En un dispositivo Android real se recomienda reemplazarlo por
  `pyjnius` + `ConnectivityManager` para reaccionar instantáneamente a
  cambios de red.
- **Velocidad de audio**: ffpyplayer no permite cambiar la velocidad de un
  stream ya abierto, así que cada cambio de velocidad reabre el reproductor
  con el filtro FFmpeg `atempo=<velocidad>` y salta a la posición donde iba.
  Esto es transparente para quien escucha.
- **Mismo reproductor en Inicio y Descargas**: ambos flujos llaman a
  `app.abrir_reproductor(...)`, que reutiliza la única instancia de
  `PlayerScreen` / `audio_engine`.
- **Rendimiento de la animación de fondo (login)**: se midió que usar
  `kivy.animation.Animation` (interpolación suave, ~30-60 veces por
  segundo) para los "cuadernos flotando" hace que el uso de CPU suba a
  ~97% sostenido en entornos SIN aceleración de GPU (renderizado por
  software: común en máquinas virtuales, ciertas configuraciones de
  Windows sin drivers OpenGL correctos, algunos emuladores). Eso satura
  el hilo principal de Kivy y la app se percibe "congelada". Por eso la
  animación se reimplementa con pasos discretos (`PASOS_POR_SEGUNDO = 6`
  en `screens/login_screen.py`), lo que baja el consumo a ~17-21% CPU en
  el mismo escenario. Además, la animación solo corre mientras la
  pantalla de Login está visible (se detiene con `on_leave`). Si en un
  dispositivo real este consumo sigue siendo alto, se puede: (a) bajar
  aún más `PASOS_POR_SEGUNDO`, o (b) comentar la llamada a
  `Clock.schedule_once(self._spawn_notebooks, 0.3)` en `on_enter` para
  quitar la animación por completo. En un dispositivo Android real con
  aceleración GPU (lo normal), esto no debería ser un problema ni con la
  animación original.
- Contraseñas en `db.py` usan un hash sha256 simple **solo para demo**; en
  producción usar bcrypt/argon2 y, si se migra a backend real, HTTPS + JWT
  en vez de SQLite local para las credenciales.
- **Apertura de audio asíncrona**: al tocar una clase para reproducirla,
  `audio_player.AudioEngine.load()` abre el archivo (crea el
  `ffpyplayer.MediaPlayer`) en un hilo de fondo, no en el hilo principal.
  Abrir un archivo de audio implica inicializar el dispositivo de audio del
  sistema, lo cual puede tardar de forma muy variable según el dispositivo;
  si eso se hiciera en el hilo principal, toda la app dejaría de responder
  mientras tanto (Kivy es de un solo hilo). Mientras el audio carga,
  `PlayerScreen` muestra el botón de play deshabilitado con un ícono de
  reloj de arena, y se habilita solo cuando el motor ya está listo.
- **Cierre de audio también asíncrono**: por el mismo motivo, cerrar un
  reproductor anterior (`close_player()`, p.ej. al abrir una clase nueva
  mientras otra sonaba, o al cambiar de velocidad) también corre en un
  hilo de fondo. En hardware con un dispositivo de audio real (ALSA/
  PulseAudio), cerrar un stream que está sonando puede tardar de forma
  notoria, y hacerlo en el hilo principal congelaba la app justo al
  intentar abrir una segunda clase.
- **`theme_bg_color: "Custom"` es obligatorio junto a `md_bg_color`**: en
  KivyMD 2.0, `MDCard`, `MDButton` y `MDTopAppBar` con `style` ("filled",
  "elevated", etc.) IGNORAN `md_bg_color` si no se agrega también
  `theme_bg_color: "Custom"` — sin eso, usan un color de tema con tinte
  automático en vez del color pedido (por eso tarjetas y botones que
  debían verse blancos puros se veían lavanda/rosados). Todas las
  pantallas del proyecto ya llevan este ajuste donde corresponde.
- **`MDSnackbar` puede crashear por un `Fbo` mal inicializado**: en KivyMD
  2.0, `MDSnackbar` hereda de `RippleBehavior`, que al construirse crea un
  framebuffer (`Fbo`) del tamaño que tenga el widget en ESE momento. En
  ciertos drivers de GPU/OpenGL, si el widget todavía no tiene un tamaño
  real asignado, la creación del framebuffer falla con
  "FBO Initialization failed" y crashea toda la app. Por eso los avisos
  del Login ("Credenciales incorrectas", etc.) NO usan `MDSnackbar`: se
  implementan con un widget simple (`Label` + `canvas` propio, sin ripple
  ni Fbo) en `LoginScreen._toast()`, robusto en cualquier equipo/driver.
- **Cuidado con `Stencil*` de Kivy combinado con canvas de KivyMD**: se
  probó recortar un degradado a la forma redondeada de un `MDCard` usando
  `StencilPush/StencilUse/StencilPop`, y en al menos un entorno de prueba
  eso corrompió el renderizado de toda la ventana (aparecían manchas
  negras). Por eso la portada del reproductor (`player_screen`) usa un
  color sólido en vez de un degradado recortado: es un detalle decorativo
  menor y no vale la pena el riesgo de romper la app en hardware que no
  se puede probar de antemano. `screens/gradient_utils.py` documenta esto
  y solo ofrece la variante segura (sin recorte a esquinas redondeadas),
  usada en el fondo del Login (que no tiene esquinas que cuidar).
- **El crash real al cambiar de velocidad era un bug de `ffpyplayer`, no de
  threading**: se diagnosticó con `gdb` (viendo la traza nativa exacta del
  segmentation fault) y el problema real era llamar a `MediaPlayer.seek()`
  INMEDIATAMENTE después de crear el `MediaPlayer` — el reproductor recién
  creado todavía no había terminado de leer las cabeceras/formato del
  archivo en su hilo interno, y pedirle un `seek()` en ese momento
  accedía a estructuras internas que aún no estaban listas. La primera
  carga de una clase nunca lo sufría porque ahí `start_at=0` y el `seek()`
  se saltea; pero cambiar de velocidad SIEMPRE dispara un `seek()` a la
  posición donde iba, gatillando el crash. La solución en
  `audio_player.py` espera (con un límite de ~2s) a que el reproductor
  reporte una duración válida —señal de que ya inicializó— antes de
  llamar a `seek()`. Además, todas las aperturas/cierres de audio pasan
  por una única cola con un solo hilo de trabajo persistente
  (`queue.Queue` + un hilo daemon), para que nunca haya dos operaciones
  nativas de audio ejecutándose en paralelo, sin importar qué tan rápido
  el usuario toque los botones de velocidad.
- **Botón "siguiente clase"**: `PlayerScreen` guarda la lista ordenada de
  grabaciones de la categoría actual (`_lista_categoria`) y su posición
  (`_indice_actual`) al cargar una clase, para poder saltar a la
  siguiente sin volver a consultar la base de datos ni pasar por
  `app.abrir_reproductor()` (eso hubiera alterado a dónde vuelve el botón
  "atrás"). Si es la última clase de la categoría, el botón no hace nada.
- **Se quitó el botón "Retroceder 5s"** a pedido explícito: los controles
  del reproductor quedaron en Saltar al inicio / Play-Pausa / Saltar a la
  siguiente clase, más el control de velocidad. La lógica correspondiente
  se eliminó de `audio_player.py` (`AudioEngine.rewind_5s`) y de
  `player_screen.py`/`.kv` (no queda código muerto).
- **Por qué el `MDTopAppBar` no quedaba pegado arriba, y la portada
  quedaba con un hueco enorme encima**: eran dos síntomas del mismo
  problema. Primero, el `padding` estaba puesto en el `BoxLayout` que
  envolvía TODO (appbar incluido), empujando el appbar hacia abajo — se
  solucionó separando el appbar en su propia fila sin padding, y metiendo
  el padding solo en un `BoxLayout` interno con el resto del contenido.
  Segundo (más sutil): en un `BoxLayout` vertical donde NINGÚN hijo usa
  `size_hint_y` flexible (todos tienen altura fija), si sobra espacio,
  Kivy lo deja arriba del primer hijo en vez de abajo del último — al
  revés de lo intuitivo. La solución estándar es agregar un `Widget:`
  (espaciador flexible) como ÚLTIMO hijo, que absorbe el espacio sobrante
  y deja los elementos de tamaño fijo pegados arriba, contra el appbar.
- **Manija (thumb) del `MDSlider` invisible**: en KivyMD 2.0, el círculo
  que marca la posición en el slider (`MDSliderHandle`) NO se agrega
  automáticamente — hay que declararlo a mano como hijo del `MDSlider` en
  el `.kv` (`MDSliderHandle: theme_bg_color: "Custom" md_bg_color: ...`).
  Sin eso, el slider funciona pero no muestra ninguna manija.
- **Pantalla de Login rediseñada para igualar el mockup**: fondo con
  degradado azul (bandas de color apiladas en `canvas.before`, sin usar
  una textura — es más simple de depurar), logo circular con ícono de
  micrófono, campos "píldora" translúcidos con ícono (implementados con
  `TextInput` simple en vez de `MDTextField`, para lograr el look exacto
  del mockup), botón de mostrar/ocultar contraseña, y botón "Iniciar
  Sesión" blanco. Los "cuadernos flotando" de fondo usan el ícono
  `notebook-outline` de Material Design Icons (empaquetado con KivyMD) en
  vez de un emoji: los emojis dependen de que el sistema operativo tenga
  una fuente de emojis instalada, y si no la tiene se ven como cajitas
  vacías (le pasó al usuario en Linux Mint).
