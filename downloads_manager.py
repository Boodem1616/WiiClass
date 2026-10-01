"""
downloads_manager.py — Descarga (simulada) de una grabación al
almacenamiento interno del dispositivo, para reproducción offline.

Por qué "simulada": esta app no tiene un servidor remoto todavía (los
audios de ejemplo ya vienen empaquetados en `assets/audio/`). "Descargar"
acá significa copiar ese archivo a una carpeta de almacenamiento local
persistente (`descargas/`, junto a la base de datos) y registrar el
estado en la tabla `Descargas_offline` — exactamente lo que se necesita
para que, el día que haya un backend real, solo haya que cambiar el
origen del archivo (una URL en vez de una ruta local) sin tocar el resto
del flujo.

Igual que con la apertura de audio (ver `audio_player.py`), la copia de
archivo y el trabajo de disco se hacen en un hilo de fondo: aunque copiar
un archivo pequeño es rápido, tocar disco en el hilo principal de Kivy es
una mala práctica que ya nos costó un par de bugs serios en este proyecto
(congelamientos). El resultado se aplica en el hilo principal vía
`Clock.schedule_once`.
"""

import os
import shutil
import threading

from kivy.clock import Clock

import db

CARPETA_DESCARGAS = os.path.join(os.path.dirname(__file__), "descargas")


def _ruta_absoluta(ruta_relativa: str) -> str:
    if os.path.isabs(ruta_relativa):
        return ruta_relativa
    return os.path.join(os.path.dirname(__file__), ruta_relativa)


def descargar_grabacion(usuario_id: int, grabacion_id: int, on_completa=None, on_error=None):
    """Descarga una grabación en segundo plano.

    `on_completa(grabacion_id)` y `on_error(grabacion_id, exc)` se llaman
    en el hilo principal (seguro para tocar widgets desde ahí).
    Si la grabación ya estaba descargada, llama a `on_completa` de
    inmediato (no hay nada que hacer).
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
            origen = _ruta_absoluta(grab["url_audio"])
            if not os.path.exists(origen):
                raise FileNotFoundError(f"No existe el audio: {origen}")
            nombre_archivo = f"{grabacion_id}_{os.path.basename(origen)}"
            destino = os.path.join(CARPETA_DESCARGAS, nombre_archivo)

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
                Clock.schedule_once(lambda dt: on_error(grabacion_id, error))
            return
        if on_completa:
            Clock.schedule_once(lambda dt: on_completa(grabacion_id))

    threading.Thread(target=worker, daemon=True).start()


def descargar_varias(usuario_id: int, grabacion_ids, on_cada_una=None, on_todas_completas=None):
    """Descarga varias grabaciones (selección múltiple). Se encolan de a
    una (reutilizando el mismo mecanismo que `descargar_grabacion`) para
    no disparar muchos hilos de copia de archivos a la vez sin necesidad.
    `on_cada_una(grabacion_id)` se llama al terminar cada una;
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
            siguiente()

        descargar_grabacion(usuario_id, gid, on_completa=_completa, on_error=_error)

    siguiente()
