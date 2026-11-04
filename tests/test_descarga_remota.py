"""Pruebas de descarga remota + guardado en Documentos (sin Kivy).

Levantan un servidor HTTP local real: python -m unittest discover -s tests -v
"""
import http.server
import os
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
import documentos
import downloads_manager as dm

AUDIO = (b"ID3" + bytes(range(256))) * 1200          # ~307 KB


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _enviar(self, codigo, cuerpo, tipo, extra=None, largo=None):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo) if largo is None else largo))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        ruta = self.path.split("?")[0]
        if ruta == "/clase%201.mp3":
            self._enviar(200, AUDIO, "audio/mpeg")
        elif ruta == "/descarga":
            self._enviar(200, AUDIO, "application/octet-stream",
                         {"Content-Disposition": 'attachment; filename="Física 1.m4a"'})
        elif ruta == "/sin-nombre":
            self._enviar(200, AUDIO, "audio/mpeg")
        elif ruta == "/pagina.html":
            self._enviar(200, b"<html>login</html>", "text/html")
        elif ruta == "/cortado.mp3":
            # Anuncia más bytes de los que envía y cierra la conexión.
            self._enviar(200, AUDIO[:1000], "audio/mpeg", largo=len(AUDIO))
        elif ruta == "/vacio.mp3":
            self._enviar(200, b"", "audio/mpeg")
        else:
            self._enviar(404, b"no", "text/plain")


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)


class TestDescargarUrl(Base):
    def test_descarga_completa_con_progreso(self):
        prog = []
        ruta = dm.descargar_url(self.base + "/clase%201.mp3", self.dir, "7_",
                                on_progreso=lambda h, t: prog.append((h, t)))
        self.assertEqual(os.path.basename(ruta), "7_clase 1.mp3")
        with open(ruta, "rb") as f:
            self.assertEqual(f.read(), AUDIO)
        self.assertEqual(prog[-1], (len(AUDIO), len(AUDIO)))
        self.assertEqual([h for h, _ in prog], sorted(h for h, _ in prog))   # monótono
        self.assertEqual([f for f in os.listdir(self.dir) if f.endswith(".part")], [])

    def test_nombre_desde_content_disposition(self):
        ruta = dm.descargar_url(self.base + "/descarga", self.dir)
        self.assertEqual(os.path.basename(ruta), "Física 1.m4a")

    def test_sin_extension_la_deduce_del_tipo(self):
        ruta = dm.descargar_url(self.base + "/sin-nombre", self.dir)
        self.assertTrue(ruta.endswith(".mp3") or os.path.splitext(ruta)[1] in (".mpga", ".mp2", ".mp3"))

    def test_rechaza_html(self):
        with self.assertRaises(dm.DescargaError) as cm:
            dm.descargar_url(self.base + "/pagina.html", self.dir)
        self.assertIn("audio", str(cm.exception))
        self.assertEqual(os.listdir(self.dir), [])

    def test_404(self):
        with self.assertRaises(dm.DescargaError) as cm:
            dm.descargar_url(self.base + "/no-existe.mp3", self.dir)
        self.assertIn("404", str(cm.exception))

    def test_descarga_cortada_no_deja_archivo(self):
        with self.assertRaises(dm.DescargaError):
            dm.descargar_url(self.base + "/cortado.mp3", self.dir)
        self.assertEqual(os.listdir(self.dir), [])

    def test_archivo_vacio(self):
        with self.assertRaises(dm.DescargaError):
            dm.descargar_url(self.base + "/vacio.mp3", self.dir)

    def test_tope_de_tamano(self):
        with mock.patch.object(dm, "MAX_BYTES", 1000):
            with self.assertRaises(dm.DescargaError) as cm:
                dm.descargar_url(self.base + "/clase%201.mp3", self.dir)
        self.assertIn("grande", str(cm.exception))
        self.assertEqual(os.listdir(self.dir), [])

    def test_solo_http_y_https(self):
        for url in ("file:///etc/passwd", "ftp://x/a.mp3", "/ruta/local.mp3", ""):
            with self.subTest(url):
                with self.assertRaises(dm.DescargaError):
                    dm.descargar_url(url, self.dir)

    def test_servidor_caido(self):
        with self.assertRaises(dm.DescargaError):
            dm.descargar_url("http://127.0.0.1:1/a.mp3", self.dir)

    def test_es_url_remota(self):
        self.assertTrue(dm.es_url_remota("https://x/a.mp3"))
        self.assertFalse(dm.es_url_remota("C:\\audios\\a.mp3"))
        self.assertFalse(dm.es_url_remota("assets/audio/a.mp3"))


