"""Coeficiente do lado do casco por Bell-Delaware — Branan (2012), cap. 2, com estrutura
conferida contra Toledo-Velázquez et al. (2014). Port de sizing/exchanger/bell_delaware.jl.

    h_o = h_ideal · Jc · Jl · Jb · Js · Jr

Correções de janela (Jc), vazamento (Jl), desvio pelo vão (Jb), pontas de chicana (Js) e
gradiente laminar (Jr). Coeficientes das tabelas no TOML do método; os que o Julia tinha
no código estão em equipment/comum/trocador.toml.
"""
import math
from dataclasses import dataclass

from fpso_siz.core.configuracao import carregar


def _t():
    return carregar("equipment/comum/trocador.toml")


@dataclass(frozen=True)
class ShellGeometry:
    d_s: float      # diâmetro interno do casco, m
    d_otl: float    # limite externo do feixe, m
    d_o: float      # diâmetro externo do tubo, m
    p_t: float      # passo do feixe, m
    p_n: float      # passo normal ao escoamento, m
    p_p: float      # passo paralelo ao escoamento, m
    l_c: float      # corte da chicana (altura da janela), m
    l_bc: float     # espaçamento central de chicana, m
    d_sb: float     # folga diametral casco-chicana, m
    d_tb: float     # folga furo-tubo, m
    n_t: float      # tubos no total
    n_ss: float     # pares de faixas de vedação
    n_dp: float     # faixas divisoras paralelas ao escoamento
    w_p: float      # largura da faixa divisora, m
    layout: int     # 30 | 45 | 60 | 90


def _clamp(x, lo, hi):
    return min(max(x, lo), hi)


def baffle_clearance(d_s_mm, k):
    """Folga casco-chicana [mm] da Tabela 2-7, em degraus pelo diâmetro do casco."""
    tetos, folgas = [float(t) for t in k["folga_dn_max"]], [float(f) for f in k["folga_chicana"]]
    i = next((i for i, t in enumerate(tetos) if d_s_mm <= t), len(folgas) - 1)
    return folgas[i]


def layout_pitches(layout, p_t, k):
    """(p_n, p_p, limiar diagonal) da Tabela 2-6."""
    lays = [int(x) for x in k["layouts"]]
    if int(layout) not in lays:
        return float(p_t), float(p_t), 0.0
    i = lays.index(int(layout))
    return float(k["pn_sobre_pt"][i]) * p_t, float(k["pp_sobre_pt"][i]) * p_t, float(k["limiar_diagonal"][i])


def crossflow_area(g, k):
    """Área de escoamento cruzado no centro do casco (Eq. 2-19)."""
    if not (g.p_n > 0 and g.l_bc > 0):
        return math.nan
    limiar = layout_pitches(g.layout, g.p_t, k)[2]
    p_ref = g.p_t if (limiar > 0 and g.p_t / g.d_o < limiar) else g.p_n
    return g.l_bc * ((g.d_s - g.d_otl) + (g.d_otl - g.d_o) * (p_ref - g.d_o) / g.p_n)


def shell_reynolds(d_o, w_s, mu_s, a_s):
    return d_o * w_s / (mu_s * a_s) if (a_s > 0 and mu_s > 0) else math.nan


def colburn_ideal(re_s, layout, p_t, d_o, k):
    """j ideal (Eq. 2-21, Tabela 2-5)."""
    if not (math.isfinite(re_s) and re_s > 0 and d_o > 0):
        return math.nan
    lays = [int(x) for x in k["layouts"]]
    if int(layout) not in lays:
        return math.nan
    il = lays.index(int(layout))
    tetos = [float(t) for t in k["re_max"]]
    ir = next((i for i, t in enumerate(tetos) if re_s <= t), len(tetos) - 1)
    a1 = float(k[f"a1_{int(layout)}"][ir])
    a2 = float(k[f"a2_{int(layout)}"][ir])
    a3 = float(k["a3"][il])
    a4 = float(k["a4"][il])
    c = _t()["colburn"]
    a = a3 / (1 + c["coef_a"] * re_s ** a4)
    return a1 * (c["base_passo"] / (p_t / d_o)) ** a * re_s ** a2


