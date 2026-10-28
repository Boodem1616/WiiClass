"""Pruebas de remote_config (sin Kivy): python -m unittest discover -s tests -v"""
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import remote_config as rc
from remote_config import DEFAULTS, RemoteConfig, normalizar


def fuente(texto, etag=None):
    def _d(url, et):
        if etag is not None and et == etag:
            raise rc._SinCambios()
        if isinstance(texto, Exception):
            raise texto
        return texto, etag
    return _d


class Normalizar(unittest.TestCase):
    def test_vacio_da_defaults(self):
        cfg, avisos = normalizar({})
        self.assertEqual(cfg, DEFAULTS)
        self.assertEqual(avisos, [])

    def test_no_dict(self):
        for malo in (None, [], "x", 3):
            cfg, avisos = normalizar(malo)
            self.assertEqual(cfg, DEFAULTS)
            self.assertTrue(avisos)

    def test_valores_validos(self):
        cfg, _ = normalizar({
            "version": 7, "intervalo_actualizacion_seg": 120,
            "anuncio": {"activo": True, "tipo": "aviso", "titulo": "Hola", "mensaje": "m"},
            "funciones": {"descargas": False},
            "reproductor": {"velocidades": [2, 0.5, 1.25]},
            "textos": {"saludo": " Hola equipo "},
        })
        self.assertEqual(cfg["version"], 7)
        self.assertEqual(cfg["intervalo_actualizacion_seg"], 120)
        self.assertEqual(cfg["anuncio"]["tipo"], "aviso")
        self.assertFalse(cfg["funciones"]["descargas"])
        self.assertTrue(cfg["funciones"]["grabacion"])          # no enviado -> default
        self.assertEqual(cfg["reproductor"]["velocidades"], [0.5, 1.0, 1.25, 2.0])  # 1.0 agregado
        self.assertEqual(cfg["textos"]["saludo"], "Hola equipo")

    def test_invalidos_caen_al_default_sin_afectar_al_resto(self):
        cfg, avisos = normalizar({
            "intervalo_actualizacion_seg": 1,
            "funciones": {"descargas": "no", "grabacion": False},
            "anuncio": {"activo": True, "tipo": "rojo", "mensaje": "ok"},
            "reproductor": {"velocidades": [9, "x"]},
        })
        self.assertEqual(cfg["intervalo_actualizacion_seg"], 300)
        self.assertTrue(cfg["funciones"]["descargas"])
        self.assertFalse(cfg["funciones"]["grabacion"])          # este sí se aplica
        self.assertEqual(cfg["anuncio"]["tipo"], "info")
        self.assertTrue(cfg["anuncio"]["activo"])
        self.assertEqual(cfg["reproductor"]["velocidades"], [0.5, 1.0, 1.5, 2.0])
        self.assertGreaterEqual(len(avisos), 4)

    def test_anuncio_vacio_se_oculta(self):
        cfg, avisos = normalizar({"anuncio": {"activo": True}})
        self.assertFalse(cfg["anuncio"]["activo"])
        self.assertTrue(avisos)

    def test_texto_largo_se_recorta_y_claves_desconocidas_se_ignoran(self):
        cfg, _ = normalizar({"anuncio": {"activo": True, "mensaje": "x" * 999}, "hackeo": 1})
        self.assertEqual(len(cfg["anuncio"]["mensaje"]), 280)
        self.assertNotIn("hackeo", cfg)

    def test_bool_no_cuenta_como_numero(self):
        cfg, _ = normalizar({"version": True, "intervalo_actualizacion_seg": True,
                             "reproductor": {"velocidades": [True]}})
        self.assertEqual(cfg["version"], 0)
        self.assertEqual(cfg["intervalo_actualizacion_seg"], 300)