class TestFlujoCompleto(Base):
    """descargar_grabacion de punta a punta con BD temporal."""

    def setUp(self):
        super().setUp()
        self._old_db, db.DB_PATH = db.DB_PATH, os.path.join(self.dir, "t.db")
        self.addCleanup(setattr, db, "DB_PATH", self._old_db)
        env = mock.patch.dict(os.environ, {
            "WIICLASS_DATA_DIR": os.path.join(self.dir, "datos"),
            "WIICLASS_DOCUMENTOS_DIR": os.path.join(self.dir, "Documentos"),
        })
        env.start()
        self.addCleanup(env.stop)
        p = mock.patch.object(dm, "CARPETA_DESCARGAS", os.path.join(self.dir, "descargas"))
        p.start()
        self.addCleanup(p.stop)
        p2 = mock.patch.object(documentos, "plataforma", return_value="linux")
        p2.start()
        self.addCleanup(p2.stop)
        db.init_db()
        conn = db.get_connection()
        self.uid = conn.execute("SELECT id FROM Usuarios LIMIT 1").fetchone()["id"]
        self.cat = conn.execute("SELECT id FROM Categorias LIMIT 1").fetchone()["id"]
        conn.close()

    def grabacion(self, url, nombre="Clase remota"):
        conn = db.get_connection()
        cur = conn.execute(
            "INSERT INTO Grabaciones (categoria_id, nombre, url_audio, fecha_subida, duracion_seg)"
            " VALUES (?, ?, ?, datetime('now'), 60)", (self.cat, nombre, url))
        conn.commit()
        gid = cur.lastrowid
        conn.close()
        return gid

    def ejecutar(self, gid, **kw):
        ev, r = threading.Event(), {"avisos": [], "progreso": []}
        r["completa"] = r["error"] = None

        def ok(g):
            r["completa"] = g
            ev.set()

        def mal(g, e):
            r["error"] = e
            ev.set()

        dm.descargar_grabacion(self.uid, gid, on_completa=ok, on_error=mal,
                               on_progreso=lambda g, h, t: r["progreso"].append((h, t)),
                               on_aviso=lambda g, t: r["avisos"].append(t), **kw)
        self.assertTrue(ev.wait(10), "la descarga no terminó")
        return r

    def test_url_remota_queda_en_app_y_en_documentos(self):
        gid = self.grabacion(self.base + "/clase%201.mp3", "Clase: Mitosis/1")
        r = self.ejecutar(gid)
        self.assertEqual(r["completa"], gid)
        self.assertIsNone(r["error"])

        privada = db.get_ruta_local(gid)                       # copia para reproducir offline
        self.assertTrue(privada.startswith(os.path.join(self.dir, "descargas")))
        self.assertTrue(os.path.isfile(privada))

        pub = os.path.join(self.dir, "Documentos", "WiiClass", "Clase_ Mitosis_1.mp3")
        with open(pub, "rb") as f:                              # copia visible al usuario
            self.assertEqual(f.read(), AUDIO)
        self.assertEqual(r["progreso"][-1], (len(AUDIO), len(AUDIO)))
        self.assertTrue(any("Guardado en" in a for a in r["avisos"]))
        self.assertTrue(db.esta_descargada(gid))

    def test_error_de_red_no_registra_la_descarga(self):
        gid = self.grabacion(self.base + "/no-existe.mp3")
        r = self.ejecutar(gid)
        self.assertIsInstance(r["error"], dm.DescargaError)
        self.assertFalse(db.esta_descargada(gid))
        self.assertFalse(os.path.exists(os.path.join(self.dir, "Documentos")))

    def test_fallo_en_documentos_no_rompe_la_descarga(self):
        gid = self.grabacion(self.base + "/clase%201.mp3")
        with mock.patch.object(documentos, "guardar_en_documentos",
                               side_effect=documentos.DocumentosError("Disco lleno.")):
            r = self.ejecutar(gid)
        self.assertEqual(r["completa"], gid)                    # sigue disponible offline
        self.assertTrue(db.esta_descargada(gid))
        self.assertTrue(any("No se pudo guardar en Documentos" in a for a in r["avisos"]))

    def test_permiso_denegado_da_aviso_claro(self):
        gid = self.grabacion(self.base + "/clase%201.mp3")
        with mock.patch.object(documentos, "guardar_en_documentos",
                               side_effect=documentos.PermisoDenegadoError("x")):
            r = self.ejecutar(gid)
        self.assertTrue(any("Sin permiso" in a for a in r["avisos"]))
        self.assertTrue(db.esta_descargada(gid))

    def test_desactivar_documentos(self):
        gid = self.grabacion(self.base + "/clase%201.mp3")
        with mock.patch.object(dm, "GUARDAR_EN_DOCUMENTOS", False):
            r = self.ejecutar(gid)
        self.assertEqual(r["completa"], gid)
        self.assertFalse(os.path.exists(os.path.join(self.dir, "Documentos")))

    def test_audio_local_de_ejemplo_sigue_funcionando(self):
        ejemplo = os.path.join(self.dir, "ejemplo.mp3")
        with open(ejemplo, "wb") as f:
            f.write(b"local")
        gid = self.grabacion(ejemplo, "Ejemplo")
        r = self.ejecutar(gid)
        self.assertEqual(r["completa"], gid)
        self.assertEqual(r["progreso"], [])                    # sin red, sin progreso
        self.assertTrue(os.path.isfile(os.path.join(self.dir, "Documentos", "WiiClass", "Ejemplo.mp3")))

    def test_descargar_varias_continua_tras_un_error(self):
        malo = self.grabacion(self.base + "/no-existe.mp3", "Malo")
        bueno = self.grabacion(self.base + "/clase%201.mp3", "Bueno")
        ev, hechas, fallas = threading.Event(), [], []
        dm.descargar_varias(self.uid, [malo, bueno], on_cada_una=hechas.append,
                            on_error=lambda g, e: fallas.append(g), on_todas_completas=ev.set)
        self.assertTrue(ev.wait(10))
        self.assertEqual((hechas, fallas), ([bueno], [malo]))


if __name__ == "__main__":
    unittest.main()
