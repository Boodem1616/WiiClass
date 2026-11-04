"""Pruebas del módulo de analíticas (sin Kivy): python -m unittest discover -s tests -v"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import analytics as A
import analizador as Z


class BaseAnalytics(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.archivo = os.path.join(self._tmp.name, "analytics.json")
        self._old = os.environ.get("WIICLASS_ANALYTICS_FILE")
        os.environ["WIICLASS_ANALYTICS_FILE"] = self.archivo
        self._retraso = A.RETRASO_VOLCADO
        A.RETRASO_VOLCADO = 0  # escritura inmediata
        A._eventos = None
        A.establecer_rol(None)

    def tearDown(self):
        A.RETRASO_VOLCADO = self._retraso
        A._eventos = None
        if self._old is None:
            os.environ.pop("WIICLASS_ANALYTICS_FILE", None)
        else:
            os.environ["WIICLASS_ANALYTICS_FILE"] = self._old
        self._tmp.cleanup()

    def disco(self):
        with open(self.archivo, encoding="utf-8") as f:
            return json.load(f)


class TestRegistrar(BaseAnalytics):
    def test_estructura_y_archivo(self):
        A.registrar("pantalla_vista", {"nombre": "login"})
        d = self.disco()
        self.assertEqual(len(d), 1)
        self.assertEqual(d[0]["evento"], "pantalla_vista")
        self.assertIsInstance(d[0]["ts"], float)
        self.assertEqual(d[0]["datos"], {"nombre": "login"})

    def test_datos_por_defecto_y_no_serializable(self):
        A.registrar("a")
        A.registrar("b", {"obj": object()})
        d = self.disco()
        self.assertEqual(d[0]["datos"], {})
        self.assertIsInstance(d[1]["datos"]["obj"], str)

    def test_nombre_invalido_no_lanza(self):
        self.assertIsNone(A.registrar(""))
        self.assertIsNone(A.registrar(None))
        self.assertFalse(os.path.exists(self.archivo))

    def test_rol_y_sesion(self):
        A.establecer_rol("Profesor")
        e = A.registrar("x")
        self.assertEqual(e["rol"], "Profesor")
        self.assertEqual(e["sesion"], A.sesion_id())
        A.establecer_rol(None)
        self.assertNotIn("rol", A.registrar("y"))

    def test_acumula_sobre_historial_existente(self):
        A.registrar("a")
        A._eventos = None  # simula reabrir la app
        A.registrar("b")
        self.assertEqual([e["evento"] for e in self.disco()], ["a", "b"])

    def test_json_corrupto_se_aparta(self):
        with open(self.archivo, "w") as f:
            f.write("{no es json")
        A.registrar("a")
        self.assertEqual(len(self.disco()), 1)
        self.assertTrue(os.path.exists(self.archivo + ".corrupto"))

    def test_limite_de_eventos(self):
        viejo = A.MAX_EVENTOS
        A.MAX_EVENTOS = 5
        try:
            for i in range(8):
                A.registrar("e", {"i": i})
        finally:
            A.MAX_EVENTOS = viejo
        d = self.disco()
        self.assertEqual([e["datos"]["i"] for e in d], [3, 4, 5, 6, 7])

    def test_volcado_diferido(self):
        A.RETRASO_VOLCADO = 30
        A.registrar("a")
        self.assertFalse(os.path.exists(self.archivo))
        self.assertEqual(len(A.cargar()), 1)  # visible en memoria
        A.vaciar()
        self.assertEqual(len(self.disco()), 1)

    def test_borrar(self):
        A.registrar("a")
        A.borrar()
        self.assertEqual(A.cargar(), [])
        self.assertFalse(os.path.exists(self.archivo))


def ev(_evento, ts, sesion="s1", **datos):
    return {"evento": _evento, "ts": ts, "sesion": sesion, "datos": datos}


class TestAnalizador(BaseAnalytics):
    def test_total_pantallas(self):
        evs = [ev("pantalla_vista", 1, nombre="login"), ev("login_exitoso", 2),
               ev("pantalla_vista", 3, nombre="home_tab"), ev("pantalla_vista", 4, nombre="home_tab")]
        self.assertEqual(Z.total_pantallas_visitadas(evs), 3)
        self.assertEqual(Z.pantallas_mas_visitadas(evs)[0], ("home_tab", 2))
        self.assertEqual(Z.contar_eventos(evs)["login_exitoso"], 1)
        self.assertEqual(Z.total_pantallas_visitadas([]), 0)

    def test_sesiones(self):
        evs = [ev("a", 100, "s1"), ev("b", 160, "s1"), ev("a", 200, "s2"), ev("b", 320, "s2")]
        r = Z.resumen_sesiones(evs)
        self.assertEqual(r["sesiones"], 2)
        self.assertAlmostEqual(r["duracion_promedio_seg"], 90)

    def test_kpis(self):
        evs = [ev("login_exitoso", 1), ev("login_error", 2), ev("login_error", 3), ev("login_error", 4),
               ev("clase_abierta", 5, grabacion_id=1), ev("clase_abierta", 6, grabacion_id=2),
               ev("reproduccion_play", 7, grabacion_id=1),
               ev("descarga_completa", 8), ev("descarga_error", 9)]
        k = Z.kpis(evs)
        self.assertAlmostEqual(k["tasa_login_exitoso"], 0.25)
        self.assertAlmostEqual(k["tasa_clases_reproducidas"], 0.5)
        self.assertAlmostEqual(k["tasa_descarga_exitosa"], 0.5)
        self.assertIsNone(Z.kpis([])["tasa_login_exitoso"])

    def test_embudo_en_orden(self):
        evs = [
            ev("login_exitoso", 1, "a"), ev("categoria_abierta", 2, "a"), ev("clase_abierta", 3, "a"),
            ev("reproduccion_play", 4, "a"),
            ev("sesion_restaurada", 1, "b"), ev("categoria_abierta", 2, "b"),
            ev("categoria_abierta", 1, "c"),  # sin login previo: no cuenta
            ev("clase_abierta", 1, "d"), ev("login_exitoso", 2, "d"),  # fuera de orden
        ]
        f = Z.embudo(evs)
        self.assertEqual([x["sesiones"] for x in f], [3, 2, 1, 1])
        self.assertAlmostEqual(f[1]["vs_anterior"], 2 / 3)

    def test_reporte(self):
        self.assertIn("No hay eventos", Z.reporte([]))
        A.registrar("pantalla_vista", {"nombre": "login"})
        A.registrar("login_exitoso")
        txt = Z.reporte(Z.cargar_eventos())
        self.assertIn("Total de pantallas visitadas: 1", txt)
        self.assertIn("Embudo", txt)
        self.assertIn("Total de pantallas visitadas", Z.reporte(Z.cargar_eventos(self.archivo)))


if __name__ == "__main__":
    unittest.main()
