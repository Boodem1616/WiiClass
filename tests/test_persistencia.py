"""Pruebas de persistencia JSON (sin Kivy): python -m unittest discover -s tests -v"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wiiclass.data import db
from wiiclass.data import storage


class BaseTmp(unittest.TestCase):
    """Cada prueba usa una base SQLite y una carpeta de JSON propias."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self._old_env = os.environ.get("WIICLASS_DATA_DIR")
        os.environ["WIICLASS_DATA_DIR"] = os.path.join(self.dir, "datos")
        self._old_db = db.DB_PATH
        db.DB_PATH = os.path.join(self.dir, "test.db")

    def tearDown(self):
        db.DB_PATH = self._old_db
        if self._old_env is None:
            os.environ.pop("WIICLASS_DATA_DIR", None)
        else:
            os.environ["WIICLASS_DATA_DIR"] = self._old_env
        self._tmp.cleanup()

    def borrar_base(self):
        os.remove(db.DB_PATH)

    def profesor(self):
        conn = db.get_connection()
        row = conn.execute("SELECT * FROM Usuarios WHERE correo = 'profesor@uct.cl'").fetchone()
        conn.close()
        return row

    def estudiante_id(self):
        conn = db.get_connection()
        row = conn.execute("SELECT id FROM Usuarios WHERE correo = 'sflores@uct.cl'").fetchone()
        conn.close()
        return row["id"]

    def audio_falso(self, nombre="clase.m4a"):
        ruta = os.path.join(self.dir, nombre)
        with open(ruta, "wb") as f:
            f.write(b"audio")
        return ruta


class TestStorage(BaseTmp):
    def test_sesion_ida_y_vuelta(self):
        self.assertIsNone(storage.cargar_sesion())
        self.assertTrue(storage.guardar_sesion(3, "Ana@UCT.cl", "Profesor", 1))
        s = storage.cargar_sesion()
        self.assertEqual((s["usuario_id"], s["correo"], s["rol"]), (3, "ana@uct.cl", "Profesor"))

    def test_sesion_no_guarda_contrasena(self):
        storage.guardar_sesion(1, "a@b.cl", "Estudiante", 1)
        with open(os.path.join(storage.carpeta_datos(), storage.ARCHIVO_SESION), encoding="utf-8") as f:
            texto = f.read().lower()
        self.assertNotIn("password", texto)
        self.assertNotIn("hash", texto)

    def test_borrar_sesion(self):
        storage.guardar_sesion(1, "a@b.cl", "Estudiante", 1)
        storage.borrar_sesion()
        self.assertIsNone(storage.cargar_sesion())
        storage.borrar_sesion()  # borrar dos veces no falla

    def test_sesion_invalida_se_ignora(self):
        storage._escribir(storage.ARCHIVO_SESION, {"usuario_id": "x", "correo": "a", "rol": "Admin"})
        self.assertIsNone(storage.cargar_sesion())
        storage._escribir(storage.ARCHIVO_SESION, {"usuario_id": True, "correo": "a@b.cl", "rol": "Estudiante"})
        self.assertIsNone(storage.cargar_sesion())

    def test_json_corrupto_se_aparta_y_no_rompe(self):
        ruta = os.path.join(storage.carpeta_datos(), storage.ARCHIVO_GRABACIONES)
        with open(ruta, "w", encoding="utf-8") as f:
            f.write("{esto no es json")
        self.assertEqual(storage.cargar_grabaciones(), [])
        self.assertTrue(os.path.exists(ruta + ".corrupto"))
        self.assertTrue(storage.guardar_grabaciones([{"nombre": "x"}]))
        self.assertEqual(storage.cargar_grabaciones(), [{"nombre": "x"}])

    def test_formato_inesperado_se_ignora(self):
        ruta = os.path.join(storage.carpeta_datos(), storage.ARCHIVO_NOTIFICACIONES)
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump([1, 2, 3], f)
        self.assertEqual(storage.cargar_notificaciones(), [])

    def test_escritura_atomica_no_deja_temporales(self):
        storage.guardar_notificaciones([{"mensaje": "hola ñandú"}])
        restos = [n for n in os.listdir(storage.carpeta_datos()) if n.endswith(".tmp")]
        self.assertEqual(restos, [])
        self.assertEqual(storage.cargar_notificaciones()[0]["mensaje"], "hola ñandú")

    def test_escritura_que_falla_devuelve_false(self):
        self.assertFalse(storage.guardar_grabaciones([object()]))  # no serializable
        restos = [n for n in os.listdir(storage.carpeta_datos()) if n.endswith(".tmp")]
        self.assertEqual(restos, [])


