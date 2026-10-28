"""
remote_config.py — Configuración remota de WiiClass.

La app lee un JSON desde una URL (la "fuente remota") y refleja sus valores
en la interfaz sin publicar una nueva versión: anuncio en Inicio, pestañas
habilitadas, velocidades del reproductor, saludo y notificaciones del sistema.

Fuente (en este orden):
  1. Variable de entorno WIICLASS_REMOTE_CONFIG_URL
  2. URL_POR_DEFECTO (servidor local de desarrollo, ver servir_config.py)
Esquemas aceptados: http, https y file (este último útil para pruebas).

Orden de verdad al arrancar (la app NUNCA espera a la red):
  caché en disco (última config válida recibida)  >  DEFAULTS

Garantías:
  * Ninguna función pública lanza excepciones: ante red caída, JSON inválido,
    respuesta demasiado grande o disco lleno se conserva la última config
    buena y el motivo queda en `estado["error"]`.
  * Validación estricta: cada valor se comprueba por tipo y rango; lo que no
    cumple se reemplaza por su valor predeterminado (el resto sí se aplica) y
    se anota en `estado["avisos"]`. Las claves desconocidas se ignoran.
  * Sin bloqueo de UI: `actualizar()` corre en un hilo; los suscriptores se
    llaman en el hilo principal de Kivy (si hay Kivy).
  * Soporta ETag: si la fuente responde 304 no se vuelve a procesar nada.
  * Límite de 256 KB por respuesta y 5 s de timeout.

Este módulo no importa Kivy al cargarse, así que se prueba con `unittest`.
"""

import copy
import json
import logging
import os
import ssl
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from urllib.parse import urlparse

log = logging.getLogger("wiiclass.remote_config")

ENV_URL = "WIICLASS_REMOTE_CONFIG_URL"
URL_POR_DEFECTO = "http://127.0.0.1:8765/app_config.json"
ESQUEMAS_VALIDOS = ("http", "https", "file")
TIMEOUT_SEG = 5.0
MAX_BYTES = 256 * 1024

TIPOS_ANUNCIO = ("info", "aviso", "critico")
VELOCIDADES_PERMITIDAS = (0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0)
MIN_INTERVALO, MAX_INTERVALO = 30, 86400

# Valores que se usan cuando no hay fuente remota ni caché. Coinciden con el
# comportamiento que la app tenía antes de existir la configuración remota.
DEFAULTS = {
    "version": 0,
    "intervalo_actualizacion_seg": 300,
    "anuncio": {"activo": False, "tipo": "info", "titulo": "", "mensaje": ""},
    "funciones": {"descargas": True, "grabacion": True, "notificaciones_sistema": True},
    "reproductor": {"velocidades": [0.5, 1.0, 1.5, 2.0]},
    "textos": {"saludo": ""},
}


# ---------------------------------------------------------------------------
# Validación (funciones puras)
# ---------------------------------------------------------------------------
def _es_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _texto(v, defecto, maximo, avisos, ruta):
    if v is None:
        return defecto
    if not isinstance(v, str):
        avisos.append(f"{ruta}: se esperaba texto")
        return defecto
    v = v.strip()
    if len(v) > maximo:
        avisos.append(f"{ruta}: recortado a {maximo} caracteres")
        v = v[:maximo].rstrip()
    return v


def _bool(v, defecto, avisos, ruta):
    if v is None:
        return defecto
    if isinstance(v, bool):
        return v
    avisos.append(f"{ruta}: se esperaba true/false")
    return defecto


def _seccion(crudo, nombre, avisos):
    v = crudo.get(nombre)
    if v is None:
        return {}
    if not isinstance(v, dict):
        avisos.append(f"{nombre}: se esperaba un objeto")
        return {}
    return v


