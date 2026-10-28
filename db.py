"""
db.py — Capa de acceso a datos (SQLite) para WiiClass.

Contiene:
  - Creación del esquema (tablas mínimas sugeridas en la especificación).
  - Datos semilla (seed) para poder probar la app sin backend externo.
  - Funciones de consulta usadas por las pantallas.
"""

import logging
import sqlite3
import os
from datetime import datetime

import storage

log = logging.getLogger("wiiclass.db")

DB_PATH = os.path.join(os.path.dirname(__file__), "wiiclass.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS Instituciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS Usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    correo TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    fecha_nac TEXT,
    institucion_id INTEGER,
    foto_path TEXT,
    rol TEXT NOT NULL DEFAULT 'Estudiante' CHECK(rol IN ('Estudiante', 'Profesor')),
    FOREIGN KEY (institucion_id) REFERENCES Instituciones(id)
);

CREATE TABLE IF NOT EXISTS Categorias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    icono TEXT,
    grupo TEXT
);

CREATE TABLE IF NOT EXISTS Grabaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    categoria_id INTEGER NOT NULL,
    nombre TEXT NOT NULL,
    url_audio TEXT NOT NULL,
    fecha_subida TEXT,
    duracion_seg INTEGER,
    semana INTEGER,
    profesor_id INTEGER,              -- NULL = grabación de ejemplo; si no, la subió ese profesor
    FOREIGN KEY (categoria_id) REFERENCES Categorias(id),
    FOREIGN KEY (profesor_id) REFERENCES Usuarios(id)
);

-- Materias (Categorias) asignadas a cada profesor.
CREATE TABLE IF NOT EXISTS Profesor_Materia (
    profesor_id INTEGER NOT NULL,
    categoria_id INTEGER NOT NULL,
    PRIMARY KEY (profesor_id, categoria_id),
    FOREIGN KEY (profesor_id) REFERENCES Usuarios(id),
    FOREIGN KEY (categoria_id) REFERENCES Categorias(id)
);

CREATE TABLE IF NOT EXISTS Notificaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL,
    mensaje TEXT NOT NULL,
    tipo TEXT NOT NULL,               -- 'descarga_completada' | 'nueva_grabacion'
    leida INTEGER DEFAULT 0,
    fecha TEXT,
    FOREIGN KEY (usuario_id) REFERENCES Usuarios(id)
);

CREATE TABLE IF NOT EXISTS Descargas_offline (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    grabacion_id INTEGER NOT NULL,
    ruta_local TEXT NOT NULL,
    peso_mb REAL,
    fecha_descarga TEXT,
    FOREIGN KEY (grabacion_id) REFERENCES Grabaciones(id)
);

-- Evita filas duplicadas si dos descargas de la misma clase se cruzan
-- (antes solo lo prevenía un chequeo en Python, con una pequeña ventana
-- de carrera entre "¿ya existe?" y "insertar").
CREATE UNIQUE INDEX IF NOT EXISTS ux_descargas_grabacion
    ON Descargas_offline(grabacion_id);