def h_ideal(j, cp_s, w_s, a_s, k_s, mu_s, mu_ratio=1.0):
    """h ideal de feixe (Eq. 2-19)."""
    if not (math.isfinite(j) and j > 0 and a_s > 0 and cp_s > 0 and k_s > 0 and mu_s > 0):
        return math.nan
    c = _t()["casco"]
    pr_term = (k_s / (cp_s * mu_s)) ** c["expoente_prandtl"]
    return j * cp_s * (w_s / a_s) * pr_term * mu_ratio ** c["expoente_viscosidade"]


def j_baffle_cut(g, k):
    """Jc = a + b·Fc (Eq. 2-22)."""
    if not g.d_otl > 0:
        return math.nan
    phi = _clamp((g.d_s - 2 * g.l_c) / g.d_otl, -1.0, 1.0)
    ac = math.acos(phi)
    fc = (math.pi + 2 * phi * math.sin(ac) - 2 * ac) / math.pi
    return float(k["jc_a"]) + float(k["jc_b"]) * fc


def _janela(g):
    """(θ1 meio ângulo, θ2 ângulo da janela, f_w fração de tubos na janela) — Eq. 2-24 a 2-26."""
    c = _clamp(1 - 2 * g.l_c / g.d_s, -1.0, 1.0)
    c1 = g.d_s - g.d_otl
    den = g.d_s - c1
    t3 = 2 * math.acos(_clamp((g.d_s - 2 * g.l_c) / den, -1.0, 1.0)) if den > 0 else 0.0
    return math.acos(c), 2 * math.acos(c), (t3 - math.sin(t3)) / (2 * math.pi)


def leakage_areas(g):
    """(A_sb, A_tb, A_w) — Eq. 2-24 (meio ângulo), 2-25 e 2-26 (ângulo inteiro)."""
    if not g.d_s > 0:
        return math.nan, math.nan, math.nan
    t1, t2, f_w = _janela(g)
    a_sb = 0.5 * (math.pi - t1) * g.d_s * g.d_sb
    a_wg = (g.d_s * g.d_s) / 8 * (t2 - math.sin(t2))
    a_tb = math.pi * g.d_o * (1 - f_w) * g.n_t * g.d_tb / 4
    a_wt = math.pi / 4 * (f_w * g.n_t) * (g.d_o * g.d_o)
    return a_sb, a_tb, a_wg - a_wt


def j_leakage(a_sb, a_tb, a_w, k):
    """Jl (Eq. 2-23; 0,44 no segundo colchete, não os 0,044 impressos)."""
    s = a_sb + a_tb
    if not (math.isfinite(s) and s > 0 and math.isfinite(a_w) and a_w > 0):
        return math.nan
    ra = a_sb / s
    rb = s / a_w
    base = float(k["jl_a"]) * (1 - ra)
    return base + (1 - base) * math.exp(-float(k["jl_b"]) * rb)


def j_bypass(g, a_s, re_s, k):
    """Jb (Eq. 2-27); vedação suficiente (z ≥ 0,5) bloqueia o desvio."""
    if not (math.isfinite(a_s) and a_s > 0 and g.p_p > 0):
        return math.nan
    n_rcc = (g.d_s - 2 * g.l_c) / g.p_p
    if not n_rcc > 0:
        return math.nan
    z = g.n_ss / n_rcc
    if z >= 0.5:
        return 1.0
    a_bp = g.l_bc * (g.d_s - g.d_otl + 0.5 * g.n_dp * g.w_p)
    rc = a_bp / a_s
    c = float(k["jb_c_laminar"]) if re_s <= float(k["jb_re_corte"]) else float(k["jb_c_turbulento"])
    return math.exp(-c * rc * (1 - math.cbrt(2 * z)))