class Servicio(unittest.TestCase):
    def nuevo(self, texto, etag=None, cache=None):
        guardado = {}
        r = RemoteConfig(url="http://x/c.json", descargar=fuente(texto, etag),
                         cargar_cache=lambda: cache,
                         guardar_cache=lambda d: guardado.update(d))
        return r, guardado

    def test_arranca_con_defaults(self):
        r, _ = self.nuevo("{}")
        self.assertEqual(r.valores, DEFAULTS)
        self.assertEqual(r.estado["origen"], "predeterminada")

    def test_actualiza_y_guarda_cache(self):
        r, guardado = self.nuevo(json.dumps({"version": 2, "funciones": {"descargas": False}}), etag='"a"')
        self.assertTrue(r.actualizar_sync())
        self.assertFalse(r.funcion_activa("descargas"))
        self.assertEqual(r.estado["origen"], "remota")
        self.assertEqual(r.get("version"), 2)
        self.assertEqual(guardado["etag"], '"a"')
        self.assertEqual(guardado["config"]["version"], 2)

    def test_misma_config_no_es_cambio(self):
        r, _ = self.nuevo(json.dumps({"version": 2}))
        self.assertTrue(r.actualizar_sync())
        self.assertFalse(r.actualizar_sync())

    def test_304_conserva_valores(self):
        r, _ = self.nuevo(json.dumps({"version": 5}), etag='"e"')
        r.actualizar_sync()
        self.assertFalse(r.actualizar_sync())   # segunda vez: 304
        self.assertEqual(r.get("version"), 5)
        self.assertIsNone(r.estado["error"])

    def test_red_caida_conserva_ultima_buena(self):
        r, _ = self.nuevo(json.dumps({"version": 3}))
        r.actualizar_sync()
        r._descargar = fuente(OSError("sin red"))
        self.assertFalse(r.actualizar_sync())
        self.assertEqual(r.get("version"), 3)
        self.assertIn("sin red", r.estado["error"])
        self.assertEqual(r.estado["origen"], "remota")

    def test_json_invalido_y_raiz_no_objeto(self):
        for texto in ("{no", "[1,2]", ""):
            r, _ = self.nuevo(texto)
            self.assertFalse(r.actualizar_sync())
            self.assertEqual(r.valores, DEFAULTS)
            self.assertIn("JSON inválido", r.estado["error"])

    def test_cache_se_usa_al_arrancar(self):
        cache = {"config": {"version": 9, "funciones": {"grabacion": False}},
                 "etag": '"z"', "recibido": "2026-10-27T10:00:00"}
        r, _ = self.nuevo("{}", cache=cache)
        self.assertEqual(r.estado["origen"], "cache")
        self.assertEqual(r.get("version"), 9)
        self.assertFalse(r.funcion_activa("grabacion"))
        self.assertEqual(r.estado["ultima_actualizacion"], "2026-10-27T10:00:00")

    def test_cache_corrupta_no_rompe(self):
        r, _ = self.nuevo("{}", cache={"config": "basura"})
        self.assertEqual(r.valores, DEFAULTS)

    def test_cache_que_falla_al_guardar_no_rompe(self):
        r = RemoteConfig(url="http://x", descargar=fuente('{"version":1}'),
                         guardar_cache=lambda d: (_ for _ in ()).throw(OSError("disco lleno")))
        self.assertTrue(r.actualizar_sync())

    def test_get_ruta_y_copia_defensiva(self):
        r, _ = self.nuevo("{}")
        self.assertEqual(r.get("reproductor.velocidades"), [0.5, 1.0, 1.5, 2.0])
        self.assertEqual(r.get("no.existe", "x"), "x")
        r.valores["funciones"]["descargas"] = False   # modificar la copia no afecta
        self.assertTrue(r.funcion_activa("descargas"))

    def test_suscriptores_y_actualizar_en_hilo(self):
        r, _ = self.nuevo(json.dumps({"version": 4}))
        hecho, cambios = threading.Event(), []
        r.suscribir(lambda c: (cambios.append(c), hecho.set()))
        self.assertTrue(r.actualizar())
        self.assertTrue(hecho.wait(3))
        self.assertEqual(cambios, [True])
        self.assertFalse(r.actualizando)

    def test_suscriptor_que_falla_no_impide_a_los_demas(self):
        r, _ = self.nuevo("{}")
        vistos = []
        r.suscribir(lambda c: 1 / 0)
        r.suscribir(lambda c: vistos.append(c))
        r._avisar(True)
        self.assertEqual(vistos, [True])


