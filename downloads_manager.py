"""
downloads_manager.py — Descarga de una grabación para reproducirla offline y
copia en la carpeta Documentos del usuario.

Flujo de `descargar_grabacion`:

  1. ORIGEN. Si `Grabaciones.url_audio` es http(s) se descarga de verdad (con
     progreso). Si es una ruta local (los audios de ejemplo de `assets/audio/`
     y las grabaciones del profesor) se copia, como siempre.
  2. COPIA PRIVADA en `descargas/` (carpeta privada de la app) y registro en
     `Descargas_offline`. Es la que usa el reproductor: siempre es una ruta de
     archivo normal, sin depender de permisos ni de scoped storage.
  3. COPIA EN DOCUMENTOS (`documentos.guardar_en_documentos`). Es el archivo
     "del usuario": lo ve en su explorador de archivos / app Archivos.
     Si este paso falla la descarga NO se considera fallida (la clase sigue
     disponible offline dentro de la app); se avisa por `on_aviso`.
     Se puede desactivar con WIICLASS_GUARDAR_EN_DOCUMENTOS=0.

Todo el trabajo de red y de disco ocurre en un hilo de fondo; los callbacks se
ejecutan en el hilo principal de Kivy (si Kivy no está instalado, por ejemplo
en las pruebas, se ejecutan directamente).

Callbacks (todos opcionales salvo que se indique):
    on_completa(grabacion_id)
    on_error(grabacion_id, exc)
    on_progreso(grabacion_id, bytes_hechos, bytes_totales | None)   # solo URL
    on_aviso(grabacion_id, texto)   # info o problema no fatal (p. ej. Documentos)
"""

import email.message
import mimetypes
import os
import shutil
import ssl
import threading
import urllib.error
import urllib.request
from urllib.parse import unquote, urlparse

import db
import documentos

try:
    from kivy.clock import Clock

    def _en_principal(fn):
        Clock.schedule_once(lambda dt: fn())
except ImportError:  # pruebas / uso sin interfaz
    def _en_principal(fn):
        fn()


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
def _carpeta_descargas() -> str:
    # Android: la carpeta de la app se reemplaza al actualizar; ANDROID_PRIVATE
    # sobrevive (mismo criterio que storage.py).
    privada = os.environ.get("ANDROID_PRIVATE")
    if privada:
        return os.path.join(privada, "descargas")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "descargas")


CARPETA_DESCARGAS = _carpeta_descargas()
GUARDAR_EN_DOCUMENTOS = os.environ.get("WIICLASS_GUARDAR_EN_DOCUMENTOS", "1") != "0"

ESQUEMAS_REMOTOS = ("http", "https")
TIMEOUT_SEG = 20
MAX_BYTES = 500 * 1024 * 1024          # tope por archivo
BLOQUE = 64 * 1024
# Tipos que indican que la URL NO es un audio (página de error, login, etc.).
_TIPOS_NO_AUDIO = ("text/", "application/json", "application/xml", "application/xhtml")


class DescargaError(Exception):
    """Fallo de descarga con mensaje legible."""


def _ruta_absoluta(ruta_relativa: str) -> str:
    if os.path.isabs(ruta_relativa):
        return ruta_relativa
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), ruta_relativa)


def es_url_remota(ref: str) -> bool:
    return urlparse(str(ref or "")).scheme.lower() in ESQUEMAS_REMOTOS


# ---------------------------------------------------------------------------
# Descarga HTTP(S)
# ---------------------------------------------------------------------------
def _contexto_ssl():
    try:
        import certifi  # en Android el almacén del sistema no siempre lo ve Python
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _nombre_desde_respuesta(resp, url: str) -> str:
    """Content-Disposition > último tramo de la URL > 'audio'."""
    cd = resp.headers.get("Content-Disposition") if resp.headers else None
    if cd:
        msg = email.message.Message()
        msg["Content-Disposition"] = cd
        nombre = msg.get_filename()
        if nombre:
            return documentos.nombre_seguro(nombre)
    tramo = unquote(os.path.basename(urlparse(url).path))
    return documentos.nombre_seguro(tramo or "audio")


def descargar_url(url: str, carpeta: str, prefijo: str = "", on_progreso=None) -> str:
    """Descarga `url` en `carpeta` y devuelve la ruta final.

    Bloqueante (usar en hilo de fondo). Escribe en `<archivo>.part` y recién
    al terminar lo renombra, así nunca queda un audio a medias con nombre
    definitivo. `on_progreso(hechos, total|None)` se llama al cambiar el
    porcentaje (o cada 512 KB si el servidor no informa el tamaño).
    Lanza `DescargaError`.
    """
    if not es_url_remota(url):
        raise DescargaError("Solo se admiten enlaces http o https.")

    req = urllib.request.Request(url, headers={"User-Agent": "WiiClass-Descargas/1"})
    tmp = None
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEG, context=_contexto_ssl()) as resp:
            tipo = (resp.headers.get_content_type() if resp.headers else "") or ""
            if tipo.startswith(_TIPOS_NO_AUDIO):
                raise DescargaError("El enlace no apunta a un archivo de audio.")

            total = resp.headers.get("Content-Length") if resp.headers else None
            total = int(total) if total and total.isdigit() else None
            if total is not None and total > MAX_BYTES:
                raise DescargaError("El archivo es demasiado grande.")

            nombre = _nombre_desde_respuesta(resp, url)
            if not os.path.splitext(nombre)[1]:
                nombre += mimetypes.guess_extension(tipo) or ""
            os.makedirs(carpeta, exist_ok=True)
            destino = os.path.join(carpeta, prefijo + nombre)
            tmp = destino + ".part"

            hechos, ultimo_pct, ultimo_bytes = 0, -1, 0
            with open(tmp, "wb") as f:
                while True:
                    bloque = resp.read(BLOQUE)
                    if not bloque:
                        break
                    hechos += len(bloque)
                    if hechos > MAX_BYTES:
                        raise DescargaError("El archivo es demasiado grande.")
                    f.write(bloque)
                    if on_progreso:
                        if total:
                            pct = hechos * 100 // total
                            if pct != ultimo_pct:
                                ultimo_pct = pct
                                on_progreso(hechos, total)
                        elif hechos - ultimo_bytes >= 512 * 1024:
                            ultimo_bytes = hechos
                            on_progreso(hechos, None)
            if hechos == 0:
                raise DescargaError("El servidor devolvió un archivo vacío.")
            if total is not None and hechos < total:
                raise DescargaError("La descarga se cortó antes de terminar.")
            os.replace(tmp, destino)
            tmp = None
            return destino
    except DescargaError:
        raise
    except urllib.error.HTTPError as exc:
        raise DescargaError(f"El servidor respondió {exc.code}.") from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise DescargaError("No se pudo conectar para descargar el audio.") from exc
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# API usada por las pantallas
# ---------------------------------------------------------------------------
def _nombre_visible(grab, ruta: str) -> str:
    """Nombre con el que se ve el audio en Documentos: '<título><extensión>'."""
    ext = os.path.splitext(ruta)[1]
    return documentos.nombre_seguro((grab["nombre"] or "audio") + ext)