def j_spacing(n_b, l_bi, l_bo, l_bc, laminar, k):
    """Js (Eq. 2-28): pontas de chicana mais espaçadas que o vão central."""
    if not (l_bc > 0 and n_b >= 1):
        return 1.0
    li, lo = l_bi / l_bc, l_bo / l_bc
    n = float(k["js_n_laminar"]) if laminar else float(k["js_n_turbulento"])
    den = n_b - 1 + li + lo
    if not den > 0:
        return 1.0
    return (n_b - 1 + li ** (1 - n) + lo ** (1 - n)) / den


def j_laminar(re_s, g, k):
    """Jr (Eq. 2-29): só abaixo de Re 100; constante abaixo de 20; contínuo nas fronteiras."""
    lo, hi = float(k["jr_re_min"]), float(k["jr_re_max"])
    if not (math.isfinite(re_s) and re_s > 0):
        return math.nan
    if re_s >= hi:
        return 1.0
    if not g.p_p > 0:
        return math.nan
    n_rcc = (g.d_s - 2 * g.l_c) / g.p_p
    if not n_rcc > 0:
        return math.nan
    jr20 = min((10 / n_rcc) ** float(k["jr_expoente"]), 1.0)
    if re_s <= lo:
        return jr20
    return jr20 + (1 - jr20) * (re_s - lo) / (hi - lo)


@dataclass(frozen=True)
class Fatores:
    jc: float = math.nan
    jl: float = math.nan
    jb: float = math.nan
    js: float = math.nan
    jr: float = math.nan
    produto: float = math.nan
    h_ideal: float = math.nan
    re: float = math.nan
    a_s: float = math.nan


@dataclass(frozen=True)
class FeixeIdeal:
    """A parte de Bell-Delaware que NÃO depende do número de chicanas.

    Das cinco correções da Eq. 2-18, **só Js (Eq. 2-28) é função de n_b**; Jc, Jl, Jb e Jr
    dependem apenas da geometria do casco e do Reynolds, e h_ideal, Re e A_s idem. Quem resolve
    o ponto fixo em L varia n_b a cada passagem — e por isso pode avaliar isto UMA vez e
    recombinar só Js. A separação é da estrutura de dependência das equações, não um cache: o
    resultado é o mesmo termo a termo, na mesma ordem de multiplicação."""
    a_s: float = math.nan
    re: float = math.nan
    h_ideal: float = math.nan
    jc: float = math.nan
    jl: float = math.nan
    jb: float = math.nan
    jr: float = math.nan
    falhou: str = ""          # "" = utilizável; senão, em que passo a conta parou


def feixe_ideal(g, w_s, cp_s, mu_s, k_s, k):
    """Tudo o que a Eq. 2-18 pede menos Js, para uma geometria e um escoamento de casco."""
    a_s = crossflow_area(g, k)
    if not (math.isfinite(a_s) and a_s > 0):
        return FeixeIdeal(falhou="area_de_escoamento_cruzado")
    re = shell_reynolds(g.d_o, w_s, mu_s, a_s)
    if not (math.isfinite(re) and re > 0):
        return FeixeIdeal(falhou="reynolds_do_casco")
    j = colburn_ideal(re, g.layout, g.p_t, g.d_o, k)
    hi = h_ideal(j, cp_s, w_s, a_s, k_s, mu_s)
    if not (math.isfinite(hi) and hi > 0):
        return FeixeIdeal(falhou="h_ideal")
    jc = j_baffle_cut(g, k)
    a_sb, a_tb, a_w = leakage_areas(g)
    jl = j_leakage(a_sb, a_tb, a_w, k)
    jb = j_bypass(g, a_s, re, k)
    jr = j_laminar(re, g, k)
    return FeixeIdeal(a_s, re, hi, jc, jl, jb, jr)


