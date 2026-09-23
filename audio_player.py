"""
audio_player.py — Motor de reproducción de audio reutilizable.

Usa ffpyplayer porque a diferencia de kivy.core.audio (SDL2), permite
cambiar la velocidad de reproducción en tiempo real (0.5x, 1.0x, 1.5x, 2.0x),
requisito explícito de la especificación.

Si ffpyplayer no está disponible en el entorno, se hace fallback a
kivy.core.audio.SoundLoader (sin soporte de velocidad variable) para que
la app siga funcionando en desarrollo/pruebas.

IMPORTANTE — por qué la apertura del audio es ASÍNCRONA:
Crear un `ffpyplayer.player.MediaPlayer` implica abrir el archivo, leer sus
cabeceras/códec e inicializar el dispositivo de audio del sistema (ALSA/
PulseAudio/lo que use el SO). Ese trabajo puede tardar de forma muy variable
según el dispositivo, el archivo o si es la primera vez que se abre audio en
el proceso. Kivy corre en un solo hilo: si esa creación se hace en el hilo
principal, TODA la interfaz deja de responder mientras tanto (toques,
botones, todo) — exactamente el síntoma de "se congela y no responde".
Por eso aquí la apertura ocurre en un hilo de fondo, y el resultado se
aplica en el hilo principal vía `Clock.schedule_once`, que es la forma
segura de tocar propiedades/objetos de Kivy desde otro hilo.

IMPORTANTE — por qué hay un único hilo de trabajo (cola), y no "un hilo
por operación":
Un primer intento lanzaba un hilo nuevo por cada apertura/cierre. Eso
funciona si las operaciones nunca se superponen, pero si el usuario cambia
de velocidad varias veces seguidas (o cambia de clase mientras la anterior
seguía cerrando), pueden terminar dos hilos tocando la librería nativa de
audio (ffpyplayer/SDL) AL MISMO TIEMPO. Esa librería no está pensada para
que dos hilos abran/cierren reproductores en paralelo, y el resultado es un
"segmentation fault": la app se cierra de golpe sin ningún traceback de
Python, porque un segfault mata el proceso completo antes de que Python
pueda reportar nada.

La solución es una cola (`queue.Queue`) con UN SOLO hilo de trabajo
persistente: cada apertura/cierre se encola como una tarea, y ese único
hilo las va ejecutando una por una, en orden, nunca dos a la vez. Así se
garantiza que jamás haya dos operaciones nativas de audio corriendo en
paralelo, sin importar qué tan rápido el usuario toque los botones.
"""

import threading
import queue
import time

from kivy.clock import Clock
from kivy.event import EventDispatcher
from kivy.properties import NumericProperty, BooleanProperty, StringProperty

try:
    from ffpyplayer.player import MediaPlayer
    FFPYPLAYER_AVAILABLE = True
except Exception:
    FFPYPLAYER_AVAILABLE = False
    from kivy.core.audio import SoundLoader


