"""
storage.py — Persistencia en archivos JSON para WiiClass.

Guarda tres cosas para recuperarlas al reabrir la app:

  * sesion.json          -> quién tenía la sesión iniciada (login automático).
  * grabaciones.json     -> grabaciones subidas por los profesores.
  * notificaciones.json  -> notificaciones (con su estado leída / no leída).

SQLite sigue siendo el motor de consultas de las pantallas; estos JSON son
el respaldo duradero que `db.init_db()` usa para reconstruir lo que falte
(por ejemplo, si la base de datos se borra o se recrea en una actualización).

Dónde se guardan (carpeta `datos/`):
  1. La indicada en la variable de entorno WIICLASS_DATA_DIR (pruebas).
  2. Android: <almacenamiento privado de la app>/datos  (ANDROID_PRIVATE).
  3. Escritorio: <carpeta del proyecto>/datos

Garantías:
  * Escritura atómica (archivo temporal + os.replace): un cierre brusco a
    mitad de escritura nunca deja un JSON a medias.
  * Ninguna función lanza excepciones: si el disco falla o el JSON está
    corrupto se registra en el log y se devuelve un valor vacío / False.
    Un archivo corrupto se aparta como `*.corrupto` (no se pierde ni se
    vuelve a leer en cada arranque).
  * La contraseña NUNCA se guarda: la sesión solo guarda id, correo, rol
    e institución.

Este módulo no importa Kivy.
"""

import json
import logging
import os
import tempfile
import threading
from datetime import datetime

log = logging.getLogger("wiiclass.storage")

VERSION = 1
ARCHIVO_SESION = "sesion.json"
ARCHIVO_GRABACIONES = "grabaciones.json"
ARCHIVO_NOTIFICACIONES = "notificaciones.json"
ARCHIVO_CONFIG_REMOTA = "config_remota.json"

ROLES_VALIDOS = ("Estudiante", "Profesor")

# Un solo lock para todos los archivos: las escrituras son pequeñas y así
# se evita que dos hilos (UI + descargas) pisen el mismo archivo.
_lock = threading.RLock()


# ---------------------------------------------------------------------------
# Ubicación
# ---------------------------------------------------------------------------
def carpeta_datos() -> str:
    """Carpeta donde viven los JSON (se crea si no existe)."""
    base = os.environ.get("WIICLASS_DATA_DIR")
    if not base:
        privada = os.environ.get("ANDROID_PRIVATE")
        if privada:
            base = os.path.join(privada, "datos")
        else:
            base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos")
    os.makedirs(base, exist_ok=True)
    return base


# ---------------------------------------------------------------------------
# Lectura / escritura segura
# ---------------------------------------------------------------------------
def _leer(nombre: str, defecto):
    """Devuelve el contenido guardado bajo la clave "datos", o `defecto`."""
    with _lock:
        try:
            ruta = os.path.join(carpeta_datos(), nombre)
            with open(ruta, "r", encoding="utf-8") as f:
                contenido = json.load(f)
        except FileNotFoundError:
            return defecto
        except ValueError as exc:  # JSON corrupto
            log.warning("%s está corrupto (%s); se aparta y se parte de cero", nombre, exc)
            _apartar_corrupto(ruta)
            return defecto
        except OSError as exc:
            log.warning("No se pudo leer %s: %s", nombre, exc)
            return defecto

    if not isinstance(contenido, dict) or "datos" not in contenido:
        log.warning("%s no tiene el formato esperado; se ignora", nombre)
        _apartar_corrupto(ruta)
        return defecto
    return contenido["datos"]


def _escribir(nombre: str, datos) -> bool:
    """Escritura atómica. Devuelve True si quedó guardado."""
    with _lock:
        tmp = None
        try:
            carpeta = carpeta_datos()
            ruta = os.path.join(carpeta, nombre)
            contenido = {
                "version": VERSION,
                "actualizado": datetime.now().isoformat(timespec="seconds"),
                "datos": datos,
            }
            fd, tmp = tempfile.mkstemp(dir=carpeta, prefix=nombre + ".", suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(contenido, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, ruta)
            tmp = None
            return True
        except (OSError, TypeError, ValueError) as exc:
            log.error("No se pudo guardar %s: %s", nombre, exc)
            return False
        finally:
            if tmp and os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass


def _apartar_corrupto(ruta: str):
    try:
        os.replace(ruta, ruta + ".corrupto")
    except OSError:
        pass


def _borrar(nombre: str):
    with _lock:
        try:
            os.remove(os.path.join(carpeta_datos(), nombre))
        except FileNotFoundError:
            pass
        except OSError as exc:
            log.warning("No se pudo borrar %s: %s", nombre, exc)


# ---------------------------------------------------------------------------
# Sesión
# ---------------------------------------------------------------------------
def guardar_sesion(usuario_id: int, correo: str, rol: str, institucion_id=None) -> bool:
    return _escribir(ARCHIVO_SESION, {
        "usuario_id": int(usuario_id),
        "correo": str(correo or "").strip().lower(),
        "rol": rol,
        "institucion_id": institucion_id,
    })


def cargar_sesion():
    """Sesión guardada o None si no hay (o si el archivo es inválido)."""
    s = _leer(ARCHIVO_SESION, None)
    if (not isinstance(s, dict)
            or not isinstance(s.get("usuario_id"), int)
            or isinstance(s.get("usuario_id"), bool)
            or not isinstance(s.get("correo"), str) or not s["correo"]
            or s.get("rol") not in ROLES_VALIDOS):
        return None
    return s


def borrar_sesion():
    _borrar(ARCHIVO_SESION)


# ---------------------------------------------------------------------------
# Grabaciones y notificaciones (listas de diccionarios)
# ---------------------------------------------------------------------------
def _lista(nombre: str) -> list:
    datos = _leer(nombre, [])
    if not isinstance(datos, list):
        return []
    return [d for d in datos if isinstance(d, dict)]


def cargar_grabaciones() -> list:
    return _lista(ARCHIVO_GRABACIONES)


def guardar_grabaciones(grabaciones: list) -> bool:
    return _escribir(ARCHIVO_GRABACIONES, list(grabaciones))


def cargar_notificaciones() -> list:
    return _lista(ARCHIVO_NOTIFICACIONES)


def guardar_notificaciones(notificaciones: list) -> bool:
    return _escribir(ARCHIVO_NOTIFICACIONES, list(notificaciones))


# ---------------------------------------------------------------------------
# Caché de la configuración remota (ver remote_config.py)
# ---------------------------------------------------------------------------
def cargar_config_remota():
    """Última configuración remota recibida ({config, etag, recibido, url}) o None."""
    d = _leer(ARCHIVO_CONFIG_REMOTA, None)
    return d if isinstance(d, dict) else None


def guardar_config_remota(cache: dict) -> bool:
    return _escribir(ARCHIVO_CONFIG_REMOTA, dict(cache))
