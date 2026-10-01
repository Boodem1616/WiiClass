"""
downloads_tab.py — TAB 4: DESCARGAS (SOLO OFFLINE)

Mismo sistema de carpetas por Categoría de Clase. Dentro de cada categoría:
listado de grabaciones con el MISMO reproductor de audio (controles y
velocidades idénticos al Tab Inicio) — ver screens/player_screen.py.

Compatible con KivyMD 2.0.0.
"""

import os

from kivy.lang import Builder
from kivy.metrics import dp
from kivy.factory import Factory

from kivymd.uix.screen import MDScreen

import db
import theme

Builder.load_file(os.path.join(os.path.dirname(__file__), "downloads_tab.kv"))


class DownloadsTab(MDScreen):
    def on_pre_enter(self, *args):
        self.refrescar()

    def refrescar(self):
        contenedor = self.ids.contenedor
        contenedor.clear_widgets()

        agrupado = db.get_descargas_agrupadas()
        if not agrupado:
            # Estado vacío: explica qué hacer, no solo que no hay nada.
            contenedor.add_widget(Factory.TextoSuave(
                text="Aún no tienes clases descargadas.\n"
                     "Descárgalas con el WiFi del campus para escucharlas sin conexión.",
                size_hint_y=None, height=dp(56)))
            return

        for (cat_id, cat_nombre, cat_icono), items in agrupado.items():
            # Título de la categoría con la cantidad de clases descargadas.
            n = len(items)
            contenedor.add_widget(Factory.TituloSeccion(
                text=f"{cat_nombre}  ·  {n} {'clase' if n == 1 else 'clases'}"))
            for it in items:
                row = Factory.DownloadRow()
                row.grabacion_id = it["grabacion_id"]
                row.ruta_local = it["ruta_local"]
                row.titulo = it["grabacion_nombre"]
                row.fecha = theme.fmt_fecha(it["fecha_subida"])
                row.peso_txt = theme.fmt_peso(it["peso_mb"])
                contenedor.add_widget(row)
