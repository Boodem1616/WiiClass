# Descargas a Documentos + empaquetado con Buildozer

Qué agrega esta entrega a WiiClass:

1. **Descarga real de audio por URL** (http/https) con progreso, validaciones y
   error legible.
2. **Copia automática en la carpeta Documentos** del usuario, detectada en
   tiempo de ejecución en Windows, macOS, Linux, Android e iOS.
3. **`buildozer.spec`** listo para generar el APK de Android, y un script para
   dejar lista la carpeta en la app *Archivos* de iOS.

> **Sobre el nombre "Bulldozer":** la herramienta que empaqueta apps Kivy para
> Android/iOS se llama **Buildozer**. Este documento asume que te referías a esa.

## Decisión de stack: se mantiene Kivy + KivyMD + Buildozer

WiiClass ya es una app Kivy/KivyMD completa (login, roles, reproductor,
grabación, notificaciones, persistencia). Buildozer es justamente la
herramienta oficial de Kivy, así que:

| Opción | Veredicto |
|---|---|
| **Kivy + KivyMD + Buildozer** (actual) | **Se conserva.** Un solo código Python para escritorio y móvil, sin reescribir nada. |
| Electron/Tauri + React Native/Capacitor | Obligaría a reescribir toda la interfaz y la lógica en otro lenguaje. |
| Flutter | Excelente stack, pero también es una reescritura completa. |

No se crea una carpeta `bulldozer-app` nueva: el proyecto existente **es** la
carpeta de trabajo (`WiiClass/`), y duplicarlo solo generaría dos copias
divergentes.

## Estructura (lo nuevo está marcado)

```
WiiClass/
├── buildozer.spec                  ★ configuración de Buildozer (Android; iOS comentado)
├── documentos.py                   ★ carpeta Documentos por plataforma + guardado
├── downloads_manager.py            ✎ descarga HTTP real + copia a Documentos
├── DESCARGAS-DOCUMENTOS.md         ★ este documento
├── scripts/
│   └── ios_habilitar_archivos.py   ★ claves de Info.plist para la app Archivos
├── screens/category_screen.py      ✎ feedback: progreso, dónde se guardó, errores
├── tests/
│   ├── test_documentos.py          ★ 25 pruebas
│   ├── test_descarga_remota.py     ★ 18 pruebas (servidor HTTP local real)
│   └── test_ios_plist.py           ★ 3 pruebas
├── requirements.txt                ✎ + certifi
├── main.py, db.py, storage.py, recorder.py, audio_player.py, …   (sin cambios)
├── assets/ screens/ datos/ …
└── descargas/                      copia privada de la app (reproducción offline)
```

## Dónde quedan los audios

| Plataforma | Destino | Permiso |
|---|---|---|
| **Windows** | `Documentos\WiiClass\` (vía `SHGetKnownFolderPath`; respeta OneDrive/otro disco) | Ninguno |
| **macOS** | `~/Documents/WiiClass/` | Ninguno |
| **Linux** | `XDG_DOCUMENTS_DIR` (p. ej. `~/Documentos/WiiClass/` en español); respaldo `~/Documents` | Ninguno |
| **Android 10+** | `Documents/WiiClass/` vía **MediaStore** (scoped storage) | **Ninguno** |
| **Android 7–9** | `Documents/WiiClass/` (carpeta pública) | `WRITE_EXTERNAL_STORAGE`, se pide al descargar |
| **iOS** | `Documents/WiiClass/` **dentro del sandbox de la app** | Ninguno |

Además, la app conserva siempre su **copia privada** en `descargas/` (en Android,
`<almacenamiento privado>/descargas`). Es la que usa el reproductor, así que
reproducir offline nunca depende de permisos ni de scoped storage. Si el
guardado en Documentos falla, la descarga **no** se pierde: la clase sigue
disponible en la app y se avisa al usuario.

### iOS: por qué no se escribe en "Documentos" del sistema

iOS no permite que una app escriba fuera de su sandbox. La alternativa
correcta es guardar en el `Documents` **de la app** y hacerlo visible en la
app *Archivos* con dos claves de `Info.plist`: `UIFileSharingEnabled` y
`LSSupportsOpeningDocumentsInPlace`. Buildozer no ofrece opciones para el
`Info.plist`, por eso existe `scripts/ios_habilitar_archivos.py`. El usuario
verá los audios en *Archivos → En mi iPhone → WiiClass → WiiClass*.

## Cómo ejecutar

### Escritorio (Windows / macOS / Linux)

```bash
python3 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python3 main.py
```

Para ver la descarga real sin servidor propio, ejecuta en otra terminal:

```bash
python3 -m http.server 8000 --directory assets/audio
```

y asigna a una grabación la URL `http://localhost:8000/clase1.mp3` en la tabla
`Grabaciones.url_audio`. Al pulsar descargar, el audio aparece en
`Documentos/WiiClass/`.

