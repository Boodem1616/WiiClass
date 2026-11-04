#!/usr/bin/env python3
"""
ios_habilitar_archivos.py — Hace visible la carpeta Documents de la app en la
app "Archivos" de iOS.

Buildozer (target ios) genera el proyecto de Xcode con kivy-ios pero no ofrece
opciones para el Info.plist. Este script agrega las dos claves que iOS exige:

    UIFileSharingEnabled               = true   (Documents visible en Archivos / Finder)
    LSSupportsOpeningDocumentsInPlace  = true   (abrir/editar ahí mismo, sin copiar)

Uso (después de `buildozer ios debug`, antes de compilar en Xcode):

    python3 scripts/ios_habilitar_archivos.py              # busca el plist solo
    python3 scripts/ios_habilitar_archivos.py ruta/wiiclass-Info.plist

Es idempotente: se puede ejecutar varias veces. Si Buildozer regenera el
proyecto (`buildozer ios clean`), hay que volver a ejecutarlo.
"""
import glob
import os
import plistlib
import sys

CLAVES = {
    "UIFileSharingEnabled": True,
    "LSSupportsOpeningDocumentsInPlace": True,
}


def buscar_plist(raiz: str = ".") -> str:
    patron = os.path.join(raiz, ".buildozer", "ios", "platform", "kivy-ios", "*-ios", "*-Info.plist")
    encontrados = sorted(glob.glob(patron))
    if not encontrados:
        raise FileNotFoundError(
            "No se encontró el Info.plist. Ejecuta primero `buildozer ios debug` "
            "o pasa la ruta del archivo como argumento.")
    return encontrados[0]


def habilitar(ruta: str) -> bool:
    """Agrega las claves. Devuelve True si hubo cambios."""
    with open(ruta, "rb") as f:
        datos = plistlib.load(f)          # soporta XML y binario
    cambios = False
    for clave, valor in CLAVES.items():
        if datos.get(clave) is not valor:
            datos[clave] = valor
            cambios = True
    if cambios:
        with open(ruta, "wb") as f:
            plistlib.dump(datos, f, fmt=plistlib.FMT_XML)
    return cambios


def main(argv):
    try:
        ruta = argv[1] if len(argv) > 1 else buscar_plist()
        cambio = habilitar(ruta)
    except (OSError, plistlib.InvalidFileException, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(("Actualizado: " if cambio else "Ya estaba listo: ") + ruta)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
