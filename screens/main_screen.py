"""
main_screen.py — PANTALLA 2: PRINCIPAL (Post-Login)

Bottom Navigation Bar con animación fluida al cambiar de tab.
Orden estricto: 1. Inicio | 2. Notificaciones | 3. Perfil.
[Condicional] Si el dispositivo está OFFLINE se añade un 4° tab oculto
"Descargas" (solo visible offline), colocado justo después de Inicio para
coincidir con el layout de los mocks.

En KivyMD 2.0.0 el antiguo MDBottomNavigation fue reemplazado por
MDNavigationBar + MDScreenManager. Este screen sincroniza ambos widgets.
"""

import os

from kivy.lang import Builder
from kivy.uix.screenmanager import FadeTransition

from kivymd.uix.screen import MDScreen
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.navigationbar import (
    MDNavigationBar,
    MDNavigationItem,
    MDNavigationItemIcon,
    MDNavigationItemLabel,
)

Builder.load_file(os.path.join(os.path.dirname(__file__), "main_screen.kv"))


class MainScreen(MDScreen):
    """
    Nota de implementación: se usa un MDScreenManager interno
    (content_manager) sincronizado con los botones de un MDNavigationBar.
    Esto permite reutilizar cada Tab (Home/Notif/Perfil/Descargas) como
    screen independiente con su propio kv, y que a su vez cada uno navegue
    a sub-pantallas (p.ej. Inicio -> Categoría -> Reproductor) sin conflicto.
    """

    def on_kv_post(self, base_widget):
        self.ids.content_manager.transition = FadeTransition(duration=0.18)

    def build_tabs(self, offline: bool):
        from screens.home_tab import HomeTab
        from screens.notifications_tab import NotificationsTab
        from screens.profile_tab import ProfileTab
        from screens.downloads_tab import DownloadsTab

        bottom_nav = self.ids.bottom_nav
        bottom_nav.clear_widgets()
        content_manager = self.ids.content_manager
        content_manager.clear_widgets()

        tabs = [("home_tab", "Inicio", "home", HomeTab)]
        if offline:
            tabs.append(("downloads_tab", "Descargas", "cloud-download-outline", DownloadsTab))
        tabs.append(("notifications_tab", "Alertas", "bell-outline", NotificationsTab))
        tabs.append(("profile_tab", "Perfil", "account-outline", ProfileTab))

        self._tab_screens = {}
        for name, text, icon, screen_cls in tabs:
            screen = screen_cls(name=name)
            content_manager.add_widget(screen)
            self._tab_screens[name] = screen

            item = MDNavigationItem(active=(name == "home_tab"))
            item._tab_name = name
            item.add_widget(MDNavigationItemIcon(icon=icon))
            item.add_widget(MDNavigationItemLabel(text=text))
            bottom_nav.add_widget(item)

        content_manager.current = "home_tab"

    def on_switch_tabs(self, bar, item, item_icon, item_text):
        nombre_tab = getattr(item, "_tab_name", None)
        if nombre_tab:
            self.ids.content_manager.current = nombre_tab

    def get_screen(self, nombre_tab):
        return self._tab_screens.get(nombre_tab)
