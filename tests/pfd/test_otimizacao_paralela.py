"""F15 — paralelismo da avaliação (`_otim.py`): paralelizar NÃO muda número.

Cada indivíduo é uma avaliação independente do serviço por TAG, então a população de uma geração
sai para processos filhos. O algoritmo continua sequencial no processo principal e a ordem é
preservada, logo a rodada paralela tem de dar exatamente a mesma frente e o mesmo histórico da
sequencial — é a regra "refatoração não muda número" (CLAUDE.md) aplicada ao desempenho.
"""
from pathlib import Path

import pytest

from fpso_siz import _otim
from fpso_siz.balanco.dados import carregar_casos
from fpso_siz.pfd import otimizacao as ot

CASOS = Path(__file__).resolve().parents[1] / "fixtures" / "python_ref" / "design_cases_bot.json"
SUB = "sg_001"
PROCESSOS = 2   # dois basta para provar a equivalência; a ferramenta usa os núcleos da máquina


@pytest.fixture(scope="module")
def dados():
    return carregar_casos(CASOS)


def _igual(a, b):
    return (a.x == b.x and a.objetivos == b.objetivos and a.restricoes == b.restricoes
            and a.estados == b.estados and a.convergiu == b.convergiu)


@pytest.mark.otim
def test_rodada_paralela_da_a_mesma_frente_e_o_mesmo_historico(dados):
    kw = dict(populacao=4, geracoes=2, sub=SUB)
    f1, h1, m1 = _otim.otimizar(dados, **kw, processos=1)
    f2, h2, m2 = _otim.otimizar(dados, **kw, processos=PROCESSOS)
    assert h1 and len(h1) == len(h2)
    assert all(_igual(a, b) for a, b in zip(h1, h2)), "a ordem do histórico tem de ser preservada"
    assert f1 == f2
    assert (m1["processos"], m2["processos"]) == (1, PROCESSOS)
    assert m1["avaliacoes"] == m2["avaliacoes"] and m1["algoritmo"] == m2["algoritmo"]


@pytest.mark.otim
def test_varredura_em_processos_e_a_mesma_avaliacao_do_modulo_puro(dados):
    """`avaliar_pontos` é o caminho que a ferramenta usa na varredura exaustiva do critério 2."""
    pontos = ot.grade(SUB, {"eta_F": 0.10})[:PROCESSOS]
    assert len(pontos) == PROCESSOS
    a = _otim.avaliar_pontos(dados, pontos, sub=SUB)
    b = _otim.avaliar_pontos(dados, pontos, sub=SUB, processos=PROCESSOS)
    assert all(_igual(x, y) for x, y in zip(a, b))
    assert [x.x for x in a] == [tuple(p) for p in pontos]
