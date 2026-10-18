"""
main.py — App Android del banco IET-300 (ASTM E1876, flexión libre-libre).

- Largo fijo L = 300 mm; el usuario ingresa ancho b, espesor t y masa m.
- Modo F1 o F2 (el longitudinal queda en standby).
- Solo pide permiso de micrófono; graba PCM crudo con AudioRecord (pyjnius),
  sin sounddevice ni plyer, para que Buildozer compile solo python3+kivy+numpy.
- Todo el cálculo vive en analisis.py; la BD de calibración en calibracion.json.
"""
import threading

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.utils import platform

import analisis as an

FS = 44100            # Única frecuencia de muestreo garantizada en todo Android
DURACION_S = 4        # Ventana de escucha tras la cuenta regresiva
CUENTA_S = 3

MODOS_UI = {"1.er modo (F1)": "F1", "2.º modo (F2)": "F2"}


def _num(texto):
    """Acepta coma o punto decimal (teclados en español)."""
    return float(texto.strip().replace(",", "."))


class PantallaIET300(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=15, spacing=8, **kwargs)
        self.bd = an.cargar_calibracion()
        self.permiso_ok = platform != "android"

        self.add_widget(Label(text="[b]Banco IET-300 · ASTM E1876[/b]", markup=True,
                              font_size="20sp", size_hint=(1, 0.08)))

        grid = GridLayout(cols=2, size_hint=(1, 0.38), spacing=8)
        grid.add_widget(Label(text="Largo L:"))
        grid.add_widget(Label(text=f"[b]{an.L_M * 1000:.0f} mm (fijo)[/b]", markup=True))

        self.inp_b = self._campo(grid, "Ancho b (mm):", "25.0")
        self.inp_t = self._campo(grid, "Espesor t (mm):", "4.76")
        self.inp_m = self._campo(grid, "Masa m (g):", "280.0")

        grid.add_widget(Label(text="Modo ensayado:"))
        self.spin_modo = Spinner(text="1.er modo (F1)", values=tuple(MODOS_UI))
        self.spin_modo.bind(text=lambda *_: self._actualizar_ayuda())
        grid.add_widget(self.spin_modo)
        self.add_widget(grid)

        self.lbl_ayuda = Label(font_size="14sp", size_hint=(1, 0.08), halign="center")
        self.lbl_ayuda.bind(size=lambda w, s: setattr(w, "text_size", s))
        self.add_widget(self.lbl_ayuda)
        self._actualizar_ayuda()

        self.lbl_estado = Label(text="Ingresa los datos y presiona Iniciar",
                                font_size="16sp", size_hint=(1, 0.08))
        self.add_widget(self.lbl_estado)

        self.lbl_res = Label(text="- Esperando ensayo -", font_size="16sp", markup=True,
                             size_hint=(1, 0.26), halign="center", valign="middle")
        self.lbl_res.bind(size=lambda w, s: setattr(w, "text_size", s))
        self.add_widget(self.lbl_res)

        self.btn = Button(text=f"Iniciar captura ({CUENTA_S} s)", size_hint=(1, 0.12),
                          background_color=(0, 0.6, 0.8, 1))
        self.btn.bind(on_press=self.iniciar)
        self.add_widget(self.btn)

        if not self.permiso_ok:
            self.btn.disabled = True
            self.lbl_estado.text = "Esperando permiso de micrófono…"

    # ------------------------------------------------------------- interfaz
    @staticmethod
    def _campo(grid, etiqueta, valor):
        grid.add_widget(Label(text=etiqueta))
        ti = TextInput(text=valor, multiline=False, input_type="number")
        grid.add_widget(ti)
        return ti

    def _actualizar_ayuda(self):
        modo = MODOS_UI[self.spin_modo.text]
        pos = ", ".join(f"{p * an.L_M * 1000:.0f}" for p in an.NODOS[modo])
        self.lbl_ayuda.text = f"Apoyos ({modo}) en los nodos: {pos} mm desde un extremo"

    @mainthread
    def on_permiso(self, permisos, concedidos):
        self.permiso_ok = all(concedidos)
        if self.permiso_ok:
            self.btn.disabled = False
            self.lbl_estado.text = "Micrófono listo. Ingresa los datos y presiona Iniciar"
        else:
            self.btn.disabled = True
            self.lbl_estado.text = "Sin permiso de micrófono: actívalo en Ajustes > Apps"

    @mainthread
    def _estado(self, texto):
        self.lbl_estado.text = texto

    @mainthread
    def _fin(self, texto_res, texto_estado):
        self.lbl_res.text = texto_res
        self.lbl_estado.text = texto_estado
        self.btn.disabled = False

    # --------------------------------------------------------------- flujo
    def _leer_entradas(self):
        try:
            b_mm, t_mm, m_g = _num(self.inp_b.text), _num(self.inp_t.text), _num(self.inp_m.text)
        except ValueError:
            raise ValueError("Ingresa números válidos en b, t y m.")
        if min(b_mm, t_mm, m_g) <= 0:
            raise ValueError("b, t y m deben ser mayores que cero.")
        if an.L_M * 1000 / t_mm < 20:
            raise ValueError("L/t < 20: la ecuación simplificada de ASTM E1876 no aplica.")
        return b_mm / 1000, t_mm / 1000, m_g / 1000, MODOS_UI[self.spin_modo.text]

    def iniciar(self, *_):
        try:
            self.entradas = self._leer_entradas()
        except ValueError as e:
            self._fin(f"[color=FF5555]{e}[/color]", "Revisa los datos")
            return
        self.btn.disabled = True
        self.lbl_res.text = ""
        self.restante = CUENTA_S
        self._tick(0)
        Clock.schedule_interval(self._tick, 1)

    def _tick(self, dt):
        if self.restante > 0:
            self.lbl_estado.text = f"Prepárate para golpear en: {self.restante} s"
            self.restante -= 1
            return True
        self.lbl_estado.text = "Abriendo micrófono…"
        threading.Thread(target=self._trabajo, daemon=True).start()
        return False                      # detiene el schedule_interval

    def _trabajo(self):
        """Hilo secundario: graba y analiza. La UI solo se toca vía @mainthread."""
        try:
            audio = grabar_android(self._estado) if platform == "android" else grabar_pc(self._estado)
            self._estado("Procesando FFT…")
            b, t, m, modo = self.entradas
            banda = an.banda_busqueda(self.bd, b, t, m, modo)
            r = an.detectar_resonancia(audio, FS, banda, self.bd)
            if "error" in r:
                self._fin(f"[color=FFAA00]{r['error']}[/color]", "Ensayo no válido")
                return
            E = an.modulo_young(r["f_hz"], b, t, m, modo)
            nombre, desv, fuente = an.comparar_materiales(self.bd, E)
            aviso = "" if r["con_referencia_de_ruido"] else \
                "\n[size=13sp](sin referencia de ruido previo: espera ~1 s antes de golpear)[/size]"
            self._fin(
                f"[b]f ({modo}):[/b] {r['f_hz']:.2f} Hz   [size=13sp]SNR {r['snr_db']:.0f} dB[/size]\n"
                f"[color=00FF66][b]E = {E / 1e9:.1f} GPa[/b][/color]\n"
                f"Más cercano: [b]{nombre}[/b] ({desv * 100:+.1f} % vs {fuente})" + aviso,
                "¡Ensayo completado!")
        except Exception as e:            # noqa: BLE001 — se muestra al usuario
            mensaje = str(e)              # se copia ANTES de salir del except
            self._fin(f"[color=FF5555]{mensaje}[/color]", "Ocurrió un error")