class TestGrabaciones(BaseTmp):
    def registrar(self, titulo="Clase de prueba", semana=2):
        prof = self.profesor()
        materia = db.get_materias_profesor(prof["id"])[0]
        ruta = self.audio_falso(f"{titulo.replace(' ', '_')}.m4a")
        gid = db.registrar_grabacion_profesor(prof["id"], materia["id"], semana, titulo, ruta, 120)
        return gid, ruta, materia

    def test_se_respalda_al_registrar(self):
        db.init_db(seed=True)
        _gid, ruta, materia = self.registrar()
        guardadas = storage.cargar_grabaciones()
        self.assertEqual(len(guardadas), 1)
        g = guardadas[0]
        self.assertEqual(g["url_audio"], ruta)
        self.assertEqual(g["categoria_nombre"], materia["nombre"])
        self.assertEqual(g["profesor_correo"], "profesor@uct.cl")
        self.assertEqual((g["semana"], g["duracion_seg"]), (2, 120))

    def test_se_recupera_si_se_pierde_la_base(self):
        db.init_db(seed=True)
        _gid, ruta, materia = self.registrar("Derivadas", semana=5)
        self.borrar_base()
        db.init_db(seed=True)
        filas = [r for r in db.get_grabaciones_por_categoria(materia["id"]) if r["url_audio"] == ruta]
        self.assertEqual(len(filas), 1)
        self.assertEqual((filas[0]["nombre"], filas[0]["semana"], filas[0]["duracion_seg"]),
                         ("Derivadas", 5, 120))
        self.assertEqual(filas[0]["profesor_id"], self.profesor()["id"])

    def test_reabrir_sin_cambios_no_duplica(self):
        db.init_db(seed=True)
        _gid, _ruta, materia = self.registrar()
        for _ in range(3):
            db.init_db(seed=True)
        n = [r for r in db.get_grabaciones_por_categoria(materia["id"]) if r["profesor_id"]]
        self.assertEqual(len(n), 1)
        self.assertEqual(len(storage.cargar_grabaciones()), 1)

    def test_si_falta_el_audio_no_se_restaura_pero_el_respaldo_se_conserva(self):
        db.init_db(seed=True)
        _gid, ruta, materia = self.registrar()
        os.remove(ruta)
        self.borrar_base()
        db.init_db(seed=True)
        n = [r for r in db.get_grabaciones_por_categoria(materia["id"]) if r["profesor_id"]]
        self.assertEqual(n, [])
        self.assertEqual(len(storage.cargar_grabaciones()), 1)  # no se perdió del JSON

    def test_base_existente_sin_json_genera_el_respaldo(self):
        """Actualización desde una versión sin persistencia: la base ya tiene
        grabaciones y el JSON no existe todavía."""
        db.init_db(seed=True)
        self.registrar()
        os.remove(os.path.join(storage.carpeta_datos(), storage.ARCHIVO_GRABACIONES))
        db.init_db(seed=True)
        self.assertEqual(len(storage.cargar_grabaciones()), 1)


