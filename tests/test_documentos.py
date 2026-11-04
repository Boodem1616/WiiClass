"""Pruebas de documentos.py (sin Kivy): python -m unittest discover -s tests -v

Las pruebas de Android usan un `jnius` simulado: validan el FLUJO (insertar con
IS_PENDING, copiar, publicar, reintento de MIME, limpieza ante errores), no que
las APIs reales de Android acepten esas llamadas. Eso solo se comprueba en un
dispositivo (ver DESCARGAS-DOCUMENTOS.md, sección "Verificación").
"""
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import documentos


class BaseTmp(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self.home = os.path.join(self.dir, "home")
        os.makedirs(os.path.join(self.home, ".config"))
        self.env = mock.patch.dict(os.environ, {"HOME": self.home, "USERPROFILE": self.home},
                                   clear=False)
        self.env.start()
        for k in ("WIICLASS_DOCUMENTOS_DIR", "XDG_CONFIG_HOME", "ANDROID_ARGUMENT",
                  "ANDROID_PRIVATE", "KIVY_BUILD"):
            os.environ.pop(k, None)
        self.origen = os.path.join(self.dir, "clase.mp3")
        with open(self.origen, "wb") as f:
            f.write(b"ID3-audio-falso")

    def tearDown(self):
        self.env.stop()
        self._tmp.cleanup()

    def plat(self, nombre):
        p = mock.patch.object(documentos, "plataforma", return_value=nombre)
        p.start()
        self.addCleanup(p.stop)

    def user_dirs(self, contenido):
        with open(os.path.join(self.home, ".config", "user-dirs.dirs"), "w", encoding="utf-8") as f:
            f.write(contenido)


class TestNombres(unittest.TestCase):
    def test_caracteres_invalidos_y_rutas(self):
        self.assertEqual(documentos.nombre_seguro("a/b\\c:d?.mp3"), "a_b_c_d_.mp3")
        self.assertEqual(documentos.nombre_seguro("Clase 1/2.mp3"), "Clase 1_2.mp3")
        malo = documentos.nombre_seguro("../../etc/passwd")
        self.assertNotIn("/", malo)
        self.assertFalse(malo.startswith("."))

    def test_vacio_y_reservados(self):
        self.assertEqual(documentos.nombre_seguro(""), "audio")
        self.assertEqual(documentos.nombre_seguro("  ..  "), "audio")
        self.assertEqual(documentos.nombre_seguro("CON.mp3"), "_CON.mp3")

    def test_largo_conserva_extension(self):
        n = documentos.nombre_seguro("x" * 500 + ".m4a")
        self.assertTrue(n.endswith(".m4a"))
        self.assertLessEqual(len(n), 120)

    def test_acentos_se_conservan(self):
        self.assertEqual(documentos.nombre_seguro("Física – Clase 1.mp3"), "Física – Clase 1.mp3")


class TestPlataforma(BaseTmp):
    def test_android_ios_y_escritorio(self):
        with mock.patch.dict(os.environ, {"ANDROID_ARGUMENT": "/x"}):
            self.assertEqual(documentos.plataforma(), "android")
        with mock.patch.dict(os.environ, {"KIVY_BUILD": "ios"}):
            self.assertEqual(documentos.plataforma(), "ios")
        with mock.patch.object(sys, "platform", "win32"):
            self.assertEqual(documentos.plataforma(), "windows")
        with mock.patch.object(sys, "platform", "darwin"):
            self.assertEqual(documentos.plataforma(), "macos")
        with mock.patch.object(sys, "platform", "linux"):
            self.assertEqual(documentos.plataforma(), "linux")


class TestCarpetaEscritorio(BaseTmp):
    def test_linux_xdg_en_espanol(self):
        # Caso real: en un sistema en español la carpeta es "Documentos".
        self.plat("linux")
        self.user_dirs('XDG_DESKTOP_DIR="$HOME/Escritorio"\nXDG_DOCUMENTS_DIR="$HOME/Documentos"\n')
        self.assertEqual(documentos.carpeta_documentos(), os.path.join(self.home, "Documentos"))

    def test_linux_xdg_ruta_absoluta_y_xdg_config_home(self):
        self.plat("linux")
        otro = os.path.join(self.dir, "cfg")
        os.makedirs(otro)
        with open(os.path.join(otro, "user-dirs.dirs"), "w") as f:
            f.write('XDG_DOCUMENTS_DIR="/mnt/datos/Docs"\n')
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": otro}):
            self.assertEqual(documentos.carpeta_documentos(), "/mnt/datos/Docs")

    def test_linux_xdg_desactivada_o_sin_archivo_cae_en_documents(self):
        self.plat("linux")
        self.assertEqual(documentos.carpeta_documentos(), os.path.join(self.home, "Documents"))
        self.user_dirs('XDG_DOCUMENTS_DIR="$HOME/"\n')  # XDG: "desactivada"
        self.assertEqual(documentos.carpeta_documentos(), os.path.join(self.home, "Documents"))

    def test_macos_e_ios(self):
        for p in ("macos", "ios"):
            with self.subTest(p):
                with mock.patch.object(documentos, "plataforma", return_value=p):
                    self.assertEqual(documentos.carpeta_documentos(),
                                     os.path.join(self.home, "Documents"))

    def test_windows_usa_api_y_tiene_respaldo(self):
        self.plat("windows")
        with mock.patch.object(documentos, "_windows_documentos", return_value=r"D:\Docs"):
            self.assertEqual(documentos.carpeta_documentos(), r"D:\Docs")
        with mock.patch.object(documentos, "_windows_documentos", side_effect=OSError):
            self.assertEqual(documentos.carpeta_documentos(), os.path.join(self.home, "Documents"))

    def test_variable_de_entorno_manda(self):
        self.plat("linux")
        destino = os.path.join(self.dir, "forzada")
        with mock.patch.dict(os.environ, {"WIICLASS_DOCUMENTOS_DIR": destino}):
            self.assertEqual(documentos.carpeta_documentos(), destino)


class TestGuardarEscritorio(BaseTmp):
    def test_copia_en_subcarpeta_y_crea_carpetas(self):
        self.plat("linux")
        ruta = documentos.guardar_en_documentos(self.origen, "Clase 1.mp3")
        self.assertEqual(ruta, os.path.join(self.home, "Documents", "WiiClass", "Clase 1.mp3"))
        with open(ruta, "rb") as f:
            self.assertEqual(f.read(), b"ID3-audio-falso")

    def test_ios_va_al_documents_del_sandbox(self):
        self.plat("ios")
        ruta = documentos.guardar_en_documentos(self.origen)
        self.assertTrue(ruta.startswith(os.path.join(self.home, "Documents", "WiiClass")))

    def test_no_pisa_archivos_existentes(self):
        self.plat("linux")
        a = documentos.guardar_en_documentos(self.origen, "x.mp3")
        b = documentos.guardar_en_documentos(self.origen, "x.mp3")
        c = documentos.guardar_en_documentos(self.origen, "x.mp3")
        self.assertEqual([os.path.basename(p) for p in (a, b, c)],
                         ["x.mp3", "x (1).mp3", "x (2).mp3"])

    def test_no_deja_archivos_part(self):
        self.plat("linux")
        ruta = documentos.guardar_en_documentos(self.origen)
        self.assertEqual([f for f in os.listdir(os.path.dirname(ruta)) if f.endswith(".part")], [])

    def test_nombre_malicioso_no_escapa_de_la_carpeta(self):
        self.plat("linux")
        ruta = documentos.guardar_en_documentos(self.origen, "../../../evil.mp3")
        self.assertEqual(os.path.dirname(ruta), os.path.join(self.home, "Documents", "WiiClass"))

    def test_origen_inexistente(self):
        self.plat("linux")
        with self.assertRaises(documentos.DocumentosError):
            documentos.guardar_en_documentos(os.path.join(self.dir, "nada.mp3"))

    def test_sin_permiso_da_error_legible(self):
        self.plat("linux")
        with mock.patch("shutil.copyfile", side_effect=PermissionError):
            with self.assertRaises(documentos.DocumentosError) as cm:
                documentos.guardar_en_documentos(self.origen)
        self.assertIn("permiso", str(cm.exception).lower())

    def test_permiso_no_aplica_fuera_de_android(self):
        self.plat("linux")
        self.assertFalse(documentos.necesita_permiso_escritura())
        llamadas = []
        documentos.pedir_permiso_escritura(llamadas.append)
        self.assertEqual(llamadas, [True])


# ---------------------------------------------------------------------------
# Android con jnius simulado (valida el flujo, no las APIs reales)
# ---------------------------------------------------------------------------
class _Valores:
    def __init__(self):
        self.d = {}

    def put(self, k, v):
        self.d[k] = v


class _Salida:
    def __init__(self, log):
        self.log, self.cerrada = log, False

    def flush(self):
        pass

    def close(self):
        self.cerrada = True


class _Resolver:
    def __init__(self, rechazar_mime_audio=False, fallar_copia=False):
        self.insertados, self.actualizados, self.borrados = [], [], []
        self.rechazar_mime_audio = rechazar_mime_audio
        self.salida = _Salida(self)

    def insert(self, coleccion, valores):
        if self.rechazar_mime_audio and valores.d["mime_type"].startswith("audio/"):
            raise RuntimeError("IllegalArgumentException: Primary directory Documents not allowed")
        self.insertados.append((coleccion, dict(valores.d)))
        return "content://media/external_primary/file/42"

    def openOutputStream(self, uri):
        return self.salida

    def update(self, uri, valores, a, b):
        self.actualizados.append((uri, dict(valores.d)))

    def delete(self, uri, a, b):
        self.borrados.append(uri)


def _jnius_falso(sdk, resolver, copiar_falla=False, docs_publica="/storage/emulated/0/Documents"):
    clases = {}

    class _Cls:
        def __init__(self, **attrs):
            self.__dict__.update(attrs)

    activity = _Cls(mActivity=_Cls(getContentResolver=lambda: resolver))
    clases["org.kivy.android.PythonActivity"] = activity
    clases["android.os.Build$VERSION"] = _Cls(SDK_INT=sdk)
    clases["android.os.Environment"] = _Cls(
        DIRECTORY_DOCUMENTS="Documents",
        getExternalStoragePublicDirectory=lambda d: _Cls(getAbsolutePath=lambda: docs_publica))
    clases["android.provider.MediaStore$Files"] = _Cls(getContentUri=lambda v: f"uri://{v}")
    clases["android.provider.MediaStore$MediaColumns"] = _Cls(
        DISPLAY_NAME="_display_name", MIME_TYPE="mime_type",
        RELATIVE_PATH="relative_path", IS_PENDING="is_pending")
    clases["android.content.ContentValues"] = _Valores
    clases["java.lang.Integer"] = int

    class _File:
        def __init__(self, ruta):
            self.ruta = ruta

        def toPath(self):
            return self.ruta

    class _Files:
        @staticmethod
        def copy(ruta, salida):
            if copiar_falla:
                raise OSError("disco lleno")
            with open(ruta, "rb") as f:
                salida.log.bytes_copiados = len(f.read())

    clases["java.io.File"] = _File
    clases["java.nio.file.Files"] = _Files

    mod = types.ModuleType("jnius")
    mod.autoclass = lambda nombre: clases[nombre]
    return mod


class TestAndroid(BaseTmp):
    def setUp(self):
        super().setUp()
        self.plat("android")

    def con_jnius(self, sdk, resolver, **kw):
        m = mock.patch.dict(sys.modules, {"jnius": _jnius_falso(sdk, resolver, **kw)})
        m.start()
        self.addCleanup(m.stop)

    def test_android10_mediastore_en_documents_con_pending(self):
        r = _Resolver()
        self.con_jnius(33, r)
        res = documentos.guardar_en_documentos(self.origen, "Clase 1.mp3")
        self.assertEqual(res, "Documents/WiiClass/Clase 1.mp3")
        _, v = r.insertados[0]
        self.assertEqual(v["relative_path"], "Documents/WiiClass")
        self.assertEqual(v["_display_name"], "Clase 1.mp3")
        self.assertEqual(v["is_pending"], 1)           # oculto mientras se escribe
        self.assertEqual(r.actualizados[0][1], {"is_pending": 0})  # publicado al final
        self.assertTrue(r.salida.cerrada)
        self.assertEqual(r.bytes_copiados, len(b"ID3-audio-falso"))
        self.assertEqual(r.borrados, [])

    def test_reintenta_como_generico_si_rechaza_mime_de_audio(self):
        r = _Resolver(rechazar_mime_audio=True)
        self.con_jnius(30, r)
        documentos.guardar_en_documentos(self.origen, "Clase 1.mp3")
        self.assertEqual(r.insertados[0][1]["mime_type"], "application/octet-stream")

    def test_si_falla_la_copia_se_borra_la_entrada(self):
        r = _Resolver()
        self.con_jnius(33, r, copiar_falla=True)
        with self.assertRaises(documentos.DocumentosError):
            documentos.guardar_en_documentos(self.origen, "x.mp3")
        self.assertEqual(r.borrados, ["content://media/external_primary/file/42"])

    def test_android10_no_pide_permiso(self):
        self.con_jnius(33, _Resolver())
        self.assertFalse(documentos.necesita_permiso_escritura())

    def _android_permissions(self, concedido):
        pkg = types.ModuleType("android")
        mod = types.ModuleType("android.permissions")
        mod.Permission = types.SimpleNamespace(WRITE_EXTERNAL_STORAGE="WES")
        mod.check_permission = lambda p: concedido
        self.pedidos = []
        mod.request_permissions = lambda perms, cb: (self.pedidos.append(perms), cb(perms, [True]))
        pkg.permissions = mod
        m = mock.patch.dict(sys.modules, {"android": pkg, "android.permissions": mod})
        m.start()
        self.addCleanup(m.stop)

    def test_android9_pide_permiso_y_escribe_en_carpeta_publica(self):
        docs = os.path.join(self.dir, "pub", "Documents")
        self.con_jnius(28, _Resolver(), docs_publica=docs)
        self._android_permissions(concedido=False)
        self.assertTrue(documentos.necesita_permiso_escritura())
        with self.assertRaises(documentos.PermisoDenegadoError):
            documentos.guardar_en_documentos(self.origen, "x.mp3")
        respuestas = []
        documentos.pedir_permiso_escritura(respuestas.append)
        self.assertEqual((self.pedidos, respuestas), ([["WES"]], [True]))

    def test_android9_con_permiso_copia_a_documents(self):
        docs = os.path.join(self.dir, "pub", "Documents")
        self.con_jnius(28, _Resolver(), docs_publica=docs)
        self._android_permissions(concedido=True)
        res = documentos.guardar_en_documentos(self.origen, "x.mp3")
        self.assertEqual(res, "Documents/WiiClass/x.mp3")
        self.assertTrue(os.path.isfile(os.path.join(docs, "WiiClass", "x.mp3")))


if __name__ == "__main__":
    unittest.main()
