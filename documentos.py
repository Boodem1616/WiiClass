"""
documentos.py — Guarda archivos en la carpeta "Documentos" del usuario.

Una sola función pública para la app:

    ubicacion = guardar_en_documentos("/ruta/clase.mp3", "Clase 1.mp3")

La carpeta se detecta SIEMPRE en tiempo de ejecución (nunca hay rutas fijas):

  Windows  -> SHGetKnownFolderPath(FOLDERID_Documents). Respeta Documentos
              redirigido a OneDrive o a otro disco y nombres localizados.
  macOS    -> ~/Documents
  Linux    -> XDG_DOCUMENTS_DIR de ~/.config/user-dirs.dirs (en un sistema en
              español suele ser ~/Documentos); si no existe, ~/Documents.
  Android  -> API 29+ (Android 10+): MediaStore.Files con RELATIVE_PATH
              "Documents/WiiClass". No necesita permisos de almacenamiento
              (scoped storage: la app escribe sus propios archivos).
              API 24-28: carpeta pública Documents + permiso
              WRITE_EXTERNAL_STORAGE (se pide en tiempo de ejecución).
  iOS      -> Documents del sandbox de la app (iOS no permite escribir en
              ningún otro lugar). Se ve en la app Archivos si Info.plist tiene
              UIFileSharingEnabled y LSSupportsOpeningDocumentsInPlace
              (ver DESCARGAS-DOCUMENTOS.md y scripts/ios_habilitar_archivos.py).

Para pruebas o instalaciones portables se puede forzar la carpeta con la
variable de entorno WIICLASS_DOCUMENTOS_DIR (solo escritorio).

Este módulo NO importa Kivy. Las partes de Android importan `jnius` y
`android.permissions` solo cuando se ejecutan en Android.
"""

import mimetypes
import os
import re
import shutil
import sys

SUBCARPETA = "WiiClass"
ENV_CARPETA = "WIICLASS_DOCUMENTOS_DIR"


class DocumentosError(Exception):
    """No se pudo guardar el archivo. El mensaje es apto para el usuario."""


class PermisoDenegadoError(DocumentosError):
    """El usuario no concedió el permiso de escritura (solo Android 9-)."""


# ---------------------------------------------------------------------------
# Plataforma
# ---------------------------------------------------------------------------
def plataforma() -> str:
    """'android' | 'ios' | 'windows' | 'macos' | 'linux'."""
    if "ANDROID_ARGUMENT" in os.environ or "ANDROID_PRIVATE" in os.environ:
        return "android"
    # kivy-ios (Python 3.11) reporta sys.platform == "darwin" y marca
    # KIVY_BUILD=ios; CPython 3.13+ para iOS reporta "ios".
    if sys.platform == "ios" or os.environ.get("KIVY_BUILD") == "ios":
        return "ios"
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


# ---------------------------------------------------------------------------
# Carpeta Documentos (escritorio / iOS)
# ---------------------------------------------------------------------------
def _hogar() -> str:
    return os.path.expanduser("~")


def _windows_documentos() -> str:
    import ctypes
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    # FOLDERID_Documents = {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
    folderid = GUID(0xFDD39AD0, 0x238F, 0x46AF,
                    (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7))
    ruta = ctypes.c_wchar_p()
    shell32 = ctypes.windll.shell32
    shell32.SHGetKnownFolderPath.argtypes = [
        ctypes.POINTER(GUID), wintypes.DWORD, wintypes.HANDLE,
        ctypes.POINTER(ctypes.c_wchar_p),
    ]
    shell32.SHGetKnownFolderPath.restype = ctypes.c_long
    try:
        if shell32.SHGetKnownFolderPath(ctypes.byref(folderid), 0, None, ctypes.byref(ruta)) != 0:
            raise OSError("SHGetKnownFolderPath falló")
        return ruta.value
    finally:
        ctypes.windll.ole32.CoTaskMemFree(ruta)


def _linux_documentos() -> str:
    home = _hogar()
    conf = os.environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
    try:
        with open(os.path.join(conf, "user-dirs.dirs"), encoding="utf-8") as f:
            for linea in f:
                m = re.match(r'\s*XDG_DOCUMENTS_DIR\s*=\s*"?([^"\n]*)"?', linea)
                if not m:
                    continue
                valor = os.path.normpath(m.group(1).strip().replace("$HOME", home))
                # XDG usa "$HOME/" para indicar "carpeta desactivada".
                if valor and valor != os.path.normpath(home):
                    return valor
    except OSError:
        pass
    return os.path.join(home, "Documents")


