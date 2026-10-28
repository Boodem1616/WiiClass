"""
servir_admin.py — Igual que servir_config.py, pero permite guardar desde el panel.

    python3 servir_admin.py            # http://0.0.0.0:8765
    python3 servir_admin.py 9000       # otro puerto

Panel:  http://127.0.0.1:8765/admin.html   (el archivo va en ./remote/)

No modifica servir_config.py: reutiliza su Handler (GET + ETag + no-cache)
y solo agrega PUT /app_config.json.
"""
import functools
import json
import os
import sys
from http.server import ThreadingHTTPServer

from servir_config import CARPETA, Handler as HandlerBase

RUTA_PERMITIDA = "/app_config.json"


class Handler(HandlerBase):
    def _responder(self, codigo, datos):
        cuerpo = json.dumps(datos).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_PUT(self):
        if self.path.split("?")[0] != RUTA_PERMITIDA:
            return self._responder(404, {"error": "Solo se puede escribir " + RUTA_PERMITIDA})

        largo = int(self.headers.get("Content-Length") or 0)
        cuerpo = self.rfile.read(largo)

        try:
            json.loads(cuerpo.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            return self._responder(400, {"error": "JSON inválido: %s" % e})

        destino = os.path.join(self.directory, "app_config.json")
        temporal = destino + ".tmp"
        with open(temporal, "wb") as f:
            f.write(cuerpo)
        os.replace(temporal, destino)  # atómico: la app nunca lee un JSON a medias

        print("app_config.json guardado (%d bytes)" % len(cuerpo))
        self._responder(200, {"ok": True})


if __name__ == "__main__":
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    h = functools.partial(Handler, directory=CARPETA)
    print(f"Sirviendo {CARPETA} en http://0.0.0.0:{puerto}/admin.html  (Ctrl+C para salir)")
    ThreadingHTTPServer(("0.0.0.0", puerto), h).serve_forever()