Variables de entorno opcionales:

| Variable | Efecto |
|---|---|
| `WIICLASS_GUARDAR_EN_DOCUMENTOS=0` | Desactiva la copia a Documentos |
| `WIICLASS_DOCUMENTOS_DIR=/otra/ruta` | Fuerza la carpeta (escritorio): pruebas / instalaciones portables |

### Android (Linux, macOS o Windows con WSL2)

Buildozer **no** corre en Windows nativo: usa WSL2 (Ubuntu).

```bash
# 1. Dependencias del sistema (Ubuntu/WSL)
sudo apt update && sudo apt install -y git zip unzip openjdk-17-jdk python3-pip \
  autoconf libtool pkg-config zlib1g-dev libncurses-dev cmake libffi-dev libssl-dev

# 2. Buildozer
pip install buildozer cython==0.29.34 setuptools legacy-cgi

# 3. Compilar (la primera vez descarga SDK/NDK y compila ffmpeg: 30–60+ min)
cd WiiClass
buildozer android debug

# 4. Instalar y ver logs (teléfono con depuración USB)
buildozer android deploy run logcat
```

El APK queda en `bin/`. Antes de publicar, cambia `package.domain` en el spec.

### iOS (solo macOS + Xcode)

```bash
pip install buildozer kivy-ios
buildozer ios debug                         # genera el proyecto de Xcode
python3 scripts/ios_habilitar_archivos.py   # agrega las claves a Info.plist
buildozer ios xcode                         # abre Xcode: firma con tu Apple ID y ejecuta
```

## Pruebas

```bash
pip install pytest
python3 -m pytest -q tests          # 117 pruebas, no requieren Kivy
```

## Verificación: qué está comprobado y qué no

**Comprobado automáticamente (en Linux):**

- Detección de Documentos en Linux (incluida una carpeta `Documentos` en
  español), macOS e iOS; nombres seguros; no pisar archivos; copia atómica.
- Descarga HTTP real contra un servidor local: progreso, nombre por
  `Content-Disposition`, rechazo de HTML/404/archivos cortados/vacíos/demasiado
  grandes/esquemas no http(s), sin archivos `.part` residuales.
- Flujo completo con la base de datos: copia privada + copia en Documentos,
  descarga múltiple que continúa tras un error, el fallo de Documentos no
  rompe la descarga.
- `buildozer.spec` se interpreta sin errores ni claves desconocidas con
  Buildozer 1.6.0.
- Las 71 pruebas que ya existían siguen pasando.

**NO comprobado (necesita un dispositivo o sistema real):**

- **Ninguna build de APK/IPA se ejecutó**: el entorno donde se desarrolló esto
  no puede descargar el SDK/NDK de Android. Es posible que la primera build
  requiera ajustar versiones (NDK, receta de KivyMD/materialyoucolor).
- **El código de Android usa un `jnius` simulado en las pruebas**: valida el
  flujo (IS_PENDING, copia, reintento, limpieza), no que Android acepte cada
  llamada. Hay que probarlo en un teléfono, idealmente uno con Android 10+ y
  otro con Android 9 o menos.
- **Windows**: la llamada a `SHGetKnownFolderPath` no se pudo ejecutar fuera
  de Windows (las pruebas simulan su resultado y su fallo).
- **iOS**: el guardado y el script del plist están probados, pero **la app
  completa todavía no está portada a iOS**: `db.py` y `storage.py` escriben
  junto al código (en iOS el paquete es de solo lectura) y `recorder.py` no
  tiene backend para iOS. Hay que moverlos a `~/Library/Application Support`
  antes de ejecutar la app en un iPhone.
- Empaquetado de escritorio como instalador (`.exe`, `.dmg`): Buildozer no lo
  cubre; se haría con PyInstaller u otra herramienta.

## Checklist de aceptación en dispositivo

- [ ] Android 10+: descargar una clase → aparece en *Archivos → Documentos → WiiClass* sin pedir permisos.
- [ ] Android 9 o menor: el sistema pide permiso de almacenamiento y luego guarda.
- [ ] Android: denegar el permiso (9-) → la clase igual se reproduce offline y se muestra el aviso.
- [ ] Descargar dos veces el mismo audio → no se pisa (`Clase (1).mp3`).
- [ ] URL que devuelve una página web → mensaje de error, sin archivo guardado.
- [ ] iOS: el audio aparece en *Archivos → En mi iPhone → WiiClass*.
- [ ] Desktop Windows: aparece en la carpeta Documentos real (aunque esté en OneDrive).
