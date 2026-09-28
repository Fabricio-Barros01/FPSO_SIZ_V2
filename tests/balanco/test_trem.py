"""Trem de separação SG-001 → V-001 → V-002 (balanco/trem.py), parte do EstadoProcesso.

O que estes testes prendem:

1. o trem é uma SEQUÊNCIA: cada estágio recebe o líquido do anterior; só o primeiro recebe z₀;
2. tudo sai do estado oficial — composição, T e P de cada estágio, massas específicas —, e
   mudar a pressão nas premissas move o estágio sem código novo;
3. a base molar é a declarada: vem de massa, ṅ_F = ṁ/MW_z com MW_z = Σ zᵢ·MWᵢ (sem flash), e
   exclui o gás de lift (lacuna declarada);
4. o fechamento é do TREM: `ok` exige os três estágios; `ok_parcial` cobre os executados;
5. o trem é diagnóstico: a vazão de gás que o processo consome continua sendo a de Standing.
"""
import dataclasses
import math

import pytest

from fpso_siz.balanco import trem
from fpso_siz.balanco.dados import premissas
from fpso_siz.balanco.modelo import resolver_caso
from fpso_siz.core.unidades import c_para_k, kpa_para_pa
from fpso_siz.termo import proveniencia
from fpso_siz.termo import servico as termo

TOL = 1.0e-12       # folga sobre a precisão de máquina, não critério físico


@pytest.fixture(scope="module")
def trens(resultados):
    return [r.trem for r in resultados]


# ------------------------------------------------------------------ a sequência
def test_o_trem_percorre_os_tres_estagios_na_ordem(trens):
    ordem = [e["id"] for e in trem.cfg()["estagio"]]
    assert ordem == ["SG-001", "V-001", "V-002"]
    for t in trens:
        assert t.completo and [e.ponto for e in t.estagios] == ordem, t.interrompido


def test_a_alimentacao_de_cada_estagio_e_o_liquido_do_anterior(trens):
    for t in trens:
        for anterior, seguinte in zip(t.estagios, t.estagios[1:]):
            assert seguinte.z == anterior.x and seguinte.n_entrada_kmol_d == anterior.n_liquido_kmol_d


def test_o_primeiro_estagio_recebe_a_composicao_do_estado(resultados, trens):
    for r, t in zip(resultados, trens):
        assert t.estagios[0].z == r.composicao


def test_as_condicoes_sao_as_do_estado(resultados, trens):
    for r, t in zip(resultados, trens):
        for e in t.estagios:
            assert (e.T_C, e.P_kPa) == (r.T[e.corrente_gas], r.P[e.corrente_gas])


def test_o_estagio_segue_a_pressao_das_premissas(dados):
    """P_D1 é premissa: mudá-la move o V-001 do trem, sem código novo (variável natural da
    otimização)."""
    base = resolver_caso(dados.caso(2), dados)
    outro = resolver_caso(dados.caso(2), dados, premissas(dados, P_D1=900.0))
    assert outro.trem.estagios[1].P_kPa == 900.0 != base.trem.estagios[1].P_kPa
    assert outro.trem.estagios[1].beta != base.trem.estagios[1].beta


def test_o_trem_difere_do_flash_independente_a_partir_do_segundo_estagio(resultados):
    """No SG-001 a alimentação é z₀: mesmo β do flash de z₀. Depois não: é o que o trem muda."""
    r = resultados[0]
    for i, e in enumerate(r.trem.estagios):
        ind = termo.flash_tp(c_para_k(e.T_C), kpa_para_pa(e.P_kPa), r.composicao, r.mws_plus)
        if i == 0:
            assert ind.vapor.fracao_molar == e.beta
        else:
            assert abs(ind.vapor.fracao_molar - e.beta) > 0.1


def test_o_liquido_fica_mais_pesado_a_cada_estagio(trens):
    for t in trens:
        mws = [e.liquido.MW for e in t.estagios]
        assert mws == sorted(mws)
        b = [e.beta for e in t.estagios]
        assert b[0] > b[1] > b[2]


def test_a_quantidade_absoluta_e_propagada(trens):
    for t in trens:
        for e in t.estagios:
            assert e.n_vapor_kmol_d == pytest.approx(e.beta * e.n_entrada_kmol_d, rel=1e-15)
            assert e.n_liquido_kmol_d == pytest.approx((1 - e.beta) * e.n_entrada_kmol_d, rel=1e-15)
            assert e.m_vapor_kg_d == pytest.approx(e.n_vapor_kmol_d * e.vapor.MW, rel=1e-15)


def test_o_trem_e_guardado_no_proprio_estado(resultados):
    r = resultados[0]
    assert r.trem is r.trem


