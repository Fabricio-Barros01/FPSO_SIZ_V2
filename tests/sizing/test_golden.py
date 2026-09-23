"""F6 — casos-ouro do Julia portados: Alves & Komesu (2025), Stewart & Arnold (2008)
Exemplo 3.2 (knockout), tratador eletrostático (§4.7–4.9), β (Fig. 3) e arrasto (Eq. 9–13).
Port de test/{golden_alves_komesu,golden_knockout,treater,beta,drag}.jl."""
import math

import pytest

from fpso_siz.core import unidades as U
from fpso_siz.core.casos import Case, CaseSet
from fpso_siz.core.corrente import stream_from_case, stream_parameters
from fpso_siz.core.motor import governing_summary, size_envelope
from fpso_siz.core.parametros import defaults, with_defaults
from fpso_siz.core.trace import Rastro
from fpso_siz.sizing import (ArnoldElectrostatic, ElectrostaticTreater, KnockoutDrum, Separator, StewartArnold,
                             StewartArnoldTwoPhase)
from fpso_siz.sizing.arrasto import converge_drag, drag_coefficient, reynolds, souders_brown, terminal_velocity
from fpso_siz.sizing.beta import _segment_area, beta_coefficient, segment_height_fraction, water_area_fraction
from fpso_siz.sizing.capacidade_gas import EQS_GAS_ALVES, gas_capacity_dleff

SA, SEP = StewartArnold(), Separator()
KO, KOM = KnockoutDrum(), StewartArnoldTwoPhase()
TR, TRM = ElectrostaticTreater(), ArnoldElectrostatic()
isclose = math.isclose


def default_case_values():
    return defaults(stream_parameters()) | defaults(SA.parameters())


# ================================================================ Alves & Komesu (2025)
TABELA_3 = [(5200.0, 19.29, 25.71, 4.94), (5350.0, 18.22, 24.29, 4.54), (5500.0, 17.24, 22.98, 4.18),
            (5650.0, 16.34, 21.78, 3.86), (5800.0, 15.50, 20.67, 3.56), (5950.0, 14.73, 19.64, 3.30)]


@pytest.fixture(scope="module")
def alves():
    vals = default_case_values() | {"d_min": 5200.0, "d_max": 5950.0, "d_step": 150.0}
    return vals, SA.size_equipment(SEP, stream_from_case(vals), vals)


def test_alves_tabela_3_varredura(alves):
    _, res = alves
    assert res.feasible and res.method_id == "stewart_arnold" and len(res.sweep) == 6
    for row, (d, leff, lss, sr) in zip(res.sweep, TABELA_3):
        assert row.x == d and row.governing == "liquid"
        assert isclose(row.y, leff, rel_tol=0.005) and isclose(row.derivados["lss"], lss, rel_tol=0.005)
        assert isclose(row.derivados["sr"], sr, rel_tol=0.005)


def test_alves_gas_nao_governa_e_teto_nao_restringe(alves):
    _, res = alves
    for row in res.sweep:
        assert row.per_constraint["gas"] < 0.1 and row.per_constraint["gas"] < row.per_constraint["liquid"] / 100
    assert res.governing == "liquid" and res.ceiling_mechanism == "water_in_oil" and res.ceiling > 10_000.0
    assert all(r.x < res.ceiling for r in res.sweep)


def test_alves_tabela_4_e_vaso_instalado(alves):
    vals, res = alves
    row = next(r for r in res.sweep if r.x == 5500.0)
    assert row.ok and isclose(row.derivados["sr"], 4.18, rel_tol=0.005) and isclose(row.y, 17.24, rel_tol=0.005)
    assert isclose(row.derivados["lss"], 22.98, rel_tol=0.005) and abs(res.x - 5500.0) <= vals["d_step"]
    assert abs(row.x / 1000 - 5.30) / 5.30 < 0.10 and abs(row.y - 19.00) / 19.00 < 0.10
    assert abs(row.derivados["lss"] - 21.81) / 21.81 < 0.10


def test_alves_coeficiente_impresso_seria_reprovado():
    carga = 10.0 * 215.8 + 10.0 * 1025.8
    assert not isclose(4.12e4 * carga / 5500.0 ** 2, 17.24, rel_tol=0.005)
    assert isclose(U.liquid_capacity_coefficient() * carga / 5500.0 ** 2, 17.24, rel_tol=0.005)
    assert isclose(SA.constants()["eq22_coefficient"], U.liquid_capacity_coefficient(), rel_tol=1e-12)


