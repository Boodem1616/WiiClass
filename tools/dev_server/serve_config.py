"""
serve_config.py — Servidor local de la fuente remota (solo desarrollo).

    python3 tools/dev_server/serve_config.py        # http://0.0.0.0:8765
    python3 tools/dev_server/serve_config.py 9000   # otro puerto

Sirve `config/examples/` (ahí está app_config.json) y, además, el panel
`tools/dev_server/admin.html` en /admin.html.

La app lee http://127.0.0.1:8765/app_config.json por defecto. Desde un
emulador Android usa http://10.0.2.2:8765/app_config.json; desde un teléfono
real, la IP de tu PC en la red WiFi. Cambia la URL con la variable de entorno
WIICLASS_REMOTE_CONFIG_URL. Edita config/examples/app_config.json en caliente: el
servidor no cachea y envía ETag, así que verás el cambio al actualizar.
"""
import functools
import hashlib
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(os.path.dirname(AQUI))
CARPETA = os.path.join(RAIZ, "config", "examples")
# Rutas que se sirven desde fuera de CARPETA (el panel vive junto a este script).
ARCHIVOS_EXTRA = {"/admin.html": os.path.join(AQUI, "admin.html")}


class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        extra = ARCHIVOS_EXTRA.get(path.split("?")[0])
        return extra if extra else super().translate_path(path)

    def send_head(self):
        ruta = self.translate_path(self.path.split("?")[0])
        if os.path.isfile(ruta):
            with open(ruta, "rb") as f:
                etag = '"%s"' % hashlib.sha1(f.read()).hexdigest()[:16]
            if self.headers.get("If-None-Match") == etag:
                self.send_response(304)
                self.send_header("ETag", etag)
                self.end_headers()
                return None
            self._etag = etag
        return super().send_head()

    def end_headers(self):
        if getattr(self, "_etag", None):
            self.send_header("ETag", self._etag)
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


if __name__ == "__main__":
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    h = functools.partial(Handler, directory=CARPETA)
    print(f"Sirviendo {CARPETA} en http://0.0.0.0:{puerto}/app_config.json  (Ctrl+C para salir)")
    ThreadingHTTPServer(("0.0.0.0", puerto), h).serve_forever()
