"""F10a — propriedades na condição do equipamento (pfd/fluidos.py, porta pfd/_chedl.py).

Oráculos: os exemplos das docstrings das funções do ChEDL (que citam a fonte primária), a
coerência com premissas do balanço e os limites físicos. Nenhum valor esperado aqui foi
digitado de memória: ou sai da documentação da biblioteca, ou de uma identidade.
"""
import math
from pathlib import Path

import pytest

from fpso_siz.balanco.dados import carregar_casos, constantes, pocos, premissas
from fpso_siz.balanco.modelo import resolver_todos
from fpso_siz.balanco.propriedades import poco_do_fluido
from fpso_siz.core.trace import Rastro
from fpso_siz.core.unidades import c_para_k
from fpso_siz.pfd import _chedl, fluidos

CASOS = Path(__file__).resolve().parents[1] / "fixtures" / "python_ref" / "design_cases_bot.json"

NACL = "7647-14-5"


@pytest.fixture(scope="module")
def balanco():
    dados = carregar_casos(CASOS)
    prem = premissas(dados)
    return dados, prem, {r.num: r for r in resolver_todos(dados, prem)}


# ------------------------------------------------------------------ porta ChEDL
def test_laliberte_reproduz_os_exemplos_da_documentacao():
    """Exemplos das docstrings de thermo.electrochem (Laliberté 2009, planilha do autor)."""
    from thermo import electrochem as ec
    assert ec.Laliberte_viscosity(273.15 + 5, [0.005810], [NACL]) == pytest.approx(0.0015285828581961414, rel=1e-12)
    assert ec.Laliberte_density(273.15, [0.0037838838], [NACL]) == pytest.approx(1002.62501201, rel=1e-10)
    assert ec.Laliberte_heat_capacity(273.15 + 1.5, [0.00398447], [NACL]) == pytest.approx(4186.575407596064,
                                                                                          rel=1e-12)
    v, faixas = _chedl.salmoura_laliberte(273.15 + 5, 0.005810, NACL)
    assert v["mu"] == ec.Laliberte_viscosity(273.15 + 5, [0.005810], [NACL])
    assert set(faixas) == {"rho", "mu", "cp"} and all(t0 < t1 and w > 0 for t0, t1, w in faixas.values())


def test_iapws_reproduz_exemplo_da_documentacao():
    """chemicals.viscosity.mu_IAPWS(298.15, 998) = 889,7351 µPa·s (Huber et al. 2009)."""
    from chemicals.viscosity import mu_IAPWS
    assert mu_IAPWS(298.15, 998.0) == pytest.approx(0.000889735100149808, rel=1e-12)
    e = _chedl.agua_iapws(298.15, 1e5)
    assert e["mu"] == pytest.approx(0.000889735100149808, rel=1e-3)  # ρ(25 °C, 1 bar) ≈ 997, não 998


def test_versoes_registradas():
    v = fluidos.versoes()
    assert set(v) == {"thermo", "chemicals"} and all(v.values())


# ------------------------------------------------------------------ gás
def test_gas_tende_ao_ideal_em_pressao_baixa(balanco):
    _, _, rs = balanco
    r = rs[8]
    g = fluidos.gas(r.gp["y"], r.gp["MW"], 70.0, 1.0)
    assert g.Z == pytest.approx(1, abs=1e-3) and g.VF == 1
    ideal = 1.0 * r.gp["MW"] / (constantes().R * c_para_k(70.0))
    assert g.rho == pytest.approx(ideal / g.Z, rel=1e-12)


def test_gas_do_fwko_caso_8(balanco):
    """C-04 do caso 8 (Mid Life, 30,7 % de CO2): Z < 1 e ρ acima do ideal da premissa P-39;
    μ e k positivos; rastro com fonte em cada propriedade."""
    _, _, rs = balanco
    r = rs[8]
    tr = Rastro()
    g = fluidos.gas(r.gp["y"], r.gp["MW"], r.T["C-04"], r.P["C-04"], tr)
    ideal = r.P["C-04"] * r.gp["MW"] / (constantes().R * c_para_k(r.T["C-04"]))
    assert 0.9 < g.Z < 1 and g.rho == pytest.approx(ideal / g.Z, rel=1e-12)
    assert g.mu > 0 and g.k > 0 and g.VF == 1 and g.avisos == ()
    assert [e.var for e in tr] == ["Z", "ρ_g", "μ_g", "k_g"]
    assert all(e.block == fluidos.BLOCO and e.eq for e in tr)


