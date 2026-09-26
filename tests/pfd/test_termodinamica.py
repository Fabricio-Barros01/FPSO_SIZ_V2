"""F14 — termodinâmica preliminar: comparação do balanço com o ChEDL, sem alterar o balanço."""
import copy
import importlib.util
import math
from pathlib import Path

import pytest

from fpso_siz.balanco.dados import carregar_casos, premissas
from fpso_siz.balanco.modelo import resolver_todos
from fpso_siz.pfd import termodinamica as td

RAIZ = Path(__file__).resolve().parents[2]
CASOS = RAIZ / "tests" / "fixtures" / "python_ref" / "design_cases_bot.json"


@pytest.fixture(scope="module")
def base():
    dados = carregar_casos(CASOS)
    prem = premissas(dados)
    return prem, resolver_todos(dados, prem)


def test_comparacao_nao_altera_o_balanco(base):
    prem, R = base
    antes = [(copy.deepcopy(r.streams), dict(r.T), dict(r.duties)) for r in R]
    td.comparar(R, prem)
    assert [(r.streams, r.T, r.duties) for r in R] == antes


def test_fase_aquosa_proxima_de_laliberte(base):
    prem, R = base
    aq = [c for c in td.comparar(R, prem) if c.grandeza == "cp da fase aquosa"]
    assert aq and all(abs(c.desvio) < 0.05 for c in aq)          # cp constante do balanço a < 5 %
    assert {c.caso for c in aq} == {r.num for r in R if r.streams["C-10"]["W"] + r.streams["C-10"]["D"] > 0}


def test_gas_real_na_condicao_dos_vasos(base):
    prem, R = base
    comp = td.comparar(R[:3], prem)
    cps = [c for c in comp if c.grandeza == "cp do gás"]
    zs = [c for c in comp if c.grandeza == "Z do gás"]
    assert all(c.balanco < c.referencia for c in cps)           # gás ideal a 25 °C abaixo do cp real a T, P
    assert all(0 < c.referencia < 1 for c in zs)                  # gás não ideal
    fwko = [c.referencia for c in zs if c.corrente == "C-04"]
    v002 = [c.referencia for c in zs if c.corrente == "C-17"]
    assert min(v002) > max(fwko)                                  # P menor no V-002: Z mais perto de 1


def test_efeito_na_carga_do_aquecedor_e_pequeno(base):
    prem, R = base
    efeitos = [td.efeito_carga_aquecedor(r, prem) for r in R]
    ativos = [e for e in efeitos if e is not None]
    assert ativos and all(abs(dq / q) < 0.02 for dq, q in ativos)
    assert efeitos[0] is None                                      # caso 1: sem água no aquecedor


def test_lacunas_de_caracterizacao_declaradas():
    assert {l["grandeza"] for l in td.lacunas()} >= {"Tc, Pc e ω do pseudo-componente C20+/C20++",
                                                     "viscosidade de óleo vivo pela EOS"}


def test_relatorio_deterministico_e_atualizado():
    caminho = RAIZ / "tools" / "termodinamica_preliminar.py"
    spec = importlib.util.spec_from_file_location("termodinamica_preliminar", caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    texto = mod.gerar()
    assert texto == (RAIZ / "docs" / "validacao" / "15-termodinamica.md").read_text(encoding="utf-8")
