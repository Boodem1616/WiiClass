# Arquitectura de WiiClass: MVC y Programación Orientada a Objetos

Este documento muestra **dónde y cómo** se identifican el patrón MVC y los
conceptos de POO en el código actual. Cada afirmación apunta a un archivo, una
clase o una función real. Al final hay una sección de límites: lugares donde el
código se aparta del MVC "de manual".

---

## 1. MVC: visión general

| Capa | Responsabilidad | Dónde está |
|---|---|---|
| **Modelo** | Datos, reglas y servicios; no sabe nada de pantallas | `wiiclass/data/`, `wiiclass/services/`, y el estado de `ui/screens/notifications_state.py` |
| **Vista** | Qué se ve: estructura, estilos, colores | `wiiclass/ui/screens/*.kv`, `common.kv`, `ui/theme.py`, `widgets.py`, `notification_widgets.py`, `gradient_utils.py` |
| **Controlador** | Reacciona a lo que hace el usuario, consulta al modelo y actualiza la vista | Las clases `*Screen` / `*Tab` (`ui/screens/*.py`) y `WiiClassApp` (`app.py`) |

```
            ┌──────────────────────────── VISTA ────────────────────────────┐
            │  *.kv  (estructura y estilos)  ·  theme.py  ·  widgets.py     │
            └───────▲───────────────────────────────────────┬───────────────┘
   Properties/bind  │                                        │ on_release: root.metodo()
   (la vista se     │                                        ▼ (eventos del usuario)
   actualiza sola)  │        ┌──────────────── CONTROLADOR ─────────────────┐
                    └────────┤  LoginScreen, HomeTab, PlayerScreen, ...      │
                             │  WiiClassApp (navegación, sesión, conexión)   │
                             └───────────────────────┬───────────────────────┘
                                                     │ llama funciones / métodos
                                                     ▼
            ┌──────────────────────────── MODELO ───────────────────────────┐
            │  data/db.py · data/storage.py                                 │
            │  services/: audio_player · downloads_manager · recorder ·     │
            │  notification_service · remote_config · analytics · documentos│
            └───────────────────────────────────────────────────────────────┘
```

La dependencia va en un solo sentido: **Vista → Controlador → Modelo**. Los
módulos de `data/` no importan nada de `ui/` ni de Kivy; los de `services/`
usan Kivy solo en detalles puntuales (ver §4).

### 1.1 Vista

Cada pantalla tiene su `.kv` junto al `.py` con el mismo nombre
(`login_screen.kv` ↔ `login_screen.py`). El `.kv` declara la regla de la clase
(`<LoginScreen>:`, `<PlayerScreen>:`, `<ClaseRow>:`…) con sus widgets, tamaños
y colores. **Los colores vienen de `ui/theme.py`**, importado en cada `.kv` con
`#:import T wiiclass.ui.theme`, así que cambiar la paleta no toca los
controladores. `common.kv` concentra estilos compartidos.

Widgets reutilizables propios de la vista: `CabeceraDegradada` y `Waveform`
(`widgets.py`), `SwipeToDismissRow` (`notification_widgets.py`), `AnuncioCard`
(`home_tab.py`), `ClaseRow` y `ClaseRowSlot` (`category_screen.py`).

### 1.2 Controlador

Hay dos niveles:

1. **Controlador de pantalla** — una clase por pantalla (11 en total, todas
   heredan de `MDScreen`). Expone métodos que el `.kv` invoca y decide qué
   consultar al modelo.

   | En el `.kv` (Vista) | En el `.py` (Controlador) |
   |---|---|
   | `on_release: root.iniciar_sesion()` | `LoginScreen.iniciar_sesion()` valida, llama `db.login(...)` y avisa a la app |
   | `on_release: root.confirmar_limpiar()` | `NotificationsTab.confirmar_limpiar()` |
   | `on_release: root.descargar_seleccionadas()` | `CategoryScreen.descargar_seleccionadas()` |
   | `on_release: root.toggle_password_visibility()` | `LoginScreen.toggle_password_visibility()` |

2. **Controlador de aplicación** — `WiiClassApp(MDApp)` en `app.py`. Crea el
   `ScreenManager`, registra las pantallas, y concentra lo que atraviesa toda la
   app: navegación (`abrir_categoria`, `abrir_reproductor`,
   `abrir_todas_notificaciones`, `abrir_config_remota`), sesión
   (`on_login_success`, `cerrar_sesion`) y ciclo de vida (`on_pause`,
   `on_resume`, `on_stop`). Las pantallas lo invocan desde el `.kv` como
   `app.abrir_reproductor(...)`.

