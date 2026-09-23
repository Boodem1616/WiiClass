"""
notifications_state.py — Notificaciones "eliminadas" por el usuario, pero
SOLO para la sesión actual (nunca se tocan en la base de datos).

Decisión de diseño confirmada con el usuario: como la base de datos
pronto pasará a ser un servidor SQL remoto, "eliminar" una notificación
(deslizándola o con "Limpiar todas") NO debe borrar la fila real — solo
debe dejar de mostrarse mientras la app sigue abierta con esa sesión. Si
el usuario cierra sesión y vuelve a entrar, las notificaciones vuelven a
aparecer todas (por eso `reiniciar()` se llama en `cerrar_sesion()`).

Es un estado compartido (no por pantalla) porque tanto el Tab
"Notificaciones" como la pantalla "Todas las notificaciones" deben
reflejar los mismos ocultamientos: si el usuario desliza una notificación
en una de las dos vistas, o usa "Limpiar todas", la otra vista debe verlo
reflejado la próxima vez que se muestre.
"""


class NotificacionesState:
    def __init__(self):
        self._ocultas = set()

    def ocultar(self, notificacion_id: int):
        self._ocultas.add(notificacion_id)

    def ocultar_todas(self, ids):
        self._ocultas.update(ids)

    def es_visible(self, notificacion_id: int) -> bool:
        return notificacion_id not in self._ocultas

    def filtrar_visibles(self, notificaciones):
        return [n for n in notificaciones if self.es_visible(n["id"])]

    def reiniciar(self):
        """Se llama al cerrar sesión: una sesión nueva empieza "limpia"."""
        self._ocultas.clear()


# Instancia única compartida entre NotificationsTab y NotificationsAllScreen.
notificaciones_state = NotificacionesState()
