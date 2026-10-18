[app]
title = IET-300
package.name = iet300
package.domain = pe.edu.uni
source.dir = .
source.include_exts = py,json
source.exclude_dirs = bin,.github,.buildozer
source.exclude_patterns = prueba_sintetica.py
version = 0.2.0

# Solo lo que realmente se usa: nada de sounddevice, plyer ni matplotlib.
# (pyjnius y el módulo android vienen incluidos con el bootstrap de Kivy)
requirements = python3,kivy,numpy

orientation = portrait
fullscreen = 0

# Único permiso que pide la app
android.permissions = android.permission.RECORD_AUDIO

# arm64-v8a cubre casi todos los celulares actuales y compila en la mitad
# de tiempo. Para equipos de 32 bits añade: , armeabi-v7a
android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
