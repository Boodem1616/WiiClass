# Módulo de Analíticas (Sesión 25)

Registro local de eventos de uso en `datos/analytics.json` (junto al resto de la
persistencia; se puede cambiar con `WIICLASS_ANALYTICS_FILE`).

- `wiiclass/services/analytics.py` — motor: `registrar(nombre, datos)`. No lanza excepciones, escribe
  de forma atómica y agrupada (~1 s), guarda como máximo 5000 eventos.
- `tools/analyze_analytics.py` — `python tools/analyze_analytics.py [archivo]`: total de pantallas visitadas,
  eventos por tipo, sesiones, KPIs y embudo de uso.
- `tests/test_analytics.py` — pruebas (`python -m unittest discover -s tests`).

Evento: `{"evento", "ts", "sesion", "rol"?, "datos": {...}}`. No se guardan correos,
contraseñas ni nombres de personas.

## Eventos instrumentados
| Evento | Dónde |
|---|---|
| `app_iniciada` / `app_cerrada` | `wiiclass/app.py` (build / on_stop) |
| `pantalla_vista` | `app.py`: `on_enter` de cada pantalla + cambio de pestaña |
| `login_exitoso` / `sesion_restaurada` / `login_error` / `logout` | `app.py`, `login_screen.py` |
| `categoria_abierta` | `app.py` |
| `clase_abierta`, `reproduccion_play/pausa`, `velocidad_cambiada` | `player_screen.py` |
| `descarga_iniciada/completa/error` | `category_screen.py` |
| `grabacion_iniciada/guardada` | `recording_tab.py` (Profesor) |
| `notificacion_descartada`, `notificaciones_limpiadas` | pestaña y pantalla de notificaciones |

## Métricas vs KPIs (método MJV)
Métricas: pantallas más visitadas, eventos por tipo, duración promedio de sesión.
KPIs: % login exitoso, % clases abiertas que se reproducen, % descargas exitosas.
Una clase cuenta como "reproducida" solo si la persona tocó play (`reproduccion_play` con
`origen: manual`); el play `auto` que la app genera al abrir la clase no se cuenta.
Embudo: sesión iniciada → categoría → clase → reproducción manual (alerta si la caída es ≥ 80 %).