def test_alves_memorial(alves):
    _, res = alves
    eqs = [e.eq for e in res.trace.entries]
    assert all(e in eqs for e in ["Eq. 11", "Eq. 13", "Eq. 14", "Eq. 16", "Eq. 17", "Eq. 18", "Eq. 20", "Eq. 22",
                                  "Eq. 24"])
    assert all(math.isfinite(e.value) for e in res.trace.entries)


def test_alves_variante_geometrica_da_eq_21_registrada_e_nao_decide(alves):
    _, res = alves
    ent = {e.eq: e for e in res.trace.entries}
    beta = next(e for e in res.trace.entries if e.var == "β").value
    pub, geo = ent["Eq. 21"].value, ent["Eq. 21*"].value
    assert isclose(pub / geo, (0.5 - beta) / beta, rel_tol=1e-9) and pub > 6 * geo
    assert isclose(res.ceiling, ent["Eq. 19"].value) and res.ceiling_mechanism == "water_in_oil"
    assert geo < 4000.0 and all(r.x > geo for r in res.sweep)


def test_alves_sem_agua_livre_omite_a_variante():
    vals = default_case_values() | {"q_water": 0.0}
    ok, cons, tr = SA.sizing_constraints(stream_from_case(vals), with_defaults(SA.parameters(), vals), SA.constants())
    assert ok and cons.beta == 0.5 and "Eq. 21*" not in [e.eq for e in tr.entries]


# ================================================================ knockout — Exemplo 3.2
LB_FT3 = U.LB_KG / U.CUFT_M3
TABELA_3_4 = [(16.0, 2.5, 33.5), (20.0, 2.0, 21.4), (24.0, 1.7, 14.9), (30.0, 1.3, 9.5), (36.0, 1.1, 6.6),
              (42.0, 0.9, 4.9), (48.0, 0.8, 3.7)]


@pytest.fixture(scope="module")
def ko():
    vals = {"q_gas": 10e6 * U.CUFT_M3 / 24, "q_oil": 2000 * U.BARREL_M3 / 24, "rho_oil": 51.5 * LB_FT3,
            "rho_gas": 3.71 * LB_FT3, "mu_gas": 0.013, "pressure": 1000 * U.PSI_KPA,
            "temperature": (60 - 32) * 5 / 9, "z": 0.84, "dm_gas": 140.0, "tr_liquid": 3.0,
            "d_min": 16 * 25.4, "d_max": 48 * 25.4, "d_step": 6 * 25.4}
    s = stream_from_case(vals, required=KOM.stream_keys())
    p = with_defaults(KOM.parameters(), vals)
    ok, cons, tr = KOM.sizing_constraints(s, p, KOM.constants())
    assert ok
    return vals, s, p, cons, tr


def test_ko_sem_teto_de_decantacao(ko):
    *_, cons, tr = ko
    assert cons.d_max_mm == math.inf and cons.mechanism == "none"
    assert math.isnan(cons.beta) and math.isnan(cons.aw_over_a)
    assert not tr.block_entries("settling") and tr.block_entries("gas") and tr.block_entries("liquid")
    assert [f.fase for f in KOM.cross_section(cons)] == ["oil", "gas"]


def test_ko_arrasto_e_tabela_3_4(ko):
    *_, cons, tr = ko
    assert isclose(next(e for e in tr.entries if e.var == "C_D").value, 0.851, rel_tol=0.02)
    for d_in, leff_gas_ft, leff_liq_ft in TABELA_3_4:
        assert isclose(cons.d2_leff / (d_in * 25.4) ** 2, leff_liq_ft * U.FOOT_M, rel_tol=0.02)
        assert round(39.85 / d_in, 1) == leff_gas_ft and round(55.04 / d_in, 1) != leff_gas_ft  # erratum
    assert isclose(cons.d_leff_gas / (25.4 * U.FOOT_M), 39.85, rel_tol=0.015)


def test_ko_coeficiente_345_vs_420():
    exato = (25.4 * U.FOOT_M) * 420 * 1.8 * (24 / (1e6 * U.CUFT_M3)) * U.PSI_KPA
    assert isclose(exato, 34.202, rel_tol=1e-3) and isclose(34.5 / exato, 1.0087, rel_tol=1e-3)
    assert KOM.constants()["gas_capacity_coefficient"] == 34.5


def test_ko_bloco_de_gas_e_o_mesmo_do_trifasico(ko):
    _, s, p, cons, tr = ko
    tr3 = Rastro()
    ok3, dleff3, _ = gas_capacity_dleff(s, p["dm_gas"], 34.5, 0.34, 0.5, tr3, eqs=EQS_GAS_ALVES)
    assert ok3 and dleff3 == cons.d_leff_gas
    assert [e.eq for e in tr.block_entries("gas")] != [e.eq for e in tr3.block_entries("gas")]
    assert "Eq. 3.8b" in [e.eq for e in tr.block_entries("gas")]
    assert "Eq. 14" in [e.eq for e in tr3.block_entries("gas")]


