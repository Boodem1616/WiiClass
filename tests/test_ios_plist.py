"""Prueba de scripts/ios_habilitar_archivos.py (sin Kivy)."""
import os
import plistlib
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "scripts"))

import ios_habilitar_archivos as ios


class TestPlistIos(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ruta = os.path.join(self._tmp.name, "wiiclass-Info.plist")

    def escribir(self, datos, fmt=plistlib.FMT_XML):
        with open(self.ruta, "wb") as f:
            plistlib.dump(datos, f, fmt=fmt)

    def leer(self):
        with open(self.ruta, "rb") as f:
            return plistlib.load(f)

    def test_agrega_claves_y_conserva_las_demas(self):
        self.escribir({"CFBundleName": "WiiClass", "UIFileSharingEnabled": False})
        self.assertEqual(ios.main(["x", self.ruta]), 0)
        d = self.leer()
        self.assertIs(d["UIFileSharingEnabled"], True)
        self.assertIs(d["LSSupportsOpeningDocumentsInPlace"], True)
        self.assertEqual(d["CFBundleName"], "WiiClass")

    def test_idempotente_y_acepta_plist_binario(self):
        self.escribir({"CFBundleName": "WiiClass"}, fmt=plistlib.FMT_BINARY)
        self.assertTrue(ios.habilitar(self.ruta))
        self.assertFalse(ios.habilitar(self.ruta))

    def test_archivo_inexistente_devuelve_error(self):
        self.assertEqual(ios.main(["x", os.path.join(self._tmp.name, "no.plist")]), 1)


if __name__ == "__main__":
    unittest.main()
