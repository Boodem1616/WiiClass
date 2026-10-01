"""
theme.py — Paleta de colores y utilidades de formato de WiiClass.

Antes, los colores azules estaban repetidos "a mano" como números en cada
archivo .kv (0.09, 0.16, 0.55 aparecía decenas de veces). Ahora viven aquí:
para cambiar la identidad visual de TODA la app basta con editar este
archivo. En los .kv se usan así:

    #:import T theme
    md_bg_color: T.BG

Concepto visual: "tinta azul sobre papel". Un azul profundo (tinta) para
cabeceras y acciones principales, y un blanco azulado (papel) como fondo,
que remite a apuntes de clase.

Este módulo NO importa Kivy: es Python puro y se puede probar por separado.
"""

from datetime import datetime, timezone

# ---- Paleta (RGBA, valores 0-1, como espera Kivy) -----------------------
NAVY = (0.05, 0.09, 0.28, 1)         # #0D1747  tinta muy oscura (texto sobre degradado)
PRIMARY = (0.09, 0.16, 0.55, 1)      # #172A8C  azul principal (botones, íconos activos)
BLUE = (0.16, 0.38, 0.90, 1)         # #2961E6  azul brillante (portada del reproductor)
SKY = (0.55, 0.72, 1.00, 1)          # #8CB8FF  azul cielo (detalles suaves)
MIST = (0.89, 0.93, 1.00, 1)         # #E3EDFF  azul muy claro (fichas, seleccionado)
BG = (0.955, 0.970, 1.00, 1)         # #F4F7FF  fondo de pantallas ("papel")
SURFACE = (1, 1, 1, 1)               # tarjetas
OUTLINE = (0.84, 0.89, 0.98, 1)      # borde fino de tarjetas
TEXT = (0.07, 0.10, 0.25, 1)         # texto principal
TEXT_SOFT = (0.36, 0.41, 0.60, 1)    # texto secundario
SUCCESS = (0.10, 0.60, 0.42, 1)      # descargado / OK
SUCCESS_SOFT = (0.88, 0.97, 0.93, 1) # fondo suave del ícono de éxito
DANGER = (0.85, 0.22, 0.27, 1)       # cerrar sesión / errores

# Degradado de las cabeceras (arriba -> abajo). Son tuplas RGB de 3 valores
# porque así las espera screens/gradient_utils.aplicar_degradado.
GRAD_TOP = (0.20, 0.42, 0.92)
GRAD_BOTTOM = (0.07, 0.13, 0.48)
# Mismo color final pero en RGBA: se usa para "empalmar" la cabecera con la
# hoja redondeada de abajo (ver <Hoja> en screens/common.kv).
GRAD_BOTTOM_RGBA = GRAD_BOTTOM + (1,)

# Degradado del fondo del Login (más oscuro abajo).
LOGIN_TOP = (0.20, 0.42, 0.92)
LOGIN_BOTTOM = (0.04, 0.07, 0.25)


# ---- Utilidades de formato ----------------------------------------------
_MESES = ["ene", "feb", "mar", "abr", "may", "jun",
          "jul", "ago", "sep", "oct", "nov", "dic"]


def fmt_fecha(fecha_iso):
    """'2026-08-15' -> '15 ago 2026'. Si no se puede interpretar, devuelve
    el texto original (mejor mostrar algo que romper la pantalla)."""
    if not fecha_iso:
        return ""
    try:
        d = datetime.fromisoformat(str(fecha_iso)[:10])
        return f"{d.day} {_MESES[d.month - 1]} {d.year}"
    except ValueError:
        return str(fecha_iso)


def fmt_duracion(segundos):
    """2730 -> '45 min'; 3900 -> '1 h 05 min'."""
    segundos = int(segundos or 0)
    horas, minutos = divmod(segundos // 60, 60)
    if horas:
        return f"{horas} h {minutos:02d} min"
    return f"{minutos} min"


def fmt_peso(mb):
    """Muestra KB si pesa menos de 1 MB. Antes se usaba '{:.0f} MB', lo que
    mostraba '0 MB' para audios pequeños."""
    if not mb:
        return ""
    if mb < 1:
        return f"{mb * 1024:.0f} KB"
    return f"{mb:.0f} MB"


def tiempo_relativo(fecha_sql):
    """'2026-09-30 12:00:00' (UTC, como lo guarda SQLite con datetime('now'))
    -> 'hace 5 min', 'hace 3 h', 'hace 2 d'. Para fechas viejas, la fecha."""
    if not fecha_sql:
        return ""
    try:
        dt = datetime.strptime(str(fecha_sql)[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return fmt_fecha(fecha_sql)
    ahora = datetime.now(timezone.utc).replace(tzinfo=None)
    seg = max(0, int((ahora - dt).total_seconds()))
    if seg < 60:
        return "ahora"
    if seg < 3600:
        return f"hace {seg // 60} min"
    if seg < 86400:
        return f"hace {seg // 3600} h"
    if seg < 7 * 86400:
        return f"hace {seg // 86400} d"
    return fmt_fecha(fecha_sql)


def iniciales(nombre):
    """'Sebastián Flores' -> 'SF'."""
    partes = (nombre or "").split()
    return "".join(p[0] for p in partes[:2]).upper()


def saludo():
    """Saludo según la hora local del dispositivo."""
    hora = datetime.now().hour
    if hora < 12:
        return "Buenos días"
    if hora < 20:
        return "Buenas tardes"
    return "Buenas noches"
