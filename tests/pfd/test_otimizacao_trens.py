"""F15 — multiplicidade dos TAGs replicados (`fator_vazao`).

Um TAG replicado é dimensionado UMA vez, com a vazão dividida pelo número de unidades iguais.
O que o projeto leva é o conjunto: o objetivo que soma um derivado extensivo desse TAG tem de
somar N vezes o valor unitário. Sem isso, "mais trens" parece reduzir o volume instalado só
porque o objetivo contava um vaso de cada N — o que é erro de contabilidade, não engenharia.

A regra é genérica: vale para qualquer TAG declarado com `destino = "fator_vazao"`, e o código
não cita TAG nenhum. Os demais TAGs continuam entrando uma vez só.
"""
import math
from pathlib import Path

import pytest

from fpso_siz.balanco.dados import carregar_casos, premissas
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import otimizacao as ot
from fpso_siz.pfd import propostas as mod_propostas
from fpso_siz.pfd.ajustes import Ajustes
from fpso_siz.pfd.planta import dimensionar

CASOS = Path(__file__).resolve().parents[1] / "fixtures" / "python_ref" / "design_cases_bot.json"
SUB = "sg_001"
UNIDADES = (1, 2, 3)
# O TAG replicado deste recorte e as chaves que a declaração divide. Vêm do TOML: o teste
# confere que a declaração é a esperada, mas não fixa TAG no código de produção.
REPLICADO = "SG-001"


@pytest.fixture(scope="module")
def dados():
    return carregar_casos(CASOS)


@pytest.fixture(scope="module")
def eta(dados):
    return float(premissas(dados)["eta_F"])


@pytest.fixture(scope="module")
def plantas(dados, eta):
    """{N: Planta} do mesmo ponto com 1, 2 e 3 unidades. Um contexto só: o balanço não depende
    de N (a premissa é a mesma), e o cache do contexto poupa os TAGs que não mudam."""
    ctx = servico.Contexto(dados, propostas=mod_propostas.padrao())
    out = {}
    for n in UNIDADES:
        _, geral, trens = ot.decodificar((eta, float(n)), SUB)
        aj = ot.montar_ajustes(ctx, geral, trens)
        out[n] = dimensionar(contexto=ctx, ajustes=Ajustes(tags=aj) if aj else None)
    return out


@pytest.fixture(scope="module")
def avaliacoes(dados, eta):
    return {n: ot.avaliar(dados, (eta, float(n)), sub=SUB) for n in UNIDADES}


def _volumes(planta, o):
    return {ident: float(planta.tag(ident).resultado.derivados[o["derivado"]]) for ident in o["tags"]}


def objetivo_volume():
    o = next(o for o in ot.objetivos(SUB) if o["tipo"] == "soma_derivado")
    assert o["derivado"] == "volume" and REPLICADO in o["tags"]
    return o


def test_a_multiplicidade_sai_da_declaracao_e_nao_de_um_tag_no_codigo(eta):
    """`multiplicidade` traduz o que a decodificação replicou; só o TAG declarado com
    `fator_vazao` aparece, e nenhum outro destino gera multiplicidade."""
    for n in UNIDADES:
        _, _, trens = ot.decodificar((eta, float(n)), SUB)
        assert ot.multiplicidade(trens) == {REPLICADO: n}
    assert ot.multiplicidade({}) == {}
    declarados = {v["tag"] for v in ot.variaveis() if v["destino"] == "fator_vazao"}
    assert declarados == {REPLICADO}


@pytest.mark.otim
def test_a_vazao_por_unidade_e_a_total_dividida_pelo_numero_de_unidades(plantas):
    """Cada unidade recebe total/N nas chaves declaradas — é isso que faz o vaso encolher."""
    chaves = next(v["chaves"] for v in ot.variaveis(SUB) if v["destino"] == "fator_vazao")
    base = {c.num: c.valores for c in plantas[1].tag(REPLICADO).entradas.casos}
    conferidos = 0
    for n in UNIDADES:
        rt = plantas[n].tag(REPLICADO)
        assert rt.status == servico.DIMENSIONADO
        for c in rt.entradas.casos:
            for chave in chaves:
                v0, v = base[c.num].get(chave), c.valores.get(chave)
                # Num TAG replicado que ficou DIMENSIONADO, nenhuma chave declarada pode ter
                # escapado da divisão: é esse acoplamento que autoriza o objetivo a multiplicar
                # por N (ver `otimizacao.multiplicidade`). Chave não divisível é lacuna ou
                # faixa, e aí o TAG não estaria dimensionado.
                assert v0 is not None and not v0.lacuna and not v0.faixa and math.isfinite(v0.valor), \
                    (n, c.num, chave)
                assert v.valor == pytest.approx(v0.valor / n, rel=1e-12), (n, c.num, chave)
                conferidos += 1
    assert conferidos, "nenhuma vazão conferida: a divisão por trens não chegou às entradas"


@pytest.mark.otim
def test_o_volume_unitario_cai_com_o_numero_de_unidades(plantas):
    """O dimensionamento continua sendo de UMA unidade: o derivado publicado pelo TAG é o do
    vaso, não o do conjunto."""
    o = objetivo_volume()
    unitarios = [_volumes(plantas[n], o)[REPLICADO] for n in UNIDADES]
    assert all(planta.tag(REPLICADO).status == servico.DIMENSIONADO for planta in plantas.values())
    assert unitarios[0] > unitarios[1] > unitarios[2] > 0


@pytest.mark.otim
def test_o_objetivo_soma_n_vezes_o_replicado_e_uma_vez_os_demais(plantas, avaliacoes):
    """A conta do objetivo, termo a termo: N × unitário no TAG replicado, ×1 em todos os outros."""
    o = objetivo_volume()
    for n in UNIDADES:
        v = _volumes(plantas[n], o)
        esperado = n * v[REPLICADO] + sum(val for ident, val in v.items() if ident != REPLICADO)
        assert avaliacoes[n].objetivos[o["id"]] == pytest.approx(esperado, rel=1e-12), n


@pytest.mark.otim
def test_uma_unidade_nao_muda_numero_nenhum(plantas, avaliacoes):
    """N = 1 é o projeto de hoje: a multiplicidade não pode ter mexido nele."""
    o = objetivo_volume()
    assert avaliacoes[1].objetivos[o["id"]] == pytest.approx(sum(_volumes(plantas[1], o).values()),
                                                             rel=1e-12)


@pytest.mark.otim
def test_a_carga_do_balanco_nao_e_multiplicada(avaliacoes):
    """Só derivado EXTENSIVO do equipamento replica. A carga de utilidade vem do balanço, que
    não sabe em quantos vasos o serviço foi dividido — dividir o SG-001 em trens não multiplica
    o aquecimento da planta."""
    o = next(o for o in ot.objetivos(SUB) if o["tipo"] == "carga_balanco")
    valores = {n: avaliacoes[n].objetivos[o["id"]] for n in UNIDADES}
    assert len(set(valores.values())) == 1, valores
