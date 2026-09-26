"""
db.py — Capa de acceso a datos (SQLite) para WiiClass.

Contiene:
  - Creación del esquema (tablas mínimas sugeridas en la especificación).
  - Datos semilla (seed) para poder probar la app sin backend externo.
  - Funciones de consulta usadas por las pantallas.
"""

import sqlite3
import os
from datetime import datetime

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
"""


def init_db(seed: bool = True):
    """Crea el esquema si no existe y opcionalmente inserta datos demo."""
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    _migrar_columna_semana(conn)

    cur = conn.execute("SELECT COUNT(*) AS c FROM Instituciones")
    if seed and cur.fetchone()["c"] == 0:
        _seed_demo_data(conn)
    cur.close()
    conn.close()

    # Se recalcula siempre (es determinístico e idempotente): así, si se
    # agregan nuevas grabaciones más adelante, las semanas de toda la
    # categoría se mantienen consistentes entre sí.
    recalcular_semanas()


def _migrar_columna_semana(conn):
    """Migración liviana: agrega la columna `semana` si la base de datos
    ya existía de antes de que este campo se agregara al esquema (una
    base de datos creada con una versión previa de la app no la tendría,
    ya que `CREATE TABLE IF NOT EXISTS` no modifica tablas existentes)."""
    columnas = [r["name"] for r in conn.execute("PRAGMA table_info(Grabaciones)").fetchall()]
    if "semana" not in columnas:
        conn.execute("ALTER TABLE Grabaciones ADD COLUMN semana INTEGER")
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


def login(institucion_id: int, correo: str, password: str):
    """Devuelve la fila del usuario si las credenciales son correctas, si no None."""
    conn = get_connection()
    row = conn.execute(
        """SELECT * FROM Usuarios
           WHERE correo = ? AND institucion_id = ? AND password_hash = ?""",
        (correo, institucion_id, _fake_hash(password)),
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
    conn = get_connection()
    rows = conn.execute("SELECT * FROM Categorias ORDER BY nombre").fetchall()
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


def crear_notificacion(usuario_id: int, mensaje: str, tipo: str):
    conn = get_connection()
    conn.execute(
        """INSERT INTO Notificaciones (usuario_id, mensaje, tipo, leida, fecha)
           VALUES (?, ?, ?, 0, datetime('now'))""",
        (usuario_id, mensaje, tipo),
    )
    conn.commit()
    conn.close()


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
    la fila ni la notificación."""
    if esta_descargada(grabacion_id):
        return
    conn = get_connection()
    conn.execute(
        """INSERT INTO Descargas_offline (grabacion_id, ruta_local, peso_mb, fecha_descarga)
           VALUES (?, ?, ?, datetime('now'))""",
        (grabacion_id, ruta_local, peso_mb),
    )
    conn.commit()
    conn.close()
    grab = get_grabacion(grabacion_id)
    if grab:
        crear_notificacion(
            usuario_id,
            f"Audio descargado con éxito: {grab['nombre']}",
            "descarga_completada",
        )
