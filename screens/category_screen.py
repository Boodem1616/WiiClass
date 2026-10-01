"""
category_screen.py — Al entrar a una categoría: listado / scroll de
"Clases Grabadas". Al tocar una clase se abre el reproductor de audio.

Funcionalidad agregada (instrucciones.md - "Mejoras en la Categoría
Clases"):
  - Pestañas "Todas" / "Semana 1" / "Semana 2" / ... para filtrar la
    lista (la cantidad de semanas se calcula dinámicamente por
    categoría, ver `db.recalcular_semanas`).
  - Botón de descarga en la esquina inferior derecha de cada tarjeta;
    cambia a un ícono de "listo" (✓) una vez descargada.
  - Mantener presionada una tarjeta activa el modo de selección
    múltiple, para descargar varias clases de una sola vez.

Compatible con KivyMD 2.0.0 (MDTopAppBar declarativo con contenedores).

NOTA sobre por qué `ClaseRow` NO es un `MDCard`:
Se probó primero con `MDCard` (como el resto de las tarjetas de la app),
pero causaba tarjetas invisibles/"rotas" de forma intermitente: `MDCard`
usa `RippleBehavior`, que arma un framebuffer interno UNA SOLA VEZ, al
tamaño que tenga el widget en el momento exacto de construirse, y nunca lo
vuelve a redimensionar — si se construye antes de que el layout real haya
asignado su ancho definitivo (algo que varía según el dispositivo/driver
de GPU y no se pudo hacer 100% determinístico ni siquiera esperando y
sondeando el ancho), el framebuffer queda mal para siempre. La solución
robusta —que no depende de ninguna temporización— es no usar
`RippleBehavior` en absoluto para esta tarjeta: `ClaseRow` es un
`ButtonBehavior` + `BoxLayout` común, con el fondo redondeado dibujado a
mano en `canvas.before` (reactivo a `pos`/`size`, se actualiza solo en
cada resize, sin ningún framebuffer de por medio). Se pierde el efecto
ripple visual al tocar, pero se gana que la tarjeta SIEMPRE se vea bien,
en cualquier dispositivo.
"""

import os

from kivy.lang import Builder
from kivy.metrics import dp
from kivy.factory import Factory
from kivy.clock import Clock
from kivy.properties import (
    NumericProperty, StringProperty, BooleanProperty, ObjectProperty,
)

from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivymd.uix.button import MDIconButton
from kivymd.uix.screen import MDScreen

import db
import theme
from downloads_manager import descargar_grabacion, descargar_varias
from screens.widgets import mostrar_aviso

Builder.load_file(os.path.join(os.path.dirname(__file__), "category_screen.kv"))

DURACION_LONG_PRESS = 0.5  # segundos
UMBRAL_MOVIMIENTO_CANCELA = dp(10)
ALTO_FILA = dp(76)


class ClaseRow(ButtonBehavior, BoxLayout):
    """Tarjeta de una clase grabada: ícono/checkbox a la izquierda, título
    y fecha al centro. El botón de descarga se agrega como un hijo
    HERMANO (no propio) dentro de `ClaseRowSlot`, para poder anclarlo
    libremente en la esquina inferior derecha (ver esa clase).

    `ButtonBehavior` (no `RippleBehavior`/`MDCard`, ver el docstring del
    módulo) da el evento `on_release` de forma estándar y ya probada,
    incluida su correcta convivencia con el `ScrollView` que contiene la
    lista (no compite por el touch al hacer scroll).

    El gesto de "mantener presionado" se implementa a mano (igual que el
    swipe-to-dismiss de notificaciones): Kivy no trae long-press
    incorporado. Se agenda un `Clock.schedule_once` al tocar, que se
    cancela si el dedo se levanta antes de tiempo o si se mueve más de
    `UMBRAL_MOVIMIENTO_CANCELA` (para no confundirlo con un scroll).
    """

    grabacion_id = NumericProperty(0)
    titulo = StringProperty("")
    fecha = StringProperty("")
    duracion_txt = StringProperty("")
    descargada = BooleanProperty(False)
    seleccionada = BooleanProperty(False)
    modo_seleccion = BooleanProperty(False)
    screen = ObjectProperty(None)  # referencia explícita a CategoryScreen

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._long_press_event = None
        self._touch_start_pos = None

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._touch_start_pos = touch.pos
            self._long_press_event = Clock.schedule_once(
                self._disparar_long_press, DURACION_LONG_PRESS
            )
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if self._long_press_event and self._touch_start_pos:
            dx = touch.x - self._touch_start_pos[0]
            dy = touch.y - self._touch_start_pos[1]
            if (dx * dx + dy * dy) ** 0.5 > UMBRAL_MOVIMIENTO_CANCELA:
                self._cancelar_long_press()
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        self._cancelar_long_press()
        return super().on_touch_up(touch)

    def _cancelar_long_press(self):
        if self._long_press_event:
            self._long_press_event.cancel()
            self._long_press_event = None

    def _disparar_long_press(self, dt):
        self._long_press_event = None
        if self.screen:
            self.screen.activar_seleccion_multiple(self.grabacion_id)

    def on_release(self):
        if not self.screen:
            return
        if self.screen.modo_seleccion:
            self.screen.alternar_seleccion(self.grabacion_id)
        else:
            from kivy.app import App
            App.get_running_app().abrir_reproductor(self.grabacion_id)

    def tocar_descarga(self):
        if self.descargada or not self.screen:
            return
        self.screen.descargar_una(self.grabacion_id)