def normalizar(crudo):
    """Convierte lo recibido en una config completa y válida.

    Devuelve (config, avisos). `crudo` puede ser cualquier cosa: si no es un
    dict se devuelve DEFAULTS y un aviso.
    """
    avisos = []
    cfg = copy.deepcopy(DEFAULTS)
    if not isinstance(crudo, dict):
        return cfg, ["la raíz del JSON no es un objeto"]

    v = crudo.get("version")
    if v is not None:
        if isinstance(v, int) and not isinstance(v, bool) and v >= 0:
            cfg["version"] = v
        else:
            avisos.append("version: se esperaba un entero >= 0")

    v = crudo.get("intervalo_actualizacion_seg")
    if v is not None:
        if _es_num(v) and MIN_INTERVALO <= v <= MAX_INTERVALO:
            cfg["intervalo_actualizacion_seg"] = int(v)
        else:
            avisos.append(f"intervalo_actualizacion_seg: debe estar entre {MIN_INTERVALO} y {MAX_INTERVALO}")

    a, d = _seccion(crudo, "anuncio", avisos), cfg["anuncio"]
    d["activo"] = _bool(a.get("activo"), d["activo"], avisos, "anuncio.activo")
    tipo = a.get("tipo")
    if tipo is not None:
        if tipo in TIPOS_ANUNCIO:
            d["tipo"] = tipo
        else:
            avisos.append(f"anuncio.tipo: use {', '.join(TIPOS_ANUNCIO)}")
    d["titulo"] = _texto(a.get("titulo"), d["titulo"], 80, avisos, "anuncio.titulo")
    d["mensaje"] = _texto(a.get("mensaje"), d["mensaje"], 280, avisos, "anuncio.mensaje")
    if d["activo"] and not (d["titulo"] or d["mensaje"]):
        d["activo"] = False  # un anuncio vacío no se muestra
        avisos.append("anuncio: activo pero sin título ni mensaje; se oculta")

    f, d = _seccion(crudo, "funciones", avisos), cfg["funciones"]
    for clave in d:
        d[clave] = _bool(f.get(clave), d[clave], avisos, f"funciones.{clave}")

    r = _seccion(crudo, "reproductor", avisos)
    vel = r.get("velocidades")
    if vel is not None:
        if (isinstance(vel, list) and 1 <= len(vel) <= 6
                and all(_es_num(x) and float(x) in VELOCIDADES_PERMITIDAS for x in vel)):
            unicas = sorted({float(x) for x in vel})
            if 1.0 not in unicas:
                avisos.append("reproductor.velocidades: se agregó 1.0 (velocidad normal)")
                unicas = sorted(unicas + [1.0])
            cfg["reproductor"]["velocidades"] = unicas
        else:
            avisos.append("reproductor.velocidades: lista de 1 a 6 valores entre "
                          f"{VELOCIDADES_PERMITIDAS[0]} y {VELOCIDADES_PERMITIDAS[-1]}")

    t = _seccion(crudo, "textos", avisos)
    cfg["textos"]["saludo"] = _texto(t.get("saludo"), "", 40, avisos, "textos.saludo")
    return cfg, avisos


# ---------------------------------------------------------------------------
# Red
# ---------------------------------------------------------------------------
class _SinCambios(Exception):
    """La fuente respondió 304 Not Modified."""


def _contexto_ssl():
    try:
        import certifi  # en Android el almacén del sistema no siempre lo ve Python
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def descargar_http(url: str, etag: str = None):
    """GET de `url`. Devuelve (texto, etag). Lanza `_SinCambios` ante 304 y
    cualquier otra excepción ante errores (las atrapa RemoteConfig)."""
    esquema = urlparse(url).scheme.lower()
    if esquema not in ESQUEMAS_VALIDOS:
        raise ValueError(f"esquema no permitido: {esquema or '(vacío)'}")
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "WiiClass-RemoteConfig/1",
        **({"If-None-Match": etag} if etag and esquema != "file" else {}),
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEG, context=_contexto_ssl()) as r:
            datos = r.read(MAX_BYTES + 1)
            nuevo_etag = r.headers.get("ETag") if r.headers else None
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            raise _SinCambios() from exc
        raise
    if len(datos) > MAX_BYTES:
        raise ValueError(f"respuesta mayor a {MAX_BYTES // 1024} KB")
    return datos.decode("utf-8-sig"), nuevo_etag


def url_configurada() -> str:
    return (os.environ.get(ENV_URL) or URL_POR_DEFECTO).strip()