# ------------------------------------------------------------------- audio
def grabar_android(avisar):
    """PCM 16 bit mono con android.media.AudioRecord vía pyjnius."""
    import numpy as np
    from jnius import autoclass
    AudioRecord = autoclass("android.media.AudioRecord")
    AudioFormat = autoclass("android.media.AudioFormat")

    canal, formato = AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT
    min_buf = AudioRecord.getMinBufferSize(FS, canal, formato)
    if min_buf <= 0:
        raise RuntimeError(f"El micrófono no admite {FS} Hz (código {min_buf}).")
    chunk = 4096                                   # muestras por lectura
    buf_bytes = max(min_buf, chunk * 2) * 4

    # Fuentes en orden de preferencia: sin procesar (API 24+), reconocimiento de
    # voz (sin AGC en la mayoría de equipos) y micrófono genérico.
    rec = None
    for fuente in (9, 6, 1):                       # UNPROCESSED, VOICE_RECOGNITION, MIC
        try:
            r = AudioRecord(fuente, FS, canal, formato, buf_bytes)
        except Exception:
            continue
        if r.getState() == AudioRecord.STATE_INITIALIZED:
            rec = r
            break
        r.release()
    if rec is None:
        raise RuntimeError("No se pudo abrir el micrófono (¿permiso concedido?).")

    total = FS * DURACION_S
    out = np.empty(total, dtype=np.int16)
    buf = [0] * chunk          # pyjnius copia de vuelta a esta lista tras read()
    n = 0
    rec.startRecording()
    avisar("¡GOLPEA AHORA! (espera ~1 s y golpea)")
    try:
        while n < total:
            leidos = rec.read(buf, 0, min(chunk, total - n))
            if leidos < 0:
                raise RuntimeError(f"AudioRecord.read devolvió {leidos}.")
            out[n:n + leidos] = buf[:leidos]
            n += leidos
    finally:
        rec.stop()
        rec.release()
    return out


def grabar_pc(avisar):
    """Solo para probar en la PC (pip install sounddevice). No va al APK."""
    try:
        import sounddevice as sd
    except ImportError:
        raise RuntimeError("En la PC instala sounddevice para probar la captura.")
    avisar("¡GOLPEA AHORA! (espera ~1 s y golpea)")
    rec = sd.rec(FS * DURACION_S, samplerate=FS, channels=1, dtype="int16")
    sd.wait()
    return rec[:, 0]


class IET300(App):
    title = "IET-300"

    def build(self):
        return PantallaIET300()

    def on_start(self):
        if platform == "android":
            from android.permissions import Permission, request_permissions
            request_permissions([Permission.RECORD_AUDIO], self.root.on_permiso)


if __name__ == "__main__":
    IET300().run()
