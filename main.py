"""
main.py — WiiClass
App Android de grabaciones de clases (Kivy + KivyMD 2.0 + SQLite).

Flujo:
  LoginScreen -> MainScreen (la barra depende del rol; ver screens/main_screen.py)
    Estudiante: Inicio / [Descargas si offline] / Alertas / Perfil
    Profesor:   Inicio / [Descargas si online] / Grabación / Alertas / Perfil
  HomeTab -> CategoryScreen -> PlayerScreen
  DownloadsTab -> PlayerScreen (mismo reproductor, archivo local)
"""

from kivy.config import Config
from kivy.utils import platform

# Limita el framerate global SOLO en escritorio: reduce el costo de cualquier
# redibujo continuo en equipos sin aceleración de GPU (la causa más común de
# que la app se sienta "congelada"). En Android sí hay GPU y limitar a 30 fps
# haría que el scroll y las transiciones se vean entrecortados.
if platform != "android":
    Config.set("graphics", "maxfps", "30")

import threading

from kivy.uix.screenmanager import NoTransition, SlideTransition
from kivy.clock import Clock
from kivy.core.window import Window

from kivymd.app import MDApp
from kivymd.uix.screenmanager import MDScreenManager

import db
import storage
import theme
from screens.login_screen import LoginScreen
from screens.main_screen import MainScreen, tabs_para_rol
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
        # `with` cierra el socket siempre (antes se dejaba abierto en cada
        # chequeo, filtrando un descriptor cada 5 s). Y el timeout se fija
        # en ESTE socket: `socket.setdefaulttimeout()` cambiaba el timeout
        # de TODOS los sockets del proceso (descargas futuras incluidas).
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.5)
            s.connect(("8.8.8.8", 53))
        return True
    except OSError:
        return False


