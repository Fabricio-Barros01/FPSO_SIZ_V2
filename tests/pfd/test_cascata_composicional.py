"""Fase 5.1 — cascata composicional do trem, em modo sombra.

O que estes testes prendem:

1. a cascata é uma SEQUÊNCIA: a alimentação de cada estágio é o líquido do anterior, e o
   primeiro estágio (e só ele) recebe z₀ — por isso ele coincide com o flash independente
   da F5 e os seguintes não;
2. a base molar é a DECLARADA, vem de massa e não de split de fases, e exclui o gás de lift;
3. o trem fecha, global e componente a componente;
4. nada saiu da sombra: nenhuma propriedade mudou de status e o guarda continua recusando.
"""
import math

import pytest

from fpso_siz.balanco.dados import carregar_casos, premissas
from fpso_siz.balanco.modelo import resolver_todos
from fpso_siz.core.unidades import c_para_k, kpa_para_pa
from fpso_siz.pfd import cascata as cs
from fpso_siz.pfd import estado_termodinamico as et
from fpso_siz.pfd import integracao as ig

TOL = 1.0e-12       # folga sobre a precisão de máquina, não critério físico


@pytest.fixture(scope="module")
def entrada(planta_base):
    dados = planta_base.dados
    mws = {k: v["mw"] for k, v in dados.c20.items()}
    return dados, premissas(dados), mws


@pytest.fixture(scope="module")
def cascatas(entrada, planta_base):
    dados, prem, mws = entrada
    return cs.rodar(planta_base.balanco, dados, prem, mws)


# ------------------------------------------------------------------ a sequência
def test_a_cascata_percorre_os_tres_estagios_na_ordem(cascatas):
    sequencia = cs.cfg()["cascata"]["sequencia"]
    assert sequencia == ["SG-001", "V-001", "V-002"]
    for c, _ in cascatas:
        assert c.completa and [e.ponto for e in c.estagios] == sequencia, c.interrompida


def test_a_alimentacao_de_cada_estagio_e_o_liquido_do_anterior(cascatas):
    for c, _ in cascatas:
        for anterior, seguinte in zip(c.estagios, c.estagios[1:]):
            assert seguinte.z == anterior.x
            assert seguinte.n_entrada_kmol_d == anterior.n_liquido_kmol_d


def test_o_primeiro_estagio_recebe_a_composicao_global(cascatas, entrada):
    dados, _, _ = entrada
    for c, _ in cascatas:
        z0 = {k: v for k, v in dados.composicoes[c.fluido].items() if v > 0}
        assert c.estagios[0].z == z0


def test_a_cascata_difere_do_flash_independente_a_partir_do_segundo_estagio(cascatas, entrada):
    """Se não diferisse, a F5.1 não teria mudado nada: o teste prova que o trem é outro."""
    dados, _, mws = entrada
    c, _ = cascatas[0]
    z0 = {k: v for k, v in dados.composicoes[c.fluido].items() if v > 0}
    betas = []
    for s in c.estagios:
        ind = et.flash_poco(c_para_k(s.T_C), kpa_para_pa(s.P_kPa), z0, mws)
        betas.append((ind.vapor.fracao_molar, s.beta))
    assert betas[0][0] == betas[0][1]                                    # mesmo z: mesmo β
    assert all(abs(a - b) > 0.1 for a, b in betas[1:])                   # z diferente: β diferente


def test_o_liquido_fica_mais_pesado_a_cada_estagio(cascatas):
    """Sanidade física da sequência: o vapor que sai leva os leves."""
    for c, _ in cascatas:
        mws = [e.liquido.MW for e in c.estagios]
        assert mws == sorted(mws), (c.caso, mws)
        betas = [e.beta for e in c.estagios]
        assert betas[0] > betas[1] > betas[2], (c.caso, betas)


def test_a_quantidade_absoluta_e_propagada(cascatas):
    for c, _ in cascatas:
        for s in c.estagios:
            assert s.n_vapor_kmol_d == pytest.approx(s.beta * s.n_entrada_kmol_d, rel=1e-15)
            assert s.n_liquido_kmol_d == pytest.approx((1 - s.beta) * s.n_entrada_kmol_d, rel=1e-15)
            assert s.m_vapor_kg_d == pytest.approx(s.n_vapor_kmol_d * s.vapor.MW, rel=1e-15)


# ------------------------------------------------------------------ a base molar
def test_a_base_molar_vem_de_massa_e_nao_de_split(cascatas, entrada):
    dados, _, _ = entrada
    for c, _ in cascatas:
        b, caso = c.base, dados.caso(c.caso)
        assert b.massa_oleo_kg_d == pytest.approx(caso["oil_sm3d"] * b.rho_oleo, rel=1e-15)
        assert b.massa_gas_kg_d == pytest.approx(caso["produced_gas_sm3d"] * b.rho_gas_std, rel=1e-15)
        assert b.n_F_kmol_d == pytest.approx(b.massa_kg_d / b.MW_z, rel=1e-15)
        assert b.MW_z == pytest.approx(cs.mw_da_mistura(c.estagios[0].estado), rel=1e-15)


