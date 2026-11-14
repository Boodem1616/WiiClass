"""main.py — Punto de entrada de WiiClass (escritorio y Buildozer/Android).

Toda la lógica vive en el paquete `wiiclass/`; ver `wiiclass/app.py`.

    python3 main.py
"""
from wiiclass.app import WiiClassApp

if __name__ == "__main__":
    WiiClassApp().run()
