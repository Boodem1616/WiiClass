"""
notification_service.py — Notificaciones push/locales de confirmación.

La app no tiene servidor remoto (ver `downloads_manager.py`), así que no
existen notificaciones push remotas con las que integrarse: se implementan
notificaciones LOCALES con el sistema (estilo push, aparecen en la barra de
estado aunque la app esté en segundo plano). Si algún día hay FCM, solo hay
que cambiar `_Backend`; las pantallas siguen llamando a los mismos 4 métodos.

Uso (desde las pantallas):

    from notification_service import notificaciones
    notificaciones.show_login_welcome("Sofía Flores")
    notificaciones.show_logout_confirmation()
    notificaciones.show_recording_complete("Matrices", "Matemáticas", "Semana 3", evento_id=12)
    notificaciones.show_download_complete("Límites", evento_id=7)

Garantías:
  * NUNCA lanza excepciones hacia la pantalla que llama: cualquier fallo se
    registra en el log y el método devuelve False.
  * Cada método devuelve True si la notificación se envió/encoló, False si se
    omitió (duplicada, permiso denegado, error).
  * Anti-duplicados: el mismo evento no se notifica dos veces dentro de
    `VENTANA_DEDUPE_SEG` (p. ej. doble toque en "Cerrar sesión").
  * Permisos: en Android 13+ se pide POST_NOTIFICATIONS la primera vez que
    hace falta (normalmente en el login). Si el usuario la deniega, no se
    vuelve a insistir en esa ejecución y la app sigue funcionando.
  * Textos exactos pedidos (sin tildes ni signos adicionales).

Este módulo no importa Kivy al cargarse (solo de forma perezosa dentro de los
backends), así que su lógica se puede probar con `unittest` sin ventana.
"""

import logging
import sys
import time
import zlib

log = logging.getLogger("wiiclass.notifications")

APP_NOMBRE = "WiiClass"
CANAL_ID = "wiiclass_confirmaciones"
CANAL_NOMBRE = "Confirmaciones de WiiClass"
PERMISO_ANDROID = "android.permission.POST_NOTIFICATIONS"
VENTANA_DEDUPE_SEG = 5.0


# ---------------------------------------------------------------------------
# Textos (funciones puras: es lo que verifican las pruebas)
# ---------------------------------------------------------------------------
def _limpio(valor, por_defecto: str = "") -> str:
    """Convierte None/espacios/'None' en el fallback; si no, texto recortado."""
    if valor is None:
        return por_defecto
    texto = str(valor).strip()
    return texto or por_defecto


def texto_bienvenida(nombre_usuario) -> str:
    nombre = _limpio(nombre_usuario)
    return f"Bienvenido {nombre}" if nombre else "Bienvenido"


def texto_cierre_sesion() -> str:
    return "Se ha cerrado sesion!"


def texto_grabacion_completa(titulo, materia, semana) -> str:
    return "Grabacion {} completa en {} de la {}".format(
        _limpio(titulo, "sin titulo"),
        _limpio(materia, "su materia"),
        _limpio(semana, "semana"),
    )


def texto_descarga_completa(titulo) -> str:
    return "Se ha descargado {} correctamente!".format(_limpio(titulo, "la clase"))


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------
def _plataforma() -> str:
    try:
        from kivy.utils import platform
        return platform
    except Exception:
        return sys.platform


def _en_hilo_principal(fn):
    """Ejecuta `fn` en el hilo principal de Kivy (si hay Kivy; si no, directo)."""
    try:
        from kivy.clock import Clock
        Clock.schedule_once(lambda _dt: fn())
    except Exception:
        fn()


class _Backend:
    """Interfaz mínima que necesita `NotificationService`."""

    def tiene_permiso(self) -> bool:
        return True

    def pedir_permiso(self, callback) -> None:
        """Pide el permiso y llama `callback(concedido: bool)`."""
        callback(True)

    def mostrar(self, notif_id: int, titulo: str, mensaje: str) -> None:
        raise NotImplementedError