"""


def init_db(seed: bool = True):
    """Crea el esquema si no existe y opcionalmente inserta datos demo."""
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    _migrar_columna_semana(conn)
    _migrar_roles(conn)

    cur = conn.execute("SELECT COUNT(*) AS c FROM Instituciones")
    if seed and cur.fetchone()["c"] == 0:
        _seed_demo_data(conn)
    cur.close()
    if seed:
        _seed_profesor_demo(conn)
    # Recupera desde los JSON lo que la base no tenga (grabaciones de
    # profesores y notificaciones). Va DESPUÉS de los datos semilla para que
    # existan las materias y los usuarios a los que se asocian.
    _restaurar_desde_json(conn)
    conn.close()

    # Se recalcula siempre (es determinístico e idempotente): así, si se
    # agregan nuevas grabaciones más adelante, las semanas de toda la
    # categoría se mantienen consistentes entre sí.
    recalcular_semanas()

    # Deja los JSON al día con lo que quedó en la base (también los crea la
    # primera vez que se abre una versión con persistencia).
    exportar_grabaciones()
    exportar_notificaciones()


def _migrar_columna_semana(conn):
    """Migración liviana: agrega la columna `semana` si la base de datos
    ya existía de antes de que este campo se agregara al esquema (una
    base de datos creada con una versión previa de la app no la tendría,
    ya que `CREATE TABLE IF NOT EXISTS` no modifica tablas existentes)."""
    columnas = [r["name"] for r in conn.execute("PRAGMA table_info(Grabaciones)").fetchall()]
    if "semana" not in columnas:
        conn.execute("ALTER TABLE Grabaciones ADD COLUMN semana INTEGER")
        conn.commit()


def _migrar_roles(conn):
    """Migración liviana para bases creadas ANTES de existir los roles:
    agrega `Usuarios.rol` (los usuarios existentes quedan como Estudiante)
    y `Grabaciones.profesor_id`. Las tablas nuevas ya las crea SCHEMA."""
    cols_u = [r["name"] for r in conn.execute("PRAGMA table_info(Usuarios)").fetchall()]
    if "rol" not in cols_u:
        conn.execute(
            "ALTER TABLE Usuarios ADD COLUMN rol TEXT NOT NULL DEFAULT 'Estudiante' "
            "CHECK(rol IN ('Estudiante', 'Profesor'))"
        )
    cols_g = [r["name"] for r in conn.execute("PRAGMA table_info(Grabaciones)").fetchall()]
    if "profesor_id" not in cols_g:
        conn.execute("ALTER TABLE Grabaciones ADD COLUMN profesor_id INTEGER REFERENCES Usuarios(id)")
    conn.commit()


def _seed_profesor_demo(conn):
    """Crea (una sola vez) un profesor de prueba con dos materias asignadas."""
    if conn.execute("SELECT 1 FROM Usuarios WHERE correo = 'profesor@uct.cl'").fetchone():
        return
    inst = conn.execute("SELECT id FROM Instituciones ORDER BY id LIMIT 1").fetchone()
    if inst is None:
        return
    cur = conn.execute(
        """INSERT INTO Usuarios (nombre, correo, password_hash, fecha_nac, institucion_id, rol)
           VALUES (?, ?, ?, ?, ?, 'Profesor')""",
        ("Carolina Rojas", "profesor@uct.cl", _fake_hash("12345678"), "1985-03-22", inst["id"]),
    )
    prof_id = cur.lastrowid
    for cat in conn.execute("SELECT id FROM Categorias ORDER BY id LIMIT 2").fetchall():
        conn.execute(
            "INSERT OR IGNORE INTO Profesor_Materia (profesor_id, categoria_id) VALUES (?, ?)",
            (prof_id, cat["id"]),
        )
    conn.commit()


def _seed_demo_data(conn):
    conn.execute("INSERT INTO Instituciones (nombre) VALUES ('Universidad Central')")
    conn.execute("INSERT INTO Instituciones (nombre) VALUES ('Universidad del Sur')")
    conn.commit()

    conn.execute(
        """INSERT INTO Usuarios (nombre, correo, password_hash, fecha_nac, institucion_id, foto_path)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("Sebastián Flores", "sflores@uct.cl", _fake_hash("12345678"),
         "2003-07-16", 1, None),
    )
    conn.commit()

    categorias = [
        ("Matemáticas", "calculator", "Grupo 04"),
        ("Ciencias", "flask", "Grupo 08"),
        ("Humanidades", "book-open-page-variant", "Grupo 02"),
    ]
    conn.executemany(
        "INSERT INTO Categorias (nombre, icono, grupo) VALUES (?, ?, ?)", categorias
    )
    conn.commit()

    grabaciones = [
        (1, "Clase 1 - Introducción a Matrices", "assets/audio/clase1.mp3", "2026-08-15", 2730),
        (1, "Clase 2 - Multiplicación de Matrices", "assets/audio/clase2.mp3", "2026-08-18", 3015),
        (1, "Clase 3 - Determinantes y Propiedades", "assets/audio/clase3.mp3", "2026-08-22", 2325),
        (1, "Clase 4 - Matriz Inversa", "assets/audio/clase4.mp3", "2026-08-25", 2530),
        (1, "Clase 5 - Sistemas de Ecuaciones", "assets/audio/clase5.mp3", "2026-08-29", 2820),
        (2, "Clase 1 - Cinemática", "assets/audio/fis1.mp3", "2026-08-16", 2400),
        (3, "Clase 1 - Introducción a la Filosofía", "assets/audio/hum1.mp3", "2026-08-17", 2100),
    ]
    conn.executemany(
        """INSERT INTO Grabaciones (categoria_id, nombre, url_audio, fecha_subida, duracion_seg)
           VALUES (?, ?, ?, ?, ?)""",
        grabaciones,
    )
    conn.commit()

    # Se agregan minutos_atras distintos para que cada notificación tenga
    # una fecha realmente distinta (y el orden "más reciente primero" sea
    # significativo) — con datetime('now') igual para todas, SQLite no
    # tiene con qué desempatar el orden de forma consistente.
    notificaciones = [
        (1, "Descarga completada: Clase 3 - Derivadas y sus aplicaciones", "descarga_completada", 0, 5),
        (1, "Nueva grabación disponible en Cálculo II: Clase 5 - Integrales definidas", "nueva_grabacion", 0, 60),
        (1, "Descarga completada: Clase 1 - Introducción a Matrices", "descarga_completada", 1, 180),
        (1, "Nueva grabación disponible en Matemáticas: Clase 6 - Sistemas Lineales", "nueva_grabacion", 1, 1440),
        (1, "Descarga completada: Clase 2 - Multiplicación de Matrices", "descarga_completada", 1, 1500),
        (1, "Nueva grabación disponible en Física I: Clase 2 - Dinámica", "nueva_grabacion", 1, 2880),
        (1, "Descarga completada: Clase 1 - Cinemática", "descarga_completada", 1, 2940),
        (1, "Nueva grabación disponible en Humanidades: Clase 2 - Ética", "nueva_grabacion", 1, 4320),
    ]
    # Si hay un respaldo JSON de notificaciones, se restaura ese (con su
    # estado leída/no leída) en vez de sembrar de nuevo las de demostración,
    # que quedarían duplicadas con fechas distintas.
    if not storage.cargar_notificaciones():
        conn.executemany(
            """INSERT INTO Notificaciones (usuario_id, mensaje, tipo, leida, fecha)
               VALUES (?, ?, ?, ?, datetime('now', '-' || ? || ' minutes'))""",
            notificaciones,
        )
        conn.commit()

    conn.execute(
        """INSERT INTO Descargas_offline (grabacion_id, ruta_local, peso_mb, fecha_descarga)
           VALUES (1, 'assets/audio/clase1.mp3', 42, datetime('now'))"""
    )
    conn.execute(
        """INSERT INTO Descargas_offline (grabacion_id, ruta_local, peso_mb, fecha_descarga)
           VALUES (3, 'assets/audio/clase3.mp3', 36, datetime('now'))"""
    )
    conn.commit()


