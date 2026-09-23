"""F7 — casos-ouro portados do Julia: Moran (2016) e Saari (LUT) + Bell-Delaware (Branan).
Port de test/golden_moran.jl e test/golden_saari.jl."""
import copy
import math
from dataclasses import replace

import pytest

from fpso_siz.core import unidades as U
from fpso_siz.core.parametros import defaults, with_defaults
from fpso_siz.core.trace import Rastro
from fpso_siz.sizing import CentrifugalPump, MoranPumpSizing, SaariLMTD, ShellTubeExchanger
from fpso_siz.sizing import bell_delaware as BD
from fpso_siz.sizing.bomba import _hidraulica
from fpso_siz.sizing.hidraulica import (antoine_pressure, colebrook_white, darcy_friction, fittings_head,
                                        reynolds_pipe, straight_run_head)
from fpso_siz.sizing.trocador import (_tubo, effectiveness_ntu_counterflow, f_correction_1_2, lmtd,
                                      nusselt_dittus_boelter, overall_u)

isclose = math.isclose
M, EQ = MoranPumpSizing(), CentrifugalPump()
KB = M.constants()
S, TX = SaariLMTD(), ShellTubeExchanger()
KT = S.constants()
KBD = KT["bell_delaware"]


def ordenado(xs, rev=False):
    return list(xs) == sorted(xs, reverse=rev)


# ================================================================ Moran — hidráulica
def test_antoine_tabela_3():
    pv = antoine_pressure(5.40221, 1838.675, -31.737, 303.15)
    assert isclose(pv, 4243.81, rel_tol=1e-4)
    p = defaults(M.parameters())
    assert isclose(antoine_pressure(p["antoine_a"], p["antoine_b"], p["antoine_c"], 303.15), pv)
    assert ordenado([antoine_pressure(5.40221, 1838.675, -31.737, 283.15 + 10 * i) for i in range(9)])
    assert isclose(antoine_pressure(5.40221, 1838.675, -31.737, 373.15), 101325.0, rel_tol=0.05)


def test_colebrook_white():
    for re, rel in ((1e4, 1e-4), (1e5, 1e-3), (1e6, 1e-5), (5e6, 1e-2)):
        f, ok = colebrook_white(re, rel)
        assert ok and abs(1 / math.sqrt(f) + 2 * math.log10(rel / 3.7 + 2.51 / (re * math.sqrt(f)))) < 1e-8
    assert colebrook_white(1e6, 0.0)[0] < colebrook_white(1e5, 0.0)[0]
    fa, fb = colebrook_white(1e7, 0.02)[0], colebrook_white(1e8, 0.02)[0]
    assert isclose(fa, fb, rel_tol=5e-3) and isclose(1 / math.sqrt(fa), -2 * math.log10(0.02 / 3.7), rel_tol=5e-3)
    assert ordenado([colebrook_white(1e5, r)[0] for r in (0.0, 1e-5, 1e-4, 1e-3, 1e-2)])
    for re in (0.0, -1.0, math.nan, math.inf):
        assert not colebrook_white(re, 1e-4)[1]
    assert colebrook_white(1e5, 1e-4, maxiter=1) [1] is False


def test_regimes_de_escoamento():
    for re in (100.0, 1000.0, 2000.0):
        f, regime, confiavel = darcy_friction(re, 1e-4, KB)
        assert regime == "laminar" and confiavel and isclose(f, 64 / re)
    f, regime, confiavel = darcy_friction(3000.0, 1e-4, KB)
    assert regime == "transicao" and not confiavel and math.isfinite(f)
    assert darcy_friction(5e4, 1e-4, KB)[1:] == ("turbulento", True)
    assert darcy_friction(math.nan, 1e-4, KB)[1] == "indefinido"
    assert (KB["reynolds_laminar_max"], KB["reynolds_turbulent_min"], KB["laminar_coefficient"]) == (2300.0, 4000.0, 64.0)


