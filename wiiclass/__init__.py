"""WiiClass — app de grabaciones de clases (Kivy + KivyMD + SQLite).

`RAIZ_PROYECTO` es la carpeta que contiene `main.py`, `assets/`, `datos/`,
`descargas/` y `grabaciones/`. Los módulos que viven más abajo (data/,
services/, ui/) la usan para no depender de cuántos niveles los separan de
la raíz.
"""
import os

RAIZ_PROYECTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
