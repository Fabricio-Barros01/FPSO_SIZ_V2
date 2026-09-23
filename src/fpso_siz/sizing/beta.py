"""Geometria do segmento circular: coeficiente β (Fig. 3 de Stewart & Arnold, vaso meio
cheio), altura de segmento (Eq. 4.17, vaso cheio) e fração de área de água (Eq. 18).
Port de sizing/separator/beta.jl. β é geometria exata (bisseção), não leitura de figura.
"""
import math

from fpso_siz.core.configuracao import carregar


def _segment_area(u):
    """Área do segmento de altura relativa u = h/R, normalizada por R²."""
    if u <= 0:
        return 0.0
    if u >= 2:
        return math.pi
    c = 1.0 - u
    return math.acos(min(max(c, -1.0), 1.0)) - c * math.sqrt(max(2 * u - u * u, 0.0))


def segment_height_fraction(a):
    """h/d do segmento inferior que ocupa a fração `a` da seção inteira (a ∈ [0, 1])."""
    f = float(a)
    if f <= 0.0:
        return 0.0
    if f >= 1.0:
        return 1.0
    alvo = f * math.pi
    lo, hi = 0.0, 2.0
    for _ in range(carregar("equipment/comum/stewart_arnold.toml")["segmento"]["passos_bissecao"]):
        u = 0.5 * (lo + hi)
        if _segment_area(u) < alvo:
            lo = u
        else:
            hi = u
    return 0.5 * (lo + hi) / 2.0


def beta_coefficient(aw_over_a):
    """β = h_o/d num vaso meio cheio = 0,5 − h_w/d; extremos exatos (sem 1e-16)."""
    f = float(aw_over_a)
    if f <= 0.0:
        return 0.5
    if f >= 0.5:
        return 0.0
    return 0.5 - segment_height_fraction(f)


def water_area_fraction(q_o, q_w, tr_o, tr_w):
    """Eq. (18): Aw/A = 0,5·Qw(tr)w / ((tr)oQo + (tr)wQw)."""
    denom = tr_o * q_o + tr_w * q_w
    if denom <= 0:
        return 0.0
    return 0.5 * (q_w * tr_w) / denom