def test_figura_3_do_artigo():
    re = reynolds_pipe(999.7, 1.0, 0.025, 1.307e-3)
    f, regime, _ = darcy_friction(re, 0.0015 / 25, KB)
    h = straight_run_head(f, 100.0, 0.025, 1.0, 9.81)
    assert regime == "turbulento" and 4.0 < re / 1000 < 30.0 and isclose(h, 6.0, rel_tol=0.20) and 5.0 < h < 6.5


def test_darcy_weisbach_e_k_values():
    h1 = straight_run_head(0.02, 100.0, 0.1, 1.0, 9.81)
    assert isclose(straight_run_head(0.02, 100.0, 0.1, 2.0, 9.81), 4 * h1)
    assert isclose(straight_run_head(0.02, 200.0, 0.1, 1.0, 9.81), 2 * h1)
    assert isclose(straight_run_head(0.02, 100.0, 0.05, 1.0, 9.81), 2 * h1)
    assert straight_run_head(0.02, 100.0, 0.0, 1.0, 9.81) == math.inf
    assert isclose(fittings_head(10.8, 2.0, 9.81), 4 * fittings_head(10.8, 1.0, 9.81))
    p = defaults(M.parameters())
    assert isclose(p["k_recalque"], 10.8 + 1.0 + 0.4 + 4 * 0.4) and isclose(p["k_sucao"], 0.5 + 0.4 + 3 * 0.4)


def test_antoine_com_t_mais_c_nulo_e_zero_como_no_julia():
    assert antoine_pressure(5.40221, 1838.675, -31.737, 31.737) == 0.0   # b/0 = Inf ⇒ 10^−Inf = 0


def test_potencia_de_eixo():
    kw = U.potencia_hidraulica_kw(998.0, 100.0, 50.0, 0.7, 9.81)
    assert isclose(kw, 998.0 * 9.81 * (100.0 / 3600) * 50.0 / 0.7 / 1000) and isclose(kw, 19.4, rel_tol=0.01)


# ================================================================ Moran — método
def bomba_defaults():
    return defaults(M.stream_parameters()) | defaults(M.parameters())


def restricoes(vals):
    ok, cons, tr = M.sizing_constraints(M.case_input(vals), with_defaults(M.parameters(), vals), KB)
    return ok, cons, tr


def test_bomba_atravessa_o_motor():
    vals = bomba_defaults()
    res = M.size_equipment(EQ, M.case_input(vals), vals)
    assert res.feasible and vals["v_min"] <= res.derivados["v"] <= vals["v_max"] and res.derivados["folga_npsh"] >= 0
    assert res.x == min(r.x for r in res.sweep if r.ok)
    assert isclose(res.y, res.derivados["h_est"] + res.derivados["h_atrito"])
    assert {"estatica", "npsh", "selection"} <= set(res.trace.block_order())
    serie = [float(d) for d in KB["nominal_diameters"]]
    eixo = M.sweep_axis(vals).values
    assert set(eixo) <= set(serie) and ordenado(eixo) and len({b - a for a, b in zip(eixo, eixo[1:])}) > 1


def test_carga_estatica_negativa_e_resultado():
    ok, cons, _ = restricoes(bomba_defaults() | {"pressure": 900.0, "p_recalque": 101.3, "h_geometrica": -5.0})
    assert ok and cons.h_est < 0


def test_cavitacao_e_diagnostico():
    vals = bomba_defaults() | {"h_sucao": -8.0, "temperature": 95.0, "npsh_requerido": 6.0}
    res = M.size_equipment(EQ, M.case_input(vals), vals)
    assert not res.feasible and "cavita" in res.message.lower() and res.sweep and not any(r.ok for r in res.sweep)


def test_transicao_e_recusada_pela_correlacao():
    vals = bomba_defaults() | {"rho_oil": 900.0, "mu_oil": 45.0}
    p = with_defaults(M.parameters(), vals)
    ok, cons, _ = restricoes(vals)
    hid = _hidraulica(cons, 125.0)
    assert ok and p["v_min"] <= hid["v"] <= p["v_max"] and hid["regime"] == "transicao" and not hid["confiavel"]
    assert not M.case_admissible(125.0, cons, p) and hid["npsh"] >= cons.npsh_exigido
    d = M.derived(125.0, hid["h_total"], "atrito", cons, KB, p)
    assert d["confiavel"] == 0.0 and d["re_min_correlacao"] == KB["reynolds_turbulent_min"]
    vals |= {"dn_min": 125.0, "dn_max": 125.0}
    res = M.size_equipment(EQ, M.case_input(vals), vals)
    msg = res.message.lower()
    assert not res.feasible and "transi" in msg and "4000" in msg.replace(".0", "") and "cavita" not in msg


