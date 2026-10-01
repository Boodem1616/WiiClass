"""
notification_widgets.py — Piezas reutilizables entre el Tab "Notificaciones"
y la pantalla "Todas las notificaciones", para que ambas se vean y se
comporten exactamente igual (mismo estilo, mismo gesto de deslizar, mismo
diálogo de "Limpiar todas") sin duplicar código.

Contiene:
  - `<NotificationRow@MDCard>`: el contenido visual de una notificación
    (igual que antes).
  - `SwipeToDismissRow`: envoltorio que agrega el gesto de "deslizar para
    eliminar" a una `NotificationRow`.
  - `confirmar_limpiar_todas(...)`: diálogo de confirmación reutilizable.
  - `construir_lista(...)`: arma la lista de filas deslizables dentro de
    un contenedor, para no repetir esta lógica en cada pantalla.
"""

import os

from kivy.lang import Builder
from kivy.metrics import dp
from kivy.animation import Animation
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.widget import Widget
from kivy.factory import Factory

from kivymd.uix.dialog import (
    MDDialog,
    MDDialogHeadlineText,
    MDDialogSupportingText,
    MDDialogButtonContainer,
)
from kivymd.uix.button import MDButton, MDButtonText

import theme

Builder.load_file(os.path.join(os.path.dirname(__file__), "notification_widgets.kv"))

ALTO_FILA = dp(76)
UMBRAL_DESCARTE = 0.32  # fracción del ancho que hay que arrastrar para descartar


class SwipeToDismissRow(RelativeLayout):
    """Envuelve una `NotificationRow` y le agrega "deslizar para eliminar"
    (izquierda o derecha, ambas descartan). El gesto se implementa a mano
    porque KivyMD 2.0 no trae un componente de "swipe to dismiss" (la
    versión 1.x tenía `MDCardSwipe`, pero se quitó).

    Cómo convive con el ScrollView vertical que contiene la lista: en
    `on_touch_down` NO se agarra el touch todavía (así el ScrollView
    también lo ve, como siempre). Recién en `on_touch_move`, si el
    movimiento resulta claramente más horizontal que vertical y supera un
    umbral mínimo, esta fila agarra el touch para sí (`touch.grab(self)`)
    — a partir de ahí Kivy le manda los eventos de mover/soltar SOLO a
    esta fila, "robándoselos" al ScrollView. Si en cambio el movimiento es
    más vertical, nunca se agarra el touch, y el ScrollView desplaza la
    lista con total normalidad.
    """

    def __init__(self, notificacion_id, on_dismiss, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.height = ALTO_FILA
        self.notificacion_id = notificacion_id
        self.on_dismiss = on_dismiss
        self.card = None  # se asigna después de crear la NotificationRow
        self._arrastrando = False
        self._x_inicial_touch = None

    def set_card(self, card):
        self.card = card
        card.pos = (0, 0)
        card.size = self.size
        self.bind(size=self._sincronizar_tamano_card)
        self.add_widget(card)

    def _sincronizar_tamano_card(self, *_args):
        if self.card:
            self.card.size = self.size

    # ---- Gesto de deslizar ------------------------------------------
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.ud[f"swipe_ox_{id(self)}"] = touch.x
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        clave_ox = f"swipe_ox_{id(self)}"
        if clave_ox in touch.ud and self.card is not None:
            dx = touch.x - touch.ud[clave_ox]
            dy = touch.y - touch.oy
            if not self._arrastrando and abs(dx) > dp(12) and abs(dx) > abs(dy):
                self._arrastrando = True
                touch.grab(self)
            if self._arrastrando and touch.grab_current is self:
                self.card.x = dx
                self.card.opacity = max(0.25, 1 - abs(dx) / max(self.width, 1))
                return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self and self._arrastrando:
            touch.ungrab(self)
            self._arrastrando = False
            dx = self.card.x
            if abs(dx) > self.width * UMBRAL_DESCARTE:
                self._animar_descarte(dx)
            else:
                self._animar_vuelta()
            return True
        return super().on_touch_up(touch)

    def _animar_descarte(self, dx):
        destino = self.width if dx > 0 else -self.width
        anim = Animation(x=destino, opacity=0, duration=0.18, t="out_quad")
        anim.bind(on_complete=lambda *_a: self.on_dismiss(self.notificacion_id))
        anim.start(self.card)

    def _animar_vuelta(self):
        Animation(x=0, opacity=1, duration=0.15, t="out_quad").start(self.card)


def construir_fila(notificacion, on_dismiss):
    """Crea una `SwipeToDismissRow` lista para agregar a un contenedor."""
    wrapper = SwipeToDismissRow(notificacion_id=notificacion["id"], on_dismiss=on_dismiss)
    card = Factory.NotificationRow()
    card.mensaje = notificacion["mensaje"]
    card.tipo = notificacion["tipo"]
    # Antes esto era siempre "" (la fecha existía en la BD pero nunca se
    # mostraba, y la etiqueta reservaba 70dp en blanco). Ahora: "hace 5 min".
    card.fecha_txt = theme.tiempo_relativo(notificacion["fecha"])
    card.leida = bool(notificacion["leida"])
    wrapper.set_card(card)
    return wrapper


def construir_lista(contenedor, notificaciones, on_dismiss):
    """Limpia `contenedor` y agrega una fila deslizable por notificación."""
    contenedor.clear_widgets()
    for n in notificaciones:
        contenedor.add_widget(construir_fila(n, on_dismiss))


def confirmar_limpiar_todas(on_confirmar):
    """Diálogo '¿Seguro?' antes de ocultar todas las notificaciones."""
    dialog = MDDialog(
        MDDialogHeadlineText(text="¿Eliminar todas las notificaciones?"),
        MDDialogSupportingText(
            text="Se ocultarán todas las notificaciones de esta sesión. "
            "Podrás volver a verlas si cierras sesión y vuelves a entrar."
        ),
        MDDialogButtonContainer(
            Widget(),
            MDButton(
                MDButtonText(text="Cancelar"),
                style="text",
                on_release=lambda *_a: dialog.dismiss(),
            ),
            MDButton(
                MDButtonText(text="Eliminar"),
                style="text",
                on_release=lambda *_a: (dialog.dismiss(), on_confirmar()),
            ),
            spacing=dp(8),
        ),
    )
    dialog.open()
