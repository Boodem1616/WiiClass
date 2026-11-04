"""
analytics.py — Motor de analíticas locales de WiiClass (Sesión 25).

Registra eventos de interacción en `analytics.json`. Cada evento sigue la
"anatomía" vista en clase: QUÉ pasó (nombre), CUÁNDO (timestamp) y el
contexto (metadatos en un diccionario):

    {
      "evento": "categoria_abierta",
      "ts": 1699901045.8,
      "sesion": "a3f9c2d1",          # una por apertura de la app
      "rol": "Estudiante",           # solo si hay sesión iniciada
      "datos": {"categoria_id": 2, "nombre": "Ciencias"}
    }

Uso (en cualquier pantalla):

    from analytics import registrar
    registrar("pantalla_vista", {"nombre": "LoginScreen"})

Decisiones de diseño:
  * NUNCA lanza excepciones: medir no puede romper la app. Un fallo de
    disco o un JSON corrupto solo se registra en el log.
  * Privacidad: no se guardan contraseñas, correos ni nombres de personas.
    Solo ids, nombres de pantallas/categorías y el rol.
  * Escritura atómica (archivo temporal + os.replace) y con "debounce":
    los eventos se acumulan en memoria y se vuelcan a disco ~1 s después
    del último, para no escribir el archivo completo en cada toque. Se
    fuerza con `vaciar()` (la app lo llama al cerrarse).
  * El archivo se acota a MAX_EVENTOS (se descartan los más antiguos).
  * Vive en la carpeta `datos/` junto al resto de la persistencia (ver
    storage.py); se puede cambiar con WIICLASS_ANALYTICS_FILE.

Este módulo no importa Kivy (se puede probar y analizar sin interfaz).
"""

import json
import logging
import os
import tempfile
import threading
import time
import uuid

from storage import carpeta_datos

log = logging.getLogger("wiiclass.analytics")

ARCHIVO = "analytics.json"
MAX_EVENTOS = 5000
# Segundos de espera antes de volcar a disco. 0 = escritura inmediata.
RETRASO_VOLCADO = 1.0

# ---- Catálogo de eventos (un solo lugar: evita errores de tipeo) ----------
APP_INICIADA = "app_iniciada"
APP_CERRADA = "app_cerrada"
PANTALLA_VISTA = "pantalla_vista"
LOGIN_EXITOSO = "login_exitoso"
LOGIN_ERROR = "login_error"
SESION_RESTAURADA = "sesion_restaurada"
LOGOUT = "logout"
CATEGORIA_ABIERTA = "categoria_abierta"
CLASE_ABIERTA = "clase_abierta"
REPRODUCCION_PLAY = "reproduccion_play"
REPRODUCCION_PAUSA = "reproduccion_pausa"
VELOCIDAD_CAMBIADA = "velocidad_cambiada"
DESCARGA_INICIADA = "descarga_iniciada"
DESCARGA_COMPLETA = "descarga_completa"
DESCARGA_ERROR = "descarga_error"
GRABACION_INICIADA = "grabacion_iniciada"
GRABACION_GUARDADA = "grabacion_guardada"
NOTIFICACION_DESCARTADA = "notificacion_descartada"
NOTIFICACIONES_LIMPIADAS = "notificaciones_limpiadas"

_lock = threading.RLock()
_eventos = None          # caché en memoria (lista de dicts)
_ruta_cache = None       # ruta a la que corresponde la caché
_sucio = False           # hay eventos sin volcar a disco
_timer = None
_sesion_id = uuid.uuid4().hex[:8]
_rol = None


# ---------------------------------------------------------------------------
# Ubicación y contexto
# ---------------------------------------------------------------------------
def ruta() -> str:
    """Ruta absoluta de analytics.json."""
    return os.environ.get("WIICLASS_ANALYTICS_FILE") or os.path.join(carpeta_datos(), ARCHIVO)


def sesion_id() -> str:
    return _sesion_id


def nueva_sesion() -> str:
    """Empieza una sesión nueva (se llama al abrir la app)."""
    global _sesion_id
    _sesion_id = uuid.uuid4().hex[:8]
    return _sesion_id


def establecer_rol(rol):
    """Rol del usuario con sesión iniciada (None al cerrar sesión). Se
    agrega a cada evento para poder segmentar Estudiante vs Profesor."""
    global _rol
    _rol = rol or None


