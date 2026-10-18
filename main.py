from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.utils import platform
from plyer import audio
import os


class IET300App(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', padding=20, spacing=10)

        self.lbl_estado = Label(text="Presiona Comenzar para grabar el ensayo", font_size=20)
        self.add_widget(self.lbl_estado)

        self.btn_comenzar = Button(text="Comenzar Ensayo", size_hint=(1, 0.2), background_color=(0, 0.7, 0.3, 1))
        self.btn_comenzar.bind(on_press=self.iniciar_secuencia)
        self.add_widget(self.btn_comenzar)

        self.tiempo_restante = 10

        # Generar ruta de guardado segura según el sistema operativo
        if platform == 'android':
            from android.storage import primary_external_storage_path
            # Guarda el archivo en la carpeta principal del teléfono
            self.archivo_audio = os.path.join(primary_external_storage_path(), 'ensayo_iet300.wav')
        else:
            self.archivo_audio = 'ensayo_iet300.wav'

    def solicitar_permisos(self):
        # Llama a la API nativa de Java para pedir permisos en pantalla
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.RECORD_AUDIO, Permission.WRITE_EXTERNAL_STORAGE])

    def iniciar_secuencia(self, instancia):
        self.btn_comenzar.disabled = True
        self.solicitar_permisos()

        self.tiempo_restante = 10
        # Llama a la función de cuenta regresiva cada 1 segundo
        Clock.schedule_interval(self.actualizar_contador, 1)

    def actualizar_contador(self, dt):
        if self.tiempo_restante > 0:
            self.lbl_estado.text = f"Coloca el teléfono a 22.5 mm.\nComienza en: {self.tiempo_restante} s"
            self.tiempo_restante -= 1
        else:
            Clock.unschedule(self.actualizar_contador)
            self.lbl_estado.text = "¡GRABANDO! Realiza el golpe..."
            self.iniciar_grabacion()

    def iniciar_grabacion(self):
        try:
            audio.file_path = self.archivo_audio
            audio.start()
            # Grabar durante 3 segundos exactos para captar el impacto y la resonancia
            Clock.schedule_once(self.detener_grabacion, 3.0)
        except Exception as e:
            self.lbl_estado.text = f"Error al iniciar micrófono: {e}"
            self.btn_comenzar.disabled = False

    def detener_grabacion(self, dt):
        try:
            audio.stop()
            self.lbl_estado.text = f"Ensayo completado.\nArchivo guardado en:\n{self.archivo_audio}\n\nListo para analizar frecuencias."
        except Exception as e:
            self.lbl_estado.text = f"Error al detener grabación: {e}"

        self.btn_comenzar.disabled = False


class AplicacionAPP(App):
    def build(self):
        return IET300App()


if __name__ == '__main__':
    AplicacionAPP().run()