class InterruptorNotificaciones(unittest.TestCase):
    def test_desactivadas_remotamente_no_se_envian(self):
        from notification_service import NotificationService, _Backend

        class B(_Backend):
            enviados = []
            def mostrar(self, i, t, m): self.enviados.append(m)

        activo = [True]
        s = NotificationService(backend=B(), habilitado=lambda: activo[0])
        self.assertTrue(s.show_logout_confirmation())
        activo[0] = False
        self.assertFalse(s.show_login_welcome("Ana"))
        self.assertEqual(B.enviados, ["Se ha cerrado sesion!"])


class CachePersistente(unittest.TestCase):
    """La config recibida sobrevive a un reinicio y se usa sin red."""

    def test_reinicio_sin_red_usa_cache_de_disco(self):
        import storage
        with tempfile.TemporaryDirectory() as d:
            os.environ["WIICLASS_DATA_DIR"] = d
            try:
                a = RemoteConfig(url="http://x", cargar_cache=storage.cargar_config_remota,
                                 guardar_cache=storage.guardar_config_remota,
                                 descargar=fuente(json.dumps({"version": 9, "funciones": {"descargas": False}})))
                self.assertTrue(a.actualizar_sync())
                b = RemoteConfig(url="http://x", cargar_cache=storage.cargar_config_remota,
                                 guardar_cache=storage.guardar_config_remota,
                                 descargar=fuente(OSError("sin red")))
                self.assertEqual(b.estado["origen"], "cache")
                self.assertFalse(b.funcion_activa("descargas"))
                self.assertFalse(b.actualizar_sync())
                self.assertFalse(b.funcion_activa("descargas"))   # se mantiene la última buena
                self.assertIn("sin red", b.estado["error"])
            finally:
                os.environ.pop("WIICLASS_DATA_DIR", None)


class RedReal(unittest.TestCase):
    """Servidor HTTP real en localhost + esquema file://."""

    def test_http_etag_y_limite(self):
        import servir_config
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "c.json"), "w") as f:
                json.dump({"version": 11, "anuncio": {"activo": True, "mensaje": "hola"}}, f)
            with open(os.path.join(d, "grande.json"), "w") as f:
                f.write(" " * (rc.MAX_BYTES + 10))
            import functools
            srv = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(servir_config.Handler, directory=d))
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            try:
                base = f"http://127.0.0.1:{srv.server_port}"
                r = RemoteConfig(url=base + "/c.json")
                self.assertTrue(r.actualizar_sync())
                self.assertEqual(r.get("version"), 11)
                self.assertTrue(r.get("anuncio.activo"))
                self.assertIsNotNone(r._etag)
                self.assertFalse(r.actualizar_sync())          # 304
                self.assertIsNone(r.estado["error"])
                g = RemoteConfig(url=base + "/grande.json")
                self.assertFalse(g.actualizar_sync())
                self.assertIn("mayor", g.estado["error"])
                n = RemoteConfig(url=base + "/no-existe.json")
                self.assertFalse(n.actualizar_sync())
                self.assertIn("404", n.estado["error"])
            finally:
                srv.shutdown()

    def test_file_y_esquema_prohibido(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"version": 3}, f)
        try:
            r = RemoteConfig(url="file://" + f.name)
            self.assertTrue(r.actualizar_sync())
            self.assertEqual(r.get("version"), 3)
        finally:
            os.remove(f.name)
        x = RemoteConfig(url="ftp://host/c.json")
        self.assertFalse(x.actualizar_sync())
        self.assertIn("esquema", x.estado["error"])


if __name__ == "__main__":
    unittest.main()
