"""Propriedades de fluido e correlações do balanço preliminar (funções puras)."""
import math

from fpso_siz.core.unidades import c_para_f


def poco_do_fluido(dados, fluido):
    """Poço de origem do fluido pelo pseudocomponente pesado (premissa P-07)."""
    c = dados.composicoes[fluido]
    a, b = c.get("C20+", 0) > 0, c.get("C20++", 0) > 0
    if a == b:
        raise ValueError(f"fluido {fluido!r}: exatamente um de C20+ / C20++ deve ser positivo")
    return dados.c20["C20+" if a else "C20++"]["well"]


def gas_props(composicao, const, VM):
    """Gás = corte N2–nC4 da composição global, renormalizado (P-03)."""
    leves = list(const.MW)
    s = sum(composicao[k] for k in leves)
    y = {k: composicao[k] / s for k in leves}
    mw = sum(y[k] * const.MW[k] for k in leves)
    cpm = sum(y[k] * const.cp0[k] for k in leves)
    return dict(y=y, frac_lights=s, MW=mw, cp=cpm / mw, gamma=mw / const.MW_ar,
                rho_std=mw / VM, xsum=sum(composicao.values()))


def standing_rs(P_kPa, T_C, gamma, api, k):
    """Razão de solubilidade de Standing, em Sm³/Sm³ (`k`: coeficientes Standing)."""
    P = P_kPa / k.kPa_por_psia
    TF = c_para_f(T_C)
    rs = gamma * ((P / k.a + k.b) * 10 ** (k.c_api * api - k.c_T * TF)) ** k.expoente
    return rs * k.Sm3_Sm3_por_scf_bbl


def mu_interp(tabela, T):
    """Viscosidade por interpolação log-linear em T; fora da tabela, valor do extremo (P-40).
    Devolve (mu, marcador)."""
    (t_min, mu_min), (t_max, mu_max) = tabela[0], tabela[-1]
    if T <= t_min:
        return mu_min, f"extrapolado<{t_min}"
    if T >= t_max:
        return mu_max, f"limitado a {t_max} °C"
    for (t0, m0), (t1, m1) in zip(tabela, tabela[1:]):
        if t0 <= T <= t1:
            return math.exp(math.log(m0) + (math.log(m1) - math.log(m0)) * (T - t0) / (t1 - t0)), "interp."
    # inalcançável: com t_min < T < t_max, algum par consecutivo cerca T
    raise ValueError(f"tabela de viscosidade inválida em T = {T}")  # pragma: no cover


def split_water(O_in_v, w_in_v, bsw, C_OiW, rhoO, n_iter, extra_oil_v=0.0):
    """Divide a fase aquosa de um separador O/A em base volumétrica padrão.

    O BSW é imposto sobre o óleo que efetivamente sai na corrente de óleo (descontados o
    óleo disperso na água e eventual arraste), por iteração curta de `n_iter` passos.
    Devolve (água no óleo, água removida, óleo na água), em m³/d.
    """
    Ov = max(O_in_v - extra_oil_v, 0.0)
    w_keep = w_rem = oil_w = 0.0
    for _ in range(n_iter):
        w_keep = min(bsw / (1 - bsw) * Ov, w_in_v) if bsw < 1 else w_in_v
        w_rem = w_in_v - w_keep
        oil_w = C_OiW * w_rem / rhoO
        Ov = max(O_in_v - extra_oil_v - oil_w, 0.0)
    return w_keep, w_rem, oil_w