def test_gas_com_componente_sem_identificador():
    with pytest.raises(ValueError, match="sem identificador"):
        fluidos.gas({"C1": 0.9, "Xe": 0.1}, 17.0, 30.0, 100.0)


def test_gas_que_condensa_gera_aviso(monkeypatch):
    real = _chedl.estado_gas
    monkeypatch.setattr(_chedl, "estado_gas", lambda *a: {**real(*a), "VF": 0.98})
    g = fluidos.gas({"C1": 0.9, "C2": 0.1}, 17.6, 30.0, 1000.0)
    assert g.VF == 0.98 and "condensação parcial" in g.avisos[0]


# ------------------------------------------------------------------ água e salmoura
def test_agua_de_diluicao_e_a_da_porta():
    tr = Rastro()
    a = fluidos.agua(90.0, 700.0, tr)
    e = _chedl.agua_iapws(c_para_k(90.0), 700e3)
    assert (a.rho, a.mu, a.k) == (e["rho"], e["mu"] * 1000.0, e["k"]) and math.isnan(a.cp)
    assert [x.var for x in tr] == ["ρ_w", "μ_w", "k_w"]


def test_salmoura_coerente_com_a_premissa_P08(balanco):
    """A 15,6 °C (condição padrão do balanço), Laliberté dá a massa específica da premissa
    rho_W = 1154 kg/m³ dentro de 0,5 % — duas fontes independentes que concordam."""
    _, prem, _ = balanco
    s = fluidos.salmoura(15.6, prem["S_W"], prem["rho_W"])
    assert s.rho == pytest.approx(prem["rho_W"], rel=5e-3) and s.avisos == ()


def test_salmoura_a_90C_com_k_como_lacuna(balanco):
    _, prem, _ = balanco
    tr = Rastro()
    s = fluidos.salmoura(90.0, prem["S_W"], prem["rho_W"], tr)
    assert s.rho < prem["rho_W"] and 0 < s.mu < 1 and s.cp > 0 and math.isnan(s.k) and s.avisos == ()
    lacuna = [e for e in tr if e.var == "k_w"][0]
    assert math.isnan(lacuna.value) and "lacuna" in lacuna.eq


@pytest.mark.parametrize("T, S, trecho", [(150.0, 240000.0, "rho: fora da faixa"),
                                          (90.0, 330000.0, "w = ")])
def test_salmoura_fora_da_faixa_avisa(T, S, trecho):
    s = fluidos.salmoura(T, S, 1154.0)
    assert any(trecho in a for a in s.avisos)


# ------------------------------------------------------------------ óleo
def test_oleo_reproduz_a_tabela_do_bot_e_avisa_o_extremo(balanco):
    dados, _, rs = balanco
    poco = pocos()[poco_do_fluido(dados, rs[8].fluid)]
    for t, mu in poco.viscosidade:
        o = fluidos.oleo(poco, rs[8].rho["O"], t)
        assert o.mu == pytest.approx(mu, rel=1e-12) and o.rho == rs[8].rho["O"]
    assert fluidos.oleo(poco, rs[8].rho["O"], 45.0).avisos == ()
    quente = fluidos.oleo(poco, rs[8].rho["O"], 90.0)
    assert quente.mu == poco.viscosidade[-1][1] and "limitado" in quente.avisos[0]
    assert math.isnan(quente.k)


# ------------------------------------------------------------------ emulsão (Branan eq. 27-4)
def test_emulsao_sem_fase_dispersa_e_a_continua():
    mu, avisos = fluidos.emulsao(10.0, 0.6, 0.0)
    assert mu == 10.0 and avisos == ()


def test_emulsao_forma_da_equacao_27_4():
    a = fluidos.cfg()["emulsao"]["a"]
    tr = Rastro()
    mu, avisos = fluidos.emulsao(10.0, 0.6, 0.2, tr)
    assert mu == pytest.approx(10.0 / 0.8 * (1 + a * 0.6 * 0.2 / (0.6 + 10.0)), rel=1e-15)
    assert avisos == () and tr.entries[0].var == "μ_emulsão"


def test_emulsao_fora_da_faixa_avisa():
    _, avisos = fluidos.emulsao(0.3, 0.2, 0.95)
    assert len(avisos) == 4 and all("Zanker" in a for a in avisos)


# ------------------------------------------------------------------ pressão de vapor
def test_pressao_de_vapor_do_liquido_saturado():
    tr = Rastro()
    assert fluidos.pressao_vapor_saturado(700.0, tr) == 700.0
    assert tr.entries[0].eq == fluidos.cfg()["vapor"]["rotulo"]


