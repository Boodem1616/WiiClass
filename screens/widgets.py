"""
widgets.py — Widgets propios reutilizables por varias pantallas.

Contiene:
  - CabeceraDegradada: barra superior con fondo azul degradado.
  - Waveform: "forma de onda" decorativa que se va iluminando con el
    progreso de la clase (elemento visual distintivo del reproductor).
  - mostrar_aviso(): aviso breve (toast) usable desde cualquier pantalla.

Todo se dibuja con instrucciones simples de canvas (sin MDCard/Ripple ni
Stencil), siguiendo las lecciones documentadas en README2.md: los widgets
con framebuffer o stencil dieron problemas en algunos drivers de GPU.
"""

import random

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.properties import NumericProperty, ColorProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

import theme
from screens.gradient_utils import aplicar_degradado


class CabeceraDegradada(BoxLayout):
    """BoxLayout con el degradado azul de la marca como fondo.

    Se usa en kv como cualquier BoxLayout (`CabeceraDegradada:`), y sus
    hijos son el contenido de la cabecera (título, botones, etc.).
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 16 bandas bastan para una barra baja; menos bandas = menos
        # instrucciones de canvas que redibujar en cada frame.
        aplicar_degradado(
            self, theme.GRAD_TOP, theme.GRAD_BOTTOM,
            direccion="vertical", n_bandas=16,
        )


class Waveform(Widget):
    """Barras verticales que imitan una forma de onda de audio.

    `progress` (0..1) decide cuántas barras se pintan como "ya
    reproducidas". La altura de cada barra sale de un generador con semilla
    fija, así que la forma es estable (no parpadea) y distinta por clase
    (ver `set_semilla`). No analiza el audio real: es decorativa.
    """

    progress = NumericProperty(0.0)
    color_activo = ColorProperty((1, 1, 1, 1))
    color_inactivo = ColorProperty((1, 1, 1, 0.35))
    N_BARRAS = 34

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._alturas = []
        self._barras = []  # lista de (Color, RoundedRectangle)
        self.set_semilla(1)
        with self.canvas:
            for _ in range(self.N_BARRAS):
                color = Color(1, 1, 1, 0.35)
                rect = RoundedRectangle(pos=(0, 0), size=(1, 1), radius=[1])
                self._barras.append((color, rect))
        self.bind(
            pos=self._acomodar, size=self._acomodar,
            progress=self._colorear,
            color_activo=self._colorear, color_inactivo=self._colorear,
        )
        self._acomodar()
        self._colorear()

    def set_semilla(self, semilla):
        """Cambia la 'huella' de la onda (una distinta por cada clase)."""
        rng = random.Random(int(semilla))
        alturas = []
        previa = 0.5
        for _ in range(self.N_BARRAS):
            # Suavizado: cada barra se parece un poco a la anterior, lo que
            # da un aspecto más natural que valores totalmente aleatorios.
            previa = 0.55 * previa + 0.45 * rng.uniform(0.15, 1.0)
            alturas.append(max(0.12, previa))
        self._alturas = alturas
        if self._barras:
            self._acomodar()

    def _acomodar(self, *_args):
        """Reposiciona las barras (se llama al cambiar pos/size)."""
        n = self.N_BARRAS
        if not self._barras or self.width <= 0:
            return
        ranura = self.width / n
        ancho = max(2.0, ranura * 0.58)
        for i, (_color, rect) in enumerate(self._barras):
            alto = max(dp(4), self._alturas[i] * self.height)
            rect.pos = (self.x + i * ranura + (ranura - ancho) / 2,
                        self.center_y - alto / 2)
            rect.size = (ancho, alto)
            rect.radius = [ancho / 2]

    def _colorear(self, *_args):
        """Pinta de 'activo' las barras ya reproducidas."""
        n = self.N_BARRAS
        limite = self.progress * n
        for i, (color, _rect) in enumerate(self._barras):
            color.rgba = self.color_activo if i < limite else self.color_inactivo


def mostrar_aviso(mensaje: str, duracion: float = 2.4):
    """Muestra un aviso breve cerca de la parte baja de la ventana.

    Igual que el `_toast` original del Login, NO usa MDSnackbar (su Fbo
    interno falla en algunos drivers; ver login_screen.py). Se agrega
    directamente a la `Window`, por lo que sirve desde cualquier pantalla.
    """
    lbl = Label(
        text=mensaje,
        color=(1, 1, 1, 1),
        size_hint=(None, None),
        halign="center",
    )
    lbl.texture_update()
    ancho = min(lbl.texture_size[0] + dp(40), Window.width - dp(24))
    lbl.size = (ancho, dp(44))
    lbl.text_size = (ancho - dp(24), None)
    lbl.pos = ((Window.width - ancho) / 2, dp(96))

    with lbl.canvas.before:
        Color(0.05, 0.09, 0.28, 0.94)
        fondo = RoundedRectangle(pos=lbl.pos, size=lbl.size, radius=[dp(22)])

    def _seguir(*_a):
        fondo.pos = lbl.pos
        fondo.size = lbl.size

    lbl.bind(pos=_seguir, size=_seguir)
    Window.add_widget(lbl)
    Clock.schedule_once(lambda dt: Window.remove_widget(lbl), duracion)