# ---------------------------------------------------------------------------
# Lectura / escritura
# ---------------------------------------------------------------------------
def _valido(e) -> bool:
    return (isinstance(e, dict) and isinstance(e.get("evento"), str)
            and isinstance(e.get("ts"), (int, float)) and not isinstance(e.get("ts"), bool))


def _leer_disco(r: str) -> list:
    try:
        with open(r, "r", encoding="utf-8") as f:
            contenido = json.load(f)
    except FileNotFoundError:
        return []
    except ValueError as exc:  # JSON corrupto: se aparta, no se pierde
        log.warning("analytics.json corrupto (%s); se aparta y se parte de cero", exc)
        try:
            os.replace(r, r + ".corrupto")
        except OSError:
            pass
        return []
    except OSError as exc:
        log.warning("No se pudo leer analytics.json: %s", exc)
        return []
    if not isinstance(contenido, list):
        return []
    return [e for e in contenido if _valido(e)]


def _cache() -> list:
    """Caché en memoria; se recarga si cambió la ruta del archivo."""
    global _eventos, _ruta_cache
    r = ruta()
    if _eventos is None or _ruta_cache != r:
        _eventos = _leer_disco(r)
        _ruta_cache = r
    return _eventos


def _volcar_a_disco() -> bool:
    global _sucio
    with _lock:
        if not _sucio or _eventos is None:
            return True
        tmp = None
        try:
            r = _ruta_cache
            carpeta = os.path.dirname(os.path.abspath(r))
            os.makedirs(carpeta, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=carpeta, prefix=ARCHIVO + ".", suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(_eventos, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, r)
            tmp = None
            _sucio = False
            return True
        except (OSError, TypeError, ValueError) as exc:
            log.error("No se pudo guardar analytics.json: %s", exc)
            return False
        finally:
            if tmp and os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass


def _programar_volcado():
    global _timer
    if RETRASO_VOLCADO <= 0:
        _volcar_a_disco()
        return
    if _timer is not None and _timer.is_alive():
        return  # ya hay uno pendiente: agrupa los eventos que lleguen
    _timer = threading.Timer(RETRASO_VOLCADO, _volcar_a_disco)
    _timer.daemon = True
    _timer.start()


def vaciar() -> bool:
    """Vuelca a disco lo pendiente ya mismo (al cerrar la app / en pruebas)."""
    global _timer
    with _lock:
        if _timer is not None:
            _timer.cancel()
            _timer = None
        return _volcar_a_disco()


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------
def registrar(nombre, data=None):
    """Registra un evento. Devuelve el evento guardado, o None si no se pudo.

    `data` es un diccionario con el contexto (pantalla, método, ids...).
    Los valores no serializables a JSON se convierten a texto.
    """
    global _sucio
    try:
        if not isinstance(nombre, str) or not nombre.strip():
            return None
        datos = json.loads(json.dumps(data or {}, default=str, ensure_ascii=False))
        if not isinstance(datos, dict):
            datos = {"valor": datos}

        evento = {"evento": nombre.strip(), "ts": time.time(), "sesion": _sesion_id}
        if _rol:
            evento["rol"] = _rol
        evento["datos"] = datos

        with _lock:
            lista = _cache()
            lista.append(evento)
            if len(lista) > MAX_EVENTOS:
                del lista[:len(lista) - MAX_EVENTOS]
            _sucio = True
            _programar_volcado()
        return evento
    except Exception as exc:  # medir nunca debe romper la app
        log.error("No se pudo registrar el evento %r: %s", nombre, exc)
        return None


# Nombre usado en las diapositivas de la clase.
log_evento = registrar


def cargar() -> list:
    """Todos los eventos registrados (incluye los aún no volcados a disco)."""
    with _lock:
        return list(_cache())


def borrar() -> None:
    """Elimina todo el historial (memoria y archivo)."""
    global _eventos, _ruta_cache, _sucio
    with _lock:
        vaciar()
        _eventos, _ruta_cache, _sucio = [], ruta(), False
        try:
            os.remove(ruta())
        except FileNotFoundError:
            pass
        except OSError as exc:
            log.warning("No se pudo borrar analytics.json: %s", exc)