def _fake_hash(password: str) -> str:
    # Placeholder simple; en producción usar bcrypt/argon2.
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Consultas usadas por las pantallas
# ---------------------------------------------------------------------------

def get_instituciones():
    conn = get_connection()
    rows = conn.execute("SELECT id, nombre FROM Instituciones ORDER BY nombre").fetchall()
    conn.close()
    return rows


def login(institucion_id: int, correo: str, password: str, rol: str = "Estudiante"):
    """Devuelve la fila del usuario si las credenciales son correctas, si no None.

    El correo se compara sin distinguir mayúsculas: "SFlores@uct.cl" y
    "sflores@uct.cl" son la misma cuenta (antes fallaba con "Credenciales
    incorrectas" si el teclado del teléfono ponía la primera letra en
    mayúscula).
    """
    conn = get_connection()
    row = conn.execute(
        """SELECT * FROM Usuarios
           WHERE lower(correo) = lower(?) AND institucion_id = ? AND password_hash = ?
             AND rol = ?""",
        (correo, institucion_id, _fake_hash(password), rol),
    ).fetchone()
    conn.close()
    return row


def get_usuario(usuario_id: int):
    conn = get_connection()
    row = conn.execute(
        """SELECT Usuarios.*, Instituciones.nombre AS institucion_nombre
           FROM Usuarios JOIN Instituciones ON Usuarios.institucion_id = Instituciones.id
           WHERE Usuarios.id = ?""",
        (usuario_id,),
    ).fetchone()
    conn.close()
    return row


