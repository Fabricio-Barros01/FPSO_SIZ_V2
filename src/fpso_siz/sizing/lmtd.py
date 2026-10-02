"""ΔT médio logarítmico e fator F do arranjo 1 casco / 2 passes (Saari, Eqs. 4.6 e Fig. 4.3).

Ficam aqui, e não no método do trocador, porque DIMENSIONAMENTO e RATING usam as MESMAS duas
funções: o método (`sizing/trocador.py`) resolve a área para um Q dado, o rating
(`sizing/rating.py`) resolve o Q para uma área dada, e as duas contas precisam da mesma
ΔT_lm e do mesmo F. Separar evita que o solver de off-design dependa do método — e é uma
física só, exercitada pelos dois caminhos.
"""
import math

from fpso_siz.core.configuracao import carregar


def _t():
    return carregar("equipment/comum/trocador.toml")


def lmtd(dt1, dt2):
    """ΔT médio logarítmico (Eq. 4.6); NaN se algum ΔT ≤ 0 (cruzamento)."""
    if not (math.isfinite(dt1) and math.isfinite(dt2) and dt1 > 0 and dt2 > 0):
        return math.nan
    r = dt1 / dt2
    if abs(r - 1.0) <= _t()["singularidades"]["tol_lmtd"]:
        return float(dt1)
    return (dt1 - dt2) / math.log(r)


def f_correction_1_2(p, r):
    """Fator F do arranjo 1 casco / 2 passes (Fig. 4.3); R = 1 é limite removível."""
    if not (math.isfinite(p) and math.isfinite(r)):
        return math.nan
    if p <= 0:
        return 1.0
    if p >= 1 or r * p >= 1:
        return math.nan
    s = math.sqrt(1 + r * r)
    den_log = (2 - p * (1 + r - s)) / (2 - p * (1 + r + s))
    if not (math.isfinite(den_log) and den_log > 0):
        return math.nan
    if abs(r - 1.0) <= _t()["singularidades"]["tol_f_r1"]:
        return math.sqrt(2.0) * (p / (1 - p)) / math.log(den_log)
    return s * math.log((1 - r * p) / (1 - p)) / ((1 - r) * math.log(den_log))
