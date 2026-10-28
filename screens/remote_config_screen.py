"""
remote_config_screen.py — "Configuración remota": muestra de dónde viene la
configuración y qué valores está aplicando la app ahora mismo.

Se llega desde Perfil. Muestra:
  - Estado: origen (Remota / Caché / Predeterminada), URL, versión, última
    actualización correcta, último intento y el error si lo hubo.
  - Valores vigentes: lo que la app realmente usa tras validar el JSON.
  - Avisos de validación: valores recibidos que se descartaron.
  - Botón "Actualizar ahora": descarga de nuevo y la pantalla se redibuja
    sola cuando termina (el resto de la app también, ver main.py).
"""

import os
from datetime import datetime

from kivy.lang import Builder
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import BooleanProperty

from kivymd.uix.label import MDLabel
from kivymd.uix.screen import MDScreen

import theme

from remote_config import config_remota
from screens.widgets import mostrar_aviso

Builder.load_file(os.path.join(os.path.dirname(__file__), "remote_config_screen.kv"))

ORIGENES = {
    "remota": "Remota (recién descargada)",
    "cache": "Caché (última descarga guardada)",
    "predeterminada": "Predeterminada (sin fuente alcanzada)",
}


def _hora(iso):
    if not iso:
        return "—"
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M:%S")
    except ValueError:
        return str(iso)


def _si_no(v):
    return "Sí" if v else "No"


def filas_estado(cfg=config_remota):
    """[(etiqueta, valor)] del estado de la fuente. Función pura (probable)."""
    e = cfg.estado
    filas = [
        ("Origen", ORIGENES.get(e["origen"], e["origen"])),
        ("Fuente", cfg.url),
        ("Versión del contenido", str(e["version"])),
        ("Última actualización", _hora(e["ultima_actualizacion"])),
        ("Último intento", _hora(e["ultimo_intento"])),
        ("Próxima en", f"{cfg.segundos_hasta_proxima()} s"),
    ]
    if e["error"]:
        filas.append(("Error", e["error"]))
    for aviso in e["avisos"]:
        filas.append(("Aviso", aviso))
    return filas


def filas_valores(cfg=config_remota):
    """[(etiqueta, valor)] de lo que la app está aplicando. Función pura."""
    v = cfg.valores
    a = v["anuncio"]
    anuncio = (f"{a['tipo']} · {a['titulo'] or '(sin título)'}" if a["activo"] else "Oculto")
    return [
        ("Anuncio en Inicio", anuncio),
        ("Saludo personalizado", v["textos"]["saludo"] or "(automático por hora)"),
        ("Descargas nuevas", _si_no(v["funciones"]["descargas"])),
        ("Grabación", _si_no(v["funciones"]["grabacion"])),
        ("Notificaciones del sistema", _si_no(v["funciones"]["notificaciones_sistema"])),
        ("Velocidades del reproductor",
         "  ".join(f"{s:g}x" for s in v["reproductor"]["velocidades"])),
    ]


def _crear_fila(etiqueta, valor):
    """Renglón etiqueta/valor; el alto se adapta al texto (puede ser largo)."""
    fila = BoxLayout(orientation="vertical", size_hint_y=None, padding=(0, dp(4)))
    fila.bind(minimum_height=fila.setter("height"))
    chica = MDLabel(text=str(etiqueta), size_hint_y=None, height=dp(18),
                    font_style="Body", role="small",
                    theme_text_color="Custom", text_color=theme.TEXT_SOFT)
    grande = MDLabel(text=str(valor), size_hint_y=None, font_style="Body", role="medium",
                     theme_text_color="Custom",
                     text_color=theme.DANGER if etiqueta == "Error" else theme.TEXT)
    grande.bind(width=lambda w, v: setattr(w, "text_size", (v, None)),
                texture_size=lambda w, v: setattr(w, "height", v[1]))
    fila.add_widget(chica)
    fila.add_widget(grande)
    return fila


class RemoteConfigScreen(MDScreen):
    actualizando = BooleanProperty(False)

    def on_pre_enter(self, *args):
        self.refrescar()

    def refrescar(self):
        self.actualizando = config_remota.actualizando
        self._llenar(self.ids.estado, filas_estado())
        self._llenar(self.ids.valores, filas_valores())

    @staticmethod
    def _llenar(contenedor, filas):
        contenedor.clear_widgets()
        for etiqueta, valor in filas:
            contenedor.add_widget(_crear_fila(etiqueta, valor))

    def actualizar_ahora(self):
        if not config_remota.actualizar():
            mostrar_aviso("Ya se está actualizando")
            return
        self.actualizando = True

    def al_terminar(self, cambio: bool):
        """Lo llama main.py cuando termina un intento de actualización."""
        self.refrescar()
        if self.manager and self.manager.current == self.name:
            error = config_remota.estado["error"]
            if error:
                mostrar_aviso("No se pudo actualizar; se mantiene la última", duracion=3)
            else:
                mostrar_aviso("Configuración actualizada" if cambio else "Sin cambios")
