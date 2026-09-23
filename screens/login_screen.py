"""
login_screen.py — Pantalla 1: LOGIN

Replica el mockup original (Inicio_sesion.png):
  - Fondo con degradado azul (más claro arriba, más oscuro abajo) y
    "cuadernos" flotando hacia arriba (animación loop, ligera).
  - Logo circular blanco con ícono de micrófono.
  - Campos "píldora" translúcidos directamente sobre el fondo azul
    (sin tarjeta blanca envolvente): Institución (desplegable),
    Correo Institucional, Contraseña (con botón de mostrar/ocultar).
  - Botón "Iniciar Sesión" blanco con texto azul.
  - Sin registro de usuarios (solo inicio de sesión).

Compatible con KivyMD 2.0.0 (API declarativa: MDButton/MDButtonText,
MDDropdownMenu). Los campos de texto se implementan con `TextInput` simple
(no `MDTextField`) para poder lograr el estilo "píldora translúcida con
ícono" del mockup, que es distinto al estilo Material de MDTextField. Los
avisos ("Selecciona tu institución", etc.) se muestran con un widget propio
en vez de `MDSnackbar` — ver el docstring de `_toast` más abajo.

NOTA DE RENDIMIENTO: cualquier animación continua obliga a Kivy a redibujar
toda la ventana en cada frame. En dispositivos/entornos sin aceleración de
GPU (renderizado por software) eso puede saturar la CPU y hacer que la app
"se sienta congelada". Por eso aquí la animación:
  1) se limita a pocos elementos concurrentes y a un ritmo de aparición bajo,
  2) usa pasos discretos en vez de interpolación continua,
  3) SOLO corre mientras esta pantalla está realmente visible (se detiene
     por completo con on_leave / se reanuda con on_enter).
"""

import random
import os

from kivy.lang import Builder
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.properties import ObjectProperty
from kivy.graphics import Color, Rectangle

from kivymd.uix.screen import MDScreen
from kivymd.uix.menu import MDDropdownMenu

import db

MAX_NOTEBOOKS_CONCURRENTES = 3
INTERVALO_SPAWN_SEG = 3.2

# Colores del degradado de fondo (arriba -> abajo), tomados del mockup.
COLOR_GRADIENTE_ARRIBA = (0.22, 0.34, 0.64)
COLOR_GRADIENTE_ABAJO = (0.05, 0.09, 0.28)

# Color "píldora" translúcida de los campos (blanco a baja opacidad sobre
# el fondo azul, igual que en el mockup).
COLOR_CAMPO = (1, 1, 1, 0.14)
COLOR_TEXTO_CLARO = (0.85, 0.88, 0.97, 1)
COLOR_TEXTO_LABEL = (0.75, 0.8, 0.95, 1)

Builder.load_file(os.path.join(os.path.dirname(__file__), "login_screen.kv"))


