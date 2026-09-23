"""
notifications_tab.py — TAB 2: NOTIFICACIONES ("Alertas" en el mock)

Lista vertical con:
  - "Descarga completada"
  - "Nueva grabación disponible en [Categoría]"

Funcionalidad agregada (Categoria_notifaciones_update.md):
  - Deslizar una notificación (izq. o der.) la oculta de la lista.
  - Botón "Limpiar todas" arriba a la derecha (con confirmación).
  - Muestra como máximo 6 notificaciones. Si hay 7 o más, aparece un
    botón "Mostrar todas las notificaciones" debajo del título, que
    navega a NotificationsAllScreen (pantalla con estilo idéntico).

IMPORTANTE: "eliminar"/"ocultar" NUNCA borra de la base de datos — es un
ocultamiento de la sesión actual en memoria (`notifications_state`). Ver
ese módulo para el porqué.

Compatible con KivyMD 2.0.0.
"""

import os

from kivy.lang import Builder
from kivy.properties import BooleanProperty

from kivymd.uix.screen import MDScreen

import db
from screens.notifications_state import notificaciones_state
from screens.notification_widgets import construir_lista, confirmar_limpiar_todas

Builder.load_file(os.path.join(os.path.dirname(__file__), "notifications_tab.kv"))

MAX_VISIBLES = 6
UMBRAL_MOSTRAR_TODAS = 7  # el botón "Mostrar todas" aparece con 7 o más


class NotificationsTab(MDScreen):
    mostrar_boton_todas = BooleanProperty(False)

    def on_pre_enter(self, *args):
        self.refrescar()

    def refrescar(self):
        from kivy.app import App

        app = App.get_running_app()
        if not app.usuario:
            self.ids.lista.clear_widgets()
            self.mostrar_boton_todas = False
            return

        todas = db.get_notificaciones(app.usuario["id"])
        visibles = notificaciones_state.filtrar_visibles(todas)

        self.mostrar_boton_todas = len(visibles) >= UMBRAL_MOSTRAR_TODAS
        construir_lista(self.ids.lista, visibles[:MAX_VISIBLES], self._on_dismiss)

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

    def ir_a_todas(self):
        from kivy.app import App
        App.get_running_app().abrir_todas_notificaciones()