# ------------------------------------------------------------------ óleo vivo (Beggs & Robinson)
def test_oleo_vivo_e_a_forma_da_correlacao():
    """μ_o = A·μ_od^B, A = a(Rs+b)^c, B = d(Rs+e)^f, com os coeficientes de fluidos.toml."""
    c = fluidos.cfg()["oleo_vivo"]
    for rs in (30.0, 64.3, 500.0):
        mu, avisos = fluidos.oleo_vivo(13.28, rs, 27.5, 60.0)
        assert mu == c["a"] * (rs + c["b"]) ** c["c"] * 13.28 ** (c["d"] * (rs + c["e"]) ** c["f"])
        assert not avisos


def test_oleo_vivo_reduz_mu_com_o_gas_dissolvido():
    mus = [fluidos.oleo_vivo(13.28, rs, 27.5, 60.0)[0] for rs in (20.0, 60.0, 200.0, 1000.0)]
    assert all(a > b for a, b in zip(mus, mus[1:])) and mus[0] < 13.28


def test_oleo_vivo_sem_gas_ou_abaixo_da_faixa_e_o_oleo_morto():
    """Abaixo da faixa de Rs a correlação não é extrapolada: com os coeficientes arredondados,
    A(0)·μ^B(0) > μ (óleo vivo mais viscoso que o morto, sem sentido físico)."""
    c = fluidos.cfg()["oleo_vivo"]
    assert c["a"] * c["b"] ** c["c"] * 13.28 ** (c["d"] * c["e"] ** c["f"]) > 13.28
    for rs in (0.0, -0.0, -1e-12, 1e-9, 0.4):
        assert fluidos.oleo_vivo(13.28, rs, 27.5, 60.0) == (13.28, [])


def test_oleo_vivo_avisa_fora_da_faixa_de_dados():
    c = fluidos.cfg()["oleo_vivo"]
    mu, av = fluidos.oleo_vivo(13.28, c["faixa_rs_scf_stb"][0] / 2, 27.5, 60.0)
    assert mu == 13.28 and len(av) == 1 and "óleo morto" in av[0]
    _, av = fluidos.oleo_vivo(13.28, c["faixa_rs_scf_stb"][1] * 2, c["faixa_api"][0] - 1, 0.0)
    assert len(av) == 3


def test_oleo_vivo_no_rastro():
    tr = Rastro()
    p = pocos()[next(iter(pocos()))]
    o = fluidos.oleo(p, 900.0, 60.0, tr, rs_scf_stb=64.3)
    nomes = [e.var for e in tr.entries]
    assert nomes[:3] == ["μ_od", "Rs", "μ_o"]
    mu_od = tr.entries[0].value
    assert o.mu == fluidos.oleo_vivo(mu_od, 64.3, p.api, 60.0)[0] < mu_od
    tr_baixo = Rastro()
    assert fluidos.oleo(p, 900.0, 60.0, tr_baixo, rs_scf_stb=0.0).mu == tr_baixo.entries[0].value
    assert [e.var for e in tr_baixo.entries][:2] == ["μ_od", "μ_o"]
    tr_morto = Rastro()
    assert fluidos.oleo(p, 900.0, 60.0, tr_morto).mu == mu_od and tr_morto.entries[0].var == "μ_o"


def test_sg001_usa_o_rs_da_saida_de_oleo(planta_base, planta_oleo_morto):
    """No SG-001, μ_o vivo = Beggs & Robinson sobre o μ do óleo morto do mesmo caso, com o Rs
    (Q_G/Q_O padrão) da corrente de óleo que sai do vaso (C-06)."""
    from types import SimpleNamespace

    from fpso_siz.pfd import entradas
    vivo, morto = planta_base.tag("SG-001"), planta_oleo_morto.tag("SG-001")
    for r, cv, cm in zip(planta_base.balanco, vivo.entradas.casos, morto.entradas.casos, strict=True):
        rs = entradas._rs(SimpleNamespace(r=r), "C-06")
        api = pocos()[poco_do_fluido(planta_base.dados, r.fluid)].api
        mu_od = cm.valores["mu_oil"].valor
        assert rs > 0 and cv.valores["mu_oil"].valor == fluidos.oleo_vivo(mu_od, rs, api, 0.0)[0] < mu_od
        assert "Beggs & Robinson" in cv.valores["mu_oil"].fonte and "Rs de C-06" in cv.valores["mu_oil"].fonte
        assert "Beggs" not in cm.valores["mu_oil"].fonte
