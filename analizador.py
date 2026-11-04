"""
analizador.py — Métricas, KPIs y embudo sobre `analytics.json` (Sesión 25).

Sigue el método MJV: eventos crudos -> métricas descriptivas -> KPIs ->
análisis de embudo. Se ejecuta fuera de la app:

    python analizador.py                 # usa datos/analytics.json
    python analizador.py ruta/otro.json  # analiza otro archivo

Las funciones reciben la lista de eventos (la que devuelve
`analytics.cargar()`), así que también se pueden usar desde pruebas.
No importa Kivy.
"""

import sys
from collections import Counter, defaultdict
from datetime import datetime

import analytics as A

# Un embudo es una lista de pasos; cada paso acepta uno o varios eventos.
EMBUDO_ESTUDIANTE = [
    ("Sesión iniciada", (A.LOGIN_EXITOSO, A.SESION_RESTAURADA)),
    ("Abre una categoría", (A.CATEGORIA_ABIERTA,)),
    ("Abre una clase", (A.CLASE_ABIERTA,)),
    ("Reproduce la clase", (A.REPRODUCCION_PLAY,)),
]
UMBRAL_CAIDA_ALERTA = 0.80  # una caída >= 80% entre pasos indica un problema


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------
def cargar_eventos(ruta=None) -> list:
    """Eventos del archivo indicado (o del archivo de la app)."""
    if ruta is None:
        return A.cargar()
    return A._leer_disco(ruta)


# ---------------------------------------------------------------------------
# Métricas (qué está pasando)
# ---------------------------------------------------------------------------
def contar_eventos(eventos) -> Counter:
    """Cuántas veces aparece cada evento. (Desafío de lógica: `for` + `if`.)"""
    c = Counter()
    for e in eventos:
        c[e["evento"]] += 1
    return c


def total_pantallas_visitadas(eventos) -> int:
    """Desafío autónomo: total de pantallas visitadas."""
    total = 0
    for e in eventos:
        if e["evento"] == A.PANTALLA_VISTA:
            total += 1
    return total


def pantallas_mas_visitadas(eventos, n=5) -> list:
    c = Counter()
    for e in eventos:
        if e["evento"] == A.PANTALLA_VISTA:
            c[(e.get("datos") or {}).get("nombre", "?")] += 1
    return c.most_common(n)


def agrupar_sesiones(eventos) -> dict:
    """{id_sesion: [eventos ordenados por ts]}. Eventos sin sesión se ignoran."""
    grupos = defaultdict(list)
    for e in eventos:
        if e.get("sesion"):
            grupos[e["sesion"]].append(e)
    for lista in grupos.values():
        lista.sort(key=lambda e: e["ts"])
    return dict(grupos)


def duracion_sesion(eventos_sesion) -> float:
    """Segundos entre el primer y el último evento de la sesión."""
    if len(eventos_sesion) < 2:
        return 0.0
    return eventos_sesion[-1]["ts"] - eventos_sesion[0]["ts"]


def resumen_sesiones(eventos) -> dict:
    grupos = agrupar_sesiones(eventos)
    duraciones = [duracion_sesion(g) for g in grupos.values()]
    dias = {datetime.fromtimestamp(g[0]["ts"]).date() for g in grupos.values()}
    return {
        "sesiones": len(grupos),
        "dias_con_uso": len(dias),
        "sesiones_por_dia": (len(grupos) / len(dias)) if dias else 0.0,
        "duracion_promedio_seg": (sum(duraciones) / len(duraciones)) if duraciones else 0.0,
    }


def _tasa(parte, total):
    return (parte / total) if total else None


# ---------------------------------------------------------------------------
# KPIs (alineados al éxito del proyecto)
# ---------------------------------------------------------------------------
def kpis(eventos) -> dict:
    c = contar_eventos(eventos)
    intentos = c[A.LOGIN_EXITOSO] + c[A.LOGIN_ERROR]
    clases_escuchadas = {(e.get("datos") or {}).get("grabacion_id")
                         for e in eventos if e["evento"] == A.REPRODUCCION_PLAY}
    clases_escuchadas.discard(None)
    clases_abiertas = {(e.get("datos") or {}).get("grabacion_id")
                       for e in eventos if e["evento"] == A.CLASE_ABIERTA}
    clases_abiertas.discard(None)
    cerradas_descargas = c[A.DESCARGA_COMPLETA] + c[A.DESCARGA_ERROR]
    return {
        "tasa_login_exitoso": _tasa(c[A.LOGIN_EXITOSO], intentos),
        "tasa_clases_reproducidas": _tasa(len(clases_escuchadas & clases_abiertas), len(clases_abiertas)),
        "clases_distintas_escuchadas": len(clases_escuchadas),
        "tasa_descarga_exitosa": _tasa(c[A.DESCARGA_COMPLETA], cerradas_descargas),
        "grabaciones_guardadas": c[A.GRABACION_GUARDADA],
    }