class ClaseRowSlot(FloatLayout):
    """Envuelve una `ClaseRow` y le agrega el botón de descarga anclado en
    la esquina inferior derecha, usando `pos_hint` — algo que `ClaseRow`
    (un `BoxLayout`) no permite hacer directamente con sus propios hijos.
    """

    def __init__(self, screen, grabacion, descargada: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_x = 1
        self.size_hint_y = None
        self.height = ALTO_FILA
        self.grabacion_id = grabacion["id"]

        # `descargada` llega precalculado por CategoryScreen (una sola
        # consulta para toda la lista) en vez de consultar la BD por fila.
        self.row = ClaseRow(
            screen=screen,
            grabacion_id=grabacion["id"],
            titulo=grabacion["nombre"],
            fecha=theme.fmt_fecha(grabacion["fecha_subida"]),
            duracion_txt=theme.fmt_duracion(grabacion["duracion_seg"]),
            descargada=descargada,
            modo_seleccion=screen.modo_seleccion,
            seleccionada=grabacion["id"] in screen._seleccionadas,
            size_hint=(1, 1),
            pos=(0, 0),
        )
        self.add_widget(self.row)
        # FloatLayout NO redimensiona a sus hijos solos: se sincroniza a mano
        # cada vez que cambia el tamaño/posición del contenedor.
        self.bind(size=self._sincronizar_fila, pos=self._sincronizar_fila)
        self._sincronizar_fila()

        self.boton_descarga = MDIconButton(
            icon="check-circle" if descargada else "download-outline",
            theme_text_color="Custom",
            text_color=theme.SUCCESS if descargada else theme.TEXT_SOFT,
            # Centrado verticalmente en la tarjeta, pegado al borde derecho.
            pos_hint={"right": 0.985, "center_y": 0.5},
            size_hint=(None, None),
            disabled=descargada,
        )
        self.boton_descarga.bind(on_release=lambda *_a: self.row.tocar_descarga())
        # El botón de descarga no debe abrir el reproductor ni activar la
        # selección múltiple: se atiende aparte, no es hijo de la tarjeta
        # (al ser un hijo posterior en el FloatLayout, Kivy ya le da
        # prioridad de recepción del touch sobre la tarjeta que está
        # debajo, así que un toque ahí nunca llega a `ClaseRow`).
        self.add_widget(self.boton_descarga)

    def _sincronizar_fila(self, *_args):
        self.row.pos = self.pos
        self.row.size = self.size


class CategoryScreen(MDScreen):
    modo_seleccion = BooleanProperty(False)
    categoria_id = NumericProperty(0)
    num_seleccionadas = NumericProperty(0)
    titulo_categoria = StringProperty("")  # se muestra en la cabecera

    def on_kv_post(self, base_widget):
        self._semana_actual = None  # None = pestaña "Todas"
        self._seleccionadas = set()
        self._week_buttons = {}

    def atras(self):
        """Botón de la esquina izquierda de la cabecera: en modo selección
        cancela la selección; en modo normal vuelve al Inicio."""
        from kivy.app import App
        if self.modo_seleccion:
            self.salir_de_seleccion()
        else:
            App.get_running_app().volver_a_inicio()

    def mostrar_categoria(self, categoria_id: int, nombre: str):
        self.categoria_id = categoria_id
        self.titulo_categoria = nombre
        self._semana_actual = None
        self.modo_seleccion = False
        self._seleccionadas = set()
        self.num_seleccionadas = 0
        self._construir_pestanas_semana()
        self._refrescar_lista()

    # ---- Pestañas de semana ------------------------------------------
    def _construir_pestanas_semana(self):
        contenedor = self.ids.semanas_row
        contenedor.clear_widgets()
        self._week_buttons = {}

        semanas = db.get_semanas_disponibles(self.categoria_id)

        btn_todas = Factory.WeekTab()
        btn_todas.valor = None
        btn_todas.activo = True
        btn_todas.texto = "Todas"
        btn_todas.bind(on_release=lambda inst: self._filtrar_por_semana(None))
        contenedor.add_widget(btn_todas)
        self._week_buttons[None] = btn_todas

        for n in semanas:
            btn = Factory.WeekTab()
            btn.valor = n
            btn.activo = False
            btn.texto = f"Semana {n}"
            btn.bind(on_release=lambda inst, s=n: self._filtrar_por_semana(s))
            contenedor.add_widget(btn)
            self._week_buttons[n] = btn

    def _filtrar_por_semana(self, semana):
        self._semana_actual = semana
        for valor, btn in self._week_buttons.items():
            btn.activo = (valor == semana)
        self._refrescar_lista()

    # ---- Lista de clases -----------------------------------------------
    def _refrescar_lista(self):
        contenedor = self.ids.lista_clases
        contenedor.clear_widgets()

        grabaciones = db.get_grabaciones_por_categoria(self.categoria_id, self._semana_actual)
        descargadas = db.get_ids_descargados()  # una consulta para toda la lista
        if not grabaciones:
            contenedor.add_widget(Factory.TextoSuave(
                text="No hay clases en esta semana.", size_hint_y=None, height=dp(28)))
        for g in grabaciones:
            contenedor.add_widget(ClaseRowSlot(self, g, descargada=g["id"] in descargadas))

    # ---- Selección múltiple (mantener presionado) ----------------------
    def activar_seleccion_multiple(self, grabacion_id_inicial: int):
        if self.modo_seleccion:
            return
        self.modo_seleccion = True
        self._seleccionadas = {grabacion_id_inicial}
        self.num_seleccionadas = len(self._seleccionadas)
        self._refrescar_lista()

    def alternar_seleccion(self, grabacion_id: int):
        if grabacion_id in self._seleccionadas:
            self._seleccionadas.discard(grabacion_id)
        else:
            self._seleccionadas.add(grabacion_id)
        self.num_seleccionadas = len(self._seleccionadas)
        if not self._seleccionadas:
            self.salir_de_seleccion()
        else:
            self._refrescar_lista()

    def salir_de_seleccion(self):
        self.modo_seleccion = False
        self._seleccionadas = set()
        self.num_seleccionadas = 0
        self._refrescar_lista()

    def descargar_seleccionadas(self):
        from kivy.app import App
        app = App.get_running_app()
        if not app.usuario or not self._seleccionadas:
            return
        ids = list(self._seleccionadas)

        def _cada_una(grabacion_id):
            self._refrescar_lista()

        def _completas():
            mostrar_aviso("Descarga terminada")
            self.salir_de_seleccion()

        descargar_varias(app.usuario["id"], ids, on_cada_una=_cada_una, on_todas_completas=_completas)

    # ---- Descarga individual --------------------------------------------
    def descargar_una(self, grabacion_id: int):
        from kivy.app import App
        app = App.get_running_app()
        if not app.usuario:
            return

        def _completa(g_id):
            self._refrescar_lista()

        def _error(g_id, exc):
            # Antes un error de descarga no se mostraba: el ícono se quedaba
            # igual y el usuario no sabía si había fallado.
            mostrar_aviso("No se pudo descargar la clase")

        descargar_grabacion(app.usuario["id"], grabacion_id,
                            on_completa=_completa, on_error=_error)