def test_a_base_molar_exclui_o_gas_de_lift(cascatas, entrada):
    dados, _, _ = entrada
    com_lift = [c for c, _ in cascatas if c.base.tem_lift]
    assert len(com_lift) == 4 and {c.caso for c in com_lift} == {9, 11, 15, 16}
    for c in com_lift:
        caso = dados.caso(c.caso)
        assert c.base.gas_lift_sm3d == caso["lift_gas_sm3d"] > 0
        # a massa da base NÃO contém o lift: se contivesse, bateria com produced + lift
        assert c.base.massa_gas_kg_d < (caso["produced_gas_sm3d"] + caso["lift_gas_sm3d"]) * c.base.rho_gas_std
        assert c.base.fracao_de_lift > 0


def test_a_lacuna_do_gas_de_lift_esta_declarada():
    lac = cs.lacunas()
    ids = {x["id"] for x in lac}
    assert "composicao_gas_de_lift" in ids
    d = next(x for x in lac if x["id"] == "composicao_gas_de_lift")
    assert d["situacao"] == "ausente" and d["fonte_procurada"] and d["decisao"]
    assert cs.regra_base_molar()["inclui_gas_de_lift"] is False


def test_a_regra_da_base_molar_esta_no_toml_e_nao_no_codigo():
    r = cs.regra_base_molar()
    for chave in ("regra", "massa", "mw", "rho_oleo", "rho_gas", "unidade", "por_que_nao_o_split"):
        assert r[chave]


def test_o_volume_molar_padrao_e_o_do_balanco(entrada, planta_base):
    dados, _, _ = entrada
    assert cs.volume_molar_padrao(dados) == pytest.approx(planta_base.balanco[0].VM, rel=1e-15)


# ------------------------------------------------------------------ fechamento
def test_o_trem_fecha_globalmente(cascatas):
    for c, f in cascatas:
        assert f is not None and f.ok, c.caso
        assert f.erro_molar_relativo < TOL and f.erro_massico_relativo < TOL


def test_o_trem_fecha_componente_a_componente(cascatas):
    for c, f in cascatas:
        assert f.erro_componente_max < TOL, (c.caso, f.componente_pior, f.erro_componente_max)


def test_o_fechamento_global_e_a_soma_dos_vapores_mais_o_liquido_final(cascatas):
    for c, _ in cascatas:
        saida = c.n_vapor_total + c.n_liquido_final
        assert saida == pytest.approx(c.base.n_F_kmol_d, rel=1e-12)


def test_cada_flash_da_cascata_tambem_fecha(cascatas):
    for c, _ in cascatas:
        for s in c.estagios:
            assert s.fechamento is not None and s.fechamento.ok, (c.caso, s.ponto)


# ------------------------------------------------------------------ continua em sombra
def test_nenhuma_propriedade_saiu_da_sombra():
    m = ig.mapa()
    assert {i for i, d in m.items() if d["status"] == ig.LIBERADA} == {"Z", "MW", "rho_vapor"}
    for prop in ("beta", "x", "y"):
        assert ig.status(prop) == ig.SOMBRA
    for prop in ("h", "cp", "rho_liquido", "mu", "k"):
        assert ig.status(prop) == ig.BLOQUEADA


@pytest.mark.parametrize("prop", ["beta", "x", "y", "h", "cp", "rho_liquido", "mu", "k"])
def test_o_guarda_continua_recusando(prop):
    with pytest.raises(ValueError, match="não pode ser consumida"):
        ig.exigir_liberada(prop)


def test_a_cascata_declara_o_modo_sombra():
    assert cs.cfg()["cascata"]["modo"] == "sombra"


def test_a_cascata_nao_altera_o_balanco(entrada, planta_base):
    """Modo sombra: rodar a cascata não pode mexer no resultado produtivo."""
    dados, prem, mws = entrada
    antes = [(r.num, dict(r.gas), {k: v for k, v in r.T.items()}) for r in planta_base.balanco]
    cs.rodar(planta_base.balanco, dados, prem, mws)
    depois = [(r.num, dict(r.gas), {k: v for k, v in r.T.items()}) for r in planta_base.balanco]
    assert antes == depois


# ------------------------------------------------------------------ interrupção declarada
def test_estagio_sem_liquido_interrompe_a_cascata_sem_inventar_alimentacao(entrada, planta_base, monkeypatch):
    """Se um estágio perder a fase líquida, a cascata para e diz por quê — não continua com z₀."""
    dados, prem, mws = entrada
    original = et.flash_poco
    chamadas = [0]

    def so_vapor(T, P, z, mws_plus):
        e = original(T, P, z, mws_plus)
        chamadas[0] += 1
        if chamadas[0] == 1:
            return type(e)(**{**e.__dict__, "fases": tuple(f for f in e.fases if f.nome == "vapor")})
        return e

    monkeypatch.setattr(et, "flash_poco", so_vapor)
    c = cs.cascata(planta_base.balanco[0], dados, prem, mws)
    assert len(c.estagios) == 1 and not c.completa
    assert "sem fase líquida" in c.interrompida
    assert cs.fechamento_trem(c) is not None and math.isfinite(c.n_liquido_final)
