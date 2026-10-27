# Notificaciones push/locales de confirmación

Servicio centralizado: `notification_service.py` (instancia `notificaciones`).
La app no tiene servidor remoto, así que son notificaciones **locales** estilo push
(barra de estado de Android, también con la app en segundo plano).

| Pantalla | Dónde se dispara | Método | Texto |
|---|---|---|---|
| login_screen | `LoginScreen.iniciar_sesion`, tras `on_login_success` | `show_login_welcome(nombre)` | `Bienvenido {nombreUsuario}` (fallback: correo, o `Bienvenido`) |
| profile_tab | `ProfileTab.cerrar_sesion`, solo si `app.cerrar_sesion()` devuelve `True` | `show_logout_confirmation()` | `Se ha cerrado sesion!` |
| recording_tab | `detener_y_guardar`, tras guardar en disco **y** en la BD | `show_recording_complete(titulo, materia, semana)` | `Grabacion {tituloGrabacion} completa en {materia} de la {semanaMateria}` |
| category_screen | `on_completa` de la descarga (individual y múltiple) | `show_download_complete(titulo)` | `Se ha descargado {tituloGrabacion} correctamente!` |

No se notifica en errores, cancelaciones, grabaciones demasiado cortas, audio sin registrar en la BD,
descargas fallidas ni clases que ya estaban descargadas.

## Configuración Android (buildozer.spec)
```
android.api = 33            # o superior: necesario para pedir POST_NOTIFICATIONS
android.permissions = RECORD_AUDIO, POST_NOTIFICATIONS
requirements = python3,kivy,kivymd,ffpyplayer,pyjnius
```
* Android 13+: el diálogo de permiso aparece la primera vez que hace falta (normalmente en el login);
  la notificación pendiente se muestra al aceptar. Si se deniega, la app sigue normal y no se vuelve a insistir.
* Android 8+: se crea el canal `wiiclass_confirmaciones` automáticamente.
* Tocar la notificación abre/devuelve al frente la app (no navega a una pantalla concreta).

## Escritorio (desarrollo)
`pip install -r requirements.txt` (incluye `plyer`). Si el sistema no soporta notificaciones nativas,
se muestra el mismo texto con el aviso interno de la app.

## Pruebas
`python -m unittest discover -s tests -v` — 15 pruebas (textos exactos de los 4 escenarios, fallbacks,
duplicados, permiso concedido/denegado, backend que falla). No requieren Kivy.
