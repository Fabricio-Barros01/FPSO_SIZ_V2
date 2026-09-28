"""F2 — propriedades, correlações e validação de entrada (casos de borda)."""
import json
import math

import pytest

from fpso_siz.balanco.dados import carregar_casos, constantes, pocos, premissas
from fpso_siz.balanco.modelo import corrente
from fpso_siz.balanco.propriedades import gas_props, poco_do_fluido, split_water, standing_rs
from fpso_siz.termo.servico import mu_interp
from fpso_siz.core.unidades import c_para_f, c_para_k

K = constantes().standing
TAB_A = pocos()["Well A"].viscosidade


def test_unidades_exatas():
    assert c_para_f(100) == 212 and c_para_f(0) == 32
    assert c_para_k(0) == 273.15


def test_standing_cresce_com_pressao_e_zero_de_referencia():
    rs = [standing_rs(p, 60.0, 0.8, 28.0, K) for p in (200.0, 700.0, 2500.0)]
    assert rs == sorted(rs) and rs[0] > 0
    # forma logarítmica (independente) do mesmo valor, como na auditoria do original
    P, TF = 2500.0 / K.kPa_por_psia, c_para_f(60.0)
    log = 0.8 * 10 ** (K.expoente * (math.log10(P / K.a + K.b) + (K.c_api * 28.0 - K.c_T * TF))) * K.Sm3_Sm3_por_scf_bbl
    assert math.isclose(rs[2], log, rel_tol=1e-12)


@pytest.mark.parametrize("T, esperado", [(20.0, (32.2, "extrapolado<30")), (30, (32.2, "extrapolado<30")),
                                          (80.0, (7.9, "limitado a 70 °C")), (70, (7.9, "limitado a 70 °C"))])
def test_viscosidade_fora_da_tabela(T, esperado):
    assert mu_interp(TAB_A, T) == esperado


def test_viscosidade_interpola_em_log():
    mu, flag = mu_interp(TAB_A, 45.0)
    assert flag == "interp." and math.isclose(mu, math.sqrt(21.0 * 14.5), rel_tol=1e-12)
    assert math.isclose(mu_interp(TAB_A, 40.0)[0], 21.0, rel_tol=1e-12)


def test_split_water_impoe_bsw_no_oleo_que_sai():
    w_keep, w_rem, oil_w = split_water(1000.0, 500.0, 0.1, 2.0, 900.0, 8)
    assert math.isclose(w_keep / (w_keep + 1000.0 - oil_w), 0.1, rel_tol=1e-12)
    assert math.isclose(w_keep + w_rem, 500.0, rel_tol=1e-15)


def test_split_water_bordas():
    assert split_water(1000.0, 500.0, 1.0, 2.0, 900.0, 8)[:2] == (500.0, 0.0)  # BSW ≥ 1: nada removido
    assert split_water(1000.0, 0.0, 0.1, 2.0, 900.0, 8) == (0.0, 0.0, 0.0)      # sem água
    assert split_water(10.0, 5.0, 0.1, 2.0, 900.0, 8, extra_oil_v=50.0)[0] == 0.0  # arraste > óleo


def test_gas_props_renormaliza_o_corte_leve():
    const = constantes()
    comp = {k: 0.0 for k in const.MW} | {"C1": 0.3, "CO2": 0.1, "C7": 0.6}
    g = gas_props(comp, const, 23.6)
    assert math.isclose(sum(g["y"].values()), 1.0, rel_tol=1e-15)
    assert math.isclose(g["frac_lights"], 0.4) and math.isclose(g["xsum"], 1.0)
    assert math.isclose(g["MW"], 0.75 * const.MW["C1"] + 0.25 * const.MW["CO2"], rel_tol=1e-12)
    assert g["gamma"] == g["MW"] / const.MW_ar and g["rho_std"] == g["MW"] / 23.6


def test_poco_do_fluido(dados):
    assert {poco_do_fluido(dados, f) for f in dados.composicoes} == {"Well A", "Well B"}


def escrever(tmp_path, d):
    p = tmp_path / "casos.json"
    p.write_text(json.dumps(d), encoding="utf-8")
    return p


def test_poco_ambiguo_e_erro(dados, tmp_path):
    d = json.loads(json.dumps(dados.bruto))
    f = next(iter(d["fluid_compositions"]))
    d["fluid_compositions"][f]["C20+"] = d["fluid_compositions"][f]["C20++"] = 0.1
    with pytest.raises(ValueError, match="C20"):
        poco_do_fluido(carregar_casos(escrever(tmp_path, d)), f)


def test_validacao_do_arquivo_de_casos(dados, tmp_path):
    d = json.loads(json.dumps(dados.bruto))
    del d["h2s_ppmv"]
    with pytest.raises(ValueError, match="h2s_ppmv"):
        carregar_casos(escrever(tmp_path, d))
    d = json.loads(json.dumps(dados.bruto))
    del d["cases"][0]["oil_sm3d"]
    with pytest.raises(ValueError, match="oil_sm3d"):
        carregar_casos(escrever(tmp_path, d))
    d = json.loads(json.dumps(dados.bruto))
    d["cases"][0]["fluid_type"] = "Inexistente"
    with pytest.raises(ValueError, match="Inexistente"):
        carregar_casos(escrever(tmp_path, d))


def test_acesso_aos_dados(dados):
    assert dados.origem == "design_cases_bot.json" and len(dados.sha256) == 64
    assert dados.caso(8)["num"] == 8 and set(dados.h2s_ppmv) == set(dados.composicoes)
    with pytest.raises(KeyError):
        dados.caso(99)


def test_premissas_alteracao_e_chave_desconhecida(dados):
    assert premissas(dados, BSW_F=0.1)["BSW_F"] == 0.1
    with pytest.raises(KeyError, match="BSW_X"):
        premissas(dados, BSW_X=0.1)


def test_corrente_rejeita_componente_desconhecido():
    assert corrente(O=1.0) == {"O": 1.0, "W": 0.0, "D": 0.0, "G": 0.0}
    with pytest.raises(KeyError):
        corrente(X=1.0)