def com_chicanas(feixe, n_b, l_bi, l_bo, l_bc, k):
    """(h_o, fatores, ok) do feixe já avaliado, para um número de chicanas.

    É o único passo que o ponto fixo em L precisa refazer."""
    if feixe.falhou:
        return math.nan, Fatores(), False
    js = j_spacing(n_b, l_bi, l_bo, l_bc, feixe.re <= float(k["jb_re_corte"]), k)
    jc, jl, jb, jr, hi = feixe.jc, feixe.jl, feixe.jb, feixe.jr, feixe.h_ideal
    todos = (jc, jl, jb, js, jr)
    if not all(math.isfinite(x) and x > 0 for x in todos):
        return math.nan, Fatores(jc, jl, jb, js, jr, math.nan, hi, feixe.re, feixe.a_s), False
    produto = jc * jl * jb * js * jr
    return hi * produto, Fatores(jc, jl, jb, js, jr, produto, hi, feixe.re, feixe.a_s), True


def bell_delaware(g, w_s, cp_s, mu_s, k_s, n_b, l_bi, l_bo, k):
    """(h_o, fatores, ok). Avalia o feixe e combina com o número de chicanas, numa passagem."""
    return com_chicanas(feixe_ideal(g, w_s, cp_s, mu_s, k_s, k), n_b, l_bi, l_bo, g.l_bc, k)


# ------------------------------------------------------------------ perda de carga do casco
def _faixa_re(re_s, k):
    tetos = [float(t) for t in k["re_max"]]
    return next((i for i, t in enumerate(tetos) if re_s <= t), len(tetos) - 1)


def _dp():
    return carregar("equipment/comum/bell_delaware_dp.toml")


def friction_ideal(re_s, layout, p_t, d_o, k):
    """(f_ideal, validado) do feixe ideal — Eq. 2-32 com os b da Tabela 2-5. `validado` é falso
    nas faixas que o TOML declara não validadas (`b_nao_validado`): o valor IMPRESSO é usado,
    e quem consome o resultado não pode aprová-lo nem reprová-lo."""
    if not (math.isfinite(re_s) and re_s > 0 and d_o > 0):
        return math.nan, False
    lays = [int(x) for x in k["layouts"]]
    if int(layout) not in lays:
        return math.nan, False
    il, ir = lays.index(int(layout)), _faixa_re(re_s, k)
    d = _dp()
    b1, b2 = float(d[f"b1_{int(layout)}"][ir]), float(d[f"b2_{int(layout)}"][ir])
    b = float(d["b3"][il]) / (1 + float(d["coef_b"]) * re_s ** float(d["b4"][il]))
    f = b1 * (_t()["colburn"]["base_passo"] / (p_t / d_o)) ** b * re_s ** b2
    validado = [int(layout), ir] not in [[int(a), int(i)] for a, i in d["b_nao_validado"]]
    return f, validado


@dataclass(frozen=True)
class PerdaCasco:
    """ΔP de UM casco, entre os bocais (Eq. 2-38 exclui os bocais), e as parcelas."""
    dp: float = math.nan            # Pa
    dp_cruzado_ideal: float = math.nan
    dp_janela_ideal: float = math.nan
    f_ideal: float = math.nan
    rb: float = math.nan
    rl: float = math.nan
    n_rcc: float = math.nan
    n_rtw: float = math.nan
    n_tw: float = math.nan
    re: float = math.nan
    validado: bool = False
    motivo: str = ""


