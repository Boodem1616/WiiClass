"""
notifications_all_screen.py — "Categoría Notificaciones 2"

Muestra TODAS las notificaciones (sin el límite de 6 del Tab), con el
mismo estilo visual, el mismo gesto de deslizar para eliminar, y el mismo
botón "Limpiar todas" que el Tab de Notificaciones — comparten el mismo
módulo `notification_widgets` y el mismo estado `notifications_state`,
así que cualquier cambio hecho acá se refleja en el Tab (y viceversa) la
próxima vez que cada uno se muestre.

Es una pantalla de nivel de app (como CategoryScreen/PlayerScreen), no un
tab más: se llega a ella desde el botón "Mostrar todas las
notificaciones" del Tab, y se vuelve con la flecha "atrás".
"""

import os

from kivy.lang import Builder

from kivymd.uix.screen import MDScreen

import db
from screens.notifications_state import notificaciones_state
from screens.notification_widgets import construir_lista, confirmar_limpiar_todas

Builder.load_file(os.path.join(os.path.dirname(__file__), "notifications_all_screen.kv"))


class NotificationsAllScreen(MDScreen):
    def on_pre_enter(self, *args):
        self.refrescar()

    def refrescar(self):
        from kivy.app import App

        app = App.get_running_app()
        if not app.usuario:
            self.ids.lista.clear_widgets()
            return

        todas = db.get_notificaciones(app.usuario["id"])
        visibles = notificaciones_state.filtrar_visibles(todas)
        construir_lista(self.ids.lista, visibles, self._on_dismiss)

    def _on_dismiss(self, notificacion_id):
        notificaciones_state.ocultar(notificacion_id)
        self.refrescar()

    def confirmar_limpiar(self):
        from kivy.app import App

        app = App.get_running_app()
        if not app.usuario:
            return
        todas_ids = [n["id"] for n in db.get_notificaciones(app.usuario["id"])]

        def _limpiar():
            notificaciones_state.ocultar_todas(todas_ids)
            self.refrescar()

        confirmar_limpiar_todas(_limpiar)