@pytest.mark.parametrize("mu, regime, eq_f, trecho", [(200.0, "laminar", "Hagen", "NÃO consta do artigo"),
                                                      (None, "turbulento", "Eq. 2", "Colebrook-White")])
def test_memorial_credita_a_equacao_que_produziu_f(mu, regime, eq_f, trecho):
    vals = bomba_defaults() | ({"rho_oil": 900.0, "mu_oil": mu} if mu else {})
    p = with_defaults(M.parameters(), vals)
    _, cons, _ = restricoes(vals)
    hid = _hidraulica(cons, 125.0)
    assert hid["regime"] == regime and M.case_admissible(125.0, cons, p)
    if regime == "laminar":
        assert isclose(hid["f"], 64 / hid["re"])
    tr = Rastro()
    d = M.derived(125.0, hid["h_total"], "atrito", cons, KB, p)
    M.trace_selection(tr, type("B", (), dict(x=125.0, y=hid["h_total"], derivados=d))(), p)
    linha = next(e for e in tr.entries if e.var == "f")
    assert linha.eq == eq_f and trecho in linha.formula
    assert any("regime" in e.var for e in tr.entries)


@pytest.mark.parametrize("ajuste, trecho", [
    ({"rho_oil": -1.0}, "Densidade do líquido"),
    ({"mu_oil": 0.0}, "Viscosidade do líquido"),
    ({"q_oil": 0.0}, "Vazão bombeada"),
    ({"antoine_c": -303.2}, "Antoine"),     # T + C = −0,05 K ⇒ 10^(+3,7×10⁴) estoura
])
def test_bomba_entradas_invalidas(ajuste, trecho):
    ok, msg, _ = restricoes(bomba_defaults() | ajuste)
    assert not ok and trecho in msg


def test_bomba_mensagens_de_selecao():
    vals = bomba_defaults()
    p = with_defaults(M.parameters(), vals)
    assert M.selection_message([], math.inf, p) == "A grade de diâmetros nominais ficou vazia."
    res = M.size_equipment(EQ, M.case_input(vals | {"v_min": 9.0, "v_max": 9.5}), vals | {"v_min": 9.0, "v_max": 9.5})
    assert "Nenhum diâmetro da grade mantém a velocidade na banda 9.0–9.5 m/s" in res.message
    linhas = [type("R", (), dict(derivados={"v": 1.2, "confiavel": 1.0, "folga_npsh": 2.0}))()]
    assert "A recusa não veio deste caso" in M.selection_message(linhas, math.inf, p)
    ok, msg = M.envelope_params([p | {"v_min": 2.0}, p | {"v_max": 1.0}])
    assert not ok and "v ≥ 2.0 m/s e outro v ≤ 1.0 m/s" in msg


# ================================================================ Saari — Exemplo 4.1 e funções
def test_exemplo_4_1_cadeia_inteira():
    c_h, c_c = 0.60 * 2500.0, 0.30 * 4200.0
    q = c_h * (90.0 - 40.0)
    t_co = 10.0 + q / c_c
    dtlm = lmtd(90.0 - t_co, 40.0 - 10.0)
    assert (c_h, c_c, q) == (1500.0, 1260.0, 75000.0) and isclose(t_co, 69.5, abs_tol=0.05)
    assert isclose(dtlm, 24.95, abs_tol=0.02)
    a = q / (200.0 * dtlm)
    l = a / (math.pi * 0.0334)
    assert isclose(a, 15.03, rel_tol=2e-3) and isclose(l, 143.2, rel_tol=2e-3) and math.ceil(l / 1.8) == 80
    assert math.isnan(lmtd(90.0 - 10.0, 40.0 - t_co))              # paralelo: impossível
    t_errado = 10.0 + q / (0.20 * 4200.0)                          # erratum da vazão
    assert t_errado > 90.0 and math.isnan(lmtd(90.0 - t_errado, 30.0))


