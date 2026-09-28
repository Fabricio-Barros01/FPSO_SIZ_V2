"""F2 — CalcTrace do balanço: bijeção com o catálogo e coerência com o resultado."""
import pytest

from fpso_siz.core.configuracao import carregar
from fpso_siz.core.trace import CalcTrace

CATALOGO = carregar("equacoes_balanco.toml")


def pares_declarados(avaliavel):
    """Pares (equação, escopo) que o catálogo declara para a classe do caso."""
    classe = "avaliaveis" if avaliavel else "nao_avaliaveis"
    return {(eq, esc) for eq, e in CATALOGO.items() for esc in e["escopos"] if e.get("casos", classe) == classe}


def test_catalogo_bem_formado():
    for eq, e in CATALOGO.items():
        assert e["descricao"] and e["forma"] and e["unidade"] and e["escopos"], eq


def test_bijecao_catalogo_trace_em_todos_os_casos(resultados):
    for r in resultados:
        assert r.trace.pares() == pares_declarados(r.avaliavel), r.num
    assert {r.avaliavel for r in resultados} == {True, False}


def test_trace_corresponde_ao_resultado_final(resultados):
    for r in resultados:
        t = r.trace
        passo = lambda eq, esc: t.passo(eq, esc).valor
        assert passo("carga_aquecedor", "P-002") == r.duties["Q_H"]
        assert passo("carga_preaquecedor", "P-001") == r.duties["Q_pre"]
        assert passo("carga_resfriador", "P-003") == r.duties["Q_C"]
        assert passo("carga_diluicao", "DWH-001") == r.duties["Q_D"]
        assert passo("potencia_bomba", "B-001") == r.duties["W_Bo"]
        assert passo("agua_diluicao", "C-14") == r.gas["Dv"]
        assert passo("gas_estagio_flash" if r.avaliavel else "gas_por_estagio", "C-04") == r.gas["G_F"]
        assert passo("mistura", "C-02") == r.streams["C-02"]
        assert passo("temperatura_mistura", "C-02") == r.T["C-02"]
        assert passo("temperatura_mistura", "C-16") == r.T["C-16"]
        assert passo("convergencia_reciclo", "M-03") == r.residuo_reciclo
        assert t.passo("convergencia_reciclo", "M-03").entradas["iteracao"] == r.iters
        assert passo("viscosidade_oleo", "SG-001") == r.mu[0]
        for sid in ("C-04", "C-05", "C-06", "C-09", "C-12", "C-14", "C-17", "C-19"):
            assert passo("corrente_separada", sid) == r.streams[sid]


def test_calctrace_sobrescreve_e_e_imutavel():
    t = CalcTrace()
    assert t.reg("x", "A", 1.0, a=2) == 1.0
    t.reg("x", "A", 3.0, a=4)
    assert len(t) == 1 and t.passo("x", "A").valor == 3.0
    assert [p.valor for p in t] == [3.0]
    with pytest.raises(TypeError):
        t.passo("x", "A").entradas["a"] = 5
