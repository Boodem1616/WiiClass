"""
recording_tab.py — TAB "GRABACIÓN" (exclusivo del rol Profesor)

Controles, en este orden (ver mock de Figma):
  1. Materia            -> solo las materias ASIGNADAS al profesor (BD).
  2. Semana de la materia
  3. Título de la grabación
  4. Tiempo transcurrido (MM:SS)
  5. Botón Grabar / Detener

Al detener, el audio se guarda en
    <carpeta>/grabaciones/<materia>/semana_<N>/<titulo>_<fecha>.<ext>
y se registra en SQLite (tabla Grabaciones, con profesor_id). Como los
estudiantes leen esa misma tabla, la clase les aparece en Inicio/Categoría.
"""

import os
import re
import time
import unicodedata
from datetime import datetime

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.utils import platform

from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.screen import MDScreen

import db
from recorder import RecorderError, crear_grabadora
from screens.widgets import mostrar_aviso

Builder.load_file(os.path.join(os.path.dirname(__file__), "recording_tab.kv"))

N_SEMANAS = 16
DURACION_MINIMA_SEG = 2


def carpeta_grabaciones() -> str:
    """Carpeta raíz de las grabaciones. En Android debe ser el almacenamiento
    privado de la app (user_data_dir); en escritorio, junto al proyecto."""
    if platform == "android":
        from kivy.app import App
        base = App.get_running_app().user_data_dir
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "grabaciones")


def _slug(texto: str, por_defecto: str = "sin_titulo") -> str:
    """'Introducción a Matrices' -> 'Introduccion_a_Matrices' (apto para nombre de archivo)."""
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    t = re.sub(r"[^A-Za-z0-9]+", "_", t).strip("_")
    return t[:60] or por_defecto


class RecordingTab(MDScreen):
    materia_texto = StringProperty("")
    semana_texto = StringProperty("")
    grabando = BooleanProperty(False)
    segundos = NumericProperty(0)
    tiempo_txt = StringProperty("00:00")
    estado_txt = StringProperty("Lista para grabar")

    def on_kv_post(self, base_widget):
        self._materia_id = None
        self._semana = None
        self._menu = None
        self._grabadora = crear_grabadora()
        self._inicio = 0.0
        self._reloj = None
        self._materias = []

    # ---- Ciclo de vida -------------------------------------------------
    def on_pre_enter(self, *args):
        self.refrescar()

    def refrescar(self):
        """Recarga las materias asignadas al profesor. Si hay una grabación
        en curso NO se toca nada (no se pueden perder las selecciones)."""
        if self.grabando:
            return
        from kivy.app import App
        usuario = App.get_running_app().usuario
        if not usuario:
            return
        self._materias = list(db.get_materias_profesor(usuario["id"]))
        ids = [m["id"] for m in self._materias]
        if self._materia_id not in ids:
            self._materia_id = None
            self.materia_texto = ""
        if not self._materias:
            self.estado_txt = "No tienes materias asignadas"

    # ---- Selectores ------------------------------------------------------
    def abrir_menu_materias(self, caller):
        if self.grabando:
            return
        if not self._materias:
            mostrar_aviso("No tienes materias asignadas")
            return
        items = [
            {"text": m["nombre"],
             "on_release": lambda m=m: self._elegir_materia(m)}
            for m in self._materias
        ]
        self._abrir_menu(caller, items)

    def abrir_menu_semanas(self, caller):
        if self.grabando:
            return
        items = [
            {"text": f"Semana {n}", "on_release": lambda n=n: self._elegir_semana(n)}
            for n in range(1, N_SEMANAS + 1)
        ]
        self._abrir_menu(caller, items, alto_max=True)

    def _abrir_menu(self, caller, items, alto_max=False):
        if self._menu:
            self._menu.dismiss()
        kwargs = {"max_height": caller.height * 5} if alto_max else {}
        self._menu = MDDropdownMenu(caller=caller, items=items, **kwargs)
        self._menu.open()

    def _elegir_materia(self, materia):
        self._materia_id = materia["id"]
        self.materia_texto = materia["nombre"]
        if self._menu:
            self._menu.dismiss()

    def _elegir_semana(self, n):
        self._semana = n
        self.semana_texto = f"Semana {n}"
        if self._menu:
            self._menu.dismiss()

    # ---- Grabar / detener -----------------------------------------------
    def alternar_grabacion(self):
        if self.grabando:
            self.detener_y_guardar()
        else:
            self.iniciar_grabacion()

    def iniciar_grabacion(self):
        titulo = self.ids.titulo.text.strip()
        if not self._materia_id:
            mostrar_aviso("Selecciona la materia")
            return
        if not self._semana:
            mostrar_aviso("Selecciona la semana")
            return
        if not titulo:
            mostrar_aviso("Escribe un título para la grabación")
            return

        # Android: el permiso se pide en el momento; si lo conceden, se reintenta.
        if platform == "android":
            from recorder import AndroidRecorder
            if not AndroidRecorder.tiene_permiso():
                AndroidRecorder.pedir_permiso(
                    lambda ok: Clock.schedule_once(
                        lambda dt: self.iniciar_grabacion() if ok
                        else mostrar_aviso("Sin permiso de micrófono")))
                return

        materia = next(m for m in self._materias if m["id"] == self._materia_id)
        marca = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = os.path.join(
            carpeta_grabaciones(), _slug(materia["nombre"]), f"semana_{self._semana}",
            f"{_slug(titulo)}_{marca}",
        )
        try:
            self._grabadora.iniciar(base)
        except RecorderError as exc:
            mostrar_aviso(str(exc), duracion=4)
            return

        self._inicio = time.monotonic()
        self.segundos = 0
        self.tiempo_txt = "00:00"
        self.estado_txt = "Grabando…"
        self.grabando = True
        self._reloj = Clock.schedule_interval(self._tick, 0.25)

    def _tick(self, dt):
        self.segundos = int(time.monotonic() - self._inicio)
        self.tiempo_txt = f"{self.segundos // 60:02d}:{self.segundos % 60:02d}"

    def detener_y_guardar(self):
        if not self.grabando:
            return
        if self._reloj:
            self._reloj.cancel()
            self._reloj = None
        self.grabando = False

        from kivy.app import App
        usuario = App.get_running_app().usuario
        titulo = self.ids.titulo.text.strip()
        try:
            ruta, duracion = self._grabadora.detener()
        except Exception as exc:
            self.estado_txt = "Lista para grabar"
            mostrar_aviso(f"Error al detener la grabación: {exc}", duracion=4)
            return

        if duracion < DURACION_MINIMA_SEG or not ruta or not os.path.exists(ruta):
            if ruta and os.path.exists(ruta):
                os.remove(ruta)
            self._reiniciar_indicador()
            mostrar_aviso("Grabación demasiado corta: no se guardó")
            return

        try:
            db.registrar_grabacion_profesor(
                usuario["id"], self._materia_id, self._semana, titulo, ruta, duracion)
        except Exception as exc:
            # El audio ya está en disco; se conserva para no perder la clase.
            self._reiniciar_indicador()
            mostrar_aviso(f"Audio guardado, pero no se registró en la base: {exc}", duracion=5)
            return

        self.ids.titulo.text = ""
        self._reiniciar_indicador()
        mostrar_aviso("Grabación guardada")

    def _reiniciar_indicador(self):
        self.tiempo_txt = "00:00"
        self.segundos = 0
        self.estado_txt = "Lista para grabar"

    def finalizar_si_activa(self):
        """Se llama al cerrar sesión: no se pierde una clase a medio grabar."""
        if self.grabando:
            self.detener_y_guardar()