def get_categorias():
    """Categorías con la cantidad de clases de cada una (`n_clases`),
    calculada en la misma consulta con un LEFT JOIN (así una categoría sin
    grabaciones aparece igual, con 0)."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT Categorias.*, COUNT(Grabaciones.id) AS n_clases
           FROM Categorias
           LEFT JOIN Grabaciones ON Grabaciones.categoria_id = Categorias.id
           GROUP BY Categorias.id
           ORDER BY Categorias.nombre"""
    ).fetchall()
    conn.close()
    return rows


def get_grabaciones_recientes(limite: int = 3):
    """Las últimas grabaciones subidas (todas las categorías), para la
    sección "Clases recientes" del Inicio."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT Grabaciones.*, Categorias.nombre AS categoria_nombre,
                  Categorias.icono AS categoria_icono
           FROM Grabaciones
           JOIN Categorias ON Grabaciones.categoria_id = Categorias.id
           ORDER BY Grabaciones.fecha_subida DESC, Grabaciones.id DESC
           LIMIT ?""",
        (limite,),
    ).fetchall()
    conn.close()
    return rows


def get_grabaciones_por_categoria(categoria_id: int, semana: int = None):
    """Si `semana` es None, devuelve todas las grabaciones de la
    categoría (pestaña "Todas"); si no, solo las de esa semana."""
    conn = get_connection()
    if semana is None:
        rows = conn.execute(
            "SELECT * FROM Grabaciones WHERE categoria_id = ? ORDER BY fecha_subida",
            (categoria_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM Grabaciones WHERE categoria_id = ? AND semana = ? ORDER BY fecha_subida",
            (categoria_id, semana),
        ).fetchall()
    conn.close()
    return rows


def get_semanas_disponibles(categoria_id: int):
    """Lista ordenada de números de semana presentes en una categoría,
    para generar las pestañas 'Semana 1', 'Semana 2', ... dinámicamente."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT DISTINCT semana FROM Grabaciones
           WHERE categoria_id = ? AND semana IS NOT NULL
           ORDER BY semana""",
        (categoria_id,),
    ).fetchall()
    conn.close()
    return [r["semana"] for r in rows]


def recalcular_semanas(dias_por_semana: int = 7):
    """Asigna el campo `semana` a cada grabación según su orden
    cronológico DENTRO DE SU CATEGORÍA: la semana 1 empieza en la fecha
    de la primera grabación de esa categoría, y cada bloque de
    `dias_por_semana` días (7 por defecto) forma la siguiente semana.

    Se recalcula para TODAS las categorías cada vez que se llama (es
    barato: son pocas filas, y así una grabación nueva no deja
    inconsistente la numeración de las que ya tenían semana asignada).
    """
    conn = get_connection()
    categorias = conn.execute("SELECT id FROM Categorias").fetchall()
    for cat in categorias:
        grabaciones = conn.execute(
            """SELECT id, fecha_subida FROM Grabaciones
               WHERE categoria_id = ? AND fecha_subida IS NOT NULL
                 AND profesor_id IS NULL
               ORDER BY fecha_subida""",
            (cat["id"],),
        ).fetchall()
        if not grabaciones:
            continue
        primera_fecha = datetime.fromisoformat(grabaciones[0]["fecha_subida"])
        for g in grabaciones:
            fecha = datetime.fromisoformat(g["fecha_subida"])
            dias_desde_inicio = (fecha - primera_fecha).days
            semana = dias_desde_inicio // dias_por_semana + 1
            conn.execute("UPDATE Grabaciones SET semana = ? WHERE id = ?", (semana, g["id"]))
    conn.commit()
    conn.close()


def get_grabacion(grabacion_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM Grabaciones WHERE id = ?", (grabacion_id,)).fetchone()
    conn.close()
    return row


def get_notificaciones(usuario_id: int):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM Notificaciones WHERE usuario_id = ? ORDER BY fecha DESC",
        (usuario_id,),
    ).fetchall()
    conn.close()
    return rows


def marcar_notificacion_leida(notificacion_id: int):
    conn = get_connection()
    conn.execute("UPDATE Notificaciones SET leida = 1 WHERE id = ?", (notificacion_id,))
    conn.commit()
    conn.close()
    exportar_notificaciones()