def test_lmtd_e_ntu_concordam():
    for c_h, c_c, t_hi, t_ci, t_ho, u in ((1500.0, 1260.0, 90.0, 10.0, 40.0, 200.0), (4000.0, 4000.0, 120.0, 20.0, 70.0, 350.0),
                                          (2000.0, 60000.0, 150.0, 25.0, 60.0, 500.0), (900.0, 3300.0, 80.0, 15.0, 35.0, 120.0)):
        q = c_h * (t_hi - t_ho)
        t_co = t_ci + q / c_c
        area = q / (u * lmtd(t_hi - t_co, t_ho - t_ci))
        c_min, c_max = min(c_h, c_c), max(c_h, c_c)
        eps = effectiveness_ntu_counterflow(u * area / c_min, c_min / c_max)
        assert isclose(eps * c_min * (t_hi - t_ci), q, rel_tol=1e-9)
    assert effectiveness_ntu_counterflow(0.0, 0.5) == 0.0 and isclose(effectiveness_ntu_counterflow(60.0, 0.5), 1.0, rel_tol=1e-6)
    assert isclose(effectiveness_ntu_counterflow(3.0, 1.0), 0.75)
    assert isclose(effectiveness_ntu_counterflow(3.0, 1.0 - 1e-9), 0.75, rel_tol=1e-6)
    assert math.isnan(effectiveness_ntu_counterflow(-1.0, 0.5))


def test_lmtd():
    assert lmtd(30.0, 30.0) == 30.0 and isclose(lmtd(30.0 + 1e-10, 30.0), 30.0, rel_tol=1e-6)
    assert isclose(lmtd(20.5, 30.0), lmtd(30.0, 20.5))
    for a, b in ((10.0, 40.0), (5.0, 80.0), (25.0, 26.0)):
        assert min(a, b) <= lmtd(a, b) <= max(a, b) and lmtd(a, b) <= (a + b) / 2
    assert all(math.isnan(lmtd(a, b)) for a, b in ((-5.0, 30.0), (30.0, 0.0), (math.nan, 30.0)))


def test_fator_f_1_2():
    for r in (0.2, 0.5, 1.0, 2.0, 4.0):
        for p in (0.05, 0.2, 0.4):
            f = f_correction_1_2(p, r)
            if r * p < 1 and math.isfinite(f):
                assert 0 < f <= 1 + 1e-12
    assert isclose(f_correction_1_2(1e-6, 2.0), 1.0, rel_tol=1e-4)
    assert ordenado([f_correction_1_2(p, 2.0) for p in (0.05, 0.10, 0.20, 0.30)], rev=True)
    f1 = f_correction_1_2(0.3, 1.0)
    assert 0 < f1 < 1 and isclose(f_correction_1_2(0.3, 1.0 - 1e-7), f1, rel_tol=1e-4)
    assert isclose(f_correction_1_2(0.3, 1.0 + 1e-7), f1, rel_tol=1e-4)
    assert math.isnan(f_correction_1_2(1.2, 0.5)) and math.isnan(f_correction_1_2(0.9, 2.0))
    assert f_correction_1_2(0.0, 2.0) == 1.0 and math.isnan(f_correction_1_2(math.nan, 2.0))
    r1, p1 = 2.654, (40.0 - 25.0) / (110.0 - 25.0)
    t2o = 110.0 - r1 * (40.0 - 25.0)
    assert isclose(f_correction_1_2(p1, r1), f_correction_1_2((110.0 - t2o) / (110.0 - 25.0), 1 / r1), rel_tol=1e-9)