def test_ko_lss_regra_do_livro():
    k = KOM.constants()
    for d in (400.0, 900.0, 1200.0):
        esperado = max(2.0 + d / 1000, (4 / 3) * 2.0)
        assert isclose(KOM.lss_from(d, 2.0, "liquid", k), esperado) and isclose(KOM.lss_from(d, 2.0, "gas", k), esperado)
    assert isclose(SA.lss_from(5950.0, 14.73, "liquid", SA.constants()), (4 / 3) * 14.73)


def test_ko_dimensiona_e_resumo_sem_teto(ko):
    vals, s, *_ = ko
    res = KOM.size_equipment(KO, s, vals)
    assert res.feasible and res.method_id == "stewart_arnold_2f" and 3.0 <= res.derivados["sr"] <= 4.0
    assert res.governing == "liquid" and abs(res.x - 36 * 25.4) <= 2 * vals["d_step"] and math.isinf(res.ceiling)
    env = size_envelope(KO, KOM, CaseSet([Case("único", vals)]))
    assert env.feasible and math.isinf(env.ceiling)
    assert "Governa" in governing_summary(KOM, env) and "Teto de decantação" not in governing_summary(KOM, env)
    env3 = size_envelope(SEP, SA, CaseSet([Case("t", default_case_values())]))
    assert "Teto de decantação" in governing_summary(SA, env3)
    env2 = size_envelope(KO, KOM, CaseSet([Case("normal", vals), Case("dobro", vals | {"q_oil": 2 * vals["q_oil"]})]))
    assert env2.feasible and env2.driver_case == "dobro" and all(x >= -1e-9 for x in env2.slack)
    assert all(isclose(r.y, max(r.per_case_y)) for r in env2.rows)


def test_ko_liquido_ausente_e_inviavel():
    vals = {"q_gas": 100.0, "rho_oil": 800.0, "rho_gas": 20.0, "mu_gas": 0.012, "pressure": 2000.0,
            "temperature": 30.0, "z": 0.9}
    s = stream_from_case(vals, required=tuple(k for k in KOM.stream_keys() if k != "q_oil"))
    ok, msg, _ = KOM.sizing_constraints(s, with_defaults(KOM.parameters(), {}), KOM.constants())
    assert not ok and "Eq. 3.9b" in msg


# ================================================================ tratador eletrostático
KT = TRM.constants()
IN_MM = U.INCH_M * 1000


def tratador_defaults():
    return defaults(TRM.stream_parameters()) | defaults(TRM.parameters())


def test_tr_coeficientes_do_livro():
    c = float(KT["settling_coefficient"])
    assert c == 0.033 and isclose(c * 500 ** 2, 8250.0) and isclose(320 * IN_MM, c * 500 ** 2, rel_tol=0.02)
    assert float(SA.constants()["eq17_coefficient"]) == c
    assert isclose(c * 200 ** 2, 1320.0) and not isclose(51.2 * IN_MM, 1520.0, rel_tol=0.05)  # Eq. 4.9b: 1320
    assert KT["retention_coefficient"] == 21000.0
    assert isclose(KT["retention_coefficient"] / 0.5, U.liquid_capacity_coefficient(), rel_tol=0.005)


def test_segmento_circular_eq_4_17():
    assert segment_height_fraction(0.0) == 0.0 and segment_height_fraction(1.0) == 1.0
    assert isclose(segment_height_fraction(0.5), 0.5, abs_tol=1e-9)

    def area(b):
        return (math.acos(1 - 2 * b) - (1 - 2 * b) * math.sqrt(max(4 * b * (1 - b), 0.0))) / math.pi
    for i in range(33):
        a = 0.02 + 0.03 * i
        assert isclose(area(segment_height_fraction(a)), a, abs_tol=1e-9)
    hs = [segment_height_fraction(0.05 * i) for i in range(21)]
    assert hs == sorted(hs)
    for i in range(1, 10):
        a = 0.05 * i
        assert isclose(segment_height_fraction(a) + segment_height_fraction(1 - a), 1.0, abs_tol=1e-8)
    for a in (0.1, 0.25, 0.4131):
        assert isclose(beta_coefficient(a), 0.5 - segment_height_fraction(a))


