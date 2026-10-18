"""
analisis.py — Núcleo numérico del ensayo IET-300 (ASTM E1876, flexión libre-libre).

Solo depende de numpy, así que se prueba igual en la PC que en Android.
La interfaz (main.py) solo llama a:  cargar_calibracion, banda_busqueda,
detectar_resonancia, modulo_young y comparar_materiales.
"""
import json
import math
import os

import numpy as np

# ---------------------------------------------------------------- constantes
L_M = 0.300                 # Longitud fija de la platina: 300 mm
RATIO_F2_F1 = 2.7566        # f2/f1 de una viga libre-libre = (7.8532/4.7300)^2
MODOS = ("F1", "F2")

# Posiciones de los nodos (fracción de L) para colocar los apoyos
NODOS = {
    "F1": (0.224, 0.776),
    "F2": (0.132, 0.500, 0.868),
}


# ---------------------------------------------------------- base de datos
def cargar_calibracion(ruta=None):
    """Lee calibracion.json (materiales, frecuencias parásitas, umbrales)."""
    if ruta is None:
        ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "calibracion.json")
    with open(ruta, encoding="utf-8") as fh:
        bd = json.load(fh)

    # Expande cada fuente parásita en una lista plana de (f_centro, tolerancia)
    parasitas = []
    for p in bd.get("frecuencias_parasitas", []):
        n = int(p.get("armonicos", 1))
        for k in range(1, n + 1):
            parasitas.append((k * float(p["f_hz"]), float(p["tol_hz"])))
    bd["_parasitas_planas"] = parasitas
    return bd


def e_referencia(material):
    """E de referencia (Pa): calibrado con el iPhone si existe; si no, teórico."""
    if material.get("E_calibrado_GPa") is not None:
        return material["E_calibrado_GPa"] * 1e9, "calibrado"
    return material["E_teorico_GPa"] * 1e9, "teórico"


# ------------------------------------------------------------ ASTM E1876
def factor_T1(t_m):
    """Corrección de Rayleigh simplificada (válida para L/t >= 20)."""
    return 1.0 + 6.585 * (t_m / L_M) ** 2


def modulo_young(f_hz, b_m, t_m, m_kg, modo):
    """E (Pa) a partir de la frecuencia medida en el modo indicado.

    En F2 se pasa primero a f1 con la relación de Euler-Bernoulli y se aplica
    la ecuación de F1. Para L/t ~ 60 el error de usar T1 en lugar de la
    corrección propia del 2.º modo es del orden de 0,3 %.
    """
    f1 = f_hz / RATIO_F2_F1 if modo == "F2" else f_hz
    return 0.9465 * m_kg * f1 ** 2 * L_M ** 3 * factor_T1(t_m) / (b_m * t_m ** 3)


def frecuencia_esperada(E_pa, b_m, t_m, m_kg, modo):
    """Inversa de modulo_young: la frecuencia que daría un E dado."""
    f1 = math.sqrt(E_pa * b_m * t_m ** 3 / (0.9465 * m_kg * L_M ** 3 * factor_T1(t_m)))
    return f1 * RATIO_F2_F1 if modo == "F2" else f1


def banda_busqueda(bd, b_m, t_m, m_kg, modo):
    """Ventana de frecuencias físicamente posible para los materiales de la BD.

    Con margen_E = 0,4 la banda de F1 y la de F2 no se solapan, así que un
    F1 residual no se confunde con F2 (y viceversa).
    """
    margen = bd["deteccion"]["margen_E"]
    E = [e_referencia(mat)[0] for mat in bd["materiales"]]
    f_min = frecuencia_esperada(min(E) * (1 - margen), b_m, t_m, m_kg, modo)
    f_max = frecuencia_esperada(max(E) * (1 + margen), b_m, t_m, m_kg, modo)
    return f_min, f_max


def comparar_materiales(bd, E_pa):
    """Material de la BD más cercano al E medido y su desviación relativa."""
    mejor = None
    for mat in bd["materiales"]:
        E_ref, fuente = e_referencia(mat)
        desv = (E_pa - E_ref) / E_ref
        if mejor is None or abs(desv) < abs(mejor[1]):
            mejor = (mat["nombre"], desv, fuente)
    return mejor


