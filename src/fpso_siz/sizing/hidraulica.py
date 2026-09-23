"""Hidráulica de tubo para a bomba (Moran, 2016): Reynolds, Colebrook-White, regime,
Darcy-Weisbach, perdas localizadas e Antoine. Port de sizing/pump/hydraulics.jl.

Fora das faixas em que a fonte declara as correlações o resultado é marcado como NÃO
confiável: laminar (f = 64/Re, exata) até 2300; Colebrook-White a partir de 4000; a
transição fica sem correlação e o motor recusa o ponto.
"""
import math

from fpso_siz.core.configuracao import carregar
from fpso_siz.core.ieee import div
from fpso_siz.core.unidades import BAR_PA


def _cw():
    return carregar("equipment/comum/hidraulica.toml")["colebrook"]


def reynolds_pipe(rho, v, d_m, mu):
    return rho * v * d_m / mu


def colebrook_white(re, rel_rough, f0=None, tol=None, maxiter=None):
    """(f de Darcy, convergiu). Iteração em x = 1/√f."""
    if not (math.isfinite(re) and re > 0):
        return math.nan, False
    k = _cw()
    it = carregar("equipment/comum/hidraulica.toml")["colebrook_iteracao"]
    f0 = it["f0"] if f0 is None else f0
    tol = it["tolerancia"] if tol is None else tol
    maxiter = it["max_iteracoes"] if maxiter is None else maxiter
    x = 1.0 / math.sqrt(f0)
    for _ in range(maxiter):
        novo = -k["coef_log"] * math.log10(rel_rough / k["div_rugosidade"] + k["coef_re"] * x / re)
        if not novo > 0:
            return math.nan, False
        if abs(novo - x) <= tol * max(1.0, abs(novo)):
            return 1.0 / (novo * novo), True
        x = novo
    return 1.0 / (x * x), False


def flow_regime(re, k):
    """(regime, correlação confiável?) com as fronteiras do TOML do método."""
    if not (math.isfinite(re) and re > 0):
        return "indefinido", False
    if re <= float(k["reynolds_laminar_max"]):
        return "laminar", True
    if re >= float(k["reynolds_turbulent_min"]):
        return "turbulento", True
    return "transicao", False


def friction_equation(regime):
    """(equação citada, forma) — o memorial credita a correlação que de fato produziu f."""
    if regime == "laminar":
        return "Hagen", "f = 64/Re — Hagen-Poiseuille, exata no laminar; NÃO consta do artigo"
    if regime == "indefinido":
        return "—", "regime indefinido: Re não é número positivo"
    return "Eq. 2", "1/√f = −2log₁₀(ε/3,7D + 2,51/(Re√f)) — Colebrook-White"


def darcy_friction(re, rel_rough, k):
    """(f, regime, confiável)."""
    regime, confiavel = flow_regime(re, k)
    if regime == "indefinido":
        return math.nan, regime, False
    if regime == "laminar":
        return float(k["laminar_coefficient"]) / re, regime, confiavel
    f, ok = colebrook_white(re, rel_rough, f0=float(k["colebrook_initial"]), tol=float(k["colebrook_tolerance"]),
                            maxiter=int(k["colebrook_max_iter"]))
    if not ok:
        return f, "nao_convergiu", False
    return f, regime, confiavel


def straight_run_head(f, l_m, d_m, v, g):
    """Darcy-Weisbach: f·(L/D)·v²/2g."""
    return f * (l_m / d_m) * (v * v) / (2 * g) if d_m > 0 else math.inf


def fittings_head(k_total, v, g):
    return k_total * (v * v) / (2 * g)


def antoine_pressure(a, b, c, t_k):
    """Pv [Pa] pela forma do NIST: log₁₀(Pv[bar]) = A − B/(T + C)."""
    try:
        return 10.0 ** (a - div(b, t_k + c)) * BAR_PA
    except OverflowError:   # o Julia dá Inf
        return math.inf
