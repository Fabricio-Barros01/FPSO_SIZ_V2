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


def leakage_areas(g):
    """(A_sb, A_tb, A_w) — Eq. 2-24 (meio ângulo), 2-25 e 2-26 (ângulo inteiro)."""
    if not g.d_s > 0:
        return math.nan, math.nan, math.nan
    c = _clamp(1 - 2 * g.l_c / g.d_s, -1.0, 1.0)
    t1 = math.acos(c)
    a_sb = 0.5 * (math.pi - t1) * g.d_s * g.d_sb
    t2 = 2 * math.acos(c)
    a_wg = (g.d_s * g.d_s) / 8 * (t2 - math.sin(t2))
    c1 = g.d_s - g.d_otl
    den = g.d_s - c1
    t3 = 2 * math.acos(_clamp((g.d_s - 2 * g.l_c) / den, -1.0, 1.0)) if den > 0 else 0.0
    f_w = (t3 - math.sin(t3)) / (2 * math.pi)
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
