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

from kivymd.uix.screen import MDScreen
from kivymd.uix.menu import MDDropdownMenu

import db
import theme
from screens.gradient_utils import aplicar_degradado
from screens.widgets import mostrar_aviso

MAX_NOTEBOOKS_CONCURRENTES = 3
INTERVALO_SPAWN_SEG = 3.2

Builder.load_file(os.path.join(os.path.dirname(__file__), "login_screen.kv"))


class LoginScreen(MDScreen):
    institucion_seleccionada = ObjectProperty(None, allownone=True)

    def on_kv_post(self, base_widget):
        # Degradado de fondo compartido con el resto de la app (ver
        # screens/gradient_utils.py) — antes esta pantalla tenía su propia
        # copia "a mano" de exactamente el mismo cálculo de bandas.
        aplicar_degradado(self, theme.LOGIN_TOP, theme.LOGIN_BOTTOM,
                           direccion="vertical", n_bandas=28)
        self._instituciones = {row["nombre"]: row["id"] for row in db.get_instituciones()}
        self._institucion_id = None
        self._menu = None
        self._spawn_start_event = None
        self._spawn_interval_event = None
        self._notebooks_activos = 0
        self._eventos_paso = []  # relojes de cada cuaderno en vuelo (para cancelarlos)

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
        # Cancela el reloj de cada cuaderno en vuelo. Antes solo se quitaban
        # los widgets, pero los Clock.schedule_interval seguían corriendo
        # ("fantasmas") hasta llegar al techo, gastando CPU y descuadrando el
        # contador si se volvía al Login (cerrar sesión) enseguida.
        for evento in self._eventos_paso:
            evento.cancel()
        self._eventos_paso = []
        self.ids.notebook_layer.clear_widgets()
        self._notebooks_activos = 0

    # ---- Selector de institución ----------------------------------
    def abrir_menu_instituciones(self, caller):
        # Si ya había un menú abierto, se cierra antes de crear otro (antes
        # cada toque creaba un menú nuevo sin descartar el anterior).
        if self._menu:
            self._menu.dismiss()
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

    def olvide_contrasena(self):
        # En esta maqueta no hay servidor que envíe correos de recuperación.
        mostrar_aviso("Recuperación de contraseña: disponible con el servidor")

    # ---- Login ------------------------------------------------------
    def iniciar_sesion(self):
        correo = self.ids.correo.text.strip().lower()
        # La contraseña NO se recorta con .strip(): si tiene espacios al
        # inicio/fin son parte de ella (antes se descartaban en silencio).
        password = self.ids.password.text

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
        """Aviso breve abajo de la pantalla.

        Ahora delega en `screens.widgets.mostrar_aviso`, que se comparte con
        otras pantallas. Sigue SIN usar `MDSnackbar`: en KivyMD 2.0 su
        `RippleBehavior` crea un `Fbo` con el tamaño que tenga el widget en
        ese instante, y con tamaño (0, 0) el framebuffer falla ("FBO
        Initialization failed: Incomplete attachment") y crashea la app en
        algunos drivers. Un Label con canvas propio no tiene ese riesgo.
        """
        mostrar_aviso(mensaje)

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
                if evento in self._eventos_paso:
                    self._eventos_paso.remove(evento)
                return False  # cancela el schedule_interval

        evento = Clock.schedule_interval(_paso, 1.0 / self.PASOS_POR_SEGUNDO)
        self._eventos_paso.append(evento)