# ---------------------------------------------------------------------------
# Embudo (dónde abandona el usuario)
# ---------------------------------------------------------------------------
def embudo(eventos, pasos=EMBUDO_ESTUDIANTE) -> list:
    """Cuenta en cuántas sesiones se llegó a cada paso, EN ORDEN.

    Devuelve [{"paso", "sesiones", "vs_anterior", "caida"}...]; `caida` es
    la fracción de sesiones perdidas respecto del paso anterior.
    """
    alcanzados = [0] * len(pasos)
    for evs in agrupar_sesiones(eventos).values():
        k = 0
        for e in evs:
            if k < len(pasos) and e["evento"] in pasos[k][1]:
                alcanzados[k] += 1
                k += 1
    filas = []
    for i, (nombre, _evs) in enumerate(pasos):
        previo = alcanzados[i - 1] if i else None
        vs = _tasa(alcanzados[i], previo) if i else None
        filas.append({
            "paso": nombre,
            "sesiones": alcanzados[i],
            "vs_anterior": vs,
            "caida": (1 - vs) if vs is not None else None,
        })
    return filas


# ---------------------------------------------------------------------------
# Reporte
# ---------------------------------------------------------------------------
def _pct(x):
    return "sin datos" if x is None else f"{x * 100:.0f}%"


def _dur(seg):
    seg = int(seg)
    return f"{seg // 60}m {seg % 60:02d}s"


def reporte(eventos) -> str:
    if not eventos:
        return "No hay eventos registrados todavía. Abre la app y navega un poco."
    L = []
    L.append("=" * 52)
    L.append(" ANALÍTICAS WIICLASS")
    L.append("=" * 52)
    L.append(f"Eventos registrados: {len(eventos)}")
    L.append(f"Total de pantallas visitadas: {total_pantallas_visitadas(eventos)}")

    L.append("\nPantallas más visitadas")
    for nombre, n in pantallas_mas_visitadas(eventos):
        L.append(f"  {nombre:<22} {n}")

    L.append("\nEventos por tipo")
    for nombre, n in contar_eventos(eventos).most_common():
        L.append(f"  {nombre:<26} {n}")

    s = resumen_sesiones(eventos)
    L.append("\nSesiones")
    L.append(f"  Sesiones: {s['sesiones']}  |  días con uso: {s['dias_con_uso']}"
             f"  |  promedio por día: {s['sesiones_por_dia']:.1f}")
    L.append(f"  Duración promedio: {_dur(s['duracion_promedio_seg'])}")

    k = kpis(eventos)
    L.append("\nKPIs")
    L.append(f"  Login exitoso:               {_pct(k['tasa_login_exitoso'])}")
    L.append(f"  Clases abiertas que se reproducen: {_pct(k['tasa_clases_reproducidas'])}")
    L.append(f"  Clases distintas escuchadas: {k['clases_distintas_escuchadas']}")
    L.append(f"  Descargas exitosas:          {_pct(k['tasa_descarga_exitosa'])}")
    L.append(f"  Grabaciones guardadas:       {k['grabaciones_guardadas']}")

    L.append("\nEmbudo de uso (sesiones que llegan a cada paso)")
    for f in embudo(eventos):
        extra = ""
        if f["caida"] is not None:
            extra = f"  ({_pct(f['vs_anterior'])} del paso anterior)"
            if f["caida"] >= UMBRAL_CAIDA_ALERTA:
                extra += "  ⚠ caída fuerte: revisar usabilidad"
        L.append(f"  {f['paso']:<22} {f['sesiones']:>4}{extra}")
    return "\n".join(L)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    ruta = argv[0] if argv else None
    print(reporte(cargar_eventos(ruta)))


if __name__ == "__main__":
    main()