def marcar_todas_leidas(usuario_id: int):
    """Marca como leídas todas las notificaciones del usuario (se llama al
    salir de la pestaña Alertas)."""
    conn = get_connection()
    conn.execute("UPDATE Notificaciones SET leida = 1 WHERE usuario_id = ?", (usuario_id,))
    conn.commit()
    conn.close()
    exportar_notificaciones()


def crear_notificacion(usuario_id: int, mensaje: str, tipo: str):
    conn = get_connection()
    conn.execute(
        """INSERT INTO Notificaciones (usuario_id, mensaje, tipo, leida, fecha)
           VALUES (?, ?, ?, 0, datetime('now'))""",
        (usuario_id, mensaje, tipo),
    )
    conn.commit()
    conn.close()
    exportar_notificaciones()


def get_descargas_agrupadas():
    """Devuelve las descargas offline agrupadas por categoría."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT Descargas_offline.*, Grabaciones.nombre AS grabacion_nombre,
                  Grabaciones.fecha_subida, Grabaciones.duracion_seg,
                  Categorias.id AS categoria_id, Categorias.nombre AS categoria_nombre,
                  Categorias.icono AS categoria_icono
           FROM Descargas_offline
           JOIN Grabaciones ON Descargas_offline.grabacion_id = Grabaciones.id
           JOIN Categorias ON Grabaciones.categoria_id = Categorias.id
           ORDER BY Categorias.nombre, Grabaciones.fecha_subida"""
    ).fetchall()
    conn.close()

    agrupado = {}
    for r in rows:
        agrupado.setdefault(
            (r["categoria_id"], r["categoria_nombre"], r["categoria_icono"]), []
        ).append(r)
    return agrupado


def esta_descargada(grabacion_id: int) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM Descargas_offline WHERE grabacion_id = ? LIMIT 1", (grabacion_id,)
    ).fetchone()
    conn.close()
    return row is not None


def get_ids_descargados() -> set:
    """IDs de todas las grabaciones descargadas, en UNA sola consulta.

    Antes, al armar la lista de una categoría se llamaba a `esta_descargada`
    por cada clase (una conexión + consulta por fila, y se repetía en cada
    refresco de la lista, p. ej. al seleccionar/deseleccionar).
    """
    conn = get_connection()
    rows = conn.execute("SELECT grabacion_id FROM Descargas_offline").fetchall()
    conn.close()
    return {r["grabacion_id"] for r in rows}


def get_ruta_local(grabacion_id: int):
    """Devuelve la ruta local si la grabación ya está descargada, o None.
    Se usa para preferir el archivo ya descargado al reproducir (funciona
    tanto online como offline, y evita copiar/leer el asset empaquetado
    de nuevo si ya hay una copia local)."""
    conn = get_connection()
    row = conn.execute(
        "SELECT ruta_local FROM Descargas_offline WHERE grabacion_id = ? LIMIT 1",
        (grabacion_id,),
    ).fetchone()
    conn.close()
    return row["ruta_local"] if row else None


def registrar_descarga(usuario_id: int, grabacion_id: int, ruta_local: str, peso_mb: float):
    """Registra una descarga como completada y genera la notificación
    correspondiente. Es idempotente: si ya estaba descargada, no duplica
    la fila ni la notificación.

    Usa `INSERT OR IGNORE` apoyado en el índice único de `grabacion_id`:
    la propia base de datos decide de forma atómica si la fila es nueva
    (`rowcount`), en vez de "consultar y luego insertar" en dos pasos.
    """
    conn = get_connection()
    cur = conn.execute(
        """INSERT OR IGNORE INTO Descargas_offline (grabacion_id, ruta_local, peso_mb, fecha_descarga)
           VALUES (?, ?, ?, datetime('now'))""",
        (grabacion_id, ruta_local, peso_mb),
    )
    es_nueva = cur.rowcount > 0
    conn.commit()
    conn.close()
    if not es_nueva:
        return
    grab = get_grabacion(grabacion_id)
    if grab:
        crear_notificacion(
            usuario_id,
            f"Audio descargado con éxito: {grab['nombre']}",
            "descarga_completada",
        )


# ---------------------------------------------------------------------------
# Roles y grabación (módulo del Profesor)
# ---------------------------------------------------------------------------