class AudioEngine(EventDispatcher):
    """Motor único de audio, controlado por la pantalla del reproductor."""

    position = NumericProperty(0.0)      # segundos
    duration = NumericProperty(0.0)      # segundos
    is_playing = BooleanProperty(False)
    is_loading = BooleanProperty(False)  # True mientras se abre el archivo
    speed = NumericProperty(1.0)
    source = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._player = None
        self._sound = None
        self._clock_event = None
        # Contador de "operación de carga": cada tarea encolada lleva un
        # número. Si el resultado de una tarea vieja llega después de que
        # ya se pidió algo más nuevo, se descarta comparando este id.
        self._load_token = 0

        # Cola + único hilo de trabajo persistente para TODAS las
        # operaciones nativas de audio (abrir y cerrar). Ver docstring del
        # módulo: esto es lo que evita el segmentation fault por dos hilos
        # tocando ffpyplayer/SDL al mismo tiempo.
        self._cola = queue.Queue()
        self._worker = threading.Thread(target=self._bucle_worker, daemon=True)
        self._worker.start()

    def _bucle_worker(self):
        while True:
            tarea = self._cola.get()
            try:
                tarea()
            except Exception as exc:
                print(f"[audio_player] Error en una tarea de audio: {exc}")

    # -- Carga (asíncrona) --------------------------------------------
    def load(self, path: str, duration_hint: float = 0.0):
        old_player = self._player
        old_sound = self._sound
        self._player = None
        self._sound = None
        if self._clock_event:
            self._clock_event.cancel()
            self._clock_event = None

        self.source = path
        self.duration = duration_hint
        self.position = 0.0
        self.is_playing = False
        self.is_loading = True

        if old_sound:
            # SoundLoader.stop()/unload() son rápidos (sin dispositivo real
            # que negociar cierre), no hace falta pasar por la cola.
            old_sound.stop()
            old_sound.unload()

        self._encolar_apertura(old_player, start_at=0.0, resume_playing=True)

    def _encolar_apertura(self, old_player, start_at: float, resume_playing: bool):
        """Encola una tarea que cierra (si corresponde) el reproductor
        anterior y abre uno nuevo. Se ejecuta en el único hilo de trabajo
        (ver `_bucle_worker`), nunca en paralelo con otra tarea de audio.
        """
        self._load_token += 1
        my_token = self._load_token
        source = self.source
        speed = self.speed

        def tarea():
            if old_player is not None:
                try:
                    old_player.close_player()
                except Exception as exc:
                    print(f"[audio_player] Aviso al cerrar el reproductor anterior: {exc}")

            if not FFPYPLAYER_AVAILABLE:
                sound = SoundLoader.load(source)
                Clock.schedule_once(
                    lambda dt: self._on_sound_ready(my_token, sound, start_at, resume_playing)
                )
                return

            ff_opts = {"paused": True, "af": f"atempo={speed}"}
            try:
                player = MediaPlayer(source, ff_opts=ff_opts)
                if start_at > 0:
                    # ¡OJO! Llamar a `seek()` INMEDIATAMENTE después de crear
                    # el MediaPlayer puede crashear (segmentation fault) — es
                    # una condición de carrera dentro de la propia librería
                    # ffpyplayer: el reproductor recién creado todavía no
                    # terminó de leer las cabeceras/formato del archivo en su
                    # hilo interno, y pedirle un `seek()` en ese momento
                    # accede a estructuras que aún no están listas. Se
                    # confirmó con gdb: el crash ocurre exactamente dentro de
                    # `MediaPlayer._seek`, llamado desde acá.
                    # La solución es esperar (con un límite) a que el
                    # reproductor reporte una duración válida —señal de que
                    # ya terminó de inicializarse— antes de buscar posición.
                    for _ in range(40):  # hasta ~2s de espera máxima
                        metadata = player.get_metadata()
                        if metadata and metadata.get("duration"):
                            break
                        time.sleep(0.05)
                    player.seek(start_at, relative=False)
            except Exception as exc:
                Clock.schedule_once(lambda dt: self._on_player_error(my_token, exc))
                return
            Clock.schedule_once(
                lambda dt: self._on_player_ready(my_token, player, resume_playing)
            )

        self._cola.put(tarea)

    def _on_player_ready(self, token, player, resume_playing):
        if token != self._load_token:
            # Llegó tarde: el usuario ya pidió otra cosa mientras tanto.
            # Cerrarlo también se encola, nunca en un hilo aparte.
            self._encolar_cierre(player)
            return
        self._player = player
        self.is_loading = False
        self._player.set_pause(not resume_playing)
        self.is_playing = resume_playing
        if self._clock_event is None:
            self._clock_event = Clock.schedule_interval(self._tick, 0.2)

    def _on_sound_ready(self, token, sound, start_at, resume_playing):
        if token != self._load_token:
            if sound:
                sound.unload()
            return
        self._sound = sound
        self.is_loading = False
        if sound:
            self.duration = sound.length or self.duration
            if start_at > 0:
                sound.seek(start_at)
            if resume_playing:
                sound.play()
        self.is_playing = resume_playing and bool(sound)
        if self._clock_event is None:
            self._clock_event = Clock.schedule_interval(self._tick, 0.2)

    def _on_player_error(self, token, exc):
        if token != self._load_token:
            return
        self.is_loading = False
        self.is_playing = False
        print(f"[audio_player] No se pudo abrir el audio: {exc}")

    # -- Transporte ----------------------------------------------------
    def play(self):
        if self.is_loading:
            return
        if FFPYPLAYER_AVAILABLE and self._player:
            self._player.set_pause(False)
            self.is_playing = True
        elif self._sound:
            self._sound.play()
            self.is_playing = True

    def pause(self):
        if FFPYPLAYER_AVAILABLE and self._player:
            self._player.set_pause(True)
        elif self._sound:
            self._sound.stop()
        self.is_playing = False

    def toggle_play_pause(self):
        self.pause() if self.is_playing else self.play()

    def seek(self, seconds: float):
        if self.is_loading:
            return
        seconds = max(0.0, min(seconds, self.duration or seconds))
        if FFPYPLAYER_AVAILABLE and self._player:
            self._player.seek(seconds, relative=False)
        elif self._sound:
            self._sound.seek(seconds)
        self.position = seconds

    def restart(self):
        """Botón 'Saltar al inicio'."""
        self.seek(0.0)

    def set_speed(self, speed: float):
        self.speed = speed
        if self.is_loading or not self.source:
            return  # se aplicará cuando termine la carga en curso
        if FFPYPLAYER_AVAILABLE:
            was_playing = self.is_playing
            resume_at = self.position
            self.is_loading = True
            old_player, self._player = self._player, None
            # Se encola (nunca un hilo suelto): así, aunque el usuario
            # cambie de velocidad varias veces seguidas, cada cierre+
            # apertura espera su turno en el único hilo de trabajo.
            self._encolar_apertura(old_player, start_at=resume_at, resume_playing=was_playing)
        # SoundLoader (fallback de escritorio) no soporta cambio de velocidad.

    def stop(self):
        self._load_token += 1  # invalida cualquier carga en curso
        self.is_loading = False
        if self._clock_event:
            self._clock_event.cancel()
            self._clock_event = None
        if FFPYPLAYER_AVAILABLE and self._player:
            old_player, self._player = self._player, None
            self._encolar_cierre(old_player)
        if self._sound:
            # SoundLoader.stop()/unload() son rápidos (sin dispositivo real
            # que negociar cierre), no hace falta pasar por la cola.
            self._sound.stop()
            self._sound.unload()
            self._sound = None
        self.is_playing = False
        self.position = 0.0

    def _encolar_cierre(self, player):
        """Encola el cierre de un MediaPlayer que ya no se va a reabrir
        (p.ej. al salir del reproductor). Igual que la apertura, pasa por
        la misma cola/hilo único: nunca un hilo aparte por su cuenta."""
        def tarea():
            try:
                player.close_player()
            except Exception as exc:
                print(f"[audio_player] Aviso al cerrar el reproductor anterior: {exc}")

        self._cola.put(tarea)

    # -- Loop interno ----------------------------------------------
    def _tick(self, dt):
        if FFPYPLAYER_AVAILABLE and self._player:
            pts = self._player.get_pts()
            if pts is not None and pts >= 0:
                self.position = pts
            metadata = self._player.get_metadata()
            dur = metadata.get("duration") if metadata else None
            if dur:
                self.duration = dur
        elif self._sound:
            self.position = self._sound.get_pos()
            if self.position >= (self.duration or 0) and self.duration:
                self.is_playing = False


# Instancia global compartida entre Tab Inicio y Tab Descargas
audio_engine = AudioEngine()