### 1.3 Modelo

- **`data/db.py`** — esquema SQLite y consultas como funciones
  (`login`, `get_categorias`, `get_grabaciones_por_categoria`,
  `get_notificaciones`, `crear_notificacion`, …). Devuelve `sqlite3.Row`.
- **`data/storage.py`** — persistencia en JSON (sesión, respaldos,
  notificaciones ocultas, caché de configuración remota).
- **`services/`** — lógica de negocio y acceso a recursos externos, sin
  pantallas: reproducir audio, descargar, grabar, notificar, leer
  configuración remota, registrar analíticas, guardar en Documentos.

### 1.4 Flujo completo de ejemplo: iniciar sesión

```
Usuario toca "Iniciar Sesión"
   │  login_screen.kv:  on_release: root.iniciar_sesion()                [Vista → Controlador]
   ▼
LoginScreen.iniciar_sesion()                                              [Controlador]
   │  valida campos → db.login(institucion, correo, password, rol)       [→ Modelo]
   ▼
WiiClassApp.on_login_success(usuario_id)                                  [Controlador de app]
   │  db.get_usuario · notificaciones_state.activar · analytics ...      [→ Modelo]
   │  sm.current = "main"                                                 [cambia la Vista]
   ▼
MainScreen muestra las pestañas según el rol (tabs_para_rol)              [Vista]
```

### 1.5 Flujo de ejemplo: reproducir (la Vista reacciona sola)

`PlayerScreen` se suscribe al modelo con
`audio_engine.bind(is_playing=..., is_loading=...)`. Cuando el motor de audio
cambia de estado (aunque sea desde un hilo de carga), la pantalla se entera y
actualiza el ícono de play/pausa. El controlador **no asume** el estado: lo
refleja. Es el mecanismo de **Observer** que une Modelo y Vista (ver §3.3).

---

## 2. POO en el código

### 2.1 Clases del proyecto

| Capa | Clases |
|---|---|
| App | `WiiClassApp` |
| Controladores / pantallas | `LoginScreen`, `MainScreen`, `HomeTab`, `CategoryScreen`, `PlayerScreen`, `NotificationsTab`, `NotificationsAllScreen`, `ProfileTab`, `DownloadsTab`, `RecordingTab`, `RemoteConfigScreen` |
| Widgets (Vista) | `CabeceraDegradada`, `Waveform`, `SwipeToDismissRow`, `AnuncioCard`, `ClaseRow`, `ClaseRowSlot` |
| Modelo (servicios) | `AudioEngine`, `RemoteConfig`, `NotificationService`, `DesktopRecorder`, `AndroidRecorder` |
| Modelo (estado) | `NotificacionesState` |
| Estrategias de notificación | `_Backend`, `AndroidBackend`, `DesktopBackend`, `_NullBackend` |
| Excepciones | `DocumentosError`, `PermisoDenegadoError`, `DescargaError`, `RecorderError`, `_SinCambios` |

`db.py`, `storage.py`, `analytics.py`, `documentos.py` y `downloads_manager.py`
están escritos como **módulos con funciones**, no como clases (ver §4).

### 2.2 Herencia

- **Frameworks:** `WiiClassApp(MDApp)`; las 11 pantallas heredan de `MDScreen`;
  `AudioEngine(EventDispatcher)` hereda el sistema de eventos y propiedades de
  Kivy.
- **Herencia múltiple como mixin:** `ClaseRow(ButtonBehavior, BoxLayout)` suma
  el comportamiento de "botón" (`on_release`) a un contenedor.
- **Jerarquía propia de backends:** `_Backend` define la interfaz;
  `AndroidBackend`, `DesktopBackend` y `_NullBackend` la implementan.
- **Jerarquía de excepciones:** `PermisoDenegadoError(DocumentosError)`, para
  poder capturar el caso específico o toda la familia.

### 2.3 Polimorfismo

`NotificationService` llama `self._backend.mostrar(id, titulo, mensaje)` sin
saber qué backend tiene: en Android publica una notificación nativa, en
escritorio muestra un aviso en pantalla, y `_NullBackend` no hace nada. La
elección se hace una sola vez en `_crear_backend()` según la plataforma.