class LoginScreen(MDScreen):
    institucion_seleccionada = ObjectProperty(None, allownone=True)

    N_BANDAS_DEGRADADO = 28

    def _construir_fondo_degradado(self):
        """Pinta un degradado vertical con bandas de color apiladas.

        Se hace "a mano" con instrucciones de canvas (en vez de una
        textura) porque es más simple de depurar y no depende de que el
        `blit_buffer` de la textura tenga el formato/orden exacto que
        Kivy espera: cada banda es sencillamente un rectángulo de un color
        interpolado, así que si algo se ve mal es evidente por qué.
        """
        # No usamos `self.canvas.before.clear()`: KivyMD ata instrucciones
        # de Push/Pop de estado internamente (por `BackgroundColorBehavior`)
        # y limpiarlo a mano rompe ese balance (crashea con
        # "IndexError: list index out of range" al dibujar). En cambio,
        # simplemente agregamos nuestras bandas AL FINAL del mismo grupo:
        # al dibujarse después, quedan pintadas encima y tapan el fondo
        # sólido por defecto sin tocar lo que KivyMD ya armó.
        self._bandas = []
        n = self.N_BANDAS_DEGRADADO
        r1, g1, b1 = COLOR_GRADIENTE_ARRIBA
        r2, g2, b2 = COLOR_GRADIENTE_ABAJO
        with self.canvas.before:
            for i in range(n):
                t = i / (n - 1)
                color = Color(
                    r1 + (r2 - r1) * t,
                    g1 + (g2 - g1) * t,
                    b1 + (b2 - b1) * t,
                    1,
                )
                rect = Rectangle(pos=(0, 0), size=(1, 1))
                self._bandas.append(rect)
        self.bind(size=self._actualizar_fondo_degradado, pos=self._actualizar_fondo_degradado)
        self._actualizar_fondo_degradado()

    def _actualizar_fondo_degradado(self, *args):
        n = len(self._bandas)
        if not n or self.height <= 0:
            return
        alto_banda = self.height / n
        for i, rect in enumerate(self._bandas):
            # i=0 debe quedar arriba de la pantalla (coordenadas Kivy: y
            # crece hacia arriba, así que "arriba" = self.y + self.height).
            y = self.y + self.height - (i + 1) * alto_banda
            rect.pos = (self.x, y)
            rect.size = (self.width, alto_banda + 1)  # +1 evita líneas finas entre bandas

    def on_kv_post(self, base_widget):
        self._construir_fondo_degradado()
        self._instituciones = {row["nombre"]: row["id"] for row in db.get_instituciones()}
        self._institucion_id = None
        self._menu = None
        self._spawn_start_event = None
        self._spawn_interval_event = None
        self._notebooks_activos = 0

    def on_enter(self, *args):
        # La animación solo corre mientras el Login está realmente visible:
        # así evitamos gastar CPU/batería redibujando de fondo una vez que
        # el usuario ya pasó a la pantalla principal.
        if self._spawn_start_event is None and self._spawn_interval_event is None:
            self._spawn_start_event = Clock.schedule_once(self._spawn_notebooks, 0.3)

    def on_leave(self, *args):
        if self._spawn_start_event:
            self._spawn_start_event.cancel()
            self._spawn_start_event = None
        if self._spawn_interval_event:
            self._spawn_interval_event.cancel()
            self._spawn_interval_event = None
        # Limpia los cuadernos que hayan quedado animándose a mitad de camino.
        self.ids.notebook_layer.clear_widgets()
        self._notebooks_activos = 0

    # ---- Selector de institución ----------------------------------
    def abrir_menu_instituciones(self, caller):
        items = [
            {
                "text": nombre,
                "on_release": lambda n=nombre: self._elegir_institucion(n),
            }
            for nombre in self._instituciones.keys()
        ]
        self._menu = MDDropdownMenu(caller=caller, items=items)
        self._menu.open()

    def _elegir_institucion(self, nombre):
        self.institucion_seleccionada = nombre
        self._institucion_id = self._instituciones[nombre]
        self.ids.institucion_label.text = nombre
        if self._menu:
            self._menu.dismiss()

    # ---- Mostrar/ocultar contraseña ------------------------------
    def toggle_password_visibility(self):
        campo = self.ids.password
        campo.password = not campo.password
        self.ids.toggle_password.icon = "eye-off-outline" if campo.password else "eye-outline"

    # ---- Login ------------------------------------------------------
    def iniciar_sesion(self):
        correo = self.ids.correo.text.strip()
        password = self.ids.password.text.strip()

        if not self._institucion_id:
            self._toast("Selecciona tu institución")
            return
        if not correo or not password:
            self._toast("Completa correo y contraseña")
            return

        usuario = db.login(self._institucion_id, correo, password)
        if usuario is None:
            self._toast("Credenciales incorrectas")
            return

        from kivy.app import App
        App.get_running_app().on_login_success(usuario["id"])

    @staticmethod
    def _toast(mensaje: str):
        """Muestra un aviso breve abajo de la pantalla.

        NO usa `MDSnackbar`: en KivyMD 2.0, `MDSnackbar` hereda de
        `RippleBehavior`, que al construirse crea un `Fbo` (framebuffer)
        del tamaño que tenga el widget en ESE momento. Si todavía no tiene
        un tamaño real asignado (0, 0) —algo que puede pasar según el
        driver de GPU/OpenGL— la creación del framebuffer falla con
        "FBO Initialization failed: Incomplete attachment" y crashea la
        app. Por eso este aviso se arma con widgets simples (Label +
        canvas propio), sin ripple ni Fbo, para que sea robusto en
        cualquier equipo/driver.
        """
        from kivy.app import App
        from kivy.uix.label import Label
        from kivy.graphics import Color, RoundedRectangle

        app = App.get_running_app()
        contenedor = app.sm.get_screen("login").ids.root_layout

        lbl = Label(
            text=mensaje,
            color=(1, 1, 1, 1),
            size_hint=(None, None),
            padding=(dp(18), dp(10)),
            pos_hint={"center_x": 0.5, "y": 0.06},
        )
        lbl.texture_update()
        lbl.size = (lbl.texture_size[0] + dp(36), dp(42))

        with lbl.canvas.before:
            Color(0.12, 0.12, 0.16, 0.92)
            rect = RoundedRectangle(pos=lbl.pos, size=lbl.size, radius=[dp(21)])

        def _seguir_widget(*_args):
            rect.pos = lbl.pos
            rect.size = lbl.size

        lbl.bind(pos=_seguir_widget, size=_seguir_widget)

        contenedor.add_widget(lbl)
        Clock.schedule_once(lambda dt: contenedor.remove_widget(lbl), 2.2)

    # ---- Animación de fondo (cuadernos flotando) --------------------
    #
    # IMPORTANTE sobre rendimiento: se probó con `kivy.animation.Animation`
    # (interpolación suave) y, en entornos SIN aceleración de GPU
    # (renderizado por software), eso obliga a Kivy a redibujar la ventana
    # completa a la máxima tasa de fps posible sin parar -> ~97% de CPU
    # sostenido y la sensación de "app congelada". Se midió en este mismo
    # proyecto: con Animation continua, ~97% CPU; con la animación
    # completamente apagada, ~1% CPU.
    #
    # Solución: en vez de interpolar cada frame, se reposiciona el widget en
    # pasos discretos con un Clock.schedule_interval de baja frecuencia
    # (varias veces por segundo en vez de 30-60). Sigue viéndose como
    # "flotando hacia arriba", pero el canvas solo se invalida esa pocas
    # veces por segundo en lugar de continuamente.
    PASOS_POR_SEGUNDO = 6          # a más alto, más fluido pero más CPU
    ALTO_POR_PASO = dp(10)

    def _spawn_notebooks(self, dt):
        layer = self.ids.notebook_layer
        for _ in range(MAX_NOTEBOOKS_CONCURRENTES):
            self._spawn_one(layer)
        self._spawn_interval_event = Clock.schedule_interval(
            lambda _dt: self._spawn_one(layer), INTERVALO_SPAWN_SEG
        )

    def _spawn_one(self, layer):
        # Límite duro de elementos animándose a la vez: evita que, si el
        # layout tarda en tener tamaño real al inicio, se acumulen widgets.
        if self._notebooks_activos >= MAX_NOTEBOOKS_CONCURRENTES:
            return

        # Se usa MDIcon (fuente Material Design Icons, empaquetada con
        # KivyMD) en vez de un emoji de libro: los emojis dependen de que
        # el sistema operativo tenga una fuente de emojis instalada, y si
        # no la tiene se ven como cajitas vacías (le pasó al usuario en
        # Linux Mint). El ícono de Material Design siempre está disponible.
        from kivymd.uix.label import MDIcon

        lbl = MDIcon(
            icon="notebook-outline",
            font_size=f"{random.randint(20, 34)}sp",
            size_hint=(None, None),
            size=(dp(40), dp(40)),
            opacity=0.18,
            theme_text_color="Custom",
            text_color=(1, 1, 1, 1),
            pos=(random.uniform(0, layer.width or 300), -dp(40)),
        )
        layer.add_widget(lbl)
        self._notebooks_activos += 1

        techo = (layer.height or 600) + dp(50)

        def _paso(_dt):
            lbl.y += self.ALTO_POR_PASO
            if lbl.y >= techo:
                layer.remove_widget(lbl)
                self._notebooks_activos = max(0, self._notebooks_activos - 1)
                return False  # cancela el schedule_interval

        Clock.schedule_interval(_paso, 1.0 / self.PASOS_POR_SEGUNDO)
