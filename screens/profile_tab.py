"""
profile_tab.py — TAB 3: PERFIL

Muestra: foto (placeholder con iniciales), nombre completo, fecha de
nacimiento, establecimiento universitario. Botón "Cerrar Sesión".

Compatible con KivyMD 2.0.0.
"""

import os

from kivy.lang import Builder
from kivy.metrics import dp

from kivymd.uix.screen import MDScreen

import theme

Builder.load_file(os.path.join(os.path.dirname(__file__), "profile_tab.kv"))


class ProfileTab(MDScreen):
    def on_pre_enter(self, *args):
        self.refrescar()

    def refrescar(self):
        from kivy.app import App
        app = App.get_running_app()
        if not app.usuario:
            return
        u = app.usuario
        self.ids.nombre_lbl.text = u["nombre"]
        self.ids.campo_nombre.value = u["nombre"]
        self.ids.campo_fecha.value = self._fmt_fecha(u["fecha_nac"])
        self.ids.campo_institucion.value = u["institucion_nombre"]
        self.ids.iniciales.text = theme.iniciales(u["nombre"])

    @staticmethod
    def _fmt_fecha(fecha_iso: str) -> str:
        """Convierte 'AAAA-MM-DD' (como se guarda en SQLite) al formato
        pedido para mostrar en el perfil: 'DIA/MES/AÑO'."""
        if not fecha_iso:
            return "-"
        try:
            y, m, d = fecha_iso.split("-")
            return f"{int(d):02d}/{int(m):02d}/{y}"
        except Exception:
            return fecha_iso
