"""Fase A (docs/validacao/44): P-18/P-19 = 500/130 kPa, premissa preliminar do autor.

O que se prova aqui é o que a nota 44 afirma: com as premissas anteriores (700/200 kPa) a TVP do
óleo tratado violava o BOT; com as vigentes ela é atendida nos 12 casos avaliáveis com a folga que
a grade da nota 42 deu, os 4 casos com gás de lift continuam sem TVP verificada (sem composição
substituta), a premissa declara a fonte e as ressalvas, a planta segue completa e o NPSH disponível
das bombas não depende da pressão do vaso de sucção (o líquido sai no ponto de bolha).
"""
import math

import pytest

from fpso_siz.core import memoria
from fpso_siz.core.configuracao import carregar
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import otimizacao as ot

ANTERIORES = {"P_D1": 700.0, "P_D2": 200.0}   # premissas de antes da nota 44
BOMBAS = ("B-001", "B-002", "B-003")


def restricao_tvp():
    return next(r for r in ot.restricoes_balanco("pressao") if r["grandeza"] == "tvp_kPa")


@pytest.fixture(scope="module")
def contexto_anterior(planta_propostas):
    return servico.Contexto(planta_propostas.dados, alteracoes=ANTERIORES, propostas=planta_propostas.contexto.propostas)


def test_a_premissa_declara_fonte_e_ressalvas():
    prem = carregar("premissas.toml")
    for nome in ("P_D1", "P_D2"):
        assert "44-premissa-pressao-tvp" in prem[nome]["fonte"]
        assert "absoluta" in prem[nome]["descricao"] and "preliminar" in prem[nome]["descricao"]
    ressalva = prem["P_D1"]["fonte"]
    assert "não é margem de segurança validada" in ressalva
    assert "9, 11, 15 e 16" in ressalva and "VRU não verificada" in ressalva
    assert "fase_a_pressao" not in carregar("premissas_candidatas.toml")


def test_as_premissas_anteriores_violavam_a_tvp(contexto_anterior):
    g, caso = ot.restricao_balanco(restricao_tvp(), contexto_anterior.balanco)
    assert g == pytest.approx(0.583, abs=1e-3) and caso == 14


def test_as_vigentes_atendem_a_tvp_nos_avaliaveis(planta_propostas):
    """TVP máxima entre os 12 avaliáveis abaixo do limite, com a folga da grade da nota 42
    (g = −0,034, caso 14). Nos casos com gás de lift a TVP não é verificada (NaN)."""
    b = planta_propostas.contexto.balanco
    g, caso = ot.restricao_balanco(restricao_tvp(), b)
    assert g == pytest.approx(-0.034, abs=5e-4) and caso == 14
    sem_lift = {r.num for r in b if r.caso["lift_gas_sm3d"] == 0}
    assert {r.num for r in b if r.avaliavel} == sem_lift and len(sem_lift) == 12
    assert all(math.isnan(r.tvp_kPa) for r in b if r.num not in sem_lift)


def test_a_planta_segue_completa(planta_propostas):
    assert planta_propostas.completa
    i = planta_propostas.contexto.integracao
    assert i.aplicavel and 0 < i.q_realizado_total <= i.q_alvo_total


def test_o_npsh_disponivel_nao_depende_da_pressao_do_vaso(planta_propostas, contexto_anterior):
    """Pv = P do vaso (ponto de bolha): NPSHd = (P₀ − Pv)/(ρg) + h₀ − h_atrito ≈ h₀ − h_atrito. Baixar
    a pressão de sucção não tira NPSH; o que muda é só ρ e o atrito. A comparação com o NPSHr do
    fabricante segue PENDENTE: o NPSH exigido é proposta do usuário, não curva de bomba."""
    for ident in BOMBAS:
        novo = memoria.operacao(planta_propostas.tag(ident).resultado)
        velho = memoria.operacao(servico.executar(contexto_anterior, servico.estado_inicial(ident)).resultado)
        for (nome, o), (_, a) in zip(novo, velho, strict=True):
            assert o["npsh"] == pytest.approx(a["npsh"], abs=1e-2), (ident, nome)
            assert o["folga_npsh"] >= 0, (ident, nome)
        c = next(c for c in planta_propostas.tag(ident).entradas.casos if c.ativo)
        assert c.valores["npsh_requerido"].origem == "proposta"
