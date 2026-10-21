"""
recorder.py — Captura de audio para el módulo "Grabación" (rol Profesor).

Por qué dos backends (y no `plyer.audio`):
  - `plyer.audio` solo funciona en Android/iOS; en escritorio lanza
    NotImplementedError. Además, en Android graba en 3GP/AMR-NB (calidad de
    teléfono, pésima para voz de aula) y no permite elegir el formato.
  - Escritorio  -> `sounddevice` (PortAudio) + módulo `wave` de la librería
    estándar. Graba .wav 16 bits mono sin depender de numpy.
  - Android     -> `MediaRecorder` vía pyjnius (viene con python-for-android).
    Graba AAC en contenedor MP4 (.m4a), liviano y reproducible con
    ffpyplayer, que es lo que ya usa el reproductor de la app.

La interfaz es la misma en ambos casos:

    rec = crear_grabadora()
    rec.iniciar(ruta_sin_extension)   # -> ruta final (con extensión)
    ...
    ruta, duracion_seg = rec.detener()

`iniciar` puede lanzar `RecorderError` con un mensaje apto para mostrar al
usuario (sin micrófono, sin permiso, etc.).
"""

import os
import time
import wave

from kivy.utils import platform

SAMPLE_RATE = 44100


class RecorderError(Exception):
    """Error al grabar, con un mensaje legible para el usuario."""


# ---------------------------------------------------------------------------
# Escritorio: sounddevice + wave
# ---------------------------------------------------------------------------
class DesktopRecorder:
    extension = ".wav"

    def __init__(self):
        self._stream = None
        self._wav = None
        self._ruta = None
        self._inicio = 0.0

    @property
    def activa(self) -> bool:
        return self._stream is not None

    def iniciar(self, ruta_base: str) -> str:
        try:
            import sounddevice as sd
        except Exception as exc:  # ImportError o PortAudio ausente (OSError)
            raise RecorderError(
                "Falta 'sounddevice' (pip install sounddevice) o PortAudio."
            ) from exc

        ruta = ruta_base + self.extension
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        wav = wave.open(ruta, "wb")
        wav.setnchannels(1)
        wav.setsampwidth(2)  # int16
        wav.setframerate(SAMPLE_RATE)

        def callback(indata, frames, time_info, status):
            # Corre en el hilo de audio de PortAudio: solo escribe bytes.
            wav.writeframes(bytes(indata))

        try:
            stream = sd.RawInputStream(
                samplerate=SAMPLE_RATE, channels=1, dtype="int16", callback=callback
            )
            stream.start()
        except Exception as exc:
            wav.close()
            try:
                os.remove(ruta)
            except OSError:
                pass
            raise RecorderError(
                "No se pudo abrir el micrófono. Revisa que esté conectado y con permiso."
            ) from exc

        self._stream, self._wav, self._ruta = stream, wav, ruta
        self._inicio = time.monotonic()
        return ruta

    def detener(self):
        duracion = int(round(time.monotonic() - self._inicio))
        try:
            self._stream.stop()
            self._stream.close()
        finally:
            self._wav.close()
        ruta = self._ruta
        self._stream = self._wav = self._ruta = None
        return ruta, duracion


# ---------------------------------------------------------------------------
# Android: MediaRecorder (pyjnius)
# ---------------------------------------------------------------------------
class AndroidRecorder:
    extension = ".m4a"

    def __init__(self):
        self._mr = None
        self._ruta = None
        self._inicio = 0.0

    @property
    def activa(self) -> bool:
        return self._mr is not None

    @staticmethod
    def tiene_permiso() -> bool:
        from android.permissions import Permission, check_permission
        return bool(check_permission(Permission.RECORD_AUDIO))

    @staticmethod
    def pedir_permiso(callback=None):
        """Pide RECORD_AUDIO. `callback(concedido: bool)` se llama al responder."""
        from android.permissions import Permission, request_permissions

        def _resp(permisos, resultados):
            if callback:
                callback(all(resultados))

        request_permissions([Permission.RECORD_AUDIO], _resp)

    def iniciar(self, ruta_base: str) -> str:
        if not self.tiene_permiso():
            raise RecorderError("Falta el permiso de micrófono.")
        from jnius import autoclass

        MediaRecorder = autoclass("android.media.MediaRecorder")
        AudioSource = autoclass("android.media.MediaRecorder$AudioSource")
        OutputFormat = autoclass("android.media.MediaRecorder$OutputFormat")
        AudioEncoder = autoclass("android.media.MediaRecorder$AudioEncoder")

        ruta = ruta_base + self.extension
        os.makedirs(os.path.dirname(ruta), exist_ok=True)

        mr = MediaRecorder()
        try:
            mr.setAudioSource(AudioSource.MIC)
            mr.setOutputFormat(OutputFormat.MPEG_4)
            mr.setAudioEncoder(AudioEncoder.AAC)
            mr.setAudioSamplingRate(44100)
            mr.setAudioEncodingBitRate(96000)
            mr.setOutputFile(ruta)
            mr.prepare()
            mr.start()
        except Exception as exc:
            try:
                mr.release()
            except Exception:
                pass
            raise RecorderError("No se pudo iniciar la grabación en el micrófono.") from exc

        self._mr, self._ruta = mr, ruta
        self._inicio = time.monotonic()
        return ruta

    def detener(self):
        duracion = int(round(time.monotonic() - self._inicio))
        try:
            self._mr.stop()
        except Exception:
            # MediaRecorder.stop() lanza RuntimeException si se detuvo
            # demasiado pronto (sin datos): el archivo no es válido.
            pass
        finally:
            self._mr.release()
        ruta = self._ruta
        self._mr = self._ruta = None
        return ruta, duracion


def crear_grabadora():
    """Devuelve la grabadora adecuada a la plataforma."""
    return AndroidRecorder() if platform == "android" else DesktopRecorder()