ROLES = ("Estudiante", "Profesor")


def get_materias_profesor(profesor_id: int):
    """Solo las materias (Categorias) ASIGNADAS a ese profesor."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT Categorias.* FROM Categorias
           JOIN Profesor_Materia ON Profesor_Materia.categoria_id = Categorias.id
           WHERE Profesor_Materia.profesor_id = ?
           ORDER BY Categorias.nombre""",
        (profesor_id,),
    ).fetchall()
    conn.close()
    return rows


def profesor_tiene_materia(profesor_id: int, categoria_id: int) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM Profesor_Materia WHERE profesor_id = ? AND categoria_id = ?",
        (profesor_id, categoria_id),
    ).fetchone()
    conn.close()
    return row is not None


def registrar_grabacion_profesor(profesor_id: int, categoria_id: int, semana: int,
                                 titulo: str, ruta_archivo: str, duracion_seg: int) -> int:
    """Guarda la grabación hecha por un profesor y devuelve su id.

    Mapeo con los campos pedidos: id_grabacion=id, id_materia=categoria_id,
    id_profesor=profesor_id, semana, titulo=nombre, ruta_archivo=url_audio,
    duracion=duracion_seg, fecha_creacion=fecha_subida. Se guarda en la
    misma tabla `Grabaciones` que ya leen Inicio/Categoría/Reproductor, así
    los estudiantes la ven sin cambios adicionales.
    """
    if not profesor_tiene_materia(profesor_id, categoria_id):
        raise PermissionError("La materia no está asignada a este profesor")
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO Grabaciones
             (categoria_id, nombre, url_audio, fecha_subida, duracion_seg, semana, profesor_id)
           VALUES (?, ?, ?, datetime('now', 'localtime'), ?, ?, ?)""",
        (categoria_id, titulo, ruta_archivo, int(duracion_seg), int(semana), profesor_id),
    )
    conn.commit()
    nuevo_id = cur.lastrowid
    conn.close()
    exportar_grabaciones()
    return nuevo_id


# ---------------------------------------------------------------------------
# Persistencia JSON (ver storage.py)
#
# SQLite sigue siendo la fuente que leen las pantallas. Los JSON son un
# respaldo duradero:
#   * `exportar_*`  -> se llaman tras cada cambio; FUSIONAN la base con el
#     JSON (nunca borran entradas del JSON), así un registro que no se pudo
#     restaurar (p. ej. el audio ya no está) no se pierde del respaldo.
#   * `_restaurar_desde_json` -> se llama al iniciar; inserta en la base lo
#     que el JSON tiene y la base no.
# Los usuarios y las materias se enlazan por CORREO y NOMBRE (no por id), de
# modo que el respaldo sigue valiendo aunque la base se recree con otros ids.
# Un fallo de disco nunca interrumpe la app: solo queda en el log.
# ---------------------------------------------------------------------------

def _ruta_absoluta(ruta: str) -> str:
    return ruta if os.path.isabs(ruta) else os.path.join(os.path.dirname(__file__), ruta)


def _clave_grabacion(g: dict):
    return ((g.get("profesor_correo") or "").lower(), g.get("url_audio"))


def _clave_notificacion(n: dict):
    return ((n.get("usuario_correo") or "").lower(), n.get("mensaje"),
            n.get("tipo"), n.get("fecha"))


def exportar_grabaciones() -> bool:
    """Respalda en JSON las grabaciones subidas por profesores."""
    try:
        conn = get_connection()
        rows = conn.execute(
            """SELECT Grabaciones.id, Grabaciones.nombre, Grabaciones.url_audio,
                      Grabaciones.fecha_subida, Grabaciones.duracion_seg,
                      Grabaciones.semana, Grabaciones.categoria_id,
                      Categorias.nombre AS categoria_nombre,
                      Usuarios.correo AS profesor_correo
               FROM Grabaciones
               JOIN Categorias ON Grabaciones.categoria_id = Categorias.id
               JOIN Usuarios ON Grabaciones.profesor_id = Usuarios.id
               WHERE Grabaciones.profesor_id IS NOT NULL
               ORDER BY Grabaciones.id"""
        ).fetchall()
        conn.close()
        fusion = {_clave_grabacion(g): g for g in storage.cargar_grabaciones()}
        for r in rows:
            fusion[_clave_grabacion(dict(r))] = dict(r)
        return storage.guardar_grabaciones(list(fusion.values()))
    except Exception:
        log.exception("No se pudo respaldar las grabaciones en JSON")
        return False


def exportar_notificaciones() -> bool:
    """Respalda en JSON las notificaciones (incluye el estado leída)."""
    try:
        conn = get_connection()
        rows = conn.execute(
            """SELECT Notificaciones.id, Usuarios.correo AS usuario_correo,
                      Notificaciones.mensaje, Notificaciones.tipo,
                      Notificaciones.leida, Notificaciones.fecha
               FROM Notificaciones
               JOIN Usuarios ON Notificaciones.usuario_id = Usuarios.id
               ORDER BY Notificaciones.id"""
        ).fetchall()
        conn.close()
        fusion = {_clave_notificacion(n): n for n in storage.cargar_notificaciones()}
        for r in rows:
            fusion[_clave_notificacion(dict(r))] = dict(r)
        return storage.guardar_notificaciones(list(fusion.values()))
    except Exception:
        log.exception("No se pudo respaldar las notificaciones en JSON")
        return False


def _restaurar_desde_json(conn):
    """Inserta en la base las grabaciones y notificaciones que están en los
    JSON y faltan en SQLite. Idempotente: se puede llamar en cada arranque."""
    try:
        _restaurar_grabaciones(conn)
        _restaurar_notificaciones(conn)
        conn.commit()
    except Exception:
        log.exception("No se pudo restaurar desde los JSON")


def _restaurar_grabaciones(conn):
    for g in storage.cargar_grabaciones():
        ruta = g.get("url_audio")
        if not ruta or not g.get("nombre"):
            continue
        prof = conn.execute(
            "SELECT id FROM Usuarios WHERE lower(correo) = lower(?) AND rol = 'Profesor'",
            (g.get("profesor_correo") or "",),
        ).fetchone()
        if prof is None:
            continue
        if conn.execute(
            "SELECT 1 FROM Grabaciones WHERE url_audio = ? AND profesor_id = ?",
            (ruta, prof["id"]),
        ).fetchone():
            continue
        if not os.path.exists(_ruta_absoluta(ruta)):
            # El audio ya no está en el disco: se conserva el respaldo, pero
            # no se muestra una clase que no se puede reproducir.
            log.warning("No se restaura '%s': falta el archivo %s", g["nombre"], ruta)
            continue
        cat = conn.execute(
            "SELECT id FROM Categorias WHERE nombre = ?", (g.get("categoria_nombre"),)
        ).fetchone() or conn.execute(
            "SELECT id FROM Categorias WHERE id = ?", (g.get("categoria_id"),)
        ).fetchone()
        if cat is None:
            continue
        conn.execute(
            """INSERT INTO Grabaciones
                 (categoria_id, nombre, url_audio, fecha_subida, duracion_seg, semana, profesor_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (cat["id"], g["nombre"], ruta, g.get("fecha_subida"),
             g.get("duracion_seg"), g.get("semana"), prof["id"]),
        )


def _restaurar_notificaciones(conn):
    for n in storage.cargar_notificaciones():
        if not n.get("mensaje") or not n.get("tipo"):
            continue
        usuario = conn.execute(
            "SELECT id FROM Usuarios WHERE lower(correo) = lower(?)",
            (n.get("usuario_correo") or "",),
        ).fetchone()
        if usuario is None:
            continue
        existente = conn.execute(
            """SELECT id, leida FROM Notificaciones
               WHERE usuario_id = ? AND mensaje = ? AND tipo = ? AND fecha IS ?""",
            (usuario["id"], n["mensaje"], n["tipo"], n.get("fecha")),
        ).fetchone()
        if existente is None:
            conn.execute(
                """INSERT INTO Notificaciones (usuario_id, mensaje, tipo, leida, fecha)
                   VALUES (?, ?, ?, ?, ?)""",
                (usuario["id"], n["mensaje"], n["tipo"], 1 if n.get("leida") else 0, n.get("fecha")),
            )
        elif n.get("leida") and not existente["leida"]:
            conn.execute("UPDATE Notificaciones SET leida = 1 WHERE id = ?", (existente["id"],))