class AndroidBackend(_Backend):
    """Notificaciones nativas por pyjnius (sin dependencias extra).

    Crea el canal (obligatorio desde Android 8) y publica la notificación
    con un PendingIntent que abre la app al tocarla.
    """

    def __init__(self):
        from jnius import autoclass
        self._autoclass = autoclass
        self._activity = autoclass("org.kivy.android.PythonActivity").mActivity
        self._sdk = autoclass("android.os.Build$VERSION").SDK_INT
        self._canal_creado = False

    def _manager(self):
        Context = self._autoclass("android.content.Context")
        return self._activity.getSystemService(Context.NOTIFICATION_SERVICE)

    def tiene_permiso(self) -> bool:
        # En Android 13+ devuelve False mientras POST_NOTIFICATIONS no esté
        # concedido, y también si el usuario las apagó desde Ajustes.
        return bool(self._manager().areNotificationsEnabled())

    def pedir_permiso(self, callback) -> None:
        # Antes de Android 13 no hay diálogo: si están apagadas, solo se
        # pueden reactivar desde Ajustes.
        if self._sdk < 33:
            callback(False)
            return
        from android.permissions import request_permissions

        def _resp(permisos, resultados):
            callback(bool(resultados) and all(resultados))

        request_permissions([PERMISO_ANDROID], _resp)

    def _crear_canal(self):
        if self._canal_creado or self._sdk < 26:
            return
        Channel = self._autoclass("android.app.NotificationChannel")
        Manager = self._autoclass("android.app.NotificationManager")
        canal = Channel(CANAL_ID, CANAL_NOMBRE, Manager.IMPORTANCE_HIGH)
        self._manager().createNotificationChannel(canal)
        self._canal_creado = True

    def mostrar(self, notif_id: int, titulo: str, mensaje: str) -> None:
        ac = self._autoclass
        self._crear_canal()
        Builder = ac("android.app.Notification$Builder")
        PendingIntent = ac("android.app.PendingIntent")
        ctx = self._activity

        if self._sdk >= 26:
            builder = Builder(ctx, CANAL_ID)
        else:
            builder = Builder(ctx)
            builder.setPriority(1)  # Notification.PRIORITY_HIGH

        # Al tocar la notificación se abre (o vuelve al frente) la app.
        intent = ctx.getPackageManager().getLaunchIntentForPackage(ctx.getPackageName())
        flags = PendingIntent.FLAG_UPDATE_CURRENT
        if self._sdk >= 23:
            flags |= PendingIntent.FLAG_IMMUTABLE
        pendiente = PendingIntent.getActivity(ctx, notif_id, intent, flags)

        String = ac("java.lang.String")
        CharSequence = "java.lang.CharSequence"
        from jnius import cast
        builder.setContentTitle(cast(CharSequence, String(titulo)))
        builder.setContentText(cast(CharSequence, String(mensaje)))
        builder.setSmallIcon(ctx.getApplicationInfo().icon)
        builder.setContentIntent(pendiente)
        builder.setAutoCancel(True)
        self._manager().notify(notif_id, builder.build())


class DesktopBackend(_Backend):
    """Escritorio (desarrollo): `plyer` si está disponible; si el sistema no
    lo soporta, cae a un aviso dentro de la app para poder verificar el flujo."""

    def mostrar(self, notif_id: int, titulo: str, mensaje: str) -> None:
        try:
            from plyer import notification
            notification.notify(title=titulo, message=mensaje,
                                app_name=APP_NOMBRE, timeout=6)
            return
        except Exception as exc:
            log.info("plyer no disponible (%s); se usa aviso dentro de la app", exc)
        from screens.widgets import mostrar_aviso
        mostrar_aviso(mensaje, duracion=4)


def _crear_backend() -> _Backend:
    if _plataforma() == "android":
        try:
            return AndroidBackend()
        except Exception:
            log.exception("No se pudo iniciar el backend Android; notificaciones desactivadas")
            return _NullBackend()
    return DesktopBackend()


class _NullBackend(_Backend):
    """Backend de emergencia: no hace nada, sin permisos."""

    def tiene_permiso(self) -> bool:
        return False

    def pedir_permiso(self, callback) -> None:
        callback(False)

    def mostrar(self, notif_id, titulo, mensaje) -> None:
        pass