# ------------------------------------------------------------------ a base molar
def test_a_base_molar_vem_de_massa_e_nao_de_flash(resultados, trens):
    for r, t in zip(resultados, trens):
        b = t.base
        assert (b.rho_oleo, b.rho_gas_std) == (r.rho["O"], r.rho["G"])
        assert b.massa_oleo_kg_d == r.caso["oil_sm3d"] * r.rho["O"]
        assert b.massa_gas_kg_d == r.caso["produced_gas_sm3d"] * r.rho["G"]
        assert b.MW_z == termo.mw_mistura(r.composicao, r.mws_plus)
        assert b.n_F_kmol_d == b.massa_kg_d / b.MW_z


def test_a_base_nao_depende_do_primeiro_flash(resultados, monkeypatch):
    """A quantidade que entra no trem é conhecida antes de qualquer flash."""
    def proibido(*a, **k):
        raise AssertionError("a base molar chamou o flash")
    monkeypatch.setattr(termo, "flash_tp", proibido)
    assert trem.base_molar(resultados[0]).n_F_kmol_d > 0


def test_a_base_molar_exclui_o_gas_de_lift(trens):
    com_lift = [t for t in trens if t.base.tem_lift]
    assert len(com_lift) == 4
    for t in com_lift:
        assert t.base.massa_gas_kg_d == t.base.gas_produzido_sm3d * t.base.rho_gas_std
        assert 0 < t.base.fracao_de_lift < 1


def test_as_lacunas_e_a_regra_estao_declaradas():
    lac = {x["id"]: x for x in trem.lacunas()}
    assert lac["composicao_gas_de_lift"]["situacao"] == "ausente"
    b = trem.cfg()["base_molar"]
    assert b["inclui_gas_de_lift"] is False and b["regra"] and b["por_que_nao_o_split"]


def test_compatibilidade_com_o_bot_e_medida_e_nao_forcada(resultados, dados):
    """O mesmo tipo de fluido aparece em casos de GOR diferente: a composição não reproduz os
    dois volumes. A medida existe para justificar a base por massa; nada é reconciliado."""
    medidas = [trem.coerencia_com_bot(r, dados.T_std_C, dados.P_std_kPa) for r in resultados]
    assert all(m["bifasico"] for m in medidas)
    razoes = [m["gor_flash"] / m["gor_bot"] for m in medidas]
    assert min(razoes) < 0.7 and max(razoes) > 2.0


# ------------------------------------------------------------------ fechamento
def test_o_trem_fecha_global_e_por_componente(trens):
    for t in trens:
        f = t.fechamento
        assert f.ok and f.ok_parcial and f.estagios == f.esperados == 3
        assert f.erro_molar_relativo < TOL and f.erro_massico_relativo < TOL and f.erro_componente_max < TOL
        assert t.n_vapor_total + t.n_liquido_final == pytest.approx(t.base.n_F_kmol_d, rel=1e-12)


def test_cada_flash_do_trem_fecha(trens):
    for t in trens:
        assert all(e.fechamento.ok for e in t.estagios)


def test_trem_interrompido_nao_e_trem_completo(resultados, monkeypatch):
    """Um estágio sem líquido encerra a cascata: o que rodou fecha (ok_parcial), mas o trem não
    é completo e `ok` não passa."""
    original = termo.flash_tp

    def so_vapor(T, P, z, mws_plus):
        v = original(T, P, z, mws_plus).vapor
        unica = dataclasses.replace(v, fracao_molar=1.0, fracao_massica=1.0, composicao=dict(z),
                                    MW=termo.mw_mistura(z, mws_plus))
        return termo.EstadoTermodinamico(T=T, P=P, z=dict(z), fases=(unica,))

    monkeypatch.setattr(termo, "flash_tp", so_vapor)
    t = trem.resolver(resultados[0])
    assert len(t.estagios) == 1 and not t.completo and "sem fase líquida" in t.interrompido
    assert t.fechamento.ok_parcial and not t.fechamento.ok and t.fechamento.esperados == 3
    assert math.isfinite(t.n_liquido_final)


def test_flash_que_nao_converge_interrompe_sem_inventar(resultados, monkeypatch):
    def falha(T, P, z, mws_plus):
        return termo.EstadoTermodinamico(T=T, P=P, z=dict(z), ok=False, mensagem="não convergiu")

    monkeypatch.setattr(termo, "flash_tp", falha)
    t = trem.resolver(resultados[0])
    assert len(t.estagios) == 1 and t.interrompido.startswith("SG-001")
    assert not t.fechamento.ok and not t.fechamento.ok_parcial and t.fechamento.estagios == 0


# ------------------------------------------------------------------ diagnóstico, não consumo
def test_o_processo_consome_standing_e_nao_o_trem(resultados):
    consumidas = proveniencia.consumidas("dimensionamento")
    assert consumidas["gas_liberado_por_estagio"]["origem"] == ["Standing"]
    for ident in ("fracao_vapor_estagio", "composicao_vapor_estagio", "composicao_liquido_estagio",
                  "Z_vapor_estagio", "MW_vapor_estagio", "rho_vapor_estagio"):
        assert proveniencia.de(ident)["consumidores"] == []
    assert resultados[0].proveniencia["gas_liberado_por_estagio"]["origem"] == ["Standing"]
