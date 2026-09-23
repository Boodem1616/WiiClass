"""
gradient_utils.py — Utilidad compartida para pintar degradados de color
directamente en el canvas de un widget, sin usar texturas.

Se implementa con bandas de color apiladas (varios rectángulos delgados
con un color interpolado cada uno) en vez de una `Texture`, porque es más
simple de depurar: si algo se ve mal, el motivo es evidente con solo mirar
los colores de cada banda, a diferencia de una textura donde un error en
el `blit_buffer` puede dar resultados confusos (ver login_screen.py, donde
se abandonó el enfoque con textura por este motivo).

Uso típico (en `on_kv_post` de un widget/screen):

    from screens.gradient_utils import aplicar_degradado
    aplicar_degradado(self.ids.fondo, (0.3, 0.5, 0.9), (0.05, 0.15, 0.55),
                       direccion="vertical")

IMPORTANTE — por qué esta utilidad NO recorta a esquinas redondeadas:
Se probó una variante con `StencilPush/StencilUse/StencilPop` para recortar
el degradado a la forma de un `MDCard` con esquinas redondeadas, pero en al
menos un entorno (driver de GPU/OpenGL específico) esa combinación corrompió
el renderizado de la ventana completa (aparecían manchas negras y hasta
pantallas equivocadas). Los `Stencil*` de Kivy son delicados de combinar con
canvas que KivyMD ya arma internamente (elevación, ripple, etc.), y el
riesgo de romper la app en hardware que no podemos probar directamente no
vale la pena por un detalle decorativo. Por eso: usar esta utilidad solo en
widgets simples sin esquinas redondeadas (o donde un ligero desborde en las
puntas sea aceptable), como el fondo de pantalla completo del Login.
"""

from kivy.graphics import Color, Rectangle

N_BANDAS_POR_DEFECTO = 24


def aplicar_degradado(widget, color_inicio, color_fin, direccion="vertical", n_bandas=N_BANDAS_POR_DEFECTO):
    """Pinta un degradado en `widget.canvas.before` sin tocar lo que el
    widget ya haya dibujado ahí (no se usa `.clear()`, que puede romper el
    balance interno de Push/Pop que arman algunos widgets de KivyMD).

    - direccion="vertical": color_inicio arriba, color_fin abajo.
    - direccion="horizontal": color_inicio a la izquierda, color_fin a la derecha.

    Devuelve una función `actualizar()` por si se necesita forzar un
    refresco manual (normalmente no hace falta: ya queda enlazada a los
    cambios de `size`/`pos` del widget).
    """
    bandas = []
    r1, g1, b1 = color_inicio
    r2, g2, b2 = color_fin

    with widget.canvas.before:
        for i in range(n_bandas):
            t = i / (n_bandas - 1)
            Color(
                r1 + (r2 - r1) * t,
                g1 + (g2 - g1) * t,
                b1 + (b2 - b1) * t,
                1,
            )
            bandas.append(Rectangle(pos=(0, 0), size=(1, 1)))

    def actualizar(*_args):
        n = len(bandas)
        if widget.width <= 0 or widget.height <= 0:
            return
        if direccion == "vertical":
            alto_banda = widget.height / n
            for i, rect in enumerate(bandas):
                # i=0 arriba (coordenadas Kivy: y crece hacia arriba).
                y = widget.y + widget.height - (i + 1) * alto_banda
                rect.pos = (widget.x, y)
                rect.size = (widget.width, alto_banda + 1)
        else:  # horizontal
            ancho_banda = widget.width / n
            for i, rect in enumerate(bandas):
                x = widget.x + i * ancho_banda
                rect.pos = (x, widget.y)
                rect.size = (ancho_banda + 1, widget.height)

    widget.bind(size=actualizar, pos=actualizar)
    actualizar()
    return actualizar

