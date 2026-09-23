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
from kivymd.uix.label import MDLabel

import db

Builder.load_file(os.path.join(os.path.dirname(__file__), "downloads_tab.kv"))


class DownloadsTab(MDScreen):
    def on_pre_enter(self, *args):
        self.refrescar()

    def refrescar(self):
        contenedor = self.ids.contenedor
        contenedor.clear_widgets()

        agrupado = db.get_descargas_agrupadas()
        if not agrupado:
            contenedor.add_widget(
                MDLabel(text="No tienes clases descargadas todavía.",
                        theme_text_color="Secondary", size_hint_y=None, height=dp(30))
            )
            return

        for (cat_id, cat_nombre, cat_icono), items in agrupado.items():
            header = MDLabel(
                text=f"  {cat_nombre}",
                bold=True,
                font_style="Title",
                role="medium",
                size_hint_y=None,
                height=dp(28),
            )
            contenedor.add_widget(header)
            for it in items:
                row = Factory.DownloadRow()
                row.grabacion_id = it["grabacion_id"]
                row.ruta_local = it["ruta_local"]
                row.titulo = it["grabacion_nombre"]
                row.fecha = it["fecha_subida"] or ""
                row.peso_txt = f"{it['peso_mb']:.0f} MB" if it["peso_mb"] else ""
                contenedor.add_widget(row)