`DesktopRecorder` y `AndroidRecorder` exponen los mismos métodos (`iniciar`,
`detener`) y `recording_tab.py` los usa igual; es **polimorfismo por
duck-typing** (no comparten clase base). `crear_grabadora()` devuelve la que
corresponde.

### 2.4 Encapsulamiento y abstracción

- Los detalles internos llevan guion bajo (`_backend`, `_recientes`,
  `_suscriptores`, `_lock`, `_etag`) y se accede a ellos solo por la API
  pública: `NotificationService.show_login_welcome / show_download_complete /
  show_recording_complete`, `RemoteConfig.get / funcion_activa / suscribir /
  actualizar`.
- `AudioEngine` oculta el proveedor de audio (`SoundLoader`, `ffpyplayer`) tras
  una interfaz simple: `load`, `play`, `pause`, `toggle_play_pause`, `seek`,
  `seek_relativo`, `set_speed`, `stop`. La pantalla no sabe cómo se decodifica.
- `RemoteConfig` protege su estado compartido con un `RLock`, porque se
  actualiza desde un hilo de fondo.

### 2.5 Composición

- `MainScreen` **contiene** las pestañas (`HomeTab`, `DownloadsTab`,
  `RecordingTab`, `NotificationsTab`, `ProfileTab`) y las construye según el rol.
- `ClaseRowSlot` **envuelve** una `ClaseRow` y le agrega el botón de descarga
  (documentado en su docstring: un `BoxLayout` no permite anclar hijos con
  `pos_hint`).
- `NotificationService` **tiene un** `_backend`; `PlayerScreen` **usa** el
  `audio_engine`.

### 2.6 Inyección de dependencias

Los servicios reciben sus dependencias por constructor en lugar de crearlas
adentro, lo que permite sustituirlas en las pruebas:

```python
NotificationService(backend=..., ventana_dedupe=..., reloj=..., habilitado=...)
RemoteConfig(cargar_cache=..., guardar_cache=...)
```

La instancia real se arma en un solo lugar (`notificaciones = NotificationService(
habilitado=_interruptor_remoto)`, `_crear_global()`), y los tests inyectan
backends y relojes falsos (ver `tests/`). Por eso la lógica de notificaciones y
configuración remota se prueba **sin Kivy**.

---

## 3. Patrones de diseño presentes

### 3.1 Singleton (instancia única por módulo)

Una instancia creada al importar el módulo y compartida por toda la app:
`audio_engine` (`audio_player.py`), `notificaciones` (`notification_service.py`),
`config_remota` (`remote_config.py`), `notificaciones_state`
(`notifications_state.py`). Es la forma idiomática en Python: el propio sistema
de módulos garantiza que haya una sola.

### 3.2 Strategy + Null Object

Los backends de notificación son estrategias intercambiables elegidas por
plataforma; `_NullBackend` es el **objeto nulo** que evita `if backend is None`
cuando el nativo no pudo iniciarse.

### 3.3 Observer

- **Propiedades de Kivy:** `AudioEngine` declara `position`, `duration`,
  `is_playing`, `is_loading`, `speed`, `source` como `NumericProperty` /
  `BooleanProperty` / `StringProperty`; `PlayerScreen` se suscribe con `bind`.
  Lo mismo hacen las pantallas con sus propias propiedades (`grabando`,
  `tiempo_txt`, `modo_seleccion`, `rol_seleccionado`…) que el `.kv` enlaza a la
  vista.
- **Suscripción explícita:** `config_remota.suscribir(fn)` notifica a
  `WiiClassApp._on_config_remota` cuando cambia la configuración remota.

### 3.4 Factory (funciones fábrica)

`crear_grabadora()`, `_crear_backend()` y `_crear_global()` deciden qué objeto
construir según plataforma o disponibilidad, y ocultan esa decisión a quien lo
usa.

---

## 4. Límites y desviaciones del MVC "puro"

Es mejor tenerlos identificados que ignorarlos:

1. **El modelo es funcional, no de entidades.** No existen clases `Usuario`,
   `Grabacion` o `Notificacion`: `db.py` devuelve `sqlite3.Row` y los
   controladores acceden por nombre de columna. La POO está más presente en los
   servicios y la interfaz que en los datos.