@pytest.fixture(scope="module")
def tratador():
    vals = tratador_defaults()
    entrada = TRM.case_input(vals)
    ok, cons, tr = TRM.sizing_constraints(entrada, with_defaults(TRM.parameters(), vals), KT)
    assert ok
    return vals, entrada, cons, tr, TRM.size_equipment(TR, entrada, vals)


def test_tr_sem_bloco_de_gas_e_vaso_cheio(tratador):
    _, _, cons, tr, _ = tratador
    assert cons.d_leff_gas == 0.0 and math.isfinite(cons.d2_leff) and cons.d2_leff > 0
    for d in (900.0, 3000.0, 6000.0):
        assert TRM.governing_of(d, cons) == "liquid" and isclose(TRM.requirement(d, cons), cons.d2_leff / d ** 2)
    assert not tr.block_entries("gas") and len(TRM.trace_blocks()) == 3
    assert not any("gás" in t.lower() for _, t in TRM.trace_blocks())
    assert set(TRM.per_constraint(3000.0, cons)) == {"liquid"}
    faixas = TRM.cross_section(cons)
    assert [f.fase for f in faixas] == ["water", "oil"] and all(f.fracao > 0 for f in faixas)
    assert isclose(sum(f.fracao for f in faixas), 1.0) and cons.beta > 0.5
    assert segment_height_fraction(float(KT["liquid_area_fraction"])) == 1.0


def test_tr_formulario_sem_gas_e_lss_do_livro(tratador):
    vals, _, _, _, res = tratador
    chaves = {s.key for s in TRM.stream_parameters()}
    assert not chaves & {"q_gas", "rho_gas", "mu_gas", "z", "pressure", "temperature"}
    assert res.feasible and vals["sr_min"] <= res.derivados["sr"] <= vals["sr_max"]
    d, leff = res.x, res.y
    assert isclose(res.derivados["lss"], max(leff + d / 1000, float(KT["lss_liquid_factor"]) * leff))
    sr = next(e for e in res.trace.block_entries("selection") if e.var == "SR")
    assert sr.eq == "§4.9.2" and SA.slenderness_equation() == "Eq. 24" and KOM.slenderness_equation() == "§3.8.5"
    assert TRM.governing_label("liquid") == "capacidade de líquido (retenção)" and TRM.governing_label("x") == "x"


def test_tr_campo_eletrico_operativo(tratador):
    base, _, _, tr, tratado = tratador
    cru_vals = base | {"dm_water": KT["untreated_droplet_um"]}
    cru = TRM.size_equipment(TR, TRM.case_input(cru_vals), cru_vals)
    assert cru.ceiling < tratado.ceiling and isclose(tratado.ceiling / cru.ceiling, 4.0, rel_tol=1e-6)
    assert not cru.feasible and "decanta" in cru.message.lower()
    ganho = next(e for e in tr.block_entries("settling") if e.var == "ganho do campo")
    assert isclose(ganho.value, 4.0) and "hipótese" in ganho.formula and "(d_m/500 µm)²" in ganho.formula
    assert "liquid_area_fraction" not in {s.key for s in TRM.parameters()}


@pytest.mark.parametrize("ajuste, trecho", [
    ({"rho_oil": 1050.0, "rho_water": 1000.0}, "ΔSG = -0.05"),
    ({"q_oil": 0.0, "q_water": 0.0}, "Eq. 4.16"),
    ({"q_oil": 0.0, "q_water": 50.0}, "a_w = 1.0"),
])
def test_tr_inviabilidades(ajuste, trecho):
    vals = tratador_defaults() | ajuste
    res = TRM.size_equipment(TR, TRM.case_input(vals), vals)
    assert not res.feasible and trecho in res.message


# ================================================================ β, Eq. 18, separador inviável
def test_beta_figura_3():
    assert beta_coefficient(0.0) == 0.5 and isclose(beta_coefficient(0.5), 0.0, abs_tol=1e-12)
    assert beta_coefficient(-0.1) == 0.5 and beta_coefficient(0.7) == 0.0
    for aw, b in [(0.10, 0.3435), (0.25, 0.2020), (0.40, 0.0805)]:
        assert isclose(beta_coefficient(aw), b, abs_tol=2e-3)
    bs = [beta_coefficient(i / 1000) for i in range(501)]
    assert bs == sorted(bs, reverse=True) and all(0 <= b <= 0.5 for b in bs)
    assert max(abs(a - b) for a, b in zip(bs, bs[1:])) < 0.02
    for f in (0.05, 0.15, 0.3, 0.45):
        assert isclose(_segment_area(2 * (0.5 - beta_coefficient(f))) / math.pi, f, abs_tol=1e-6)
    assert _segment_area(-1) == 0.0 and _segment_area(3) == math.pi


