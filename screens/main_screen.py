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
from kivy.uix.screenmanager import NoTransition

import theme
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
        # Ver nota en main.py: NoTransition evita el redibujado completo de
        # ventana que un fade fuerza en cada cambio de tab, notorio en
        # GPU integrada/sin aceleración.
        self.ids.content_manager.transition = NoTransition()
        self._tab_screens = {}
        self._tab_actual = "home_tab"  # pestaña que el usuario está viendo

    def on_pre_enter(self, *args):
        # Al volver a esta pantalla (p. ej. desde el Reproductor o una
        # Categoría), los tabs internos NO reciben su propio on_pre_enter
        # (solo se dispara cuando cambia la pestaña). Sin esto, una descarga
        # hecha en Categoría no aparecía en "Descargas" hasta cambiar de
        # pestaña y volver.
        self._refrescar_tab(self._tab_actual)

    def _refrescar_tab(self, nombre_tab):
        tab = self._tab_screens.get(nombre_tab)
        if tab is not None and hasattr(tab, "refrescar"):
            tab.refrescar()

    def build_tabs(self, offline: bool, refrescar: bool = False):
        """Construye la barra inferior y los tabs.

        `offline=True` agrega el tab "Descargas". Se vuelve a llamar cada
        vez que cambia la conectividad, así que CONSERVA la pestaña donde
        estaba el usuario (si sigue existiendo). `refrescar=True` recarga
        los datos de esa pestaña; se usa cuando la pantalla ya está
        visible (en el primer arranque lo hace on_pre_enter).
        """
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

        # Si la pestaña que se estaba viendo ya no existe (p. ej. "Descargas"
        # al recuperar la red), se vuelve a "Inicio".
        nombres = [t[0] for t in tabs]
        destino = self._tab_actual if self._tab_actual in nombres else "home_tab"
        self._tab_actual = destino

        self._tab_screens = {}
        for name, text, icon, screen_cls in tabs:
            screen = screen_cls(name=name)
            content_manager.add_widget(screen)
            self._tab_screens[name] = screen

            item = MDNavigationItem(active=(name == destino))
            item._tab_name = name
            icono = MDNavigationItemIcon(icon=icon)
            etiqueta = MDNavigationItemLabel(text=text)
            self._estilizar_item(item, icono, etiqueta)
            item.add_widget(icono)
            item.add_widget(etiqueta)
            bottom_nav.add_widget(item)

        content_manager.current = destino
        if refrescar:
            self._refrescar_tab(destino)

    @staticmethod
    def _estilizar_item(item, icono, etiqueta):
        """Colorea la pestaña activa con la paleta azul de la marca.

        Estas propiedades existen en distintas versiones 2.0.x de KivyMD; se
        aplican solo si el widget las tiene (`hasattr`), para que una
        versión que no las defina no rompa la app (simplemente usará los
        colores del tema "Blue" configurado en main.py).
        """
        ajustes = (
            (item, {"active_indicator_color": theme.MIST}),
            (icono, {"theme_icon_color": "Custom",
                     "icon_color_active": theme.PRIMARY,
                     "icon_color_normal": theme.TEXT_SOFT}),
            (etiqueta, {"theme_text_color": "Custom",
                        "text_color_active": theme.PRIMARY,
                        "text_color_normal": theme.TEXT_SOFT}),
        )
        for widget, props in ajustes:
            for clave, valor in props.items():
                if hasattr(widget, clave):
                    setattr(widget, clave, valor)

    def on_switch_tabs(self, bar, item, item_icon, item_text):
        nombre_tab = getattr(item, "_tab_name", None)
        if nombre_tab:
            self._tab_actual = nombre_tab
            self.ids.content_manager.current = nombre_tab

    def get_screen(self, nombre_tab):
        return self._tab_screens.get(nombre_tab)
