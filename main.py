"""
main.py — WiiClass
App Android de grabaciones de clases (Kivy + KivyMD 2.0 + SQLite).

Flujo:
  LoginScreen -> MainScreen (Inicio / [Descargas si offline] / Alertas / Perfil)
  HomeTab -> CategoryScreen -> PlayerScreen
  DownloadsTab -> PlayerScreen (mismo reproductor, archivo local)
"""

from kivy.config import Config
# Limita el framerate global: reduce el costo de cualquier redibujo continuo
# (animaciones, ripples, etc.) en dispositivos sin aceleración de GPU, que es
# la causa más común de que la app se sienta "congelada" o vaya a tirones.
Config.set("graphics", "maxfps", "30")

from kivy.uix.screenmanager import FadeTransition
from kivy.clock import Clock

from kivymd.app import MDApp
from kivymd.uix.screenmanager import MDScreenManager

import db
from screens.login_screen import LoginScreen
from screens.main_screen import MainScreen
from screens.category_screen import CategoryScreen
from screens.player_screen import PlayerScreen
from screens.notifications_all_screen import NotificationsAllScreen
from screens.notifications_state import notificaciones_state


def is_online() -> bool:
    """
    Detección simple de conectividad.
    En Android real conviene usar pyjnius + ConnectivityManager para una
    detección instantánea y reactiva a cambios de red. Aquí se hace un
    chequeo de socket liviano, suficiente para desktop y como fallback.
    """
    import socket
    try:
        socket.setdefaulttimeout(1.5)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except OSError:
        return False


class WiiClassApp(MDApp):
    usuario = None

    def build(self):
        self.theme_cls.primary_palette = "Indigo"
        self.theme_cls.theme_style = "Light"
        db.init_db(seed=True)

        self.sm = MDScreenManager(transition=FadeTransition(duration=0.2))
        self.sm.add_widget(LoginScreen(name="login"))
        self.sm.add_widget(MainScreen(name="main"))
        self.sm.add_widget(CategoryScreen(name="category_screen"))
        self.sm.add_widget(PlayerScreen(name="player_screen"))
        self.sm.add_widget(NotificationsAllScreen(name="notifications_all"))
        self.sm.current = "login"
        return self.sm

    # ---- Navegación / sesión -----------------------------------------
    def on_login_success(self, usuario_id: int):
        self.usuario = db.get_usuario(usuario_id)
        main_screen = self.sm.get_screen("main")
        main_screen.build_tabs(offline=not is_online())
        self.sm.current = "main"

        # Revisión periódica de conectividad para mostrar/ocultar
        # el tab "Descargas" dinámicamente (requisito: solo visible offline).
        Clock.schedule_interval(self._chequear_conectividad, 5)

    def _chequear_conectividad(self, dt):
        if self.sm.current != "main" or not self.usuario:
            return
        main_screen = self.sm.get_screen("main")
        offline_actual = "downloads_tab" in getattr(main_screen, "_tab_screens", {})
        if offline_actual == (not is_online()):
            return  # sin cambios
        main_screen.build_tabs(offline=not is_online())

    def cerrar_sesion(self):
        Clock.unschedule(self._chequear_conectividad)
        self.usuario = None
        # Una sesión nueva empieza con las notificaciones sin ocultar
        # (ver notifications_state.py: el ocultamiento es solo por sesión).
        notificaciones_state.reiniciar()
        self.sm.current = "login"

    def abrir_categoria(self, categoria_id: int, nombre: str):
        cat_screen = self.sm.get_screen("category_screen")
        cat_screen.mostrar_categoria(categoria_id, nombre)
        self._player_origen = "category_screen"
        self.sm.current = "category_screen"

    def volver_a_inicio(self):
        self.sm.current = "main"

    def abrir_reproductor(self, grabacion_id: int, ruta_local: str = None):
        player = self.sm.get_screen("player_screen")
        # Si no se pasó una ruta local explícita (caso Tab Descargas, que
        # ya sabe exactamente cuál usar), preferimos la copia descargada
        # si existe — funciona igual online u offline, y deja el código
        # listo para cuando `url_audio` sea una URL remota de verdad.
        if ruta_local is None:
            ruta_local = db.get_ruta_local(grabacion_id)
        player.cargar_grabacion(grabacion_id, local_path=ruta_local)
        # Recuerda si veníamos de una Categoría (Tab Inicio) o de Descargas,
        # para volver al lugar correcto con el botón "atrás".
        self._player_origen = "category_screen" if self.sm.current == "category_screen" else "main"
        self.sm.current = "player_screen"

    def volver_desde_reproductor(self):
        self.sm.current = getattr(self, "_player_origen", "main")

    def abrir_todas_notificaciones(self):
        self.sm.current = "notifications_all"

    def volver_de_todas_notificaciones(self):
        self.sm.current = "main"


if __name__ == "__main__":
    WiiClassApp().run()