# --------------------------------------------------------- procesamiento
def _espectro(seg, fs, nfft):
    """Espectro de amplitud con ventana de Hann, normalizado a amplitud."""
    w = np.hanning(len(seg))
    A = np.abs(np.fft.rfft(seg * w, nfft)) * 2.0 / w.sum()
    return np.fft.rfftfreq(nfft, 1.0 / fs), A


def detectar_resonancia(x, fs, banda, bd):
    """Busca la frecuencia de resonancia tras el impacto.

    1. Ubica el impacto (máximo de |x|).
    2. Toma el decaimiento posterior como señal y lo previo como ruido de fondo.
    3. Dentro de la banda física, descarta las frecuencias parásitas de la BD y
       todo pico que ya existía antes del golpe (zumbido, luminaria, etc.).
    4. Refina el pico con interpolación parabólica.

    Devuelve un dict; si falla, dict con la clave "error".
    """
    cfg = bd["deteccion"]
    x = np.asarray(x, dtype=np.float64)
    x = x - x.mean()
    a = np.abs(x)

    i_pk = int(np.argmax(a))
    # Un golpe es un pico aislado: grande en absoluto Y frente al nivel típico
    # (mediana de |x|). Un tono estacionario o ruido no supera ese cociente.
    cresta = a[i_pk] / (float(np.median(a)) + 1e-9)
    if a[i_pk] < cfg["amplitud_min_impacto"] or cresta < cfg["cresta_min_impacto"]:
        return {"error": "No se detectó un impacto. Golpea más fuerte o acerca el celular."}

    # Decaimiento: desde 10 ms después del golpe (se salta el clic de banda ancha)
    ini = i_pk + int(0.010 * fs)
    fin = min(len(x), i_pk + int(cfg["duracion_analisis_s"] * fs))
    post = x[ini:fin]
    if len(post) < int(0.3 * fs):
        return {"error": "El golpe llegó muy tarde. Golpea apenas aparezca el aviso."}

    # Ruido de fondo: hasta 1 s, terminando 20 ms antes del golpe
    fin_pre = i_pk - int(0.020 * fs)
    pre = x[max(0, fin_pre - fs):fin_pre] if fin_pre > 0 else np.empty(0)
    hay_ref = len(pre) >= int(0.2 * fs)

    nfft = 1 << int(math.ceil(math.log2(4 * len(post))))
    f, A_post = _espectro(post, fs, nfft)
    A_pre = _espectro(pre, fs, nfft)[1] if hay_ref else None
    df = f[1] - f[0]

    f_min, f_max = banda
    f_max = min(f_max, 0.45 * fs)
    en_banda = (f >= f_min) & (f <= f_max)
    if not en_banda.any():
        return {"error": "La banda de búsqueda quedó vacía. Revisa b, t y m."}

    valido = en_banda.copy()
    for fc, tol in bd["_parasitas_planas"]:
        valido &= ~((f > fc - tol) & (f < fc + tol))

    piso = float(np.median(A_post[en_banda])) + 1e-12
    idx = np.flatnonzero(valido)
    idx = idx[(idx > 0) & (idx < len(f) - 1)]
    orden = idx[np.argsort(A_post[idx])[::-1]]

    k_ok = None
    descartados = 0
    for k in orden[:5000]:
        if not (A_post[k] >= A_post[k - 1] and A_post[k] >= A_post[k + 1]):
            continue                                  # no es máximo local
        if A_post[k] / piso < cfg["snr_min"]:
            break                                     # lo que queda es ruido
        if hay_ref and A_post[k] < cfg["ratio_post_pre_min"] * A_pre[k]:
            descartados += 1                          # ya sonaba antes del golpe
            continue
        k_ok = int(k)
        break

    if k_ok is None:
        return {"error": "No apareció una resonancia clara en la banda esperada. "
                         "Revisa los apoyos y repite el golpe."}

    # Interpolación parabólica sobre log-amplitud
    y0, y1, y2 = np.log(A_post[k_ok - 1:k_ok + 2] + 1e-12)
    den = y0 - 2 * y1 + y2
    delta = 0.5 * (y0 - y2) / den if den != 0 else 0.0
    f_pk = float(f[k_ok] + delta * df)

    return {
        "f_hz": f_pk,
        "snr_db": 20 * math.log10(A_post[k_ok] / piso),
        "picos_previos_descartados": descartados,
        "con_referencia_de_ruido": hay_ref,
        "banda_hz": (f_min, f_max),
    }