# ---------------------------------------------------------------------------
# Servicio
# ---------------------------------------------------------------------------
class NotificationService:
    def __init__(self, backend: _Backend = None, ventana_dedupe: float = VENTANA_DEDUPE_SEG,
                 reloj=time.monotonic, habilitado=None):
        # `habilitado()` -> bool: interruptor externo (configuración remota).
        self._habilitado = habilitado
        self._backend = backend
        self._ventana = ventana_dedupe
        self._reloj = reloj
        self._recientes = {}      # clave -> instante del último envío aceptado
        self._pendientes = []     # (clave, mensaje) esperando la respuesta del permiso
        self._permiso_pedido = False
        self._permiso_denegado = False

    # ---- API pública --------------------------------------------------
    def show_login_welcome(self, nombre_usuario, usuario_id=None) -> bool:
        clave = ("login", usuario_id if usuario_id is not None else _limpio(nombre_usuario))
        return self._enviar(clave, texto_bienvenida(nombre_usuario))

    def show_logout_confirmation(self) -> bool:
        return self._enviar(("logout",), texto_cierre_sesion())

    def show_recording_complete(self, titulo_grabacion, materia, semana_materia,
                                evento_id=None) -> bool:
        mensaje = texto_grabacion_completa(titulo_grabacion, materia, semana_materia)
        clave = ("grabacion", evento_id if evento_id is not None else mensaje)
        return self._enviar(clave, mensaje)

    def show_download_complete(self, titulo_grabacion, evento_id=None) -> bool:
        mensaje = texto_descarga_completa(titulo_grabacion)
        clave = ("descarga", evento_id if evento_id is not None else mensaje)
        return self._enviar(clave, mensaje)

    # ---- Núcleo ----------------------------------------------------------
    def _backend_listo(self) -> _Backend:
        if self._backend is None:
            self._backend = _crear_backend()
        return self._backend

    def _es_duplicada(self, clave) -> bool:
        ahora = self._reloj()
        # Limpia entradas vencidas para que el dict no crezca sin límite.
        self._recientes = {k: t for k, t in self._recientes.items()
                           if ahora - t < self._ventana}
        if clave in self._recientes:
            return True
        self._recientes[clave] = ahora
        return False

    def _enviar(self, clave, mensaje: str) -> bool:
        try:
            if self._habilitado is not None and not self._habilitado():
                log.info("Notificaciones desactivadas por configuración remota")
                return False
            if self._es_duplicada(clave):
                log.info("Notificación duplicada omitida: %s", clave)
                return False
            backend = self._backend_listo()

            if backend.tiene_permiso():
                return self._mostrar(backend, clave, mensaje)

            if self._permiso_denegado:
                log.info("Notificaciones sin permiso; se omite: %r", mensaje)
                return False

            # Permiso aún no concedido: se encola y se pide (una sola vez).
            self._pendientes.append((clave, mensaje))
            if not self._permiso_pedido:
                self._permiso_pedido = True
                backend.pedir_permiso(
                    lambda ok: _en_hilo_principal(lambda: self._resolver_permiso(ok)))
            return True
        except Exception:
            log.exception("Error al enviar la notificación %r", mensaje)
            return False

    def _resolver_permiso(self, concedido: bool):
        pendientes, self._pendientes = self._pendientes, []
        if not concedido:
            self._permiso_denegado = True
            log.info("Permiso de notificaciones denegado; %d descartadas", len(pendientes))
            return
        for clave, mensaje in pendientes:
            try:
                self._mostrar(self._backend_listo(), clave, mensaje)
            except Exception:
                log.exception("Error al mostrar la notificación %r", mensaje)

    @staticmethod
    def _mostrar(backend: _Backend, clave, mensaje: str) -> bool:
        # id estable por evento: el mismo evento reemplaza, eventos distintos conviven.
        notif_id = zlib.crc32(repr(clave).encode()) & 0x7FFFFFFF
        backend.mostrar(notif_id, APP_NOMBRE, mensaje)
        log.info("Notificación enviada: %r", mensaje)
        return True


# Instancia única compartida por todas las pantallas.
def _interruptor_remoto() -> bool:
    try:
        from remote_config import config_remota
        return config_remota.funcion_activa("notificaciones_sistema")
    except Exception:
        return True


notificaciones = NotificationService(habilitado=_interruptor_remoto)
