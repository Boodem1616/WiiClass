[app]

# ---------------------------------------------------------------------------
# Identidad
# ---------------------------------------------------------------------------
title = WiiClass
package.name = wiiclass
# Cámbialo por un dominio tuyo antes de publicar (ej. cl.uct). Es el id único
# de la app: <package.domain>.<package.name>.
package.domain = org.wiiclass
version = 0.1.0

# ---------------------------------------------------------------------------
# Código fuente
# ---------------------------------------------------------------------------
source.dir = .
source.include_exts = py,kv,png,jpg,atlas,mp3,json
# No se empaqueta lo que se genera en tiempo de ejecución ni lo de desarrollo:
# la BD y los JSON se crean al primer arranque (db.init_db / storage), y los
# audios descargados/grabados viven en el almacenamiento del dispositivo.
source.exclude_dirs = tests, bin, .buildozer, descargas, grabaciones, datos, remote, assets/screenshots, __pycache__, .git
source.exclude_patterns = *.db, *.md, servir_*.py, analizador.py, scripts/*

# ---------------------------------------------------------------------------
# Dependencias (se compilan para Android con python-for-android)
# ---------------------------------------------------------------------------
# - sqlite3 .......... el módulo sqlite3 de Python necesita su receta en Android
# - openssl + certifi  HTTPS para descargar audios por URL
# - ffpyplayer ....... reproducción con velocidad variable (compila ffmpeg: la
#                      primera build tarda bastante)
# - pyjnius + android  MediaRecorder, MediaStore, notificaciones y permisos
# - sounddevice NO va: es solo de escritorio (grabación con PortAudio)
# KivyMD 2.0 necesita estas dependencias puras de Python. Si la build falla al
# resolver kivymd==2.0.0, prueba con la rama de desarrollo:
#   https://github.com/kivymd/KivyMD/archive/master.zip
requirements = python3,kivy==2.3.1,kivymd==2.0.0,materialyoucolor,exceptiongroup,asyncgui,asynckivy,pillow,ffpyplayer,pyjnius,android,plyer,sqlite3,openssl,certifi

orientation = portrait
fullscreen = 0

# ---------------------------------------------------------------------------
# Android
# ---------------------------------------------------------------------------
# - INTERNET ............. descargar audios por URL y configuración remota
# - RECORD_AUDIO ......... módulo Grabación (rol Profesor)
# - POST_NOTIFICATIONS ... notificaciones locales (Android 13+)
# - WRITE_EXTERNAL_STORAGE solo hasta Android 9 (API 28). Desde Android 10 el
#   guardado en Documents usa MediaStore y NO necesita permiso (scoped
#   storage), por eso se limita con maxSdkVersion y no se le pide nada al
#   usuario en equipos modernos.
android.permissions = android.permission.INTERNET, android.permission.RECORD_AUDIO, android.permission.POST_NOTIFICATIONS, (name=android.permission.WRITE_EXTERNAL_STORAGE;maxSdkVersion=28)

# Valores recomendados por la documentación de Buildozer 1.6 para compilar con
# API 36 (Google Play exige targetSdk 36 para apps nuevas y actualizaciones
# desde el 31-08-2026). Para pruebas/sideload local sirven igual.
p4a.branch = develop
android.api = 36
android.minapi = 24
android.ndk = 29
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True

# Datos internos en el almacenamiento privado de la app (no en "public storage").
android.private_storage = True

# ---------------------------------------------------------------------------
# iOS (solo desde macOS con Xcode; ver DESCARGAS-DOCUMENTOS.md)
# ---------------------------------------------------------------------------
# Ojo: Buildozer genera el proyecto de Xcode vía kivy-ios, pero NO tiene
# opciones para el Info.plist. Las claves UIFileSharingEnabled y
# LSSupportsOpeningDocumentsInPlace se agregan después con
# scripts/ios_habilitar_archivos.py.
ios.kivy_ios_url = https://github.com/kivy/kivy-ios
ios.kivy_ios_branch = master
ios.codesign.allowed = false
# Para firmar y ejecutar en un dispositivo real:
#ios.codesign.allowed = true
#ios.codesign.debug = "iPhone Developer: <tu nombre> (<TEAMID>)"

[buildozer]
# 0 = errores, 1 = info, 2 = debug (verboso)
log_level = 2
# Avisa si se ejecuta como root (Buildozer no lo recomienda)
warn_on_root = 1
build_dir = ./.buildozer
bin_dir = ./bin
