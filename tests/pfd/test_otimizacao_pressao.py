"""Subproblema de pressão (config/pfd/otimizacao.toml `pressao`, docs/validacao/42).

Prende: P_D1 e P_D2 entram pelo decodificador como premissas do balanço (nenhum segundo
resolvedor); os extremos são domínio de estudo declarado, e os limites com fonte ou de processo
são restrição explícita; os objetivos e a restrição de TVP saem do EstadoProcesso pelas definições
do TOML (conferidas aqui contra as grandezas do estado); a TVP só é verificada nos 12 casos
avaliáveis; P_D2 ≥ P_D1 não é avaliado; a conferência da frente contra a grade usa a resolução
da própria grade; e a mesma semente dá a mesma frente.
"""
import math
from types import SimpleNamespace

import pytest

from fpso_siz.balanco import trem
from fpso_siz.core.configuracao import carregar
from fpso_siz.pfd import otimizacao as ot

SUB = "pressao"


def test_o_problema_completo_da_f15_nao_absorve_as_pressoes():
    assert [v["id"] for v in ot.variaveis()] == ["eta_F", "trens_sg", "passes_p002", "passes_p003"]
    assert {"perda_oleo", "carga_vru"}.isdisjoint(o["id"] for o in ot.objetivos())
    assert ot.ids_restricoes() == ot.tags_restritas()


def test_pressoes_sao_premissas_com_extremos_de_natureza_declarada():
    prem, geral, trens = ot.decodificar((650.0, 140.0), SUB)
    assert prem == {"P_D1": 650.0, "P_D2": 140.0} and not geral and not trens
    naturezas = {"fonte", "processo", "diagnostico", "sem_fonte", "dominio_estudo"}
    for v in ot.variaveis(SUB):
        assert v["destino"] == "premissa" and v["fonte"].strip()
        assert {v["natureza_min"], v["natureza_max"]} <= naturezas
    # o limite com fonte da sucção do compressor fica fora do domínio: nunca ativo
    compressor = next(x for x in carregar("pfd/mapa_pressao.toml")["limite"] if x["id"] == "p_d1_compressor")
    assert max(v["max"] for v in ot.variaveis(SUB) if v["id"] == "P_D1") < compressor["valor"]


def test_restricoes_do_subproblema_sao_explicitas_e_so_os_tres_vasos():
    assert ot.tags_restritas(SUB) == ["SG-001", "V-001", "V-002"]
    assert ot.ids_restricoes(SUB) == ["SG-001", "V-001", "V-002", "p_d2_menor_que_p_d1", "tvp"]
    tvp = ot.restricoes_balanco(SUB)[0]
    assert tvp["casos"] == "avaliaveis" and ot.limite(tvp) == trem.cfg()["tvp"]["limite_kPa"]


def test_p_d2_maior_ou_igual_a_p_d1_nao_e_avaliado():
    a = ot.avaliar(None, (200.0, 200.0), sub=SUB)   # sem dados: não pode chegar ao balanço
    assert a.situacao == "inviavel" and a.restricoes["p_d2_menor_que_p_d1"] == 1.0
    assert all(math.isnan(v) for v in a.objetivos.values())


def _caso(num, avaliavel, tvp):
    return SimpleNamespace(num=num, avaliavel=avaliavel, tvp_kPa=tvp)


def test_restricao_de_tvp_e_continua_e_so_dos_avaliaveis():
    r = ot.restricoes_balanco(SUB)[0]
    lim = ot.limite(r)
    # o caso não avaliável (TVP NaN) não entra: a restrição não é verificada nele
    b = [_caso(1, True, lim / 2), _caso(2, True, lim * 1.1), _caso(9, False, math.nan)]
    g, num = ot.restricao_balanco(r, b)
    assert num == 2 and g == pytest.approx(0.1)
    g, _ = ot.restricao_balanco(r, [_caso(1, True, lim / 2)])
    assert g == pytest.approx(-0.5)                     # folga, não zero
    g, num = ot.restricao_balanco(r, [_caso(1, True, lim / 2), _caso(3, True, math.nan)])
    assert math.isnan(g) and num == 3                  # TVP sem solução: ponto não avaliável