def carpeta_documentos() -> str:
    """Ruta de la carpeta Documentos de este equipo (no se crea)."""
    forzada = os.environ.get(ENV_CARPETA)
    if forzada:
        return os.path.abspath(os.path.expanduser(forzada))
    plat = plataforma()
    if plat == "windows":
        try:
            return _windows_documentos()
        except Exception:
            return os.path.join(_hogar(), "Documents")
    if plat == "linux":
        return _linux_documentos()
    if plat == "android":
        return _android_documentos_publica()
    # macOS e iOS: ~/Documents (en iOS, HOME es el contenedor de la app).
    return os.path.join(_hogar(), "Documents")


def descripcion_destino(subcarpeta: str = SUBCARPETA) -> str:
    """Texto corto para mostrar al usuario dónde quedan los audios."""
    if plataforma() == "android":
        return f"Documents/{subcarpeta}"
    return os.path.join(carpeta_documentos(), subcarpeta)


# ---------------------------------------------------------------------------
# Nombres de archivo
# ---------------------------------------------------------------------------
_INVALIDOS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVADOS_WIN = {"CON", "PRN", "AUX", "NUL",
                   *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def nombre_seguro(nombre: str, defecto: str = "audio", maximo: int = 120) -> str:
    """Nombre válido en Windows, macOS, Linux y Android (sin rutas ni
    caracteres reservados, sin puntos/espacios finales, largo acotado)."""
    # Es un NOMBRE, no una ruta: los separadores se reemplazan (no se recorta a
    # lo que haya tras la última "/"), así "Clase 1/2" -> "Clase 1_2" y
    # "../x" no puede salir de la carpeta.
    nombre = _INVALIDOS.sub("_", str(nombre or "")).strip(" .")
    base, ext = os.path.splitext(nombre)
    base = base.strip(" .")[: max(1, maximo - len(ext))]
    if not base:
        base = defecto
    if base.upper() in _RESERVADOS_WIN:
        base = "_" + base
    return base + ext


def _nombre_unico(carpeta: str, nombre: str) -> str:
    """Si `nombre` ya existe devuelve 'nombre (1).ext', 'nombre (2).ext'..."""
    base, ext = os.path.splitext(nombre)
    candidato, n = nombre, 1
    while os.path.exists(os.path.join(carpeta, candidato)):
        candidato = f"{base} ({n}){ext}"
        n += 1
    return candidato


def _mime(nombre: str) -> str:
    return mimetypes.guess_type(nombre)[0] or "application/octet-stream"


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------
def guardar_en_documentos(origen: str, nombre: str = None,
                          subcarpeta: str = SUBCARPETA) -> str:
    """Copia `origen` a Documentos/<subcarpeta>/<nombre> y devuelve dónde
    quedó (ruta en escritorio/iOS; 'Documents/<subcarpeta>/<nombre>' en
    Android). Nunca pisa un archivo existente: agrega ' (1)', ' (2)'...

    Es bloqueante: llamar desde un hilo de fondo, no desde el hilo de la UI.
    Lanza `DocumentosError` (o `PermisoDenegadoError`) con mensaje legible.
    """
    if not origen or not os.path.isfile(origen):
        raise DocumentosError("No se encontró el archivo a guardar.")
    nombre = nombre_seguro(nombre or os.path.basename(origen))
    subcarpeta = nombre_seguro(subcarpeta, "WiiClass")

    if plataforma() == "android":
        return _guardar_android(origen, nombre, subcarpeta)
    return _guardar_en_carpeta(origen, nombre, subcarpeta)


def _guardar_en_carpeta(origen: str, nombre: str, subcarpeta: str) -> str:
    """Escritorio e iOS: copia atómica (archivo .part + os.replace)."""
    carpeta = os.path.join(carpeta_documentos(), subcarpeta)
    try:
        os.makedirs(carpeta, exist_ok=True)
        nombre = _nombre_unico(carpeta, nombre)
        destino = os.path.join(carpeta, nombre)
        tmp = destino + ".part"
        try:
            shutil.copyfile(origen, tmp)
            os.replace(tmp, destino)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
    except PermissionError as exc:
        raise DocumentosError("Sin permiso para escribir en la carpeta Documentos.") from exc
    except OSError as exc:
        raise DocumentosError(f"No se pudo guardar en Documentos: {exc.strerror or exc}") from exc
    return destino


# ---------------------------------------------------------------------------
# Android
# ---------------------------------------------------------------------------
def _sdk_android() -> int:
    from jnius import autoclass
    return int(autoclass("android.os.Build$VERSION").SDK_INT)


def _android_documentos_publica() -> str:
    from jnius import autoclass
    Environment = autoclass("android.os.Environment")
    return Environment.getExternalStoragePublicDirectory(
        Environment.DIRECTORY_DOCUMENTS).getAbsolutePath()


def necesita_permiso_escritura() -> bool:
    """True solo en Android 9 o menor y mientras el permiso no esté concedido.
    En Android 10+ y en el resto de plataformas siempre es False."""
    if plataforma() != "android":
        return False
    try:
        if _sdk_android() >= 29:
            return False
        from android.permissions import Permission, check_permission
        return not check_permission(Permission.WRITE_EXTERNAL_STORAGE)
    except Exception:
        return False


def pedir_permiso_escritura(callback):
    """Pide WRITE_EXTERNAL_STORAGE si hace falta. `callback(concedido: bool)`
    se llama al responder el usuario (puede ocurrir fuera del hilo de Kivy)."""
    if not necesita_permiso_escritura():
        callback(True)
        return
    from android.permissions import Permission, request_permissions

    def _resp(permisos, resultados):
        callback(bool(resultados) and all(resultados))

    request_permissions([Permission.WRITE_EXTERNAL_STORAGE], _resp)


def _guardar_android(origen: str, nombre: str, subcarpeta: str) -> str:
    try:
        sdk = _sdk_android()
    except Exception as exc:
        raise DocumentosError("No se pudo acceder a las APIs de Android.") from exc
    if sdk >= 29:
        return _guardar_mediastore(origen, nombre, subcarpeta)
    return _guardar_android_legacy(origen, nombre, subcarpeta)


def _guardar_android_legacy(origen: str, nombre: str, subcarpeta: str) -> str:
    """Android 9 y menor: carpeta pública Documents + WRITE_EXTERNAL_STORAGE."""
    if necesita_permiso_escritura():
        raise PermisoDenegadoError("Falta el permiso para guardar en Documentos.")
    try:
        carpeta = os.path.join(_android_documentos_publica(), subcarpeta)
        os.makedirs(carpeta, exist_ok=True)
        nombre = _nombre_unico(carpeta, nombre)
        destino = os.path.join(carpeta, nombre)
        shutil.copyfile(origen, destino)
    except OSError as exc:
        raise DocumentosError(f"No se pudo guardar en Documentos: {exc.strerror or exc}") from exc
    return f"Documents/{subcarpeta}/{nombre}"


def _guardar_mediastore(origen: str, nombre: str, subcarpeta: str) -> str:
    """Android 10+: inserta el archivo en MediaStore.Files bajo
    Documents/<subcarpeta>. Con IS_PENDING=1 mientras se escribe, para que
    ninguna otra app vea un archivo a medias. MediaStore resuelve solo los
    nombres repetidos ('nombre (1).ext')."""
    from jnius import autoclass

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Environment = autoclass("android.os.Environment")
    MediaStoreFiles = autoclass("android.provider.MediaStore$Files")
    MediaColumns = autoclass("android.provider.MediaStore$MediaColumns")
    ContentValues = autoclass("android.content.ContentValues")
    Integer = autoclass("java.lang.Integer")
    File = autoclass("java.io.File")
    Files = autoclass("java.nio.file.Files")  # API 26+ (aquí siempre >= 29)

    resolver = PythonActivity.mActivity.getContentResolver()
    coleccion = MediaStoreFiles.getContentUri("external_primary")
    relativo = f"{Environment.DIRECTORY_DOCUMENTS}/{subcarpeta}"

    def insertar(mime):
        v = ContentValues()
        v.put(MediaColumns.DISPLAY_NAME, nombre)
        v.put(MediaColumns.MIME_TYPE, mime)
        v.put(MediaColumns.RELATIVE_PATH, relativo)
        v.put(MediaColumns.IS_PENDING, Integer(1))
        return resolver.insert(coleccion, v)

    uri = None
    try:
        # Algunas versiones rechazan un MIME de audio fuera de las carpetas
        # de música: si ocurre, se reintenta como archivo genérico.
        try:
            uri = insertar(_mime(nombre))
        except Exception:
            uri = None
        if uri is None:
            uri = insertar("application/octet-stream")
        if uri is None:
            raise DocumentosError("Android rechazó crear el archivo en Documentos.")

        salida = resolver.openOutputStream(uri)
        if salida is None:
            raise DocumentosError("Android no permitió abrir el archivo de destino.")
        try:
            # Copia del lado de Java: sin buffers de bytes en Python.
            Files.copy(File(origen).toPath(), salida)
            salida.flush()
        finally:
            salida.close()

        listo = ContentValues()
        listo.put(MediaColumns.IS_PENDING, Integer(0))
        resolver.update(uri, listo, None, None)
    except DocumentosError:
        _borrar_uri(resolver, uri)
        raise
    except Exception as exc:
        _borrar_uri(resolver, uri)
        raise DocumentosError("No se pudo guardar en Documentos.") from exc
    return f"{relativo}/{nombre}"


def _borrar_uri(resolver, uri):
    if uri is None:
        return
    try:
        resolver.delete(uri, None, None)
    except Exception:
        pass
