"""
Paquete de pantallas.

Al importarse por primera vez (lo hace main.py), registra los widgets
propios y carga `common.kv`, que define componentes de estilo compartidos
(tarjetas, chips, textos, hoja redondeada). Debe cargarse ANTES que los
.kv de cada pantalla, porque estos los usan por nombre.
"""

import os

from kivy.lang import Builder

# Importar estos módulos registra en la Factory las clases de KivyMD que
# common.kv usa como base (MDLabel, MDIconButton).
import kivymd.uix.label  # noqa: F401
import kivymd.uix.button  # noqa: F401

from screens import widgets  # noqa: F401  (registra CabeceraDegradada, Waveform)

Builder.load_file(os.path.join(os.path.dirname(__file__), "common.kv"))