def perda_carga_casco(g, w_s, rho_s, mu_s, n_b, k, mu_ratio=1.0):
    """ΔP do lado casco de UM casco por Bell-Delaware (Branan 2012, Eq. 2-32 a 2-38), com as
    divergências 6 a 11 do TOML (`equipment/comum/bell_delaware_dp.toml`): A_s² na 2-33 e Ws²
    na 2-36/2-37 (a forma impressa não tem dimensão de pressão), as duas faixas da Tabela 2-5
    não validadas e n_r,tw (fileiras na janela) no lugar de n_tw na 2-36.

    ΔP_s = [(n_b − 1)·ΔP_b,ideal·R_b + n_b·ΔP_w,ideal]·R_l + 2·ΔP_b,ideal·R_b·(1 + n_r,tw/n_r,cc)

    Os vãos de entrada e saída são os do vão central (mesma premissa de Js = 1), e os bocais
    não entram."""
    if not (rho_s > 0 and mu_s > 0 and w_s > 0 and n_b >= 1):
        return PerdaCasco(motivo="sem ρ, µ ou vazão do casco")
    a_s = crossflow_area(g, k)
    re = shell_reynolds(g.d_o, w_s, mu_s, a_s)
    if not (math.isfinite(a_s) and a_s > 0 and math.isfinite(re) and re > 0):
        return PerdaCasco(motivo="área de escoamento cruzado ou Reynolds do casco indefinidos")
    f, validado = friction_ideal(re, g.layout, g.p_t, g.d_o, k)
    k = {**k, **_dp()}   # constantes das Eq. 2-33 a 2-38 (as do coeficiente de troca seguem em `k`)
    n_rcc = (g.d_s - 2 * g.l_c) / g.p_p if g.p_p > 0 else math.nan
    a_sb, a_tb, a_w = leakage_areas(g)
    _t1, t2, f_w = _janela(g)
    n_tw = f_w * g.n_t
    n_rtw = float(k["nrtw_coef"]) * (g.l_c - float(k["nrtw_meio"]) * (g.d_s - g.d_otl + g.d_o)) / g.p_p
    if not (math.isfinite(f) and n_rcc > 0 and a_w > 0 and a_sb + a_tb > 0):
        return PerdaCasco(f_ideal=f, re=re, n_rcc=n_rcc, validado=validado, motivo="geometria da janela indefinida")
    expo = _t()["casco"]["expoente_viscosidade"]
    dp_b = float(k["dpb_coef"]) * f * w_s * w_s * n_rcc / (2 * rho_s * a_s * a_s) * mu_ratio ** expo   # 2-33
    z = g.n_ss / n_rcc                                                                                   # 2-34
    if z >= float(k["rb_zeta_max"]):
        rb = 1.0
    else:
        rc = g.l_bc * (g.d_s - g.d_otl + 0.5 * g.n_dp * g.w_p) / a_s
        cbp = float(k["rb_c_laminar"]) if re <= float(k["jb_re_corte"]) else float(k["rb_c_turbulento"])
        rb = math.exp(-cbp * rc * (1 - math.cbrt(2 * z)))
    ra, rb_vaz = a_sb / (a_sb + a_tb), (a_sb + a_tb) / a_w                                                # 2-35
    c = float(k["rl_c_a"]) * (1 + ra) + float(k["rl_c_b"])
    rl = math.exp(-float(k["rl_a"]) * (1 + ra) * rb_vaz ** c)
    if re >= float(k["dpw_re_corte"]):                                                                   # 2-36
        # divergência 11: o 0,6 é por FILEIRA cruzada na janela (n_r,tw), não por tubo (n_tw)
        dp_w = w_s * w_s * (float(k["dpw_base"]) + float(k["dpw_coef"]) * n_rtw) / (2 * a_s * a_w * rho_s)
    else:                                                                                                # 2-37
        d_w = float(k["dw_coef"]) * a_w / (math.pi * g.d_o * n_tw + g.d_s * t2 / 2)
        dp_w = (float(k["dpw_laminar_coef"]) * mu_s * w_s / (math.sqrt(a_s * a_w) * rho_s)
                * (n_rtw / (g.p_t - g.d_o) + g.l_bc / (d_w * d_w)) + w_s * w_s / (a_s * a_w * rho_s))
    dp = ((n_b - 1) * dp_b * rb + n_b * dp_w) * rl + 2 * dp_b * rb * (1 + n_rtw / n_rcc)                # 2-38
    return PerdaCasco(dp, dp_b, dp_w, f, rb, rl, n_rcc, n_rtw, n_tw, re, validado,
                      "" if validado else "coeficiente b da Tabela 2-5 numa faixa não validada")
