# Configuración remota

La app lee un JSON desde una URL y aplica sus valores sin publicar una versión nueva.
Código: `remote_config.py` (sin Kivy). Pantalla de estado: **Perfil → Configuración remota**.

## Probarlo en 3 pasos
```bash
python3 servir_config.py        # 1. sirve ./remote en http://127.0.0.1:8765/app_config.json
python3 main.py                 # 2. abre la app (login demo: sflores@uct.cl / 12345678)
# 3. edita remote/app_config.json y toca "Actualizar ahora" en Perfil → Configuración remota
```
Otra fuente: `WIICLASS_REMOTE_CONFIG_URL=https://tu-servidor/app_config.json python3 main.py`
(emulador Android: `http://10.0.2.2:8765/...`; teléfono real: la IP de tu PC. En Android agrega
`INTERNET` a `android.permissions` en buildozer.spec y usa HTTPS fuera de desarrollo.)

## Qué se refleja en la app
| Clave del JSON | Efecto visible |
|---|---|
| `anuncio.activo/tipo/titulo/mensaje` | Tarjeta arriba de **Inicio** (`tipo`: `info`, `aviso`, `critico`) |
| `textos.saludo` | Reemplaza "Buenos días/tardes/noches" en la cabecera de Inicio |
| `funciones.descargas` | `false` → no se pueden iniciar descargas nuevas (lo ya descargado sigue disponible offline) |
| `funciones.grabacion` | `false` → el profesor no puede iniciar grabaciones |
| `funciones.notificaciones_sistema` | `false` → no se emiten las notificaciones de la barra de estado |
| `reproductor.velocidades` | Botones de velocidad del reproductor (1 a 6 valores de 0.5 a 3.0; se agrega 1.0 si falta) |
| `intervalo_actualizacion_seg` | Cada cuántos segundos vuelve a consultar (30–86400; por defecto 300) |
| `version` | Número informativo, se muestra en la pantalla de estado |

Ejemplo completo: `remote/app_config.json`.

## Cuándo se consulta
Al abrir la app, al volver del segundo plano (`on_resume`) y cada `intervalo_actualizacion_seg`
segundos. Si hubo cambios, la pestaña visible se redibuja sola.

## Cómo se comporta
* **Arranque instantáneo**: la app nunca espera a la red. Usa la última config guardada (`datos/config_remota.json`)
  o los valores por defecto, y consulta la fuente en segundo plano.
* **Sin red / fuente caída / JSON roto**: se mantiene la última config buena; el motivo aparece como *Error* en la pantalla de estado.
* **Validación por valor**: un valor inválido vuelve a su predeterminado y se lista como *Aviso*; el resto sí se aplica.
  Claves desconocidas se ignoran. Máximo 256 KB y 5 s por consulta; solo `http`, `https` y `file`.
* **ETag**: si la fuente lo envía, las consultas sin cambios responden 304.
* Los cambios se aplican en la pestaña visible al instante; las velocidades, al abrir la siguiente clase.

## Seguridad
La config **no** puede cambiar código, URLs de audio, credenciales ni datos de usuarios: solo los valores de la tabla.
Aun así, quien controle la URL controla esos textos; en producción sirve el JSON por HTTPS desde un dominio propio.

## Pruebas
`python -m unittest discover -s tests -v` (`tests/test_remote_config.py`: validación, caché, 304, red caída,
servidor HTTP real, límite de tamaño, interruptor de notificaciones).