def test_u_em_serie():
    d_i, d_o, k_w = 0.01483, 0.01905, 50.0
    u = overall_u(6000.0, 500.0, 0.00018, 0.00035, d_i, d_o, k_w)
    assert 0 < u < 500.0 and 1 / u > 0.002
    assert overall_u(6000.0, 500.0, 0.0005, 0.0009, d_i, d_o, k_w) < overall_u(6000.0, 500.0, 0.0, 0.0, d_i, d_o, k_w)
    u0 = overall_u(6000.0, 500.0, 0.0, 0.0, d_i, d_o, k_w)
    assert isclose(u0, 1 / (1 / 500.0 + d_o * math.log(d_o / d_i) / (2 * k_w) + (d_o / d_i) / 6000.0))
    assert math.isnan(overall_u(6000.0, 500.0, 0.0, 0.0, d_o, d_i, k_w)) and math.isnan(overall_u(-1.0, 500.0, 0, 0, d_i, d_o, k_w))


def test_dittus_boelter():
    re, pr = 5e4, 5.0
    assert isclose(nusselt_dittus_boelter(re, pr, True, KT)[0], 0.024 * re ** 0.8 * pr ** 0.4)
    assert isclose(nusselt_dittus_boelter(re, pr, False, KT)[0], 0.026 * re ** 0.8 * pr ** 0.3)
    assert (KT["dittus_boelter_heating"], KT["dittus_boelter_cooling"]) == (0.024, 0.026)
    assert math.isnan(nusselt_dittus_boelter(-1.0, pr, True, KT)[0])
    assert not nusselt_dittus_boelter(3.0e3, pr, True, KT)[1] and nusselt_dittus_boelter(3.0e4, pr, True, KT)[1]
    assert nusselt_dittus_boelter(1.0e4, pr, True, KT)[1] and nusselt_dittus_boelter(1.2e5, pr, True, KT)[1]
    assert not nusselt_dittus_boelter(1.3e5, pr, True, KT)[1] and not nusselt_dittus_boelter(3.0e4, 0.5, True, KT)[1]


# ================================================================ Saari — método e Bell-Delaware
def trocador_defaults():
    return defaults(S.parameters())


def restr_trocador(vals, k=KT):
    return S.sizing_constraints(S.case_input(vals), with_defaults(S.parameters(), vals), k)


@pytest.fixture(scope="module")
def res_trocador():
    vals = trocador_defaults()
    return vals, S.size_equipment(TX, S.case_input(vals), vals)


def test_trocador_atravessa_o_motor(res_trocador):
    vals, res = res_trocador
    d = res.derivados
    assert res.feasible and vals["v_min"] <= d["v"] <= vals["v_max"] and d["d_casco"] <= vals["d_casco_max"]
    assert res.y <= vals["l_tubo_max"] and isclose(d["area"], min(r.derivados["area"] for r in res.sweep if r.ok))
    assert isclose(d["area"], d["q"] / (d["u"] * d["f"] * d["dt_lm"]))
    assert isclose(res.y, d["area"] / (d["n_total"] * math.pi * U.mm_para_m(vals["d_externo"])))
    assert ordenado([r.derivados["v"] for r in res.sweep], rev=True)
    assert ordenado([r.derivados["u"] for r in res.sweep], rev=True)
    assert ordenado([r.derivados["area"] for r in res.sweep])
    assert res.trace.block_order() == ["balanco", "tubo", "casco", "selection"]
    assert 0 < d["j_produto"] < 1 and len({round(r.derivados["h_casco"], 6) for r in res.sweep}) > 1


def geo_teste(d_s=0.60, corte=0.25, l_bc=0.24, layout=30, n_ss=1.0, n_t=400.0):
    d_o = 0.01905
    p_t = 1.25 * d_o
    p_n, p_p, _ = BD.layout_pitches(layout, p_t, KBD)
    folga = U.mm_para_m(BD.baffle_clearance(d_s * 1000, KBD))
    return BD.ShellGeometry(d_s, d_s - folga, d_o, p_t, p_n, p_p, corte * d_s, l_bc, folga, 0.0008, n_t, n_ss, 0.0,
                            2 * d_o, layout)


