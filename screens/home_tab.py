"""
home_tab.py — TAB 1: INICIO

Cabecera con saludo + dos secciones:
  - "Categorías": scroll horizontal de tarjetas. Al tocar una se navega a
    CategoryScreen (listado de "Clases Grabadas").
  - "Clases recientes": las 3 últimas grabaciones subidas, tocables para
    abrir el reproductor directamente. (Antes había una tarjeta con el
    título "Clases Recientes" pero sin ninguna clase dentro.)

Compatible con KivyMD 2.0.0.
"""

import os

from kivy.lang import Builder
from kivy.metrics import dp
from kivy.factory import Factory
from kivy.uix.scrollview import ScrollView
from kivy.uix.boxlayout import BoxLayout

from kivymd.uix.screen import MDScreen

import db
import theme

Builder.load_file(os.path.join(os.path.dirname(__file__), "home_tab.kv"))

N_RECIENTES = 3


class HomeTab(MDScreen):
    def on_pre_enter(self, *args):
        self.refrescar()

    def refrescar(self):
        from kivy.app import App
        app = App.get_running_app()

        # ---- Cabecera ----
        self.ids.saludo.text = theme.saludo()
        if app.usuario:
            nombre = app.usuario["nombre"]
            self.ids.nombre_usuario.text = nombre
            self.ids.iniciales.text = theme.iniciales(nombre)

        # ---- Contenido: se reconstruye completo (son pocos widgets) ----
        contenedor = self.ids.categorias_container
        contenedor.clear_widgets()

        # Sección 1: categorías (scroll horizontal)
        contenedor.add_widget(Factory.TituloSeccion(text="Categorías"))
        scroll = ScrollView(
            do_scroll_x=True, do_scroll_y=False,
            size_hint_y=None, height=dp(142),
            bar_width=0,  # sin la barrita gris que se veía bajo las tarjetas
        )
        fila = BoxLayout(orientation="horizontal", spacing=dp(12),
                         size_hint_x=None, padding=(0, dp(2)))
        # El ancho de la fila crece con la cantidad de tarjetas.
        fila.bind(minimum_width=fila.setter("width"))

        for cat in db.get_categorias():
            tarjeta = Factory.CategoryCard()
            tarjeta.categoria_id = cat["id"]
            tarjeta.nombre = cat["nombre"]
            tarjeta.grupo = cat["grupo"] or ""
            tarjeta.icono = cat["icono"] or "book-outline"
            tarjeta.n_clases = cat["n_clases"]
            fila.add_widget(tarjeta)
        scroll.add_widget(fila)
        contenedor.add_widget(scroll)

        # Sección 2: clases recientes
        contenedor.add_widget(Factory.TituloSeccion(text="Clases recientes"))
        recientes = db.get_grabaciones_recientes(N_RECIENTES)
        if not recientes:
            contenedor.add_widget(Factory.TextoSuave(
                text="Aún no hay clases grabadas.", size_hint_y=None, height=dp(24)))
        for g in recientes:
            fila_rec = Factory.RecienteRow()
            fila_rec.grabacion_id = g["id"]
            fila_rec.titulo = g["nombre"]
            fila_rec.detalle = f"{g['categoria_nombre']}  •  {theme.fmt_fecha(g['fecha_subida'])}"
            contenedor.add_widget(fila_rec)
