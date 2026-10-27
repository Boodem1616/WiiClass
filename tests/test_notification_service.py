"""Pruebas de NotificationService (sin Kivy, sin ventana): python -m unittest discover -s tests -v"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import notification_service as ns
from notification_service import NotificationService


class FakeBackend(ns._Backend):
    def __init__(self, permiso=True, respuesta=True):
        self.permiso, self.respuesta = permiso, respuesta
        self.mostradas, self.pedidos = [], 0

    def tiene_permiso(self):
        return self.permiso

    def pedir_permiso(self, callback):
        self.pedidos += 1
        if self.respuesta:
            self.permiso = True
        callback(self.respuesta)

    def mostrar(self, notif_id, titulo, mensaje):
        self.mostradas.append(mensaje)


class Reloj:
    t = 0.0
    def __call__(self):
        return self.t


def servicio(**kw):
    b = FakeBackend(**kw)
    return NotificationService(backend=b, reloj=Reloj()), b


class Textos(unittest.TestCase):
    def test_login(self):
        self.assertEqual(ns.texto_bienvenida("Sofía"), "Bienvenido Sofía")
        self.assertEqual(ns.texto_bienvenida(None), "Bienvenido")
        self.assertEqual(ns.texto_bienvenida("   "), "Bienvenido")

    def test_logout(self):
        self.assertEqual(ns.texto_cierre_sesion(), "Se ha cerrado sesion!")

    def test_grabacion(self):
        self.assertEqual(ns.texto_grabacion_completa("Matrices", "Álgebra", "Semana 3"),
                         "Grabacion Matrices completa en Álgebra de la Semana 3")
        self.assertEqual(ns.texto_grabacion_completa(None, "", " "),
                         "Grabacion sin titulo completa en su materia de la semana")

    def test_descarga(self):
        self.assertEqual(ns.texto_descarga_completa("Límites"), "Se ha descargado Límites correctamente!")
        self.assertEqual(ns.texto_descarga_completa(None), "Se ha descargado la clase correctamente!")


class Escenarios(unittest.TestCase):
    def test_1_login(self):
        s, b = servicio()
        self.assertTrue(s.show_login_welcome("Sofía Flores", usuario_id=1))
        self.assertEqual(b.mostradas, ["Bienvenido Sofía Flores"])

    def test_2_logout(self):
        s, b = servicio()
        self.assertTrue(s.show_logout_confirmation())
        self.assertEqual(b.mostradas, ["Se ha cerrado sesion!"])

    def test_3_grabacion(self):
        s, b = servicio()
        self.assertTrue(s.show_recording_complete("Intro", "Física", "Semana 2", evento_id=9))
        self.assertEqual(b.mostradas, ["Grabacion Intro completa en Física de la Semana 2"])

    def test_4_descarga(self):
        s, b = servicio()
        self.assertTrue(s.show_download_complete("Clase 1", evento_id=4))
        self.assertEqual(b.mostradas, ["Se ha descargado Clase 1 correctamente!"])


class Duplicados(unittest.TestCase):
    def test_mismo_evento_en_ventana(self):
        s, b = servicio()
        self.assertTrue(s.show_logout_confirmation())
        self.assertFalse(s.show_logout_confirmation())  # doble toque
        self.assertEqual(len(b.mostradas), 1)

    def test_pasada_la_ventana_vuelve_a_notificar(self):
        s, b = servicio()
        s.show_logout_confirmation()
        s._reloj.t = ns.VENTANA_DEDUPE_SEG + 1
        self.assertTrue(s.show_logout_confirmation())
        self.assertEqual(len(b.mostradas), 2)

    def test_descargas_distintas_conviven(self):
        s, b = servicio()
        s.show_download_complete("A", evento_id=1)
        s.show_download_complete("B", evento_id=2)
        self.assertEqual(len(b.mostradas), 2)


class Permisos(unittest.TestCase):
    def test_sin_permiso_se_pide_y_se_muestra_al_conceder(self):
        s, b = servicio(permiso=False, respuesta=True)
        # Fuera de Kivy el callback se ejecuta directo (ver _en_hilo_principal).
        self.assertTrue(s.show_login_welcome("Ana", usuario_id=1))
        self.assertEqual(b.pedidos, 1)
        self.assertEqual(b.mostradas, ["Bienvenido Ana"])

    def test_permiso_denegado_no_rompe_ni_insiste(self):
        s, b = servicio(permiso=False, respuesta=False)
        s.show_login_welcome("Ana", usuario_id=1)
        self.assertFalse(s.show_logout_confirmation())
        self.assertEqual(b.mostradas, [])
        self.assertEqual(b.pedidos, 1)  # no vuelve a pedir

    def test_permiso_concedido_luego_desde_ajustes(self):
        s, b = servicio(permiso=False, respuesta=False)
        s.show_login_welcome("Ana", usuario_id=1)
        b.permiso = True
        self.assertTrue(s.show_logout_confirmation())
        self.assertEqual(b.mostradas, ["Se ha cerrado sesion!"])


class Errores(unittest.TestCase):
    def test_backend_que_falla_no_lanza(self):
        class Roto(FakeBackend):
            def mostrar(self, *a):
                raise RuntimeError("boom")
        s = NotificationService(backend=Roto(), reloj=Reloj())
        with self.assertLogs("wiiclass.notifications", level="ERROR"):
            self.assertFalse(s.show_download_complete("X", evento_id=1))


if __name__ == "__main__":
    unittest.main()