def test_tabelas_2_6_e_2_7():
    p_t = 0.0238125
    for lay, pn, pp in ((30, p_t, math.sqrt(3) / 2 * p_t), (45, math.sqrt(2) * p_t, p_t / math.sqrt(2)),
                        (60, math.sqrt(3) * p_t, p_t / 2), (90, p_t, p_t)):
        a, b, _ = BD.layout_pitches(lay, p_t, KBD)
        assert isclose(a, pn) and isclose(b, pp)
    assert isclose(BD.layout_pitches(45, p_t, KBD)[2], 1 + 1 / math.sqrt(2))
    assert isclose(BD.layout_pitches(60, p_t, KBD)[2], 2 + math.sqrt(3)) and BD.layout_pitches(30, p_t, KBD)[2] == 0.0
    assert BD.layout_pitches(15, p_t, KBD) == (p_t, p_t, 0.0)
    for dn, folga in ((300.0, 2.540), (400.0, 3.175), (500.0, 3.810), (900.0, 4.445), (1200.0, 5.715), (2000.0, 7.620)):
        assert isclose(BD.baffle_clearance(dn, KBD), folga)
    assert ordenado([BD.baffle_clearance(200.0 + 100 * i, KBD) for i in range(19)])


def test_eq_2_26_angulo_inteiro_e_2_24_meio_angulo():
    for corte in (0.15, 0.20, 0.25, 0.30, 0.35, 0.45):
        g = geo_teste(corte=corte)
        a_sb, _, a_w = BD.leakage_areas(g)
        R, u = g.d_s / 2, g.l_c / (g.d_s / 2)
        exata = R ** 2 * (math.acos(1 - u) - (1 - u) * math.sqrt(max(2 * u - u * u, 0.0)))
        t3 = 2 * math.acos(min(max((g.d_s - 2 * g.l_c) / g.d_otl, -1.0), 1.0))
        f_w = (t3 - math.sin(t3)) / (2 * math.pi)
        assert isclose(a_w + math.pi / 4 * (f_w * g.n_t) * g.d_o ** 2, exata, rel_tol=1e-9)
    g = geo_teste()
    theta = 2 * math.acos(1 - 2 * g.l_c / g.d_s)
    assert isclose(BD.leakage_areas(g)[0], (2 * math.pi - theta) / 4 * g.d_s * g.d_sb, rel_tol=1e-12)
    assert all(math.isnan(x) for x in BD.leakage_areas(replace(g, d_s=0.0)))


def test_cinco_fatores_nas_faixas_da_fonte():
    g = geo_teste()
    a_s = BD.crossflow_area(g, KBD)
    re = BD.shell_reynolds(g.d_o, 15.0, 3.0e-3, a_s)
    a_sb, a_tb, a_w = BD.leakage_areas(g)
    assert 0.50 <= BD.j_baffle_cut(g, KBD) <= 1.20 and 0.30 <= BD.j_leakage(a_sb, a_tb, a_w, KBD) <= 1.00
    assert 0.50 <= BD.j_bypass(g, a_s, re, KBD) <= 1.00 and BD.j_laminar(re, g, KBD) == 1.0
    assert ordenado([BD.j_baffle_cut(geo_teste(corte=c), KBD) for c in (0.45, 0.35, 0.25, 0.15)])
    assert isclose(BD.j_spacing(20.0, 0.3, 0.3, 0.3, False, KBD), 1.0) and BD.j_spacing(20.0, 0.6, 0.6, 0.3, False, KBD) < 1
    assert BD.j_spacing(0.5, 0.3, 0.3, 0.3, False, KBD) == 1.0
    assert BD.j_bypass(geo_teste(n_ss=40.0), a_s, re, KBD) == 1.0
    assert BD.j_bypass(geo_teste(n_ss=0.0), a_s, re, KBD) < BD.j_bypass(geo_teste(n_ss=2.0), a_s, re, KBD)
    j20 = BD.j_laminar(20.0, g, KBD)
    assert j20 < 1 and BD.j_laminar(5.0, g, KBD) == j20 and isclose(BD.j_laminar(20.0 + 1e-9, g, KBD), j20, abs_tol=1e-6)
    assert isclose(BD.j_laminar(100.0 - 1e-9, g, KBD), 1.0, abs_tol=1e-6)
    assert ordenado([BD.j_laminar(20.0 + 10 * i, g, KBD) for i in range(9)])


