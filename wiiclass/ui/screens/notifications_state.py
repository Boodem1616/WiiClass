"""
notifications_state.py — Notificaciones "eliminadas" por el usuario.

"Eliminar" una notificación (deslizándola o con "Limpiar todas") NO borra la
fila de la base de datos (que pronto será un servidor SQL remoto): solo la
deja de mostrar en la lista de Alertas de ESE usuario.

Lo eliminado se conserva entre sesiones: se guarda por correo en
`datos/notificaciones_ocultas.json` (ver `storage.py`), así que al cerrar
sesión y volver a entrar —o al reabrir la app— no reaparece. Otro usuario en
el mismo dispositivo conserva su propia lista.

Se identifica cada notificación por (mensaje, tipo, fecha) y no por su `id`,
porque el `id` cambia si la base se recrea y se restaura desde el respaldo
JSON (la misma clave que usa `db.exportar_notificaciones`). Una notificación
nueva tiene otra fecha, así que siempre aparece.

Es un estado compartido (no por pantalla) porque el Tab "Notificaciones" y la
pantalla "Todas las notificaciones" deben reflejar los mismos ocultamientos.
"""
from wiiclass.data import db, storage


def _clave(n) -> tuple:
    return (n["mensaje"], n["tipo"], n["fecha"])


class NotificacionesState:
    def __init__(self):
        self._usuario_id = None
        self._correo = None
        self._ocultas = set()

    def activar(self, usuario_id: int, correo: str):
        """Se llama al iniciar o restaurar sesión: carga lo que este usuario
        ya había eliminado."""
        self._usuario_id = usuario_id
        self._correo = (correo or "").strip().lower()
        self._ocultas = {tuple(c) for c in storage.cargar_notificaciones_ocultas(self._correo)}

    def ocultar(self, notificacion_id: int):
        self.ocultar_todas([notificacion_id])

    def ocultar_todas(self, ids):
        if self._usuario_id is None:
            return
        ids = set(ids)
        self._ocultas.update(
            _clave(n) for n in db.get_notificaciones(self._usuario_id) if n["id"] in ids
        )
        storage.guardar_notificaciones_ocultas(self._correo, sorted(self._ocultas))

    def es_visible(self, notificacion) -> bool:
        return _clave(notificacion) not in self._ocultas

    def filtrar_visibles(self, notificaciones):
        return [n for n in notificaciones if self.es_visible(n)]

    def reiniciar(self):
        """Se llama al cerrar sesión: olvida al usuario en memoria. NO borra
        lo guardado en disco; se recupera con `activar()` al volver a entrar."""
        self._usuario_id = None
        self._correo = None
        self._ocultas = set()


# Instancia única compartida entre NotificationsTab y NotificationsAllScreen.
notificaciones_state = NotificacionesState()
