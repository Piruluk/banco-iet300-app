"""Prueba del algoritmo con una señal sintética (sin Kivy)."""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from analisis import *

bd = cargar_calibracion()
fs, dur = 44100, 4
b, t, m = 0.025, 0.00476, 0.280

E_real = 205e9
f1 = frecuencia_esperada(E_real, b, t, m, "F1")
f2 = f1 * RATIO_F2_F1
print(f"Verdad: E = {E_real/1e9:.1f} GPa -> f1 = {f1:.3f} Hz, f2 = {f2:.3f} Hz")

rng = np.random.default_rng(1)
tt = np.arange(fs * dur) / fs
def senal(t_golpe, A1, A2, ruido_luminaria=True):
    x = 300*np.sin(2*np.pi*60*tt) + 150*np.sin(2*np.pi*120*tt) + 80*np.sin(2*np.pi*180*tt)
    if ruido_luminaria:   # tonos estacionarios que NO están en la BD
        x += 900*np.sin(2*np.pi*(f1*1.08)*tt) + 500*np.sin(2*np.pi*(f2*0.95)*tt)
    x += rng.normal(0, 120, tt.size)
    g = tt >= t_golpe; td = tt[g] - t_golpe
    x[g] += A1*np.exp(-td/0.6)*np.sin(2*np.pi*f1*td) + A2*np.exp(-td/0.3)*np.sin(2*np.pi*f2*td)
    i0 = int(t_golpe*fs)
    if i0 < len(x): x[i0:i0+40] += rng.normal(0, 12000, len(x[i0:i0+40]))   # clic
    return np.clip(x, -32768, 32767).astype(np.int16)

for modo, A1, A2 in [("F1", 6000, 800), ("F2", 1500, 5000)]:
    x = senal(1.2, A1, A2)
    banda = banda_busqueda(bd, b, t, m, modo)
    r = detectar_resonancia(x, fs, banda, bd)
    E = modulo_young(r["f_hz"], b, t, m, modo)
    mat = comparar_materiales(bd, E)
    print(f"[{modo}] banda {banda[0]:.0f}-{banda[1]:.0f} Hz | f = {r['f_hz']:.3f} Hz | "
          f"SNR {r['snr_db']:.1f} dB | descartados {r['picos_previos_descartados']} | "
          f"E = {E/1e9:.2f} GPa (err {100*(E/E_real-1):+.3f} %) | {mat[0]} {100*mat[1]:+.1f} % ({mat[2]})")

print("Sin golpe:", detectar_resonancia(senal(99, 0, 0), fs, banda_busqueda(bd,b,t,m,"F1"), bd))
print("Golpe tardío:", detectar_resonancia(senal(3.85, 6000, 800), fs, banda_busqueda(bd,b,t,m,"F1"), bd))
r = detectar_resonancia(senal(0.05, 6000, 800), fs, banda_busqueda(bd,b,t,m,"F1"), bd)
print("Golpe inmediato:", {k: r[k] for k in ('f_hz','con_referencia_de_ruido')} if 'f_hz' in r else r)

import time; x = senal(1.2, 6000, 800); t0=time.time()
for _ in range(5): detectar_resonancia(x, fs, banda_busqueda(bd,b,t,m,"F1"), bd)
print(f"Tiempo por análisis (PC): {(time.time()-t0)/5*1000:.0f} ms")