def test_colburn_tabela_2_5():
    p_t, d_o = 0.0238125, 0.01905
    for lay in (30, 45, 60, 90):
        js = [BD.colburn_ideal(re, lay, p_t, d_o, KBD) for re in (5.0, 50.0, 500.0, 5e3, 5e4, 5e5)]
        assert all(math.isfinite(x) and x > 0 for x in js) and ordenado(js, rev=True)
    assert all(float(a) < 0 for lay in (30, 45, 60, 90) for a in KBD[f"a2_{lay}"])
    assert isclose(BD.colburn_ideal(1e4, 30, p_t, d_o, KBD), BD.colburn_ideal(1e4, 30, p_t * 1000, d_o * 1000, KBD))
    assert math.isnan(BD.colburn_ideal(1e4, 15, p_t, d_o, KBD)) and math.isnan(BD.colburn_ideal(-1.0, 30, p_t, d_o, KBD))


def test_h_o_e_o_produto_de_branan():
    g = geo_teste()
    h_o, fat, ok = BD.bell_delaware(g, 15.0, 2100.0, 3.0e-3, 0.13, 20.0, g.l_bc, g.l_bc, KBD)
    assert ok and isclose(h_o, fat.h_ideal * fat.jc * fat.jl * fat.jb * fat.js * fat.jr) and 0.35 <= fat.produto <= 0.85
    assert h_o < fat.h_ideal
    pr_termo = (0.13 / (2100.0 * 3.0e-3)) ** (2 / 3)
    j = BD.colburn_ideal(fat.re, g.layout, g.p_t, g.d_o, KBD)
    assert isclose(fat.h_ideal, j * 2100.0 * (15.0 / fat.a_s) * pr_termo)
    h, _, ok2 = BD.bell_delaware(replace(g, p_n=0.0), 15.0, 2100.0, 3.0e-3, 0.13, 20.0, g.l_bc, g.l_bc, KBD)
    assert not ok2 and math.isnan(h)


def test_eq_2_23_jl_nunca_amplifica():
    assert (KBD["jl_a"], KBD["jl_b"]) == (0.44, 2.2)
    for ra in (0.0, 0.25, 0.5, 0.75, 1.0):
        assert isclose(BD.j_leakage(ra, 1 - ra, 1.0e12, KBD), 1.0, abs_tol=1e-9)
    assert 0.6 < BD.j_leakage(0.3, 0.7, 6.0, KBD) < 0.95
    assert math.isnan(BD.j_leakage(0.0, 0.0, 1.0, KBD))


def test_bell_delaware_desligado_devolve_h_do_formulario():
    vals = trocador_defaults()
    k = copy.deepcopy(KT)
    k["bell_delaware"]["ativo"] = False
    ok, cons, _ = restr_trocador(vals, k)
    t = _tubo(cons, 40.0)
    assert ok and not cons.bd_ativo and isclose(t["h_o"], vals["h_casco"]) and math.isnan(t["j_produto"]) and t["ok"]
    res = S.size_equipment(TX, S.case_input(vals), vals)   # com o TOML padrão, ligado
    tr = [e.var for e in res.trace.entries]
    assert "Jc" in tr and "Pr (casco)" in tr


def test_eq_2_13_e_2_14_area_de_celula_por_layout():
    vals = trocador_defaults()
    p_t = vals["razao_passo"] * vals["d_externo"] / 1000
    d_tri = math.sqrt(4 * 200 * (math.sqrt(3) / 2) * p_t ** 2 / math.pi)
    d_qua = math.sqrt(4 * 200 * 1.0 * p_t ** 2 / math.pi)

    def feixe(layout):
        _, c, _ = restr_trocador(vals | {"layout_tubos": float(layout)})
        return _tubo(c, 100)["d_casco"]
    assert isclose(feixe(30), d_tri) and isclose(feixe(60), d_tri) and isclose(feixe(45), d_qua)
    assert isclose(feixe(90), d_qua) and isclose(feixe(17), d_tri)      # layout inválido → 30°
    assert isclose(d_qua / d_tri, math.sqrt(2 / math.sqrt(3)))