def descargar_grabacion(usuario_id: int, grabacion_id: int, on_completa=None, on_error=None,
                        on_progreso=None, on_aviso=None):
    """Descarga una grabación en segundo plano (ver el docstring del módulo).

    Si la grabación ya estaba descargada, llama a `on_completa` de inmediato.
    """
    if db.esta_descargada(grabacion_id):
        if on_completa:
            on_completa(grabacion_id)
        return

    def worker():
        try:
            grab = db.get_grabacion(grabacion_id)
            if not grab:
                raise ValueError("Grabación no encontrada")

            os.makedirs(CARPETA_DESCARGAS, exist_ok=True)
            origen = grab["url_audio"]
            if es_url_remota(origen):
                progreso = None
                if on_progreso:
                    def progreso(hechos, total):
                        _en_principal(lambda: on_progreso(grabacion_id, hechos, total))
                destino = descargar_url(origen, CARPETA_DESCARGAS,
                                        prefijo=f"{grabacion_id}_", on_progreso=progreso)
            else:
                origen = _ruta_absoluta(origen)
                if not os.path.exists(origen):
                    raise FileNotFoundError(f"No existe el audio: {origen}")
                destino = os.path.join(CARPETA_DESCARGAS,
                                       f"{grabacion_id}_{os.path.basename(origen)}")
                shutil.copyfile(origen, destino)

            peso_mb = os.path.getsize(destino) / (1024 * 1024)
            db.registrar_descarga(usuario_id, grabacion_id, destino, round(peso_mb, 2))
        except Exception as exc:
            # OJO: en Python 3 la variable de `except ... as exc` se BORRA al
            # terminar el bloque. La lambda se ejecuta después (en el hilo
            # principal), y ahí `exc` ya no existe -> NameError. Por eso se
            # copia a `error` (variable normal) antes de agendar.
            error = exc
            if on_error:
                _en_principal(lambda: on_error(grabacion_id, error))
            return

        aviso = None
        if GUARDAR_EN_DOCUMENTOS:
            try:
                ubicacion = documentos.guardar_en_documentos(destino, _nombre_visible(grab, destino))
                aviso = f"Guardado en {ubicacion}"
            except documentos.PermisoDenegadoError:
                aviso = ("Sin permiso para guardar en Documentos. "
                         "La clase sigue disponible dentro de la app.")
            except Exception as exc:  # DocumentosError u otro: no es fatal
                aviso = f"No se pudo guardar en Documentos. {exc}"
        if aviso and on_aviso:
            _en_principal(lambda: on_aviso(grabacion_id, aviso))
        if on_completa:
            _en_principal(lambda: on_completa(grabacion_id))

    def iniciar():
        threading.Thread(target=worker, daemon=True).start()

    # Android 9 y menor: el permiso de escritura se pide ANTES de empezar. Si
    # el usuario lo rechaza igual se descarga (copia privada) y se avisa.
    if GUARDAR_EN_DOCUMENTOS and documentos.necesita_permiso_escritura():
        documentos.pedir_permiso_escritura(lambda concedido: _en_principal(iniciar))
    else:
        iniciar()


def descargar_varias(usuario_id: int, grabacion_ids, on_cada_una=None, on_todas_completas=None,
                     on_error=None, on_aviso=None):
    """Descarga varias grabaciones (selección múltiple). Se encolan de a
    una (reutilizando `descargar_grabacion`) para no disparar muchos hilos
    de copia de archivos a la vez sin necesidad.
    `on_cada_una(grabacion_id)` se llama al terminar cada una;
    `on_error(grabacion_id, exc)` si alguna falla (la cola continúa);
    `on_todas_completas()` al terminar la última.
    """
    pendientes = list(grabacion_ids)
    if not pendientes:
        if on_todas_completas:
            on_todas_completas()
        return

    def siguiente():
        if not pendientes:
            if on_todas_completas:
                on_todas_completas()
            return
        gid = pendientes.pop(0)

        def _completa(g_id):
            if on_cada_una:
                on_cada_una(g_id)
            siguiente()

        def _error(g_id, exc):
            print(f"[downloads_manager] Error descargando {g_id}: {exc}")
            if on_error:
                on_error(g_id, exc)
            siguiente()

        descargar_grabacion(usuario_id, gid, on_completa=_completa, on_error=_error,
                            on_aviso=on_aviso)

    siguiente()
