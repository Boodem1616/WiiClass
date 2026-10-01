"""
player_screen.py — Reproductor de Audio (compartido entre Tab Inicio y
Tab Descargas, ya que la especificación pide "el mismo reproductor").

Controles:
  - Play / Pausa
  - Anterior: si la clase lleva más de 3 s, vuelve al inicio; si no, salta a
    la clase anterior de la categoría (como cualquier reproductor de música)
  - Retroceder / adelantar 10 s (muy usado para repasar una explicación)
  - Siguiente clase de la misma categoría
  - Control de velocidad: botones fijos 0.5x / 1.0x / 1.5x / 2.0x

Compatible con KivyMD 2.0.0.
"""

import os

from kivy.lang import Builder
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.factory import Factory

from kivymd.uix.screen import MDScreen

import db
from audio_player import audio_engine
from screens.widgets import mostrar_aviso

Builder.load_file(os.path.join(os.path.dirname(__file__), "player_screen.kv"))

SPEEDS = [0.5, 1.0, 1.5, 2.0]


class PlayerScreen(MDScreen):
    grabacion_actual = None

    def on_kv_post(self, base_widget):
        # True mientras el dedo está sobre la barra de progreso. Mientras
        # tanto, el ciclo de UI NO debe reescribir el valor del slider (antes
        # peleaba con el dedo y la perilla "saltaba" hacia atrás al arrastrar).
        self._arrastrando_slider = False
        self._build_speed_buttons()
        Clock.schedule_interval(self._actualizar_ui, 0.3)
        # Reacciona a los cambios de estado del motor de audio (que ahora
        # carga el archivo en un hilo de fondo) en vez de asumir el estado
        # a mano: así el ícono de play/pausa y los controles siempre
        # reflejan la realidad, incluso si la carga tarda o falla.
        audio_engine.bind(
            is_playing=self._on_engine_state,
            is_loading=self._on_engine_state,
        )

    def _build_speed_buttons(self):
        row = self.ids.speed_row
        row.clear_widgets()
        self._speed_buttons = {}
        for s in SPEEDS:
            btn = Factory.SpeedButton()
            btn.value = s
            btn.active = (s == 1.0)
            btn.texto = f"{s}x"
            btn.bind(on_release=lambda inst, sp=s: self.set_speed(sp))
            row.add_widget(btn)
            self._speed_buttons[s] = btn

    def cargar_grabacion(self, grabacion_id: int, local_path: str = None):
        grab = db.get_grabacion(grabacion_id)
        if not grab:
            return
        self.grabacion_actual = grab
        categoria = None
        try:
            cats = db.get_categorias()
            categoria = next((c for c in cats if c["id"] == grab["categoria_id"]), None)
        except Exception:
            pass

        # Lista ordenada de clases de la misma categoría, para que los
        # botones anterior/siguiente sepan cuál es cuál. Sin conexión solo se
        # consideran las clases ya descargadas: antes "siguiente" intentaba
        # abrir una clase que no estaba en el teléfono y no sonaba nada.
        from kivy.app import App
        lista = db.get_grabaciones_por_categoria(grab["categoria_id"])
        if App.get_running_app().offline:
            descargadas = db.get_ids_descargados()
            lista = [g for g in lista if g["id"] in descargadas or g["id"] == grabacion_id]
        self._lista_categoria = lista
        self._indice_actual = next(
            (i for i, g in enumerate(self._lista_categoria) if g["id"] == grabacion_id), 0
        )

        self.ids.titulo_clase.text = grab["nombre"]
        if categoria:
            grupo = categoria["grupo"] or ""
            self.ids.subtitulo_clase.text = (
                f"{categoria['nombre']} • {grupo}" if grupo else categoria["nombre"]
            )
            self.ids.icono_categoria.icon = categoria["icono"] or "book-outline"
        else:
            self.ids.subtitulo_clase.text = ""
            self.ids.icono_categoria.icon = "book-outline"
        self.ids.slider.value = 0
        self.ids.lbl_pos.text = "00:00"
        self.ids.lbl_dur.text = "00:00"
        self.ids.onda.set_semilla(grabacion_id)  # cada clase tiene su "huella"
        self.ids.onda.progress = 0

        path = local_path or db.get_ruta_local(grabacion_id) or grab["url_audio"]
        if not os.path.isabs(path):
            path = os.path.join(os.path.dirname(os.path.dirname(__file__)), path)

        # Si el archivo no existe, avisar en vez de quedarse "reproduciendo"
        # en silencio (ffpyplayer no siempre lanza error al abrir un archivo
        # inexistente).
        if not os.path.exists(path):
            audio_engine.stop()
            mostrar_aviso("No se encontró el audio de esta clase")
            return

        # Vuelve siempre a 1.0x con cada clase nueva.
        audio_engine.speed = 1.0
        for s, btn in self._speed_buttons.items():
            btn.active = (s == 1.0)

        # load() es asíncrono: abre el archivo en un hilo de fondo y
        # reproduce automáticamente en cuanto esté listo (ver
        # audio_player.AudioEngine.load). Mientras tanto la UI muestra el
        # estado "cargando" a través de _on_engine_state, sin bloquear
        # nada de la interfaz.
        audio_engine.load(path, duration_hint=grab["duracion_seg"] or 0)

    # ---- Reacciones al estado del motor de audio ----------------------
    def _on_engine_state(self, *args):
        if audio_engine.is_loading:
            self.ids.btn_play.icon = "timer-sand"
            self.ids.btn_play.disabled = True
        else:
            self.ids.btn_play.disabled = False
            self.ids.btn_play.icon = "pause" if audio_engine.is_playing else "play"

    # ---- Controles ---------------------------------------------------
    def toggle_play(self):
        if audio_engine.is_loading:
            return
        audio_engine.toggle_play_pause()

    def retroceder_10(self):
        audio_engine.seek_relativo(-10)

    def adelantar_10(self):
        audio_engine.seek_relativo(10)

    def saltar_anterior(self):
        """Estilo reproductor de música: con más de 3 s reproducidos vuelve
        al inicio de esta clase; si no, salta a la clase anterior."""
        if audio_engine.position > 3:
            audio_engine.restart()
            return
        self._ir_a_indice(getattr(self, "_indice_actual", 0) - 1)

    def saltar_siguiente(self):
        """Reproduce la siguiente clase de la misma categoría, si existe."""
        self._ir_a_indice(getattr(self, "_indice_actual", 0) + 1)

    def _ir_a_indice(self, indice: int):
        lista = getattr(self, "_lista_categoria", None)
        if not lista or indice < 0 or indice >= len(lista):
            return  # ya es la primera / última clase de la categoría
        # Ya estamos en PlayerScreen: solo recargamos la nueva grabación,
        # sin pasar por app.abrir_reproductor() (eso reescribiría a dónde
        # vuelve el botón "atrás", ya que se fija según la pantalla activa
        # en ese momento). `cargar_grabacion` prefiere la copia descargada
        # si existe (antes "siguiente" siempre usaba la ruta original).
        self.cargar_grabacion(lista[indice]["id"])

    def set_speed(self, speed):
        audio_engine.set_speed(speed)
        for s, btn in self._speed_buttons.items():
            btn.active = (s == speed)

    def on_slider_press(self, instance, touch):
        """El dedo tocó la barra: se pausa la actualización automática."""
        if instance.collide_point(*touch.pos):
            self._arrastrando_slider = True

    def on_slider_release(self, instance, touch):
        """Al soltar, salta a la posición elegida. Se usa la bandera en vez
        de `collide_point`: si el dedo se salía de la barra hacia arriba o
        abajo antes de soltar, el salto se perdía y la perilla volvía atrás."""
        if self._arrastrando_slider:
            self._arrastrando_slider = False
            audio_engine.seek(instance.value)

    # ---- UI loop -------------------------------------------------
    def _actualizar_ui(self, dt):
        if self.manager and self.manager.current != "player_screen":
            return
        dur = audio_engine.duration or 0
        pos = audio_engine.position or 0
        self.ids.slider.max = max(dur, 1)
        if not self._arrastrando_slider:
            self.ids.slider.value = pos
        self.ids.lbl_pos.text = self._fmt(pos)
        self.ids.lbl_dur.text = self._fmt(dur)
        # La onda decorativa avanza junto con la reproducción.
        self.ids.onda.progress = (pos / dur) if dur else 0

    @staticmethod
    def _fmt(seconds):
        seconds = int(seconds or 0)
        return f"{seconds // 60:02d}:{seconds % 60:02d}"

    def on_leave(self, *args):
        audio_engine.stop()