def test_eq_18():
    assert isclose(water_area_fraction(215.8, 1025.8, 10.0, 10.0), 0.41310, abs_tol=1e-5)
    assert water_area_fraction(100.0, 0.0, 10.0, 10.0) == 0.0 and water_area_fraction(0.0, 100.0, 10.0, 10.0) == 0.5
    assert water_area_fraction(0.0, 0.0, 10.0, 10.0) == 0.0


@pytest.mark.parametrize("ajuste, trecho", [
    ({"rho_oil": 1100.0}, "ΔSG"),
    ({"q_oil": 0.0}, "metade inferior"),
    ({"d_min": 3000.0, "d_max": 3300.0}, "esbeltez na banda 3.0–5.0"),
    ({"q_oil": 1.0, "q_water": 1.0, "mu_oil": 1e6, "mu_water": 1e6, "d_min": 3000.0}, "teto de decantação"),
])
def test_separador_inviavel_com_diagnostico(ajuste, trecho):
    vals = default_case_values() | ajuste
    r = size_envelope(SEP, SA, CaseSet([Case("X", vals)]))
    assert not r.feasible and trecho in r.message


def test_vazoes_nulas_e_bandas_que_nao_se_cruzam():
    vals = default_case_values() | {"q_oil": 0.0, "q_water": 0.0, "q_gas": 0.0}
    r = TRM.selection_message([type("R", (), {"y": 0.0, "x": 1.0})()], math.inf, {})
    assert "vazões informadas são nulas" in r
    e = size_envelope(SEP, SA, CaseSet([Case("A", default_case_values() | {"sr_min": 4.5}),
                                        Case("B", default_case_values() | {"sr_max": 4.0})]))
    assert not e.feasible and "SR ≥ 4.5 e outro pede SR ≤ 4.0" in e.message
    assert vals["q_oil"] == 0.0


def test_arrasto_dois_regimes_e_ponto_fixo():
    RL, RG, DM = 863.0, 17.0, 100.0
    r = converge_drag(RL, RG, DM, 0.012)
    assert r.converged and isclose(r.cd, 1.82, rel_tol=0.02) and 20 < r.re < 35 and r.iterations < 200
    r2 = converge_drag(RL, RG, DM, 0.6)
    assert r2.converged and r2.cd > 500 and r2.re < 0.1
    for mu in (0.012, 0.05, 0.6):
        r = converge_drag(RL, RG, DM, mu)
        assert isclose(terminal_velocity(RL, RG, DM, r.cd), r.vt, rel_tol=1e-8)
        assert isclose(reynolds(RG, DM, r.vt, mu), r.re, rel_tol=1e-8)
        assert isclose(drag_coefficient(r.re), r.cd, rel_tol=1e-6)


def test_arrasto_relaxacao_e_nao_convergencia():
    RL, RG, DM = 863.0, 17.0, 100.0
    for mu in (0.012, 0.6):
        direta = converge_drag(RL, RG, DM, mu, relax=1.0, maxiter=2000)
        amortec = converge_drag(RL, RG, DM, mu, relax=0.5, maxiter=2000)
        assert direta.converged and amortec.converged and isclose(direta.cd, amortec.cd, rel_tol=1e-6)
        assert amortec.iterations > direta.iterations
    cd, traj = 0.34, []
    for _ in range(12):
        cd = drag_coefficient(reynolds(RG, DM, terminal_velocity(RL, RG, DM, cd), 0.6))
        traj.append(cd)
    assert traj == sorted(traj)
    r = converge_drag(RL, RG, DM, 0.012, maxiter=3)
    assert not r.converged and r.iterations == 3
    assert converge_drag(RL, RG, DM, -0.012).converged is False  # Re ≤ 0 interrompe a iteração
    K = souders_brown(RL, RG, DM, 1.82)
    assert K > 0 and souders_brown(RL, RG, DM, 2 * 1.82) > K and souders_brown(RL, RG, 2 * DM, 1.82) < K


def test_arrasto_nao_convergido_vira_mensagem(monkeypatch):
    from fpso_siz.sizing import arrasto
    k = dict(arrasto._k(), max_iteracoes=2)
    monkeypatch.setattr(arrasto, "_k", lambda: k)
    r = size_envelope(SEP, SA, CaseSet([Case("X", default_case_values())]))
    assert not r.feasible
    assert r.message == ("Caso 'X': O coeficiente de arrasto não convergiu em 2 iterações. "
                         "Verifique a viscosidade do gás (µ_g = 0.012 cP).")