class TestNotificaciones(BaseTmp):
    def test_se_respalda_al_crear_y_al_leer(self):
        db.init_db(seed=True)
        uid = self.estudiante_id()
        db.crear_notificacion(uid, "Audio descargado con éxito: X", "descarga_completada")
        guardadas = storage.cargar_notificaciones()
        nueva = [n for n in guardadas if n["mensaje"].endswith(": X")][0]
        self.assertEqual(nueva["leida"], 0)
        db.marcar_todas_leidas(uid)
        self.assertTrue(all(n["leida"] == 1 for n in storage.cargar_notificaciones()
                            if n["usuario_correo"] == "sflores@uct.cl"))

    def test_se_recuperan_con_su_estado_si_se_pierde_la_base(self):
        db.init_db(seed=True)
        uid = self.estudiante_id()
        db.crear_notificacion(uid, "Audio descargado con éxito: Y", "descarga_completada")
        antes = db.get_notificaciones(uid)
        no_leida = [n for n in antes if n["mensaje"].endswith(": Y")][0]
        ya_leida = [n for n in antes if n["leida"] == 1][0]

        self.borrar_base()
        db.init_db(seed=True)
        despues = db.get_notificaciones(self.estudiante_id())

        # Mismas notificaciones, SIN duplicar las de demostración.
        self.assertEqual(sorted(n["mensaje"] for n in despues),
                         sorted(n["mensaje"] for n in antes))
        d = {n["mensaje"]: n for n in despues}
        self.assertEqual(d[no_leida["mensaje"]]["leida"], 0)
        self.assertEqual(d[ya_leida["mensaje"]]["leida"], 1)
        self.assertEqual(d[ya_leida["mensaje"]]["fecha"], ya_leida["fecha"])

    def test_leida_se_conserva_tras_reabrir(self):
        db.init_db(seed=True)
        uid = self.estudiante_id()
        db.marcar_todas_leidas(uid)
        self.borrar_base()
        db.init_db(seed=True)
        self.assertTrue(all(n["leida"] == 1 for n in db.get_notificaciones(self.estudiante_id())))

    def test_reabrir_sin_cambios_no_duplica(self):
        db.init_db(seed=True)
        n0 = len(db.get_notificaciones(self.estudiante_id()))
        for _ in range(3):
            db.init_db(seed=True)
        self.assertEqual(len(db.get_notificaciones(self.estudiante_id())), n0)
        self.assertEqual(len(storage.cargar_notificaciones()), n0)

    def test_registrar_descarga_queda_respaldada(self):
        db.init_db(seed=True)
        uid = self.estudiante_id()
        db.registrar_descarga(uid, 2, self.audio_falso("d.mp3"), 1.5)
        self.assertTrue(any(n["mensaje"].startswith("Audio descargado con éxito")
                            for n in storage.cargar_notificaciones()))

    def test_fallo_de_disco_no_rompe_la_app(self):
        db.init_db(seed=True)
        os.environ["WIICLASS_DATA_DIR"] = os.path.join(self.dir, "archivo_no_carpeta")
        with open(os.environ["WIICLASS_DATA_DIR"], "w") as f:  # un archivo donde iría la carpeta
            f.write("x")
        uid = self.estudiante_id()
        db.crear_notificacion(uid, "no debe fallar", "nueva_grabacion")  # no lanza
        self.assertTrue(any(n["mensaje"] == "no debe fallar" for n in db.get_notificaciones(uid)))