def test_eq_2_17_casco_e_teto():
    vals = trocador_defaults()
    p = with_defaults(S.parameters(), vals)
    _, c, _ = restr_trocador(vals)
    for n in (40, 100, 200):
        t = _tubo(c, n)
        assert isclose(t["d_shell"], t["d_casco"] + 2 * c.d_o)
    assert 0.70 < _tubo(c, 40)["jb"] < 0.90
    t = _tubo(c, 100)
    der_n = S.derived(100, t["l"], "termica", c, KT, p)
    assert isclose(der_n["d_shell"], 1000 * t["d_shell"]) and der_n["d_shell"] > der_n["d_casco"]
    assert not S.admissible(100, der_n, p | {"d_casco_max": (der_n["d_casco"] + der_n["d_shell"]) / 2})
    assert S.admissible(100, der_n, p | {"d_casco_max": der_n["d_shell"] + 1.0})
    assert _tubo(c, 0)["ok"] is False


@pytest.mark.parametrize("ajuste, trecho", [
    ({"t_tubo_out": 108.0, "m_tubo": 60.0}, "Cruzamento de temperatura"),
    ({"m_tubo": 0.0}, "lado tubo inválida"),
    ({"m_casco": 0.0}, "lado casco inválida"),
    ({"t_tubo_out": 25.0, "t_tubo_in": 25.0}, "são iguais"),
    ({"espessura": 20.0}, "consome o diâmetro externo"),
    ({"k_tubo": 0.0}, "Prandtl do fluido do tubo"),
    ({"mu_casco": 0.0}, "Viscosidade do fluido do casco"),
    ({"k_casco": -1.0}, "Condutividade do fluido do casco"),
    ({"passes_tubo": 2.0, "t_tubo_out": 80.0, "m_casco": 40.0}, "arranjo 1-2 não fecha"),
])
def test_trocador_inviabilidades(ajuste, trecho):
    vals = trocador_defaults() | ajuste
    res = S.size_equipment(TX, S.case_input(vals), vals)
    assert not res.feasible and trecho in res.message


def test_entrada_faltando_e_fora_de_dittus_boelter():
    vals = trocador_defaults()
    del vals["cp_casco"]
    with pytest.raises(ValueError, match="cp_casco"):
        S.case_input(vals)
    vals = trocador_defaults() | {"m_tubo": 20.0, "cp_tubo": 2100.0, "t_tubo_in": 25.0, "t_tubo_out": 60.0,
                                  "rho_tubo": 850.0, "mu_tubo": 5.0, "k_tubo": 0.13, "mu_casco": 0.3, "k_casco": 0.62,
                                  "cp_casco": 4180.0}
    p = with_defaults(S.parameters(), vals)
    ok, c, _ = restr_trocador(vals)
    t = _tubo(c, 100)
    assert ok and 0.7 <= c.pr_tubo <= 120 and p["v_min"] <= t["v"] <= p["v_max"] and t["re"] < 1.0e4
    assert not t["nu_valido"] and not S.case_admissible(100, c, p)
    res = S.size_equipment(TX, S.case_input(vals), vals)
    assert not res.feasible and "dittus" in res.message.lower() and "reynolds" in res.message.lower()


def test_trocador_mensagens_de_selecao():
    p = with_defaults(S.parameters(), trocador_defaults())
    assert S.selection_message([], math.inf, p) == "A grade de números de tubos ficou vazia."
    R = lambda **d: type("R", (), dict(derivados=d))()
    assert "Nenhum feixe da grade" in S.selection_message([R(v=9.0)], math.inf, p)
    assert "tubo mais longo" in S.selection_message([R(v=1.5, nu_valido=1.0, l=99.0)], math.inf, p)
    assert "casco maior" in S.selection_message([R(v=1.5, nu_valido=1.0, l=1.0, d_shell=9e9)], math.inf, p)
    ok, msg = S.envelope_params([p | {"v_min": 2.5}, p | {"v_max": 2.0}])
    assert not ok and "O feixe é um só" in msg
    assert S.governing_label("termica") == "área de troca térmica" and S.governing_label("x") == "x"