# ---------------------------------------------------------------------------
# Servicio
# ---------------------------------------------------------------------------
def _ahora_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class RemoteConfig:
    def __init__(self, url=None, cargar_cache=None, guardar_cache=None,
                 descargar=descargar_http, reloj=time.time):
        self._url = url
        self._descargar = descargar
        self._reloj = reloj
        self._lock = threading.RLock()
        self._suscriptores = []
        self._en_curso = False
        self._cargar_cache = cargar_cache
        self._guardar_cache = guardar_cache

        self._valores = copy.deepcopy(DEFAULTS)
        self._crudo = None
        self._etag = None
        self.estado = {
            "origen": "predeterminada",   # remota | cache | predeterminada
            "ultima_actualizacion": None,  # ISO, última descarga correcta
            "ultimo_intento": None,
            "error": None,
            "avisos": [],
            "version": 0,
        }
        self._leer_cache()

    # ---- Propiedades -------------------------------------------------------
    @property
    def url(self) -> str:
        return self._url or url_configurada()

    @property
    def valores(self) -> dict:
        with self._lock:
            return copy.deepcopy(self._valores)

    def get(self, ruta: str, defecto=None):
        """Lee un valor por ruta con puntos: get("funciones.descargas")."""
        with self._lock:
            nodo = self._valores
        for parte in ruta.split("."):
            if not isinstance(nodo, dict) or parte not in nodo:
                return defecto
            nodo = nodo[parte]
        return copy.deepcopy(nodo)

    def funcion_activa(self, nombre: str) -> bool:
        return bool(self.get(f"funciones.{nombre}", True))

    # ---- Caché -------------------------------------------------------------
    def _leer_cache(self):
        if not self._cargar_cache:
            return
        try:
            cache = self._cargar_cache()
            if not isinstance(cache, dict):
                return
            cfg, avisos = normalizar(cache.get("config"))
            self._valores = cfg
            self._crudo = cache.get("config")
            self._etag = cache.get("etag") if isinstance(cache.get("etag"), str) else None
            self.estado.update(origen="cache", avisos=avisos, version=cfg["version"],
                               ultima_actualizacion=cache.get("recibido"))
        except Exception:
            log.exception("No se pudo leer la caché de configuración remota")

    def _guardar(self, crudo):
        if not self._guardar_cache:
            return
        try:
            self._guardar_cache({"config": crudo, "etag": self._etag,
                                 "recibido": self.estado["ultima_actualizacion"],
                                 "url": self.url})
        except Exception:
            log.exception("No se pudo guardar la caché de configuración remota")

    # ---- Suscripción -------------------------------------------------------
    def suscribir(self, fn):
        """`fn(cambio: bool)` se llama tras cada intento terminado: True si los
        valores cambiaron. En Kivy corre en el hilo principal."""
        self._suscriptores.append(fn)

    def _avisar(self, cambio: bool):
        def _llamar(*_a):
            for fn in list(self._suscriptores):
                try:
                    fn(cambio)
                except Exception:
                    log.exception("Error en un suscriptor de configuración remota")
        try:
            from kivy.clock import Clock
            Clock.schedule_once(_llamar)
        except Exception:
            _llamar()

    # ---- Actualización -----------------------------------------------------
    def actualizar(self) -> bool:
        """Lanza la descarga en segundo plano. False si ya había una en curso."""
        with self._lock:
            if self._en_curso:
                return False
            self._en_curso = True
        threading.Thread(target=self._trabajar, daemon=True).start()
        return True

    def _trabajar(self):
        try:
            cambio = self.actualizar_sync()
        except Exception:  # no debería ocurrir; el hilo nunca debe morir en silencio
            log.exception("Fallo inesperado actualizando la configuración remota")
            cambio = False
        finally:
            with self._lock:
                self._en_curso = False
        self._avisar(cambio)

    @property
    def actualizando(self) -> bool:
        return self._en_curso

    def actualizar_sync(self) -> bool:
        """Descarga y aplica la config. Devuelve True si los valores cambiaron."""
        url = self.url
        with self._lock:
            self.estado["ultimo_intento"] = _ahora_iso()
        try:
            texto, etag = self._descargar(url, self._etag)
        except _SinCambios:
            with self._lock:
                self.estado.update(error=None, ultima_actualizacion=_ahora_iso())
                if self.estado["origen"] != "remota":
                    self.estado["origen"] = "remota"
            self._guardar(self._crudo_cache())
            return False
        except Exception as exc:
            with self._lock:
                self.estado["error"] = f"{type(exc).__name__}: {exc}"
            log.info("Configuración remota no disponible (%s); se mantiene la última", exc)
            return False

        try:
            crudo = json.loads(texto)
        except ValueError as exc:
            with self._lock:
                self.estado["error"] = f"JSON inválido: {exc}"
            return False
        if not isinstance(crudo, dict):
            with self._lock:
                self.estado["error"] = "JSON inválido: la raíz no es un objeto"
            return False

        nueva, avisos = normalizar(crudo)
        with self._lock:
            cambio = nueva != self._valores
            self._valores = nueva
            self._etag = etag
            self._crudo = crudo
            self.estado.update(origen="remota", error=None, avisos=avisos,
                               version=nueva["version"], ultima_actualizacion=_ahora_iso())
        self._guardar(crudo)
        return cambio

    def _crudo_cache(self):
        # Tras un 304 se vuelve a guardar lo último recibido (renueva `recibido`).
        return self._crudo or self.valores

    def segundos_hasta_proxima(self) -> int:
        return int(self.get("intervalo_actualizacion_seg", DEFAULTS["intervalo_actualizacion_seg"]))


def _crear_global():
    try:
        import storage
        return RemoteConfig(cargar_cache=storage.cargar_config_remota,
                            guardar_cache=storage.guardar_config_remota)
    except Exception:
        log.exception("No se pudo iniciar RemoteConfig con caché; se usa sin caché")
        return RemoteConfig()


# Instancia única compartida por toda la app.
config_remota = _crear_global()