def _cargar_estado():
    """Carga notifications_state.py directo del archivo: el paquete
    `wiiclass.ui.screens` importa Kivy y estas pruebas no lo necesitan."""
    import importlib.util
    ruta = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "wiiclass", "ui", "screens", "notifications_state.py")
    spec = importlib.util.spec_from_file_location("_notifications_state_test", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestNotificacionesOcultas(BaseTmp):
    """Lo que el usuario elimina de Alertas sigue eliminado tras cerrar
    sesión, volver a entrar o reiniciar la app."""

    def setUp(self):
        super().setUp()
        db.init_db(seed=True)
        self.mod = _cargar_estado()
        self.uid = self.estudiante_id()
        self.correo = "sflores@uct.cl"

    def estado_nuevo(self):
        """Simula reabrir la app (estado en memoria vacío)."""
        e = self.mod.NotificacionesState()
        e.activar(self.uid, self.correo)
        return e

    def ids(self, estado):
        return {n["id"] for n in estado.filtrar_visibles(db.get_notificaciones(self.uid))}

    def test_ocultar_una_sobrevive_a_cerrar_sesion_y_volver_a_entrar(self):
        e = self.estado_nuevo()
        todas = [n["id"] for n in db.get_notificaciones(self.uid)]
        self.assertGreaterEqual(len(todas), 2)
        e.ocultar(todas[0])
        e.reiniciar()                       # cerrar sesión
        e.activar(self.uid, self.correo)    # volver a iniciar
        self.assertEqual(self.ids(e), set(todas) - {todas[0]})

    def test_limpiar_todas_sobrevive_a_reabrir_la_app(self):
        e = self.estado_nuevo()
        e.ocultar_todas([n["id"] for n in db.get_notificaciones(self.uid)])
        self.assertEqual(self.ids(self.estado_nuevo()), set())

    def test_no_se_borra_de_la_base(self):
        e = self.estado_nuevo()
        n0 = len(db.get_notificaciones(self.uid))
        e.ocultar_todas([n["id"] for n in db.get_notificaciones(self.uid)])
        self.assertEqual(len(db.get_notificaciones(self.uid)), n0)

    def test_notificacion_nueva_si_aparece(self):
        e = self.estado_nuevo()
        e.ocultar_todas([n["id"] for n in db.get_notificaciones(self.uid)])
        db.crear_notificacion(self.uid, "clase nueva", "nueva_grabacion")
        visibles = self.estado_nuevo().filtrar_visibles(db.get_notificaciones(self.uid))
        self.assertEqual([n["mensaje"] for n in visibles], ["clase nueva"])

    def test_cada_usuario_tiene_su_lista(self):
        prof = self.profesor()
        db.crear_notificacion(prof["id"], "para el profe", "nueva_grabacion")
        e = self.estado_nuevo()
        e.ocultar_todas([n["id"] for n in db.get_notificaciones(self.uid)])
        ep = self.mod.NotificacionesState()
        ep.activar(prof["id"], prof["correo"])
        self.assertEqual([n["mensaje"] for n in ep.filtrar_visibles(db.get_notificaciones(prof["id"]))],
                         ["para el profe"])
        self.assertEqual(self.ids(self.estado_nuevo()), set())   # el del estudiante sigue intacto

    def test_sigue_oculta_si_la_base_se_recrea(self):
        """Los ids cambian al restaurar desde el JSON; la clave no."""
        e = self.estado_nuevo()
        todas = db.get_notificaciones(self.uid)
        e.ocultar(todas[0]["id"])
        mensaje = todas[0]["mensaje"]
        self.borrar_base()
        db.init_db(seed=True)               # recrea y restaura desde los JSON
        self.uid = self.estudiante_id()
        visibles = self.estado_nuevo().filtrar_visibles(db.get_notificaciones(self.uid))
        self.assertNotIn(mensaje, [n["mensaje"] for n in visibles])
        self.assertGreater(len(visibles), 0)

    def test_sin_sesion_activa_no_hace_nada(self):
        e = self.mod.NotificacionesState()
        e.ocultar(1)                        # no lanza ni escribe
        self.assertEqual(storage.cargar_notificaciones_ocultas(self.correo), [])

    def test_archivo_corrupto_no_oculta_nada_ni_rompe(self):
        os.makedirs(storage.carpeta_datos(), exist_ok=True)
        with open(os.path.join(storage.carpeta_datos(), storage.ARCHIVO_NOTIFICACIONES_OCULTAS), "w") as f:
            f.write("{no es json")
        e = self.estado_nuevo()
        self.assertEqual(len(self.ids(e)), len(db.get_notificaciones(self.uid)))
        e.ocultar_todas([n["id"] for n in db.get_notificaciones(self.uid)])   # se recupera
        self.assertEqual(self.ids(self.estado_nuevo()), set())


if __name__ == "__main__":
    unittest.main()