class WiiClassApp(MDApp):
    usuario = None
    # True cuando el chequeo de conectividad detecta que no hay red. Lo lee
    # el reproductor para no saltar a clases que no están descargadas.
    offline = False

    @property
    def rol(self) -> str:
        return self.usuario["rol"] if self.usuario else "Estudiante"

    @property
    def es_profesor(self) -> bool:
        return self.rol == "Profesor"

    def build(self):
        # "Blue" en vez de "Indigo": Indigo genera tonos lavanda/rosados en
        # los componentes que KivyMD colorea solo (barra de navegación,
        # contornos, íconos), que chocaban con el azul de la marca.
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.theme_style = "Light"
        db.init_db(seed=True)

        # En Android, el teclado tapaba los campos del Login. "below_target"
        # sube la ventana lo justo para que el campo activo quede visible.
        Window.softinput_mode = "below_target"

        # Al redimensionar la ventana, el fondo con degradado de LoginScreen
        # (pintado "a mano" con Rectangle en canvas.before, ver
        # login_screen.py) se recalcula reactivamente, pero llega UN frame
        # después de que el tamaño de la ventana ya cambió. En ese frame de
        # por medio se ve el color de limpieza por defecto de la ventana
        # (blanco en Windows) asomando en el área recién expuesta. Fijar el
        # clearcolor al tono superior del degradado hace ese frame
        # imperceptible en vez de un parpadeo blanco.
        Window.clearcolor = theme.LOGIN_TOP + (1,)

        # SlideTransition: a diferencia de FadeTransition, no mezcla
        # opacidad (sin blending), así que es notablemente más liviano en
        # GPU integrada/sin aceleración — no debería reintroducir el tirón
        # que se arregló arriba. La dirección se ajusta en cada llamada de
        # navegación (izquierda al avanzar, derecha al volver) más abajo.
        self.sm = MDScreenManager(transition=SlideTransition(duration=0.22))
        self.sm.add_widget(LoginScreen(name="login"))
        self.sm.add_widget(MainScreen(name="main"))
        self.sm.add_widget(CategoryScreen(name="category_screen"))
        self.sm.add_widget(PlayerScreen(name="player_screen"))
        self.sm.add_widget(NotificationsAllScreen(name="notifications_all"))
        self.sm.current = "login"
        # Si había una sesión guardada (sesion.json), se reanuda sin pasar
        # por el Login. Va al final de build(): necesita las pantallas ya
        # creadas.
        self._restaurar_sesion()
        return self.sm

    # ---- Navegación / sesión -----------------------------------------
    def _restaurar_sesion(self) -> bool:
        """Reanuda la sesión guardada la última vez. Devuelve True si entró.

        Se valida contra la base: si el usuario ya no existe, o cambió su
        correo o rol, la sesión guardada se descarta y se muestra el Login.
        Nunca lanza excepciones: ante cualquier problema, se muestra el Login.
        """
        try:
            sesion = storage.cargar_sesion()
            if sesion is None:
                return False
            usuario = db.get_usuario(sesion["usuario_id"])
            if (usuario is None
                    or (usuario["correo"] or "").lower() != sesion["correo"]
                    or usuario["rol"] != sesion["rol"]):
                storage.borrar_sesion()
                return False
            self.on_login_success(usuario["id"], restaurada=True)
            return True
        except Exception as exc:
            print(f"[main] No se pudo restaurar la sesión: {exc}")
            self.usuario = None
            self.sm.current = "login"
            return False

    def on_login_success(self, usuario_id: int, restaurada: bool = False):
        self.usuario = db.get_usuario(usuario_id)
        storage.guardar_sesion(
            self.usuario["id"], self.usuario["correo"],
            self.usuario["rol"], self.usuario["institucion_id"],
        )
        main_screen = self.sm.get_screen("main")
        # `is_online()` abre un socket con hasta 1.5s de timeout: llamarlo
        # aquí directamente congelaba la UI en cada login (se notaba
        # sobre todo sin red). Se construye primero asumiendo "online"
        # (arranque instantáneo) y `_chequear_conectividad` corrige el
        # tab "Descargas" apenas el chequeo real termine, en segundo
        # plano — mismo patrón que `downloads_manager.py`.
        self.offline = False
        main_screen.build_tabs(offline=False, rol=self.rol)
        if restaurada:
            # Al reabrir la app no hay "pantalla anterior" que deslizar:
            # se entra directo, y la transición normal se repone enseguida.
            anterior = self.sm.transition
            self.sm.transition = NoTransition()
            self.sm.current = "main"
            Clock.schedule_once(
                lambda _dt: setattr(self.sm, "transition", anterior), 0.5)
        else:
            self.sm.transition.direction = "left"
            self.sm.current = "main"

        # Revisión periódica de conectividad para mostrar/ocultar
        # el tab "Descargas" dinámicamente (requisito: solo visible offline).
        self._chequear_conectividad(0)
        Clock.schedule_interval(self._chequear_conectividad, 5)

    def _chequear_conectividad(self, dt):
        if self.sm.current != "main" or not self.usuario:
            return

        def worker():
            offline = not is_online()
            Clock.schedule_once(lambda _dt: self._aplicar_conectividad(offline))

        threading.Thread(target=worker, daemon=True).start()

    def _aplicar_conectividad(self, offline: bool):
        main_screen = self.sm.get_screen("main")
        # Solo se reconstruye la barra si el conjunto de pestañas cambia
        # (depende del rol: p. ej. Descargas aparece offline para el
        # estudiante y online para el profesor).
        esperadas = {n for n, _t, _i in tabs_para_rol(self.rol, offline)}
        if esperadas == main_screen.nombres_tabs():
            self.offline = offline
            return  # sin cambios
        self.offline = offline
        # `refrescar=True`: la pantalla ya está visible, así que hay que
        # cargar los datos de la pestaña a mano. Además build_tabs conserva
        # la pestaña actual (antes te devolvía siempre a "Inicio" cada vez
        # que la red aparecía o desaparecía).
        main_screen.build_tabs(offline=offline, refrescar=True, rol=self.rol)

    def cerrar_sesion(self) -> bool:
        Clock.unschedule(self._chequear_conectividad)
        # Primero se borra la sesión guardada: cerrar sesión debe ser
        # definitivo aunque algo falle más abajo (la próxima apertura
        # mostrará el Login).
        storage.borrar_sesion()
        # Si el profesor estaba grabando, se guarda antes de salir.
        self.sm.get_screen("main").reiniciar_sesion()
        self.usuario = None
        # Una sesión nueva empieza con las notificaciones sin ocultar
        # (ver notifications_state.py: el ocultamiento es solo por sesión).
        notificaciones_state.reiniciar()
        self.sm.transition.direction = "right"
        self.sm.current = "login"
        # Devuelve True solo si todo el cierre terminó sin excepciones (si
        # algo falla antes, la excepción se propaga y nadie notifica éxito).
        return True

    def abrir_categoria(self, categoria_id: int, nombre: str):
        cat_screen = self.sm.get_screen("category_screen")
        cat_screen.mostrar_categoria(categoria_id, nombre)
        self._player_origen = "category_screen"
        self.sm.transition.direction = "left"
        self.sm.current = "category_screen"

    def volver_a_inicio(self):
        self.sm.transition.direction = "right"
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
        self.sm.transition.direction = "left"
        self.sm.current = "player_screen"

    def volver_desde_reproductor(self):
        self.sm.transition.direction = "right"
        self.sm.current = getattr(self, "_player_origen", "main")

    def abrir_todas_notificaciones(self):
        self.sm.transition.direction = "left"
        self.sm.current = "notifications_all"

    def volver_de_todas_notificaciones(self):
        self.sm.transition.direction = "right"
        self.sm.current = "main"


if __name__ == "__main__":
    WiiClassApp().run()
