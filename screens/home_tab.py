"""
home_tab.py — TAB 1: INICIO

Scroll horizontal de Categorías de Clases. Al tocar una categoría se navega
a CategoryScreen (scroll horizontal de "Clases Grabadas").

Compatible con KivyMD 2.0.0.
"""

import os

from kivy.lang import Builder
from kivy.metrics import dp
from kivy.factory import Factory
from kivy.uix.scrollview import ScrollView
from kivy.uix.boxlayout import BoxLayout

from kivymd.uix.screen import MDScreen
from kivymd.uix.label import MDLabel

import db

Builder.load_file(os.path.join(os.path.dirname(__file__), "home_tab.kv"))


class HomeTab(MDScreen):
    def on_pre_enter(self, *args):
        self.refrescar()

    def refrescar(self):
        from kivy.app import App
        app = App.get_running_app()
        if app.usuario:
            self.ids.nombre_usuario.text = app.usuario["nombre"]

        container = self.ids.categorias_container
        container.clear_widgets()

        categorias = db.get_categorias()

        section_title = MDLabel(
            text="Categorías",
            bold=True,
            font_style="Title",
            role="medium",
            size_hint_y=None,
            height=dp(28),
        )
        container.add_widget(section_title)

        scroll = ScrollView(do_scroll_x=True, do_scroll_y=False, size_hint_y=None, height=dp(130))
        row = BoxLayout(orientation="horizontal", spacing=dp(14), size_hint_x=None, padding=(0, 0))
        row.bind(minimum_width=row.setter("width"))

        for cat in categorias:
            card = Factory.CategoryCard()
            card.categoria_id = cat["id"]
            card.nombre = cat["nombre"]
            card.grupo = cat["grupo"] or ""
            card.icono = cat["icono"] or "book-outline"
            row.add_widget(card)
        scroll.add_widget(row)
        container.add_widget(scroll)