def test_objetivos_sao_as_grandezas_do_estado(planta_propostas):
    """No ponto das premissas, o avaliador devolve as definições do TOML lidas do mesmo
    EstadoProcesso que o `pfd` publica: perda = 1 − Σ ṁ_O(C-25)/Σ ṁ_O(C-01) nos 12 avaliáveis;
    carga da VRU = máx. (G_D1 + G_D2) nos 16; TVP máx. dos 12 contra o limite."""
    prem = planta_propostas.prem
    a = ot.avaliar(planta_propostas.dados, (prem["P_D1"], prem["P_D2"]), sub=SUB)
    b = planta_propostas.balanco
    aval = [r for r in b if r.avaliavel]
    assert len(aval) == 12 and len(b) == 16
    perda = 1 - sum(r.streams["C-25"]["O"] for r in aval) / sum(r.streams["C-01"]["O"] for r in aval)
    assert a.objetivos["perda_oleo"] == perda
    assert a.objetivos["carga_vru"] == max(r.gas["G_D1"] + r.gas["G_D2"] for r in b)
    tvp = max(r.tvp_kPa for r in aval)
    assert a.restricoes["tvp"] == tvp / trem.cfg()["tvp"]["limite_kPa"] - 1
    for ident in ot.tags_restritas(SUB):
        assert a.estados[ident] == planta_propostas.tag(ident).status
    # O conservado: o que não chega à estocagem sai pelas outras saídas globais da topologia —
    # os vapores dos três estágios e o óleo na água do FWKO
    saidas = [c for c in carregar("topologia_db.toml")["global_out"] if c != "C-25"]
    for r in aval:
        perdido = sum(r.streams[c]["O"] for c in saidas)
        assert r.streams["C-25"]["O"] + perdido == pytest.approx(r.streams["C-01"]["O"], rel=1e-9)


def test_resolucao_e_conferencia_da_frente():
    """A resolução é a maior diferença entre vizinhos viáveis da grade; a frente do algoritmo
    reproduz a da grade quando nenhum ponto da grade a supera por mais de ε e ela cobre cada
    ponto da frente da grade dentro de ε."""
    def av(x, f1, f2, viavel=True):
        return ot.Avaliacao(x, {"perda_oleo": f1, "carga_vru": f2}, {"tvp": -1.0 if viavel else 1.0}, {}, True)
    grade = [av((200.0, 110.0), 0.05, 10.0), av((200.0, 120.0), 0.04, 12.0),
             av((350.0, 110.0), 0.06, 9.0), av((350.0, 120.0), 0.01, 1.0, viavel=False)]
    eps = ot.resolucao(grade, SUB)
    assert eps == {"perda_oleo": pytest.approx(0.01), "carga_vru": pytest.approx(2.0)}
    ref = [{"perda_oleo": 0.04, "carga_vru": 12.0}, {"perda_oleo": 0.06, "carga_vru": 9.0}]
    boa = [{"perda_oleo": 0.045, "carga_vru": 11.0}, {"perda_oleo": 0.065, "carga_vru": 8.5}]
    assert ot.conferir_frente(boa, ref, eps) == ([], [])
    ruim = [{"perda_oleo": 0.2, "carga_vru": 50.0}]
    superados, descobertos = ot.conferir_frente(ruim, ref, eps)
    assert superados == ruim and descobertos == ref


def test_mesma_semente_mesma_frente_no_subproblema(monkeypatch):
    """Reprodutibilidade do algoritmo sobre o subproblema de pressão, com um avaliador sintético
    determinístico no lugar do serviço (a do avaliador real é a reavaliação de cada ponto da
    frente fora do otimizador, em tools/otimizar.py)."""
    from fpso_siz import _otim

    def falso(dados, x, propostas=None, sub=None):
        p1, p2 = x
        g = {i: 0.0 for i in ot.ids_restricoes(sub)}
        g["tvp"] = p2 / 140.0 - 1
        return ot.Avaliacao(tuple(x), {"perda_oleo": 1 / p2 + p1 / 1e5, "carga_vru": p1 / p2}, g, {}, True)

    monkeypatch.setattr(ot, "avaliar", falso)
    a = _otim.otimizar(None, populacao=8, geracoes=3, semente=3, sub=SUB)
    b = _otim.otimizar(None, populacao=8, geracoes=3, semente=3, sub=SUB)
    assert a[0] and a[0] == b[0] and [h.x for h in a[1]] == [h.x for h in b[1]]
    assert a[2]["restricoes"] == ot.ids_restricoes(SUB)


def test_a_proveniencia_declara_a_tvp_consumida_pela_otimizacao():
    """A TVP é propriedade do flash consumida só pela restrição do subproblema, só nos avaliáveis;
    a declaração descreve o código."""
    from fpso_siz.termo import proveniencia as pv
    d = pv.de("tvp_estocagem")
    assert d["consumidores"] == ["otimizacao"] and d["casos"] == pv.AVALIAVEIS and d["validade"] == pv.VALIDADA
    usadas = {r["grandeza"] for r in ot.cfg()["restricao_balanco"]}
    assert usadas == {"tvp_kPa"}
    assert all(r["casos"] == pv.AVALIAVEIS for r in ot.cfg()["restricao_balanco"])
