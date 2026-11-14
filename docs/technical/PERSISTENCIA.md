# Persistencia de datos en JSON

`wiiclass/data/storage.py` guarda en archivos JSON lo necesario para recuperar el estado al cerrar y reabrir la app.
SQLite sigue siendo la base que consultan las pantallas; los JSON son su respaldo duradero.

| Archivo | Contenido | Se escribe cuando… | Al reabrir… |
|---|---|---|---|
| `sesion.json` | `usuario_id`, `correo`, `rol`, `institucion_id` (**nunca** la contraseña) | el usuario inicia sesión | se entra directo a la pantalla principal, sin Login |
| `grabaciones.json` | grabaciones subidas por profesores (título, materia, semana, duración, ruta del audio, profesor) | el profesor detiene y guarda una grabación | las que falten en SQLite se vuelven a insertar |
| `notificaciones.json` | notificaciones de Alertas, con su estado leída / no leída | se crea una notificación o se marcan como leídas | las que falten en SQLite se vuelven a insertar |
| `notificaciones_ocultas.json` | por correo, las notificaciones que el usuario eliminó de su lista (clave: mensaje + tipo + fecha) | desliza una notificación o usa "Limpiar todas" | no reaparecen, ni al cerrar sesión y volver a entrar ni al reabrir la app |

Cerrar sesión borra `sesion.json` (la próxima apertura muestra el Login).

## Dónde están
* Escritorio: carpeta `datos/` junto al proyecto (ya está en `.gitignore`).
* Android: `<almacenamiento privado de la app>/datos/`.
* Pruebas: la variable de entorno `WIICLASS_DATA_DIR` reemplaza la ubicación.

## Notificaciones eliminadas
Deslizar una notificación o usar "Limpiar todas" **no borra la fila de la base**: la oculta de la lista de Alertas de ese usuario (`wiiclass/ui/screens/notifications_state.py`).
* Se guarda por correo, así que cada usuario del dispositivo tiene su propia lista y cerrar sesión no la borra.
* Se identifica por mensaje + tipo + fecha (no por `id`), para que siga oculta aunque la base se recree y se restaure desde el JSON.
* Las notificaciones nuevas siempre aparecen.

## Cómo funciona
* **Respaldo**: tras cada cambio, `db.exportar_grabaciones()` / `db.exportar_notificaciones()` fusionan SQLite con el JSON. Nunca eliminan entradas del JSON.
* **Restauración**: `db.init_db()` llama a `_restaurar_desde_json()` en cada arranque. Es idempotente (no duplica).
  Usuarios y materias se enlazan por **correo** y **nombre**, no por id, así que el respaldo sirve aunque la base se recree.
* Si el archivo de audio de una grabación ya no existe, esa clase no se restaura (no se mostraría una clase imposible de reproducir), pero su entrada se conserva en el JSON.
* Si un JSON está corrupto se renombra a `*.corrupto` y la app arranca igual.
* Las escrituras son atómicas (archivo temporal + `os.replace`) y un fallo de disco nunca interrumpe la app.
* Se valida la sesión guardada contra la base: si el usuario ya no existe o cambió de correo/rol, se descarta.

## Lo que NO se persiste (a propósito)
* Las notificaciones push del sistema (bienvenida, cierre de sesión, grabación completa, descarga completa) son avisos efímeros de la barra de estado; no forman parte de la lista de Alertas.

## Pruebas
`python -m unittest discover -s tests -v` — incluye `tests/test_persistencia.py` (19 pruebas: borrar la base y recuperar todo, sin duplicados, JSON corrupto, disco que falla, etc.).
