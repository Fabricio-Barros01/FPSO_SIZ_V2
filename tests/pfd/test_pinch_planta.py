"""F8 na planta — alvos de energia do pré-aquecedor (`pfd/pinch.py`, docs/validacao/22-pinch-planta.md).

O que se prova aqui não é o algoritmo (isso é `tests/sizing/test_golden_kemp.py`), e sim que a
rede montada do balanço é a rede que o usuário pediu, que o ΔTmin é a premissa P-32 e não um
valor novo, e que o alvo termodinâmico **coincide** com as cargas que o balanço realizou — a
validação cruzada da regra do P-001 por um algoritmo independente.
"""
import math
from pathlib import Path

import pytest

from fpso_siz.analysis import pinch as pa
from fpso_siz.balanco.dados import carregar_casos, premissas
from fpso_siz.balanco.modelo import resolver_todos
from fpso_siz.pfd import pinch as pp

CASOS = Path(__file__).resolve().parents[1] / "fixtures" / "python_ref" / "design_cases_bot.json"


@pytest.fixture(scope="module")
def cenario():
    dados = carregar_casos(CASOS)
    prem = premissas(dados)
    return prem, pp.redes(resolver_todos(dados, prem), prem)


def test_a_rede_e_declarada_no_toml_com_fonte(cenario):
    """Nenhuma corrente é nomeada no código: entrada, destino, capacidade, sentido e fonte vêm do
    TOML, e o ΔTmin é uma premissa do balanço, não um número do arquivo."""
    c = pp.cfg()
    assert len(c["corrente"]) == 2
    for corr in c["corrente"]:
        assert corr["sentido"] in pp.SENTIDOS
        assert corr["entrada"] and corr["destino_premissa"] and corr["capacidade"]
        assert corr["fonte"].strip() and corr["motivo_omissao"].strip()
    prem, _ = cenario
    assert c["dt_min_premissa"] in prem and "P-32" in c["fonte_dt_min"]


def test_o_dt_min_e_a_premissa_p32_em_todos_os_casos(cenario):
    prem, redes = cenario
    assert all(rc.dt_min == float(prem[pp.cfg()["dt_min_premissa"]]) for rc in redes)


def test_as_correntes_saem_do_balanco_e_do_destino_da_premissa(cenario):
    """T de entrada é a do balanço, T de destino é a premissa (não a realizada), e o CP é a
    capacidade térmica do balanço — a mesma que o modelo usa no lado correspondente do P-001."""
    prem, redes = cenario
    dados = carregar_casos(CASOS)
    balanco = resolver_todos(dados, prem)
    for rc, r in zip(redes, balanco):
        declaradas = {corr["rotulo"]: corr for corr in pp.cfg()["corrente"]}
        for s in rc.streams:
            corr = declaradas[s.name]
            seg = s.segments[0]
            assert seg.t_in == r.T[corr["entrada"]]
            assert seg.t_out == float(prem[corr["destino_premissa"]])
            assert seg.mcp == r.C(r.streams[corr["capacidade"]])


def test_corrente_sem_exigencia_e_omitida_com_motivo_e_a_rede_fica_nao_aplicavel(cenario):
    """Quando o óleo já sai do SG acima de T_trat (piso, P-11) não há exigência de aquecimento — e
    também não de resfriamento. A corrente sai da rede com o motivo, e o caso não recebe alvo
    nenhum em vez de receber um alvo inventado."""
    _, redes = cenario
    incompletas = [rc for rc in redes if rc.omitidas]
    assert incompletas, "o arquivo de casos do BOT tem casos em que o óleo já sai acima de T_trat"
    for rc in incompletas:
        assert not rc.aplicavel
        assert "rede incompleta" in rc.tabela.message
        for rotulo, motivo in rc.omitidas:
            assert rotulo in rc.tabela.message and motivo in rc.tabela.message
        assert all(not math.isfinite(v) for v in pp.alvos(rc).values())
        # sem alvo não há folga a afirmar
        assert all(not math.isfinite(v) for v in pp.folgas(rc).values())


def test_o_alvo_do_pinch_coincide_com_as_cargas_do_balanco(cenario):
    """A validação cruzada: o alvo vem da cascata de calor da Problem Table e as cargas vêm da
    regra Q_pre = min(C_frio, C_quente)·(ΔT − ΔT_app) do balanço. Dois caminhos independentes,
    o mesmo número — o arranjo do BOT alcança o alvo termodinâmico desta rede."""
    _, redes = cenario
    aplicaveis = [rc for rc in redes if rc.aplicavel]
    assert len(aplicaveis) >= 10
    for rc in aplicaveis:
        escala = max(1.0, abs(rc.realizado["utilidade_quente"]) + abs(rc.realizado["utilidade_fria"]))
        for papel, folga in pp.folgas(rc).items():
            assert abs(folga) <= 1e-9 * escala, (rc.nome, papel, folga)


def test_o_balanco_de_entalpia_fecha_em_cada_caso_aplicavel(cenario):
    """A conferência que a p. 24 manda fazer, caso a caso: QCmin − QHmin = ΣQ_quente − ΣQ_frio."""
    _, redes = cenario
    for rc in redes:
        if not rc.aplicavel:
            continue
        quente, fria = pa.heat_loads(rc.streams)
        residuo = (rc.tabela.q_c_min - rc.tabela.q_h_min) - (quente - fria)
        assert abs(residuo) <= 1e-9 * max(1.0, quente + fria), rc.nome


def test_ha_um_pinch_e_ele_esta_entre_as_temperaturas_das_correntes(cenario):
    """Com duas correntes que se cruzam na aproximação há um pinch, e ele é uma fronteira da
    própria rede — não um ponto inventado."""
    _, redes = cenario
    for rc in redes:
        if not rc.aplicavel:
            continue
        assert rc.tabela.t_pinch_shifted, rc.nome
        assert all(t in rc.tabela.boundaries for t in rc.tabela.t_pinch_shifted), rc.nome
        assert rc.curvas.q_rec >= 0