2. **Los controladores llaman a `db` directamente.** No hay capa intermedia
   (repositorio): pantallas como `CategoryScreen`, `PlayerScreen` o `HomeTab`
   importan `db`. Es simple y legible, pero acopla el controlador al esquema.
3. **Algunos controladores construyen widgets en Python.** `CategoryScreen`
   crea filas (`ClaseRow`, `ClaseRowSlot`) y `remote_config_screen.py` arma
   filas por código, en vez de declararlas por completo en el `.kv`; la
   frontera Vista/Controlador es difusa en esos puntos.
4. **`WiiClassApp` concentra mucho.** Es a la vez `App`, router de pantallas,
   dueña de la sesión y vigía de conectividad. Es el candidato natural a
   dividirse si la app crece.
5. **`NotificacionesState` vive en `ui/`** aunque es estado del modelo (no
   depende de Kivy; solo de `db` y `storage`). Está junto a las pantallas que lo
   comparten.
6. **Los servicios no son 100 % independientes de Kivy.** `audio_player.py`
   usa `EventDispatcher` y las propiedades de Kivy (a propósito, para el
   Observer), y varios servicios usan `Clock` o `platform`. Además,
   `DesktopBackend` (en `notification_service.py`) importa
   `wiiclass.ui.screens.widgets.mostrar_aviso` para mostrar el aviso: es la
   **única referencia del modelo hacia la vista**, y está hecha dentro de la
   función (import perezoso) para no acoplar el módulo al cargar.
7. **Los grabadores no comparten clase base.** `DesktopRecorder` y
   `AndroidRecorder` son polimórficos solo por convención de nombres; una clase
   base abstracta (`abc.ABC`) haría explícito el contrato, como ya ocurre con
   `_Backend`.

Ninguno impide el funcionamiento ni la lectura; son los primeros puntos a
revisar si se quiere acercar el código a un MVC estricto.

---

## 5. Guía: agregar una pantalla respetando la arquitectura

1. **Modelo:** si necesita datos nuevos, agregar la consulta en `data/db.py`
   (o un servicio en `services/` si hay lógica o recursos externos).
2. **Vista:** crear `ui/screens/mi_pantalla.kv` con la regla `<MiPantalla>:`,
   importando el tema con `#:import T wiiclass.ui.theme` y usando `T.` para
   colores.
3. **Controlador:** crear `ui/screens/mi_pantalla.py` con
   `class MiPantalla(MDScreen)`, cargar su `.kv` con `Builder.load_file(...)`,
   declarar sus `Property` de estado y los métodos que el `.kv` invocará
   (`on_release: root.metodo()`).
4. **Registro y navegación:** instanciarla en `WiiClassApp.build()`
   (`self.sm.add_widget(...)`) y, si se abre desde otras pantallas, agregar un
   método `abrir_mi_pantalla()` en `app.py` junto a los existentes.
5. **Pruebas:** la lógica que no dependa de Kivy debe quedar en `data/` o
   `services/`, donde se prueba con `unittest` sin interfaz.

---

## 6. Resumen

| Concepto | Dónde verlo |
|---|---|
| MVC — Vista | `ui/screens/*.kv`, `ui/theme.py`, `widgets.py` |
| MVC — Controlador | `*Screen` / `*Tab`, `WiiClassApp` |
| MVC — Modelo | `data/`, `services/` |
| Herencia | `MDScreen`, `MDApp`, `EventDispatcher`, `_Backend` → 3 backends, jerarquía de excepciones |
| Herencia múltiple (mixin) | `ClaseRow(ButtonBehavior, BoxLayout)` |
| Polimorfismo | `_Backend.mostrar`; `DesktopRecorder` / `AndroidRecorder` |
| Encapsulamiento | atributos `_privados` + API pública en `NotificationService`, `RemoteConfig`, `AudioEngine` |
| Composición | `MainScreen` + pestañas, `ClaseRowSlot` + `ClaseRow`, servicio + backend |
| Inyección de dependencias | `NotificationService(...)`, `RemoteConfig(...)` |
| Singleton | `audio_engine`, `notificaciones`, `config_remota`, `notificaciones_state` |
| Observer | Propiedades de Kivy + `bind`; `config_remota.suscribir` |
| Factory / Strategy / Null Object | `crear_grabadora`, `_crear_backend`; backends; `_NullBackend` |
